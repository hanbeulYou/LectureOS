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
    compose_sqlite_effective_subtitle_srt_artifact_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.effective_materialize_cli import main
from lectureos.persistence import initialize_sqlite_database
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class EffectiveMaterializeCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.storage_root = self.base / "out"
        self.storage_root.mkdir()
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"materialize-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            intake, raw.raw_transcript_id.value
        )
        candidate = compose_sqlite_effective_subtitle_generation_service(connection).generate(
            intake_id=intake
        ).candidate
        subject = compose_sqlite_effective_subtitle_review_preparation_service(
            connection
        ).prepare_review(candidate_id=candidate.identity.value).subject
        compose_sqlite_effective_subtitle_review_decision_service(connection).decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        selection = compose_sqlite_effective_subtitle_final_selection_service(
            connection
        ).select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        ).selection
        self.artifact = compose_sqlite_effective_subtitle_srt_artifact_service(
            connection
        ).generate_srt_artifact(
            final_selection_id=selection.identity.value
        ).artifact
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _common(self):
        return ["--storage-root", str(self.storage_root), "--database", str(self.database)]

    def _materialization_id(self, out: str) -> str:
        for line in out.splitlines():
            if line.startswith("materialization: "):
                return line.split(": ", 1)[1]
        raise AssertionError(out)

    def test_materialize_writes_and_reports_provenance(self):
        code, out, _err = _run(["materialize", "--artifact", self.artifact.identity.value,
                                "--location", "lecture.srt", *self._common()])
        self.assertEqual(code, 0)
        self.assertIn("created effective SRT materialization", out)
        self.assertIn("materialization: subtitle-effective-srt-materialization:", out)
        self.assertIn(f"artifact: {self.artifact.identity.value}", out)
        self.assertIn("relative location: lecture.srt", out)
        self.assertIn("materialization state: materialized", out)
        self.assertIn("write provenance, never artifact identity", out)
        self.assertIn("delivery state: not part of this contract", out)
        self.assertEqual(
            (self.storage_root / "lecture.srt").read_bytes(),
            self.artifact.srt_content.encode("utf-8"),
        )

    def test_replay_reports_reused(self):
        _run(["materialize", "--artifact", self.artifact.identity.value, *self._common()])
        code, out, _err = _run(["materialize", "--artifact", self.artifact.identity.value,
                                *self._common()])
        self.assertEqual(code, 0)
        self.assertIn("reused effective SRT materialization", out)

    def test_collision_without_overwrite_reports_failed_and_exits_one(self):
        (self.storage_root / "busy.srt").write_bytes(b"other\n")
        code, out, _err = _run(["materialize", "--artifact", self.artifact.identity.value,
                                "--location", "busy.srt", *self._common()])
        self.assertEqual(code, 1)
        self.assertIn("materialization state: failed", out)
        self.assertIn("failure reason: MaterializationCollisionError", out)
        self.assertIn("honest immutable record", out)
        self.assertEqual((self.storage_root / "busy.srt").read_bytes(), b"other\n")
        code, out, _err = _run(["materialize", "--artifact", self.artifact.identity.value,
                                "--location", "busy.srt", "--overwrite", *self._common()])
        self.assertEqual(code, 0)
        self.assertEqual(
            (self.storage_root / "busy.srt").read_bytes(),
            self.artifact.srt_content.encode("utf-8"),
        )

    def test_show_status_and_list(self):
        _code, out, _err = _run(["materialize", "--artifact", self.artifact.identity.value,
                                 *self._common()])
        materialization = self._materialization_id(out)
        code, out, _err = _run(["show", "--materialization", materialization, *self._common()])
        self.assertEqual(code, 0)
        self.assertIn("bytes written:", out)
        code, out, _err = _run(["status", "--materialization", materialization, *self._common()])
        self.assertIn("physical file currently matches payload: yes", out)
        # Deleting the file never mutates the record.
        for path in self.storage_root.rglob("*.srt"):
            path.unlink()
        code, out, _err = _run(["status", "--materialization", materialization, *self._common()])
        self.assertIn("physical file currently matches payload: absent", out)
        self.assertIn("never mutates the immutable record", out)
        code, out, _err = _run(["list", "--artifact", self.artifact.identity.value,
                                *self._common()])
        self.assertIn(": 1", out)
        self.assertIn("[materialized]", out)
        self.assertIn("append-only", out)

    def test_unknown_artifact_exits_one(self):
        code, _out, err = _run(["materialize", "--artifact",
                                "subtitle-effective-srt-artifact:" + "0" * 64,
                                *self._common()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_missing_storage_root_exits_one(self):
        code, _out, err = _run(["materialize", "--artifact", self.artifact.identity.value,
                                "--storage-root", str(self.base / "missing"),
                                "--database", str(self.database)])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_repository_validates_healthy_after_materialization(self):
        _run(["materialize", "--artifact", self.artifact.identity.value, *self._common()])
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
