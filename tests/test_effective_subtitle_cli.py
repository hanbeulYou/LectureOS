import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.effective_subtitle_cli import main
from lectureos.persistence import (
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class EffectiveSubtitleCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"sub-cli \x00\x01")
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
        self.raw_id = raw.raw_transcript_id.value
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            self.intake, self.raw_id
        )
        segment = SQLiteRawTranscriptRepository(connection).get(raw.raw_transcript_id).segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(connection).get(segment).text
        self.candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=self.intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": self.raw_id, "segment_id": segment.value,
                 "candidate_ref": "c1", "source_type": "manual", "source_reference": "human",
                 "proposed_text": "교정", "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate.identity.value
        compose_sqlite_correction_candidate_decision_service(connection).decide(
            candidate_id=self.candidate, kind="accept", reviewer="r:kim"
        )
        self.revision = compose_sqlite_corrected_revision_generation_service(connection).generate(
            candidate_id=self.candidate
        ).revision.identity.value
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _db(self):
        return ["--database", str(self.database)]

    def _select_revision(self):
        connection = open_sqlite_database(str(self.database))
        try:
            compose_sqlite_corrected_revision_selection_service(connection).select_revision(
                revision_id=self.revision, reviewer="s:kim"
            )
        finally:
            connection.close()

    def _reject(self):
        connection = open_sqlite_database(str(self.database))
        try:
            compose_sqlite_correction_candidate_decision_service(connection).decide(
                candidate_id=self.candidate, kind="reject", reviewer="r:kim"
            )
        finally:
            connection.close()

    def _candidate_id(self, out: str) -> str:
        for line in out.splitlines():
            if line.startswith("candidate: "):
                return line.split(": ", 1)[1]
        raise AssertionError(out)

    def test_generate_from_raw_reports_full_provenance(self):
        code, out, _err = _run(["generate", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("created effective subtitle candidate", out)
        self.assertIn("candidate: subtitle-effective-candidate:", out)
        self.assertIn("consumption binding: transcript-consumption:", out)
        self.assertIn("source kind: raw_transcript", out)
        self.assertIn(f"source identity: {self.raw_id}", out)
        self.assertIn(f"parent raw transcript: {self.raw_id}", out)
        self.assertIn("generator: deterministic_segment_passthrough v1", out)
        self.assertIn("cues: 1", out)
        self.assertIn("source currentness: current", out)
        self.assertIn("no review, decision, final selection, export", out)

    def test_generate_from_corrected_and_replay(self):
        self._select_revision()
        code, out, _err = _run(["generate", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("source kind: corrected_transcript_revision", out)
        self.assertIn(f"source identity: {self.revision}", out)
        code, out, _err = _run(["generate", "--intake", self.intake, *self._db()])
        self.assertIn("reused effective subtitle candidate", out)

    def test_show_reports_cues_and_lineage(self):
        _code, out, _err = _run(["generate", "--intake", self.intake, *self._db()])
        candidate = self._candidate_id(out)
        code, out, _err = _run(["show", "--candidate", candidate, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("#0 [0.0..2.0] '원본' <- transcript-segment:", out)

    def test_list_and_status_derive_currentness(self):
        _code, out, _err = _run(["generate", "--intake", self.intake, *self._db()])
        candidate = self._candidate_id(out)
        code, out, _err = _run(["list", "--intake", self.intake, *self._db()])
        self.assertIn("[current]", out)
        self._select_revision()
        code, out, _err = _run(["status", "--candidate", candidate, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("source currentness: stale_due_to_corrected_selection_change", out)
        self.assertIn("immutable, historically valid", out)

    def test_inapplicable_selection_exits_one_and_persists_nothing(self):
        self._select_revision()
        self._reject()
        before = self.database.read_bytes()
        code, _out, err = _run(["generate", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertIn("no silent", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_unknown_candidate_exits_one(self):
        code, _out, err = _run(["show", "--candidate",
                                "subtitle-effective-candidate:" + "0" * 64, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_missing_database_exits_one(self):
        code, _out, err = _run(["list", "--intake", self.intake,
                                "--database", str(self.base / "nope.db")])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_repository_validates_healthy_after_generation(self):
        _run(["generate", "--intake", self.intake, *self._db()])
        self._select_revision()
        _run(["generate", "--intake", self.intake, *self._db()])
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
