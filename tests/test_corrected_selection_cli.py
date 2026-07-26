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
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.corrected_selection_cli import main
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


class CorrectedSelectionCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"sel-cli \x00\x01")
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
        raw_record = SQLiteRawTranscriptRepository(connection).get(raw.raw_transcript_id)
        segment = raw_record.segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(connection).get(segment).text
        self.candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=self.intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw.raw_transcript_id.value, "segment_id": segment.value,
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

    def test_select_success_reports_states(self):
        code, out, _err = _run(["select", "--revision", self.revision, "--reviewer", "s:kim", *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("recorded corrected revision selection corrected-revision-selection:", out)
        self.assertIn("previous state: no selection history", out)
        self.assertIn("current applicability: applicable", out)
        self.assertIn("no revision content was mutated", out)

    def test_select_replay_reused(self):
        _run(["select", "--revision", self.revision, "--reviewer", "s:kim", *self._db()])
        code, out, _err = _run(["select", "--revision", self.revision, "--reviewer", "s:lee", *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("reused corrected revision selection", out)

    def test_fallback_and_replay(self):
        _run(["select", "--revision", self.revision, "--reviewer", "s:kim", *self._db()])
        code, out, _err = _run(["fallback", "--intake", self.intake, "--reviewer", "s:kim", *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("changed raw transcript fallback", out)
        self.assertIn("current state: raw fallback", out)
        self.assertIn("revisions remain persisted", out.lower())
        code, out, _err = _run(["fallback", "--intake", self.intake, "--reviewer", "s:lee", *self._db()])
        self.assertIn("reused raw transcript fallback", out)

    def test_status_distinguishes_all_states(self):
        code, out, _err = _run(["status", "--intake", self.intake, *self._db()])
        self.assertIn("no selection history", out)
        _run(["select", "--revision", self.revision, "--reviewer", "s:kim", *self._db()])
        code, out, _err = _run(["status", "--intake", self.intake, *self._db()])
        self.assertIn("corrected revision selected", out)
        self.assertIn("applicability: applicable", out)
        _run(["fallback", "--intake", self.intake, "--reviewer", "s:kim", *self._db()])
        code, out, _err = _run(["status", "--intake", self.intake, *self._db()])
        self.assertIn("explicit raw fallback", out)

    def test_status_reports_inapplicable_after_reject(self):
        _run(["select", "--revision", self.revision, "--reviewer", "s:kim", *self._db()])
        connection = open_sqlite_database(str(self.database))
        try:
            compose_sqlite_correction_candidate_decision_service(connection).decide(
                candidate_id=self.candidate, kind="reject", reviewer="r:kim"
            )
        finally:
            connection.close()
        code, out, _err = _run(["status", "--intake", self.intake, *self._db()])
        self.assertIn("not applicable (candidate_not_accepted)", out)
        code, out, _err = _run(["resolve", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("INAPPLICABLE", out)
        self.assertIn("no silent fallback", out)

    def test_history_ordered_with_current_marker(self):
        _run(["select", "--revision", self.revision, "--reviewer", "s:kim", *self._db()])
        _run(["fallback", "--intake", self.intake, "--reviewer", "s:kim", *self._db()])
        code, out, _err = _run(["history", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("#0 corrected_revision", out)
        self.assertIn("#1 raw_fallback", out)
        self.assertIn("*current", out)

    def test_resolve_all_reachable_outcomes(self):
        code, out, _err = _run(["resolve", "--intake", self.intake, *self._db()])
        self.assertIn("effective transcript: raw", out)
        _run(["select", "--revision", self.revision, "--reviewer", "s:kim", *self._db()])
        code, out, _err = _run(["resolve", "--intake", self.intake, *self._db()])
        self.assertIn("effective transcript: corrected", out)
        _run(["fallback", "--intake", self.intake, "--reviewer", "s:kim", *self._db()])
        code, out, _err = _run(["resolve", "--intake", self.intake, *self._db()])
        self.assertIn("effective transcript: raw", out)

    def test_unknown_revision_exits_one_and_leaves_db_unchanged(self):
        before = self.database.read_bytes()
        code, _out, err = _run(["select", "--revision", "corrected-revision:" + "0" * 64,
                                "--reviewer", "s", *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_rejected_candidate_revision_select_exits_one(self):
        connection = open_sqlite_database(str(self.database))
        try:
            compose_sqlite_correction_candidate_decision_service(connection).decide(
                candidate_id=self.candidate, kind="reject", reviewer="r:kim"
            )
        finally:
            connection.close()
        code, _out, err = _run(["select", "--revision", self.revision, "--reviewer", "s", *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_missing_database_exits_one(self):
        code, _out, err = _run(["status", "--intake", self.intake, "--database", str(self.base / "nope.db")])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_repository_validates_healthy_after_selection(self):
        _run(["select", "--revision", self.revision, "--reviewer", "s:kim", *self._db()])
        _run(["fallback", "--intake", self.intake, "--reviewer", "s:kim", *self._db()])
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
