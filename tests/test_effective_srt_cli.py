import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_final_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.effective_srt_cli import main
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class EffectiveSrtCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"srt-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            self.intake, raw.raw_transcript_id.value
        )
        candidate = compose_sqlite_effective_subtitle_generation_service(connection).generate(
            intake_id=self.intake
        ).candidate
        self.subject = compose_sqlite_effective_subtitle_review_preparation_service(
            connection
        ).prepare_review(candidate_id=candidate.identity.value).subject.identity.value
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _db(self):
        return ["--database", str(self.database)]

    def _select(self) -> str:
        connection = open_sqlite_database(str(self.database))
        try:
            compose_sqlite_effective_subtitle_review_decision_service(connection).decide(
                review_subject_id=self.subject, kind="accept", reviewer="reviewer:kim"
            )
            return compose_sqlite_effective_subtitle_final_selection_service(
                connection
            ).select_final(
                review_subject_id=self.subject, selector="selector:park"
            ).selection.identity.value
        finally:
            connection.close()

    def _artifact_id(self, out: str) -> str:
        for line in out.splitlines():
            if line.startswith("artifact: "):
                return line.split(": ", 1)[1]
        raise AssertionError(out)

    def test_eligibility_blocking_then_eligible(self):
        code, out, err = _run(["eligibility", "--selection",
                               "subtitle-effective-final-selection:" + "0" * 64, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("eligible for a new SRT artifact: no", out)
        self.assertIn("blocking reason: selection_not_found", out)
        selection = self._select()
        code, out, _err = _run(["eligibility", "--selection", selection, *self._db()])
        self.assertIn("eligible for a new SRT artifact: yes", out)
        self.assertIn("serializer: canonical_srt v1", out)

    def test_generate_reports_lineage_and_isolation(self):
        selection = self._select()
        code, out, _err = _run(["generate", "--selection", selection, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("created effective subtitle SRT artifact", out)
        self.assertIn("artifact: subtitle-effective-srt-artifact:", out)
        self.assertIn(f"final selection: {selection}", out)
        self.assertIn("serializer: canonical_srt v1 (parameters v1)", out)
        self.assertIn("cues: 1", out)
        self.assertIn("artifact currentness: current", out)
        self.assertIn("materialization state: not part of this contract", out)
        self.assertIn("physical path: not part of this contract", out)
        self.assertIn("no file was created", out)

    def test_replay_reports_reused(self):
        selection = self._select()
        _run(["generate", "--selection", selection, *self._db()])
        code, out, _err = _run(["generate", "--selection", selection, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("reused effective subtitle SRT artifact", out)

    def test_content_emits_exact_srt(self):
        selection = self._select()
        _code, out, _err = _run(["generate", "--selection", selection, *self._db()])
        artifact = self._artifact_id(out)
        code, out, _err = _run(["content", "--artifact", artifact, *self._db()])
        self.assertEqual(code, 0)
        self.assertEqual(out, "1\n00:00:00,000 --> 00:00:02,000\n원본\n")

    def test_list_and_status(self):
        selection = self._select()
        _code, out, _err = _run(["generate", "--selection", selection, *self._db()])
        artifact = self._artifact_id(out)
        code, out, _err = _run(["list", "--intake", self.intake, *self._db()])
        self.assertIn(": 1", out)
        self.assertIn("[current]", out)
        code, out, _err = _run(["status", "--artifact", artifact, *self._db()])
        self.assertIn("artifact currentness: current", out)
        self.assertIn("immutable historical record", out)

    def test_ineligible_exits_one_and_persists_nothing(self):
        before = self.database.read_bytes()
        code, _out, err = _run(["generate", "--selection",
                                "subtitle-effective-final-selection:" + "0" * 64, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_missing_database_exits_one(self):
        code, _out, err = _run(["list", "--intake", self.intake,
                                "--database", str(self.base / "nope.db")])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_repository_validates_healthy_after_generation(self):
        selection = self._select()
        _run(["generate", "--selection", selection, *self._db()])
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
