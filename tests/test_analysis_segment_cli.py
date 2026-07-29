import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.analysis_segment_cli import main
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


class AnalysisSegmentCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"segment-cli \x00\x01")
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

    def _admit(self, *segments, admission=None):
        segs = segments or ("0.0:1.0", "1.0:2.0")
        argv = ["admit", "--admission", admission or self.admission]
        for seg in segs:
            # `--segment=<value>` for leading-dash values: argparse would otherwise read a
            # negative start as an option name.
            argv += [f"--segment={seg}"] if seg.startswith("-") else ["--segment", seg]
        return _run(argv + ["--database", str(self.database)])

    def _rows(self):
        connection = open_sqlite_database(self.database)
        try:
            return connection.execute(
                "SELECT COUNT(*) FROM lecture_analysis_segments"
            ).fetchone()[0]
        finally:
            connection.close()

    def _segment_id(self, stdout):
        for line in stdout.splitlines():
            if line.startswith("lecture segment: "):
                return line.split(": ", 1)[1]
            if line.strip().startswith("[0]"):
                return line[line.index("(") + 1:line.rindex(")")]
        raise AssertionError("no segment identity in output")

    def test_admit_records_and_states_contract_boundaries(self):
        code, out, _ = self._admit()
        self.assertEqual(code, 0)
        self.assertIn("recorded lecture segmentation", out)
        self.assertIn("segmentation provider: not part of this contract", out)
        self.assertIn("analysis execution: not part of this contract", out)
        self.assertEqual(self._rows(), 2)

    def test_exact_replay_reuses_without_new_rows(self):
        self._admit()
        code, out, _ = self._admit()
        self.assertEqual(code, 0)
        self.assertIn("reused lecture segmentation", out)
        self.assertEqual(self._rows(), 2)

    def test_integral_spelling_converges(self):
        _, first, _ = self._admit("0:1", "1:2")
        code, again, _ = self._admit("0.0:1.0", "1.0:2.0")
        self.assertEqual(code, 0)
        self.assertIn("reused lecture segmentation", again)
        self.assertEqual(self._rows(), 2)

    def test_show_and_status_report_derived_anchor_standing(self):
        _, out, _ = self._admit("0.0:1.0")
        segment = self._segment_id(out)
        code, shown, _ = _run(["show", "--segment-id", segment,
                               "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("sequence: 0", shown)
        code, status, _ = _run(["status", "--segment-id", segment,
                                "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("anchor authority match: current", status)

    def test_list_reports_recorded_segments(self):
        self._admit("0.0:1.0", "1.0:2.0")
        code, out, _ = _run(
            ["list", "--admission", self.admission, "--database", str(self.database)]
        )
        self.assertEqual(code, 0)
        self.assertIn(f"lecture segments for admission {self.admission}: 2", out)

    def test_superseded_anchor_fails_without_writing(self):
        self._admit()
        connection = open_sqlite_database(self.database)
        self.connection = connection
        self.selection = compose_sqlite_corrected_revision_selection_service(connection)
        self._revise("c2", "교정 2")
        connection.close()
        code, _, err = self._admit("5.0:6.0")
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self._rows(), 2)

    def test_invalid_payload_fails_without_writing(self):
        for segment in ("1.0:0.0", "-1.0:1.0", "nonsense", "1.0"):
            with self.subTest(segment=segment):
                code, _, err = self._admit(segment)
                self.assertEqual(code, 1)
                self.assertIn("error:", err)
        self.assertEqual(self._rows(), 0)

    def test_unknown_and_malformed_admission_fail(self):
        for admission in ("lecture-analysis-input:" + "f" * 64, "nope"):
            with self.subTest(admission=admission):
                code, _, err = self._admit("0.0:1.0", admission=admission)
                self.assertEqual(code, 1)
                self.assertIn("error:", err)
        self.assertEqual(self._rows(), 0)

    def test_unknown_segment_fails(self):
        code, _, err = _run([
            "show", "--segment-id", "lecture-analysis-segment:" + "0" * 64,
            "--database", str(self.database),
        ])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)


if __name__ == "__main__":
    unittest.main()
