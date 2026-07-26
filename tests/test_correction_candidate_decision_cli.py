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
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.correction_candidate_decision_cli import main
from lectureos.persistence import (
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
)
from lectureos.transcript.identities import TranscriptId
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CorrectionCandidateDecisionCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"decide-cli \x00\x01")
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
        ).admission.raw_transcript_id.value
        compose_sqlite_current_raw_transcript_selection_service(connection).select(intake, raw)
        raw_record = SQLiteRawTranscriptRepository(connection).get(TranscriptId(raw))
        segment = raw_record.segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(connection).get(segment).text
        self.candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw, "segment_id": segment.value, "candidate_ref": "c1",
                 "source_type": "manual", "source_reference": "human", "proposed_text": "교정",
                 "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate.identity.value
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _db(self):
        return ["--database", str(self.database)]

    def test_decide_accept_states_not_applied(self):
        code, out, _err = _run(["decide", "--candidate", self.candidate, "--kind", "accept", "--reviewer", "reviewer:kim", *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("recorded human decision correction-candidate-decision:", out)
        self.assertIn("kind: accept", out)
        self.assertIn("current authority: accepted", out)
        self.assertIn("nothing was applied", out)

    def test_replay_reused(self):
        _run(["decide", "--candidate", self.candidate, "--kind", "accept", "--reviewer", "r:kim", *self._db()])
        code, out, _err = _run(["decide", "--candidate", self.candidate, "--kind", "accept", "--reviewer", "r:lee", *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("reused human decision", out)

    def test_switch_reports_changed_and_superseded(self):
        _run(["decide", "--candidate", self.candidate, "--kind", "accept", "--reviewer", "r:kim", *self._db()])
        code, out, _err = _run(["decide", "--candidate", self.candidate, "--kind", "reject", "--reviewer", "r:kim", *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("changed human decision", out)
        self.assertIn("superseded: accept", out)
        self.assertIn("current authority: rejected", out)

    def test_status_reports_authority_and_eligibility(self):
        code, out, _err = _run(["status", "--candidate", self.candidate, *self._db()])
        self.assertIn("current authority for candidate", out)
        self.assertIn("undecided", out)
        _run(["decide", "--candidate", self.candidate, "--kind", "accept", "--reviewer", "r:kim", *self._db()])
        code, out, _err = _run(["status", "--candidate", self.candidate, *self._db()])
        self.assertIn("accepted", out)
        self.assertIn("eligible for future corrected revision: yes", out)

    def test_history_lists_records(self):
        _run(["decide", "--candidate", self.candidate, "--kind", "accept", "--reviewer", "r:kim", *self._db()])
        _run(["decide", "--candidate", self.candidate, "--kind", "reject", "--reviewer", "r:kim", *self._db()])
        code, out, _err = _run(["history", "--candidate", self.candidate, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("decision history for candidate", out)
        self.assertIn("#0 accept", out)
        self.assertIn("#1 reject", out)

    def test_unknown_candidate_exits_one(self):
        code, _out, err = _run(["decide", "--candidate", "correction-candidate:" + "0" * 64, "--kind", "accept", "--reviewer", "r", *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_malformed_candidate_exits_one_and_leaves_db_unchanged(self):
        before = self.database.read_bytes()
        code, _out, err = _run(["decide", "--candidate", "nope", "--kind", "accept", "--reviewer", "r", *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_missing_database_exits_one(self):
        code, _out, err = _run(["status", "--candidate", self.candidate, "--database", str(self.base / "nope.db")])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_repository_validates_healthy_after_decisions(self):
        _run(["decide", "--candidate", self.candidate, "--kind", "accept", "--reviewer", "r:kim", *self._db()])
        _run(["decide", "--candidate", self.candidate, "--kind", "reject", "--reviewer", "r:kim", *self._db()])
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
