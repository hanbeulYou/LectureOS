"""CLI surface of the Review authority history (043 §7.6, GOAL-029).

Covers the three added subcommands — `history`, `current`, `candidate-authority` — and the position
lines every judgment now prints. Identities only: the CLI never accepts a media path.
"""

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

_ACTOR = "reviewer:lee"
_OTHER_ACTOR = "reviewer:park"


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class LectureReviewAuthorityCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"authority-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(
            str(source)
        ).record
        self.intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        self.raw = compose_sqlite_provider_transcript_admission_service(
            connection
        ).admit(
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

    def _judge(self, kind="accept", actor=_ACTOR):
        return _run([kind, "--candidate", self.candidate, "--actor", actor,
                     "--database", str(self.database)])

    def _rows(self, table):
        connection = open_sqlite_database(self.database)
        try:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            connection.close()

    # -- the position lines a judgment prints ----------------------------------------------------

    def test_a_first_judgment_reports_the_position_it_started(self):
        code, out, _ = self._judge()
        self.assertEqual(code, 0)
        self.assertIn("recorded authority position", out)
        self.assertIn("authority position: lecture-review-authority-position:", out)
        self.assertIn("authority sequence: 0", out)
        self.assertIn("supersedes: none (first judgment of this scope)", out)

    def test_a_reversal_reports_the_position_it_superseded(self):
        _, first, _ = self._judge()
        code, out, _ = self._judge("reject")
        self.assertEqual(code, 0)
        self.assertIn("authority sequence: 1", out)
        position = [
            line for line in first.splitlines()
            if line.startswith("authority position: ")
        ][0].split(": ", 1)[1]
        self.assertIn(f"supersedes: {position}", out)

    def test_replaying_the_head_reports_a_reused_position(self):
        self._judge()
        code, out, _ = self._judge()
        self.assertEqual(code, 0)
        self.assertIn("reused review decision", out)
        self.assertIn("reused authority position", out)
        self.assertEqual(self._rows("lecture_review_authority_positions"), 1)

    def test_reversing_back_reuses_the_decision_and_records_a_new_position(self):
        self._judge()
        self._judge("reject")
        code, out, _ = self._judge()
        self.assertEqual(code, 0)
        self.assertIn("reused review decision", out)
        self.assertIn("recorded authority position", out)
        self.assertIn("authority sequence: 2", out)
        self.assertEqual(self._rows("lecture_review_decisions"), 2)
        self.assertEqual(self._rows("lecture_review_authority_positions"), 3)

    # -- history ---------------------------------------------------------------------------------

    def test_history_lists_every_position_oldest_first(self):
        self._judge()
        self._judge("reject")
        self._judge()
        code, out, _ = _run(["history", "--candidate", self.candidate,
                             "--actor", _ACTOR, "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn(f"authority history for {self.candidate} / {_ACTOR}: 3", out)
        body = out.splitlines()
        self.assertIn("[0] superseded decision=", body[1])
        self.assertIn("[1] superseded decision=", body[2])
        self.assertIn("[2] current decision=", body[3])
        self.assertIn("derived, never stored", out)

    def test_history_of_a_scope_without_judgments_is_empty(self):
        self._judge()
        code, out, _ = _run(["history", "--candidate", self.candidate,
                             "--actor", _OTHER_ACTOR, "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn(": 0", out)

    def test_history_refuses_a_malformed_candidate_or_actor(self):
        self._judge()
        for candidate, actor in ((str(self.base / "a.bin"), _ACTOR),
                                 (self.candidate, "   ")):
            with self.subTest(candidate=candidate, actor=actor):
                code, _, err = _run(["history", "--candidate", candidate,
                                     "--actor", actor, "--database", str(self.database)])
                self.assertEqual(code, 1)
                self.assertTrue(err)

    # -- current ---------------------------------------------------------------------------------

    def test_current_reports_the_derived_judgment_and_what_it_supersedes(self):
        self._judge()
        self._judge("reject")
        code, out, _ = _run(["current", "--candidate", self.candidate,
                             "--actor", _ACTOR, "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn(f"current judgment for {self.candidate} / {_ACTOR}", out)
        self.assertIn("authority sequence: 1", out)
        self.assertIn("superseded judgments: 1", out)
        self.assertIn("decision kind: reject", out)
        self.assertIn("approved edit decision: none", out)

    def test_current_carries_the_approved_snapshot_of_the_judgment_it_references(self):
        self._judge()
        code, out, _ = _run(["current", "--candidate", self.candidate,
                             "--actor", _ACTOR, "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("approved edit decision: lecture-approved-edit-decision:", out)
        self.assertIn("approved candidate type or label: non_lecture_region", out)

    def test_current_reports_an_absent_history_as_absence_and_not_as_an_error(self):
        self._judge()
        code, out, _ = _run(["current", "--candidate", self.candidate,
                             "--actor", _OTHER_ACTOR, "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("no recorded authority history", out)
        self.assertIn("is not corruption", out)
        self.assertIn("never backfilled", out)

    # -- candidate-authority ---------------------------------------------------------------------

    def test_one_actor_yields_the_candidate_level_current_judgment(self):
        self._judge()
        self._judge("reject")
        code, out, _ = _run(["candidate-authority", "--candidate", self.candidate,
                             "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("authority status: single_actor", out)
        self.assertIn("actors with history: 1", out)
        self.assertIn("current judgment: reject", out)
        self.assertIn("current review decision: lecture-review-decision:", out)

    def test_two_actors_surface_a_conflict_and_derive_no_current_judgment(self):
        self._judge()
        self._judge("reject", actor=_OTHER_ACTOR)
        code, out, _ = _run(["candidate-authority", "--candidate", self.candidate,
                             "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("authority status: cross_actor_conflict", out)
        self.assertIn("actors with history: 2", out)
        self.assertIn(f"  {_ACTOR}", out)
        self.assertIn(f"  {_OTHER_ACTOR}", out)
        self.assertIn("current judgment: none — several people have judged", out)
        self.assertIn("no priority among actors", out)
        self.assertIn("cross-actor arbitration: not part of this contract", out)

    def test_an_unreviewed_candidate_reports_no_recorded_history(self):
        code, out, _ = _run(["candidate-authority", "--candidate", self.candidate,
                             "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("authority status: no_history", out)
        self.assertIn("actors with history: 0", out)
        self.assertIn("current judgment: none — no authority history is recorded", out)

    def test_an_unknown_candidate_reports_absence_like_the_released_list_command(self):
        code, out, _ = _run(["candidate-authority", "--candidate",
                             "lecture-analysis-edit-candidate:" + "f" * 64,
                             "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("authority status: no_history", out)

    def test_the_authority_commands_never_accept_a_media_path(self):
        for argv in (
            ["history", "--candidate", str(self.base / "a.bin"), "--actor", _ACTOR],
            ["current", "--candidate", str(self.base / "a.bin"), "--actor", _ACTOR],
            ["candidate-authority", "--candidate", str(self.base / "a.bin")],
        ):
            with self.subTest(command=argv[0]):
                code, _, _ = _run([*argv, "--database", str(self.database)])
                self.assertEqual(code, 1)

    def test_the_authority_commands_never_write_a_row(self):
        self._judge()
        self._judge("reject")
        before = self._rows("lecture_review_authority_positions")
        for argv in (
            ["history", "--candidate", self.candidate, "--actor", _ACTOR],
            ["current", "--candidate", self.candidate, "--actor", _ACTOR],
            ["candidate-authority", "--candidate", self.candidate],
        ):
            with self.subTest(command=argv[0]):
                code, _, _ = _run([*argv, "--database", str(self.database)])
                self.assertEqual(code, 0)
        self.assertEqual(self._rows("lecture_review_authority_positions"), before)
        self.assertEqual(self._rows("lecture_review_decisions"), 2)

    def test_a_missing_database_exits_one(self):
        for argv in (
            ["history", "--candidate", self.candidate, "--actor", _ACTOR],
            ["current", "--candidate", self.candidate, "--actor", _ACTOR],
            ["candidate-authority", "--candidate", self.candidate],
        ):
            with self.subTest(command=argv[0]):
                code, _, err = _run(
                    [*argv, "--database", str(self.base / "missing.sqlite3")]
                )
                self.assertEqual(code, 1)
                self.assertTrue(err)

    def test_a_superseded_chain_refuses_a_new_position_but_still_reports_history(self):
        self._judge()
        self.connection = open_sqlite_database(self.database)
        try:
            self.selection = compose_sqlite_corrected_revision_selection_service(
                self.connection
            )
            self._revise("c2", "교정 2")
        finally:
            self.connection.close()
        code, _, err = self._judge("reject")
        self.assertEqual(code, 1)
        self.assertTrue(err)
        self.assertEqual(self._rows("lecture_review_authority_positions"), 1)
        code, out, _ = _run(["current", "--candidate", self.candidate,
                             "--actor", _ACTOR, "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("authority sequence: 0", out)


if __name__ == "__main__":
    unittest.main()
