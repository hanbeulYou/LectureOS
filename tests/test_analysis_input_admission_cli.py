import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.analysis_input_admission_cli import main
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
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class AnalysisInputAdmissionCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"admission-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        self.raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            self.intake, self.raw.raw_transcript_id.value
        )
        segment_id = SQLiteRawTranscriptRepository(connection).get(
            self.raw.raw_transcript_id
        ).segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(connection).get(segment_id).text
        candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=self.intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": self.raw.raw_transcript_id.value,
                 "segment_id": segment_id.value, "candidate_ref": "c1",
                 "source_type": "manual", "source_reference": "human",
                 "proposed_text": "교정", "source_text_snapshot": text,
                 "rationale": "fix"}
            ),
        ).candidate.identity.value
        compose_sqlite_correction_candidate_decision_service(connection).decide(
            candidate_id=candidate, kind="accept", reviewer="r:kim"
        )
        self.revision = compose_sqlite_corrected_revision_generation_service(
            connection
        ).generate(candidate_id=candidate).revision.identity.value
        compose_sqlite_corrected_revision_selection_service(connection).select_revision(
            revision_id=self.revision, reviewer="s:kim"
        )
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _db(self):
        return ["--database", str(self.database)]

    def _admission_id(self, output):
        for line in output.splitlines():
            if line.startswith("analysis input: "):
                return line.split(" ", 2)[2]
        raise AssertionError(f"no analysis input line in: {output}")

    def test_admit_replay_show_status_and_list(self):
        code, out, err = _run(["admit", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0, err)
        self.assertIn("admitted lecture analysis input", out)
        self.assertIn(f"corrected revision: {self.revision}", out)
        self.assertIn(
            f"parent raw transcript: {self.raw.raw_transcript_id.value}", out
        )
        self.assertIn("analysis execution state: not part of this contract", out)
        admission_id = self._admission_id(out)
        code, out, err = _run(["admit", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0, err)
        self.assertIn("reused lecture analysis input", out)
        code, out, err = _run(["show", "--admission", admission_id, *self._db()])
        self.assertEqual(code, 0, err)
        self.assertIn("content fingerprint: ", out)
        code, out, err = _run(["status", "--admission", admission_id, *self._db()])
        self.assertEqual(code, 0, err)
        self.assertIn("current authority match: current", out)
        code, out, err = _run(["list", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0, err)
        self.assertIn(": 1", out)
        self.assertIn("[current]", out)

    def test_ineligible_admit_exits_nonzero_and_persists_nothing(self):
        # A new raw selection makes the current corrected selection inapplicable.
        connection = open_sqlite_database(self.database)
        try:
            raw_b = compose_sqlite_provider_transcript_admission_service(connection).admit(
                intake_id=self.intake,
                document=build_provider_transcript_document(
                    {"provider": "fake", "model": "tiny", "language": "ko",
                     "provider_result_ref": "B",
                     "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
                ),
            ).admission
            compose_sqlite_current_raw_transcript_selection_service(connection).select(
                self.intake, raw_b.raw_transcript_id.value
            )
        finally:
            connection.close()
        code, _, err = _run(["admit", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        connection = open_sqlite_database(self.database)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM lecture_analysis_input_admissions"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_unknown_inputs_error(self):
        code, _, err = _run([
            "show", "--admission", "lecture-analysis-input:" + "0" * 64, *self._db()
        ])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        code, _, err = _run([
            "admit", "--intake", "not-an-intake", *self._db()
        ])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_repository_validates_healthy_after_cli_use(self):
        _run(["admit", "--intake", self.intake, *self._db()])
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
