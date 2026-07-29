import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.analysis_finding_cli import main
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
    compose_sqlite_lecture_analysis_input_admission_service,
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


class AnalysisFindingCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"finding-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            self.intake, raw.raw_transcript_id.value
        )
        self.selection = compose_sqlite_corrected_revision_selection_service(connection)
        self.connection = connection
        self.raw = raw
        self._revise("c1", "교정 1")
        self.admission = compose_sqlite_lecture_analysis_input_admission_service(
            connection
        ).admit(intake_id=self.intake).admission.identity.value
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _revise(self, ref, text):
        segment_id = SQLiteRawTranscriptRepository(self.connection).get(
            self.raw.raw_transcript_id
        ).segment_ids[0]
        source_text = SQLiteTranscriptSegmentRepository(self.connection).get(segment_id).text
        candidate = compose_sqlite_correction_candidate_admission_service(
            self.connection
        ).admit(
            intake_id=self.intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": self.raw.raw_transcript_id.value,
                 "segment_id": segment_id.value, "candidate_ref": ref,
                 "source_type": "manual", "source_reference": "human",
                 "proposed_text": text, "source_text_snapshot": source_text,
                 "rationale": "fix"}
            ),
        ).candidate.identity.value
        compose_sqlite_correction_candidate_decision_service(self.connection).decide(
            candidate_id=candidate, kind="accept", reviewer="r:kim"
        )
        revision = compose_sqlite_corrected_revision_generation_service(
            self.connection
        ).generate(candidate_id=candidate).revision.identity.value
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        return revision

    def _admit(self, *extra):
        return _run([
            "admit", "--admission", self.admission, "--type", "background_noise",
            "--evidence", "잡음", *extra, "--database", str(self.database),
        ])

    def _rows(self):
        connection = open_sqlite_database(self.database)
        try:
            return connection.execute(
                "SELECT COUNT(*) FROM lecture_analysis_findings"
            ).fetchone()[0]
        finally:
            connection.close()

    def _finding_id(self, stdout):
        for line in stdout.splitlines():
            if line.startswith("analysis finding: "):
                return line.split(": ", 1)[1]
        raise AssertionError("no finding identity in output")

    def test_admit_records_and_states_contract_boundaries(self):
        code, out, _ = self._admit()
        self.assertEqual(code, 0)
        self.assertIn("recorded lecture analysis finding", out)
        self.assertIn("analysis execution: not part of this contract", out)
        self.assertIn("provider invocation: not part of this contract", out)
        self.assertEqual(self._rows(), 1)

    def test_exact_replay_reuses_without_new_row(self):
        self._admit()
        code, out, _ = self._admit()
        self.assertEqual(code, 0)
        self.assertIn("reused lecture analysis finding", out)
        self.assertEqual(self._rows(), 1)

    def test_show_and_status_report_derived_anchor_standing(self):
        _, out, _ = self._admit()
        finding = self._finding_id(out)
        code, shown, _ = _run(["show", "--finding", finding, "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("background_noise", shown)
        code, status, _ = _run(["status", "--finding", finding, "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("anchor authority match: current", status)

    def test_list_reports_recorded_findings(self):
        self._admit()
        self._admit("--range-start", "0.0", "--range-end", "1.0")
        code, out, _ = _run(
            ["list", "--admission", self.admission, "--database", str(self.database)]
        )
        self.assertEqual(code, 0)
        self.assertIn(f"lecture analysis findings for admission {self.admission}: 2", out)

    def test_optional_confidence_and_range_are_accepted(self):
        code, out, _ = self._admit(
            "--confidence", "0.5", "--uncertainty", "0.25",
            "--range-start", "0.5", "--range-end", "1.5",
        )
        self.assertEqual(code, 0)
        self.assertIn("confidence: 0.5", out)
        self.assertIn("source range: 0.5 -> 1.5", out)

    def test_superseded_anchor_fails_without_writing(self):
        self._admit()
        connection = open_sqlite_database(self.database)
        self.connection = connection
        self.selection = compose_sqlite_corrected_revision_selection_service(connection)
        self._revise("c2", "교정 2")
        connection.close()
        code, _, err = _run([
            "admit", "--admission", self.admission, "--type", "delivery_pause",
            "--evidence", "새 근거", "--database", str(self.database),
        ])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self._rows(), 1)

    def test_invalid_payload_fails_without_writing(self):
        for extra in (
            ["--type", "Bad Type"],
            ["--confidence", "1.5"],
            ["--range-start", "2.0", "--range-end", "1.0"],
        ):
            with self.subTest(extra=extra):
                argv = ["admit", "--admission", self.admission, "--type", "t",
                        "--evidence", "e", *extra, "--database", str(self.database)]
                code, _, err = _run(argv)
                self.assertEqual(code, 1)
                self.assertIn("error:", err)
        self.assertEqual(self._rows(), 0)

    def test_unknown_and_malformed_admission_fail(self):
        for admission in ("lecture-analysis-input:" + "f" * 64, "nope"):
            with self.subTest(admission=admission):
                code, _, err = _run([
                    "admit", "--admission", admission, "--type", "t", "--evidence", "e",
                    "--database", str(self.database),
                ])
                self.assertEqual(code, 1)
                self.assertIn("error:", err)
        self.assertEqual(self._rows(), 0)

    def test_unknown_finding_fails(self):
        code, _, err = _run([
            "show", "--finding", "lecture-analysis-finding:" + "0" * 64,
            "--database", str(self.database),
        ])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)


if __name__ == "__main__":
    unittest.main()
