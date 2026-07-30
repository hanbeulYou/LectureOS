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
    compose_sqlite_lecture_analysis_edit_candidate_service,
    compose_sqlite_lecture_analysis_finding_service,
    compose_sqlite_lecture_analysis_input_admission_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.lecture_review_cli import main
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class LectureReviewCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"review-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(
            str(source)
        ).record
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
        self.connection = connection
        self.selection = compose_sqlite_corrected_revision_selection_service(connection)
        self.revision_1 = self._revise("c1", "교정 1")
        admission = compose_sqlite_lecture_analysis_input_admission_service(
            connection
        ).admit(intake_id=self.intake).admission
        finding = compose_sqlite_lecture_analysis_finding_service(connection).admit(
            admission_id=admission.identity.value,
            finding_type="non_lecture_speech",
            evidence="근거",
        ).finding
        self.candidate = compose_sqlite_lecture_analysis_edit_candidate_service(
            connection
        ).admit_edit_candidate(
            finding_id=finding.identity.value,
            candidate_type="non_lecture_region",
            range_start=0.0,
            range_end=1.0,
            rationale="검토가 필요하다",
        ).candidate.identity.value
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _revise(self, ref, text):
        segment_id = SQLiteRawTranscriptRepository(self.connection).get(
            self.raw.raw_transcript_id
        ).segment_ids[0]
        source_text = SQLiteTranscriptSegmentRepository(self.connection).get(
            segment_id
        ).text
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

    def _accept(self, actor="reviewer:lee"):
        return _run(["accept", "--candidate", self.candidate, "--actor", actor,
                     "--database", str(self.database)])

    def _decision_id(self, output):
        for line in output.splitlines():
            if line.startswith("review decision: "):
                return line.split(": ", 1)[1]
        raise AssertionError(f"no decision identity in output: {output}")

    def _rows(self, table):
        connection = open_sqlite_database(self.database)
        try:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            connection.close()

    # -- accept / reject / modify ----------------------------------------------------------------

    def test_accept_records_a_decision_and_an_inherited_approval(self):
        code, out, _ = self._accept()
        self.assertEqual(code, 0)
        self.assertIn("recorded review decision", out)
        self.assertIn("decision kind: accept", out)
        self.assertIn("human actor: reviewer:lee", out)
        self.assertIn("approved edit decision: lecture-approved-edit-decision:", out)
        self.assertIn("approved candidate type or label: non_lecture_region", out)
        self.assertEqual(self._rows("lecture_review_decisions"), 1)
        self.assertEqual(self._rows("lecture_approved_edit_decisions"), 1)

    def test_reject_records_a_decision_with_no_approval(self):
        code, out, _ = _run(["reject", "--candidate", self.candidate,
                             "--actor", "reviewer:lee", "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("decision kind: reject", out)
        self.assertIn("approved edit decision: none", out)
        self.assertEqual(self._rows("lecture_approved_edit_decisions"), 0)

    def test_modify_records_the_complete_approved_replacement(self):
        code, out, _ = _run(["modify", "--candidate", self.candidate,
                             "--actor", "reviewer:lee", "--approved-start=0.0",
                             "--approved-end=0.5", "--approved-label", "trim_intro",
                             "--approved-rationale", "앞부분만 승인",
                             "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("decision kind: modify", out)
        self.assertIn("approved range: 0.0 -> 0.5", out)
        self.assertIn("approved candidate type or label: trim_intro", out)
        self.assertIn("approved rationale: 앞부분만 승인", out)

    def test_exact_replay_reuses_without_writing(self):
        self._accept()
        code, out, _ = self._accept()
        self.assertEqual(code, 0)
        self.assertIn("reused review decision", out)
        self.assertEqual(self._rows("lecture_review_decisions"), 1)

    def test_a_second_differing_modify_exits_one_and_writes_nothing(self):
        base = ["modify", "--candidate", self.candidate, "--actor", "reviewer:lee",
                "--approved-start=0.0", "--approved-label", "trim_intro",
                "--approved-rationale", "이유", "--database", str(self.database)]
        self.assertEqual(_run([*base, "--approved-end=0.5"])[0], 0)
        code, _, err = _run([*base, "--approved-end=0.9"])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self._rows("lecture_approved_edit_decisions"), 1)

    # -- refusals --------------------------------------------------------------------------------

    def test_an_unknown_kind_is_not_a_subcommand(self):
        with self.assertRaises(SystemExit):
            _run(["approve", "--candidate", self.candidate, "--actor", "r",
                  "--database", str(self.database)])

    def test_invalid_input_exits_one_and_writes_nothing(self):
        for argv in (
            ["accept", "--candidate", "nope", "--actor", "reviewer:lee"],
            ["accept", "--candidate", self.candidate, "--actor", "   "],
            ["accept", "--candidate",
             "lecture-analysis-edit-candidate:" + "f" * 64, "--actor", "reviewer:lee"],
            ["modify", "--candidate", self.candidate, "--actor", "reviewer:lee",
             "--approved-start=1.0", "--approved-end=0.0",
             "--approved-label", "trim_intro", "--approved-rationale", "이유"],
            ["modify", "--candidate", self.candidate, "--actor", "reviewer:lee",
             "--approved-start=-1.0", "--approved-end=1.0",
             "--approved-label", "trim_intro", "--approved-rationale", "이유"],
            ["modify", "--candidate", self.candidate, "--actor", "reviewer:lee",
             "--approved-start=0.0", "--approved-end=1.0",
             "--approved-label", "Bad Label", "--approved-rationale", "이유"],
        ):
            with self.subTest(argv=argv[0:2] + argv[4:6]):
                code, _, err = _run([*argv, "--database", str(self.database)])
                self.assertEqual(code, 1)
                self.assertIn("error:", err)
        self.assertEqual(self._rows("lecture_review_decisions"), 0)

    def test_modify_requires_every_approved_argument(self):
        with self.assertRaises(SystemExit):
            _run(["modify", "--candidate", self.candidate, "--actor", "reviewer:lee",
                  "--approved-start=0.0", "--database", str(self.database)])

    def test_a_missing_database_exits_one(self):
        code, _, err = _run(["accept", "--candidate", self.candidate,
                             "--actor", "reviewer:lee",
                             "--database", str(self.base / "absent.sqlite3")])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_a_superseded_chain_exits_one(self):
        self.connection = open_sqlite_database(self.database)
        try:
            self.selection = compose_sqlite_corrected_revision_selection_service(
                self.connection
            )
            self._revise("c2", "교정 2")
        finally:
            self.connection.close()
        code, _, err = self._accept()
        self.assertEqual(code, 1)
        self.assertIn("current effective authority", err)
        self.assertEqual(self._rows("lecture_review_decisions"), 0)

    # -- queries ---------------------------------------------------------------------------------

    def test_show_prints_the_decision_and_its_approval(self):
        decision = self._decision_id(self._accept()[1])
        code, out, _ = _run(["show", "--decision", decision,
                             "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn(decision, out)
        self.assertIn("approved edit decision: lecture-approved-edit-decision:", out)
        self.assertIn("edit application: not part of this contract", out)

    def test_show_refuses_an_unknown_decision(self):
        code, _, err = _run(["show", "--decision",
                             "lecture-review-decision:" + "e" * 64,
                             "--database", str(self.database)])
        self.assertEqual(code, 1)
        self.assertIn("unknown lecture review decision", err)

    def test_status_reports_the_derived_standing(self):
        decision = self._decision_id(self._accept()[1])
        code, out, _ = _run(["status", "--decision", decision,
                             "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("anchor chain authority match: current", out)
        self.assertIn("currentness is derived, never stored", out)

    def test_status_after_an_authority_change_reports_superseded(self):
        decision = self._decision_id(self._accept()[1])
        self.connection = open_sqlite_database(self.database)
        try:
            self.selection = compose_sqlite_corrected_revision_selection_service(
                self.connection
            )
            self._revise("c2", "교정 2")
        finally:
            self.connection.close()
        code, out, _ = _run(["status", "--decision", decision,
                             "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn(
            "anchor chain authority match: superseded_by_authority_change", out
        )

    def test_list_shows_every_coexisting_judgment(self):
        self._accept()
        _run(["reject", "--candidate", self.candidate, "--actor", "reviewer:lee",
              "--database", str(self.database)])
        self._accept(actor="reviewer:park")
        code, out, _ = _run(["list", "--candidate", self.candidate,
                             "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn(f"review decisions for candidate {self.candidate}: 3", out)
        self.assertIn("accept by reviewer:lee", out)
        self.assertIn("reject by reviewer:lee", out)
        self.assertIn("accept by reviewer:park", out)
        self.assertIn("not a canonical ordinal", out)

    def test_list_is_empty_before_any_review(self):
        code, out, _ = _run(["list", "--candidate", self.candidate,
                             "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn(": 0", out)

    def test_the_cli_never_accepts_a_media_path(self):
        code, _, _ = _run(["accept", "--candidate", str(self.base / "a.bin"),
                           "--actor", "reviewer:lee", "--database", str(self.database)])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
