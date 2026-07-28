import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.analysis_input_eligibility_cli import main
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


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class AnalysisInputEligibilityCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"eligibility-cli \x00\x01")
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
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _select_corrected(self):
        connection = open_sqlite_database(self.database)
        try:
            segment_id = SQLiteRawTranscriptRepository(connection).get(
                self.raw.raw_transcript_id
            ).segment_ids[0]
            text = SQLiteTranscriptSegmentRepository(connection).get(segment_id).text
            candidate = compose_sqlite_correction_candidate_admission_service(
                connection
            ).admit(
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
            revision = compose_sqlite_corrected_revision_generation_service(
                connection
            ).generate(candidate_id=candidate).revision.identity.value
            compose_sqlite_corrected_revision_selection_service(connection).select_revision(
                revision_id=revision, reviewer="s:kim"
            )
            return revision
        finally:
            connection.close()

    def _evaluate(self):
        return _run(["evaluate", "--intake", self.intake,
                     "--database", str(self.database)])

    def test_ineligible_without_corrected_selection_exits_one(self):
        code, out, err = self._evaluate()
        self.assertEqual(code, 1, err)
        self.assertIn("eligible for analysis input: no", out)
        self.assertIn("blocking reason: corrected_transcript_not_selected", out)
        self.assertIn("selection state: no_history", out)
        self.assertIn("analysis input state: not created", out)
        self.assertIn("analysis execution state: not part of this contract", out)

    def test_eligible_corrected_authority_exits_zero_with_lineage(self):
        revision = self._select_corrected()
        code, out, err = self._evaluate()
        self.assertEqual(code, 0, err)
        self.assertIn("eligible for analysis input: yes", out)
        self.assertIn(f"corrected revision: {revision}", out)
        self.assertIn(
            f"parent raw transcript: {self.raw.raw_transcript_id.value}", out
        )
        self.assertIn("effective transcript kind: corrected_revision", out)
        self.assertIn("content fingerprint: ", out)
        self.assertIn("segments: 1", out)
        self.assertIn("must revalidate current authority", out)

    def test_unknown_intake_is_ineligible_and_malformed_errors(self):
        code, out, err = _run([
            "evaluate", "--intake", "transcript-source-intake:sha256:" + "0" * 64,
            "--database", str(self.database),
        ])
        self.assertEqual(code, 1)
        self.assertIn("blocking reason: intake_not_found", out)
        code, _, err = _run([
            "evaluate", "--intake", "not-an-intake", "--database", str(self.database),
        ])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_cli_persists_nothing(self):
        self._select_corrected()
        connection = open_sqlite_database(self.database)
        try:
            before = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for (table,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        finally:
            connection.close()
        self._evaluate()
        self._evaluate()
        connection = open_sqlite_database(self.database)
        try:
            after = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for (table,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        finally:
            connection.close()
        self.assertEqual(after, before)
        self.assertEqual(after.get("eligible_analysis_inputs", 0), 0)


if __name__ == "__main__":
    unittest.main()
