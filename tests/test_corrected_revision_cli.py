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
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.corrected_revision_cli import main
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


class CorrectedRevisionCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"rev-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "안녕하세요 여러부"}]}
            ),
        ).admission.raw_transcript_id.value
        compose_sqlite_current_raw_transcript_selection_service(connection).select(intake, raw)
        from lectureos.transcript.identities import TranscriptId

        raw_record = SQLiteRawTranscriptRepository(connection).get(TranscriptId(raw))
        segment = raw_record.segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(connection).get(segment).text
        self.candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw, "segment_id": segment.value, "candidate_ref": "c1",
                 "source_type": "manual", "source_reference": "human",
                 "proposed_text": "안녕하세요 여러분", "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate.identity.value
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _db(self):
        return ["--database", str(self.database)]

    def _accept(self):
        connection = open_sqlite_database(str(self.database))
        try:
            compose_sqlite_correction_candidate_decision_service(connection).decide(
                candidate_id=self.candidate, kind="accept", reviewer="r:kim"
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

    def test_generate_success_states_not_current(self):
        self._accept()
        code, out, _err = _run(["generate", "--candidate", self.candidate, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("created corrected transcript revision corrected-revision:", out)
        self.assertIn("authorizing accepted decision: correction-candidate-decision:", out)
        self.assertIn("NOT selected as current", out)

    def test_generate_replay_reused(self):
        self._accept()
        _run(["generate", "--candidate", self.candidate, *self._db()])
        code, out, _err = _run(["generate", "--candidate", self.candidate, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("reused corrected transcript revision", out)

    def test_undecided_exits_one_and_leaves_db_unchanged(self):
        before = self.database.read_bytes()
        code, _out, err = _run(["generate", "--candidate", self.candidate, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_rejected_exits_one(self):
        self._reject()
        code, _out, err = _run(["generate", "--candidate", self.candidate, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_stale_selection_switch_exits_one(self):
        self._accept()
        # Admit a second raw transcript and switch the current selection away.
        connection = open_sqlite_database(str(self.database))
        try:
            intake = connection.execute(
                "SELECT transcript_source_intake_id FROM correction_candidate_admissions"
            ).fetchone()[0]
            raw2 = compose_sqlite_provider_transcript_admission_service(connection).admit(
                intake_id=intake,
                document=build_provider_transcript_document(
                    {"provider": "fake", "model": "big", "language": "ko",
                     "provider_result_ref": "B",
                     "segments": [{"start": 0.0, "end": 2.0, "text": "다른 인식"}]}
                ),
            ).admission.raw_transcript_id.value
            compose_sqlite_current_raw_transcript_selection_service(connection).select(intake, raw2)
        finally:
            connection.close()
        code, _out, err = _run(["generate", "--candidate", self.candidate, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_unknown_candidate_exits_one(self):
        code, _out, err = _run(
            ["generate", "--candidate", "correction-candidate:" + "0" * 64, *self._db()]
        )
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_show_and_list(self):
        self._accept()
        code, out, _err = _run(["generate", "--candidate", self.candidate, *self._db()])
        revision = next(
            line.split()[-1] for line in out.splitlines() if line.startswith("created corrected")
        )
        code, out, _err = _run(["show", "--revision", revision, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("안녕하세요 여러분", out)
        self.assertIn("*corrected", out)
        code, out, _err = _run(["list", "--candidate", self.candidate, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("corrected revision generations for candidate", out)
        self.assertIn(revision, out)

    def test_show_unknown_revision_exits_one(self):
        code, _out, err = _run(["show", "--revision", "corrected-revision:" + "0" * 64, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_missing_database_exits_one(self):
        code, _out, err = _run(
            ["generate", "--candidate", self.candidate, "--database", str(self.base / "nope.db")]
        )
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_repository_validates_healthy_after_cli_generation(self):
        self._accept()
        _run(["generate", "--candidate", self.candidate, *self._db()])
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
