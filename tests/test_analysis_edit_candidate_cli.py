import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.analysis_edit_candidate_cli import main
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
    compose_sqlite_lecture_analysis_finding_service,
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


class AnalysisEditCandidateCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"candidate-cli \x00\x01")
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
        admission = compose_sqlite_lecture_analysis_input_admission_service(
            connection
        ).admit(intake_id=self.intake).admission
        self.finding = compose_sqlite_lecture_analysis_finding_service(connection).admit(
            admission_id=admission.identity.value,
            finding_type="non_lecture_speech",
            evidence="관찰",
        ).finding.identity.value
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

    _RATIONALE = "이 구간은 사람이 검토할 만하다"

    def _admit(self, finding=None, ctype="non_lecture_region", start="0.0", end="1.0",
               rationale=None):
        return _run([
            "admit", "--finding", finding if finding is not None else self.finding,
            "--candidate-type", ctype,
            f"--start={start}", f"--end={end}",
            "--rationale", rationale if rationale is not None else self._RATIONALE,
            "--database", str(self.database),
        ])

    def _rows(self):
        connection = open_sqlite_database(self.database)
        try:
            return connection.execute(
                "SELECT COUNT(*) FROM lecture_analysis_edit_candidates"
            ).fetchone()[0]
        finally:
            connection.close()

    def _candidate_id(self, stdout):
        for line in stdout.splitlines():
            if line.startswith("edit candidate: "):
                return line.split(": ", 1)[1]
        raise AssertionError("no candidate identity in output")

    def test_admit_records_and_states_contract_boundaries(self):
        code, out, _ = self._admit()
        self.assertEqual(code, 0)
        self.assertIn("recorded edit candidate", out)
        self.assertIn("candidate provider: not part of this contract", out)
        self.assertIn("review workflow: not part of this contract", out)
        self.assertIn("analysis execution: not part of this contract", out)
        self.assertEqual(self._rows(), 1)

    def test_exact_replay_reuses_without_new_row(self):
        self._admit()
        code, out, _ = self._admit()
        self.assertEqual(code, 0)
        self.assertIn("reused edit candidate", out)
        self.assertEqual(self._rows(), 1)

    def test_integral_and_negative_zero_spellings_converge(self):
        self._admit(start="0", end="1")
        for start in ("0.0", "-0.0"):
            with self.subTest(start=start):
                code, out, _ = self._admit(start=start)
                self.assertEqual(code, 0)
                self.assertIn("reused edit candidate", out)
        self.assertEqual(self._rows(), 1)

    def test_different_rationale_creates_a_distinct_candidate(self):
        _, first, _ = self._admit()
        _, second, _ = self._admit(rationale="다른 이유")
        self.assertNotEqual(self._candidate_id(first), self._candidate_id(second))
        self.assertEqual(self._rows(), 2)

    def test_show_and_status_report_derived_chain_standing(self):
        _, out, _ = self._admit()
        candidate = self._candidate_id(out)
        code, shown, _ = _run(["show", "--candidate", candidate,
                               "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("candidate type: non_lecture_region", shown)
        self.assertIn(self._RATIONALE, shown)
        code, status, _ = _run(["status", "--candidate", candidate,
                                "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("anchor chain authority match: current", status)

    def test_list_reports_recorded_candidates(self):
        self._admit()
        self._admit(ctype="delivery_concern")
        code, out, _ = _run(
            ["list", "--finding", self.finding, "--database", str(self.database)]
        )
        self.assertEqual(code, 0)
        self.assertIn(f"edit candidates for finding {self.finding}: 2", out)

    def test_superseded_chain_fails_without_writing(self):
        self._admit()
        connection = open_sqlite_database(self.database)
        self.connection = connection
        self.selection = compose_sqlite_corrected_revision_selection_service(connection)
        self._revise("c2", "교정 2")
        connection.close()
        code, _, err = self._admit(ctype="delivery_concern")
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self._rows(), 1)

    def test_invalid_payload_fails_without_writing(self):
        for kwargs in ({"start": "1.0", "end": "0.0"}, {"start": "-1.0"},
                       {"ctype": "Bad Type"}, {"rationale": "   "}):
            with self.subTest(kwargs=kwargs):
                code, _, err = self._admit(**kwargs)
                self.assertEqual(code, 1)
                self.assertIn("error:", err)
        self.assertEqual(self._rows(), 0)

    def test_unknown_and_malformed_finding_fail(self):
        for finding in ("lecture-analysis-finding:" + "f" * 64, "nope"):
            with self.subTest(finding=finding):
                code, _, err = self._admit(finding=finding)
                self.assertEqual(code, 1)
                self.assertIn("error:", err)
        self.assertEqual(self._rows(), 0)

    def test_unknown_candidate_fails(self):
        code, _, err = _run([
            "show", "--candidate", "lecture-analysis-edit-candidate:" + "0" * 64,
            "--database", str(self.database),
        ])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)


if __name__ == "__main__":
    unittest.main()
