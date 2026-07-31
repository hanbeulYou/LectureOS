"""Application and persistence tests for the Review authority history (043 §7.6, GOAL-029).

Drives the append rule, the derived current judgment, the cross-actor observation, and the atomic
compare-and-append over a real released upstream chain.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.lecture_analysis_input_admission import (
    AdmissionAuthorityMatch,
)
from lectureos.application.lecture_review_authority import (
    AuthorityPositionOutcome,
    CandidateAuthorityStatus,
    LectureReviewAuthorityError,
    ReviewAuthorityConflictError,
    derive_authority_position_identity,
    plan_authority_position,
)
from lectureos.application.lecture_review_decision import (
    LectureReviewApplicationService,
    LectureReviewError,
    ReviewAnchorNotAdmissibleError,
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
    compose_sqlite_lecture_review_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.persistence.lecture_review_decision import (
    SQLiteLectureReviewCommandPersistence,
    SQLiteLectureReviewRepository,
)
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository
from lectureos.review.identities import HumanActorReference

_ACTOR = "reviewer:lee"
_OTHER_ACTOR = "reviewer:park"
_THIRD_ACTOR = "reviewer:choi"
_APPROVED_RATIONALE = "앞부분만 잘라내는 것으로 승인한다"
_CANDIDATE_RATIONALE = "이 구간은 사람이 검토할 만하다"


class _Chain(unittest.TestCase):
    """One real released upstream chain down to a current-generation Edit Candidate."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"authority \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(
            str(source)
        ).record
        self.intake = compose_sqlite_transcript_source_intake_service(
            self.connection
        ).admit(media.identity.value).intake.identity.value
        self.raw = compose_sqlite_provider_transcript_admission_service(
            self.connection
        ).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.intake, self.raw.raw_transcript_id.value
        )
        self.selection = compose_sqlite_corrected_revision_selection_service(
            self.connection
        )
        self.revision_1 = self._revise("c1", "교정 1")
        self.admission = compose_sqlite_lecture_analysis_input_admission_service(
            self.connection
        ).admit(intake_id=self.intake).admission
        self.finding = compose_sqlite_lecture_analysis_finding_service(
            self.connection
        ).admit(
            admission_id=self.admission.identity.value,
            finding_type="non_lecture_speech",
            evidence="수업과 무관한 발화가 관찰된다",
        ).finding
        self.candidate_service = compose_sqlite_lecture_analysis_edit_candidate_service(
            self.connection
        )
        self.candidate = self.candidate_service.admit_edit_candidate(
            finding_id=self.finding.identity.value,
            candidate_type="non_lecture_region",
            range_start=0.0,
            range_end=1.0,
            rationale=_CANDIDATE_RATIONALE,
        ).candidate
        self.reviews = compose_sqlite_lecture_review_service(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
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

    def _judge(self, **overrides):
        payload = {
            "candidate_id": self.candidate.identity.value,
            "decision_kind": "accept",
            "actor": _ACTOR,
        }
        payload.update(overrides)
        return self.reviews.admit_review_decision(**payload)

    def _modify(self, **overrides):
        payload = {
            "decision_kind": "modify",
            "approved_range_start": 0.0,
            "approved_range_end": 0.5,
            "approved_label": "trim_intro",
            "approved_rationale": _APPROVED_RATIONALE,
        }
        payload.update(overrides)
        return self._judge(**payload)

    def _positions(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM lecture_review_authority_positions"
        ).fetchone()[0]

    def _rows(self):
        return self.connection.execute(
            "SELECT identity, candidate_id, actor, sequence, review_decision_id, "
            "previous_position_id, position_contract_version "
            "FROM lecture_review_authority_positions ORDER BY identity"
        ).fetchall()


class AppendTests(_Chain):
    def test_the_first_judgment_starts_the_history_at_sequence_zero(self):
        recorded = self._judge()
        self.assertIs(recorded.position_outcome, AuthorityPositionOutcome.RECORDED)
        self.assertEqual(recorded.position.sequence, 0)
        self.assertIsNone(recorded.position.previous_position_id)
        self.assertEqual(
            recorded.position.review_decision_id, recorded.decision.identity
        )
        self.assertEqual(recorded.position.actor, HumanActorReference(_ACTOR))
        self.assertEqual(self._positions(), 1)

    def test_a_different_judgment_appends_and_supersedes_the_head(self):
        first = self._judge()
        second = self._judge(decision_kind="reject")
        self.assertIs(second.position_outcome, AuthorityPositionOutcome.RECORDED)
        self.assertEqual(second.position.sequence, 1)
        self.assertEqual(second.position.previous_position_id, first.position.identity)
        self.assertEqual(self._positions(), 2)

    def test_reversing_back_reuses_the_decision_and_opens_a_new_position(self):
        """AH-6: two converged decisions across three positions is the whole point."""

        first = self._judge()
        second = self._judge(decision_kind="reject")
        third = self._judge()
        self.assertEqual(third.outcome.value, "reused")
        self.assertEqual(third.decision.identity, first.decision.identity)
        self.assertIs(third.position_outcome, AuthorityPositionOutcome.RECORDED)
        self.assertEqual(third.position.sequence, 2)
        self.assertEqual(third.position.previous_position_id, second.position.identity)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_review_decisions"
            ).fetchone()[0],
            2,
        )
        self.assertEqual(self._positions(), 3)

    def test_replaying_the_judgment_the_head_records_writes_nothing(self):
        first = self._judge()
        before = self._rows()
        replayed = self._judge()
        self.assertIs(replayed.position_outcome, AuthorityPositionOutcome.REUSED)
        self.assertEqual(replayed.position.identity, first.position.identity)
        self.assertEqual(self._rows(), before)

    def test_a_modify_starts_and_extends_the_history_like_any_other_judgment(self):
        modified = self._modify()
        self.assertEqual(modified.position.sequence, 0)
        reversed_once = self._judge(decision_kind="reject")
        self.assertEqual(reversed_once.position.sequence, 1)
        back = self._modify()
        self.assertEqual(back.outcome.value, "reused")
        self.assertEqual(back.position.sequence, 2)
        self.assertEqual(back.decision.identity, modified.decision.identity)

    def test_every_position_carries_the_scope_it_belongs_to(self):
        self._judge()
        self._judge(decision_kind="reject")
        for row in self._rows():
            with self.subTest(identity=row[0]):
                self.assertEqual(row[1], self.candidate.identity.value)
                self.assertEqual(row[2], _ACTOR)
                self.assertEqual(row[6], 1)

    def test_the_history_ordinal_is_never_derived_from_a_row_count(self):
        """AH-7: the next position comes from this scope's head, not from the table."""

        self._judge(actor=_OTHER_ACTOR)
        self._judge(actor=_THIRD_ACTOR)
        first = self._judge()
        self.assertEqual(self._positions(), 3)
        self.assertEqual(first.position.sequence, 0)


class DerivedCurrentTests(_Chain):
    def test_the_current_judgment_is_the_highest_position(self):
        self._judge()
        self._judge(decision_kind="reject")
        third = self._judge()
        current = self.reviews.current_review(self.candidate.identity.value, _ACTOR)
        self.assertEqual(current.sequence, 2)
        self.assertEqual(current.superseded_count, 2)
        self.assertEqual(current.position, third.position)
        self.assertEqual(current.decision.decision_kind.value, "accept")
        self.assertEqual(current.actor, HumanActorReference(_ACTOR))

    def test_the_current_judgment_carries_the_approved_snapshot_it_references(self):
        accepted = self._judge()
        current = self.reviews.current_review(self.candidate.identity.value, _ACTOR)
        self.assertEqual(current.approved, accepted.approved)
        self.assertEqual(
            self.reviews.current_approved(self.candidate.identity.value, _ACTOR),
            accepted.approved,
        )

    def test_a_current_reject_owns_no_approval(self):
        self._judge()
        self._judge(decision_kind="reject")
        current = self.reviews.current_review(self.candidate.identity.value, _ACTOR)
        self.assertEqual(current.decision.decision_kind.value, "reject")
        self.assertIsNone(current.approved)
        self.assertIsNone(
            self.reviews.current_approved(self.candidate.identity.value, _ACTOR)
        )

    def test_currentness_is_never_stored_anywhere(self):
        """AH-8: no flag, no status column, no latest-row marker."""

        self._judge()
        columns = {
            row[1] for row in self.connection.execute(
                "PRAGMA table_info(lecture_review_authority_positions)"
            ).fetchall()
        }
        self.assertEqual(
            columns,
            {"identity", "candidate_id", "actor", "sequence", "review_decision_id",
             "previous_position_id", "position_contract_version"},
        )
        for forbidden in ("current", "is_current", "status", "stale", "selected",
                          "created_at", "superseded_at"):
            with self.subTest(column=forbidden):
                self.assertNotIn(forbidden, columns)

    def test_observing_the_current_judgment_changes_nothing(self):
        self._judge()
        self._judge(decision_kind="reject")
        before = self._rows()
        for _ in range(3):
            self.reviews.current_review(self.candidate.identity.value, _ACTOR)
            self.reviews.authority_history(self.candidate.identity.value, _ACTOR)
            self.reviews.observe_candidate_authority(self.candidate.identity.value)
        self.assertEqual(self._rows(), before)

    def test_superseded_positions_remain_immutable_history(self):
        first = self._judge()
        second = self._judge(decision_kind="reject")
        third = self._judge()
        history = self.reviews.authority_history(self.candidate.identity.value, _ACTOR)
        self.assertEqual(
            history, (first.position, second.position, third.position)
        )
        self.assertEqual([position.sequence for position in history], [0, 1, 2])

    def test_a_scope_with_no_history_derives_nothing_and_is_not_an_error(self):
        """AH-12: absence means 'no recorded authority history', never corruption."""

        self._judge()
        self.assertIsNone(
            self.reviews.current_review(self.candidate.identity.value, _OTHER_ACTOR)
        )
        self.assertEqual(
            self.reviews.authority_history(self.candidate.identity.value, _OTHER_ACTOR),
            (),
        )
        self.assertIsNone(
            self.reviews.current_approved(self.candidate.identity.value, _OTHER_ACTOR)
        )

    def test_a_judgment_recorded_before_this_contract_derives_no_current(self):
        """AH-12's read-time rule, simulated by a decision row with no position."""

        accepted = self._judge()
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute("DELETE FROM lecture_review_authority_positions")
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.assertIsNotNone(self.reviews.get(accepted.decision.identity.value))
        self.assertIsNone(
            self.reviews.current_review(self.candidate.identity.value, _ACTOR)
        )
        self.assertIs(
            self.reviews.observe_candidate_authority(
                self.candidate.identity.value
            ).status,
            CandidateAuthorityStatus.NO_HISTORY,
        )

    def test_the_next_admission_after_a_position_less_judgment_starts_at_zero(self):
        """AH-12: no backfill; the history simply begins at 0 for that scope."""

        self._judge()
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute("DELETE FROM lecture_review_authority_positions")
        self.connection.execute("PRAGMA foreign_keys = ON")
        restarted = self._judge(decision_kind="reject")
        self.assertEqual(restarted.position.sequence, 0)
        self.assertIsNone(restarted.position.previous_position_id)
        self.assertEqual(self._positions(), 1)

    def test_malformed_scope_references_are_refused_by_the_queries(self):
        for candidate, actor in (("nope", _ACTOR),
                                 (self.candidate.identity.value, "  ")):
            with self.subTest(candidate=candidate, actor=actor):
                with self.assertRaises((LectureReviewError,
                                        LectureReviewAuthorityError)):
                    self.reviews.current_review(candidate, actor)
                with self.assertRaises((LectureReviewError,
                                        LectureReviewAuthorityError)):
                    self.reviews.authority_history(candidate, actor)

    def test_a_position_referencing_a_missing_decision_is_an_integrity_failure(self):
        self._judge()
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute("DELETE FROM lecture_review_decisions")
        self.connection.execute("PRAGMA foreign_keys = ON")
        with self.assertRaises(LectureReviewAuthorityError):
            self.reviews.current_review(self.candidate.identity.value, _ACTOR)


class CrossActorTests(_Chain):
    def test_one_actor_with_history_yields_that_actors_current_judgment(self):
        self._judge()
        rejected = self._judge(decision_kind="reject")
        observation = self.reviews.observe_candidate_authority(
            self.candidate.identity.value
        )
        self.assertIs(observation.status, CandidateAuthorityStatus.SINGLE_ACTOR)
        self.assertFalse(observation.is_conflict)
        self.assertEqual(observation.actors, (HumanActorReference(_ACTOR),))
        self.assertEqual(observation.current.decision, rejected.decision)

    def test_two_actors_derive_no_current_judgment_and_report_a_conflict(self):
        """AH-9: surfaced, never auto-resolved — no priority, recency, or role ranking."""

        self._judge()
        self._judge(decision_kind="reject", actor=_OTHER_ACTOR)
        observation = self.reviews.observe_candidate_authority(
            self.candidate.identity.value
        )
        self.assertIs(observation.status, CandidateAuthorityStatus.CROSS_ACTOR_CONFLICT)
        self.assertTrue(observation.is_conflict)
        self.assertIsNone(observation.current)
        self.assertEqual(
            observation.actors,
            (HumanActorReference(_ACTOR), HumanActorReference(_OTHER_ACTOR)),
        )

    def test_the_later_judgment_never_wins_across_actors(self):
        self._judge(actor=_OTHER_ACTOR)
        self._judge(decision_kind="reject")
        self._judge(actor=_THIRD_ACTOR)
        observation = self.reviews.observe_candidate_authority(
            self.candidate.identity.value
        )
        self.assertIsNone(observation.current)
        self.assertEqual(len(observation.actors), 3)

    def test_each_actor_keeps_a_separate_history_on_one_candidate(self):
        first = self._judge()
        self._judge(decision_kind="reject")
        other = self._judge(decision_kind="reject", actor=_OTHER_ACTOR)
        self.assertEqual(other.position.sequence, 0)
        self.assertIsNone(other.position.previous_position_id)
        self.assertNotEqual(other.position.identity, first.position.identity)
        self.assertEqual(
            len(self.reviews.authority_history(self.candidate.identity.value, _ACTOR)), 2
        )
        self.assertEqual(
            len(
                self.reviews.authority_history(
                    self.candidate.identity.value, _OTHER_ACTOR
                )
            ),
            1,
        )

    def test_per_actor_currents_stay_derivable_during_a_conflict(self):
        self._judge()
        self._judge(decision_kind="reject")
        self._judge(decision_kind="reject", actor=_OTHER_ACTOR)
        self.assertEqual(
            self.reviews.current_review(
                self.candidate.identity.value, _ACTOR
            ).decision.decision_kind.value,
            "reject",
        )
        self.assertEqual(
            self.reviews.current_review(
                self.candidate.identity.value, _OTHER_ACTOR
            ).sequence,
            0,
        )

    def test_an_unreviewed_candidate_reports_no_history(self):
        observation = self.reviews.observe_candidate_authority(
            self.candidate.identity.value
        )
        self.assertIs(observation.status, CandidateAuthorityStatus.NO_HISTORY)
        self.assertEqual(observation.actors, ())
        self.assertIsNone(observation.current)

    def test_the_observation_refuses_a_malformed_candidate_reference(self):
        with self.assertRaises(LectureReviewError):
            self.reviews.observe_candidate_authority("nope")


class StandingTests(_Chain):
    def test_a_superseded_chain_refuses_a_new_position(self):
        """AH-10: appending requires R-3 standing; observation does not."""

        self._judge()
        before = self._rows()
        self._revise("c2", "교정 2")
        with self.assertRaises(ReviewAnchorNotAdmissibleError):
            self._judge(decision_kind="reject")
        self.assertEqual(self._rows(), before)

    def test_the_current_judgment_stays_observable_while_the_chain_is_superseded(self):
        accepted = self._judge()
        self._revise("c2", "교정 2")
        self.assertIs(
            self.reviews.anchor_status(accepted.decision),
            AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE,
        )
        current = self.reviews.current_review(self.candidate.identity.value, _ACTOR)
        self.assertEqual(current.decision, accepted.decision)

    def test_returning_authority_appends_nothing_for_the_same_judgment(self):
        accepted = self._judge()
        self._revise("c2", "교정 2")
        self.selection.select_revision(
            revision_id=self.revision_1, reviewer="s:kim"
        )
        converged = self._judge()
        self.assertEqual(converged.decision.identity, accepted.decision.identity)
        self.assertIs(converged.position_outcome, AuthorityPositionOutcome.REUSED)
        self.assertEqual(self._positions(), 1)

    def test_being_current_is_not_export_eligibility(self):
        """AH-10: linking this generation's approvals to `044` stays a separate decision."""

        self._judge()
        for table in ("edit_export_assemblies", "approved_edit_export_representations",
                      "approved_edit_decisions"):
            with self.subTest(table=table):
                self.assertEqual(
                    self.connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0],
                    0,
                )


class AtomicityAndConflictTests(_Chain):
    def test_the_decision_the_approval_and_the_position_are_one_unit(self):
        """AH-12 write-time: a failure while writing the position leaves nothing behind."""

        class _Failing(SQLiteLectureReviewCommandPersistence):
            def persist_review(self, *, decision, approved, position=None):
                broken = None
                if position is not None:
                    broken = object.__new__(type(position))
                    for field in type(position).__slots__:
                        object.__setattr__(broken, field, getattr(position, field))
                    object.__setattr__(broken, "sequence", None)
                super().persist_review(
                    decision=decision, approved=approved, position=broken
                )

        service = LectureReviewApplicationService(
            self.candidate_service,
            SQLiteLectureReviewRepository(self.connection),
            _Failing(self.connection),
        )
        with self.assertRaises(Exception):
            service.admit_review_decision(
                candidate_id=self.candidate.identity.value,
                decision_kind="accept",
                actor=_ACTOR,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_review_decisions"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(self._positions(), 0)
        self.assertFalse(self.connection.in_transaction)

    def test_appending_to_a_converged_decision_is_atomic_too(self):
        """The reversal path writes only the position, and a failure leaves the head intact."""

        self._judge()
        self._judge(decision_kind="reject")
        before = self._rows()

        class _Failing(SQLiteLectureReviewCommandPersistence):
            def persist_review(self, *, decision, approved, position=None):
                broken = None
                if position is not None:
                    broken = object.__new__(type(position))
                    for field in type(position).__slots__:
                        object.__setattr__(broken, field, getattr(position, field))
                    object.__setattr__(broken, "sequence", -1)
                super().persist_review(
                    decision=decision, approved=approved, position=broken
                )

        service = LectureReviewApplicationService(
            self.candidate_service,
            SQLiteLectureReviewRepository(self.connection),
            _Failing(self.connection),
        )
        with self.assertRaises(Exception):
            service.admit_review_decision(
                candidate_id=self.candidate.identity.value,
                decision_kind="accept",
                actor=_ACTOR,
            )
        self.assertEqual(self._rows(), before)
        self.assertFalse(self.connection.in_transaction)

    def test_a_competing_append_at_one_position_is_an_explicit_conflict(self):
        """AH-11 Option A: same identity, different judgment → refused, never overwritten."""

        first = self._judge()
        rejected = self._judge(decision_kind="reject")
        modified = self._modify()
        competing = plan_authority_position(
            candidate_id=self.candidate.identity,
            actor=HumanActorReference(_ACTOR),
            decision_id=modified.decision.identity,
            head=first.position,
        ).position
        self.assertEqual(competing.identity, rejected.position.identity)
        self.assertNotEqual(
            competing.review_decision_id, rejected.position.review_decision_id
        )
        persistence = SQLiteLectureReviewCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_review(
                decision=first.decision, approved=None, position=competing
            )
        stored = SQLiteLectureReviewRepository(self.connection).get_position(
            rejected.position.identity
        )
        self.assertEqual(stored.review_decision_id, rejected.decision.identity)
        self.assertEqual(self._positions(), 3)
        self.assertFalse(self.connection.in_transaction)

    def test_a_concurrent_identical_append_converges_on_the_stored_position(self):
        """R-11's convergence idiom: the same judgment at the same position is not a defect."""

        first = self._judge()
        winner = self._judge(decision_kind="reject")

        class _Stale(SQLiteLectureReviewRepository):
            """Reports the head another command has already superseded, once."""

            stale = True

            def head_position(self, candidate_id, actor):
                if self.stale:
                    type(self).stale = False
                    return first.position
                return super().head_position(candidate_id, actor)

        service = LectureReviewApplicationService(
            self.candidate_service,
            _Stale(self.connection),
            SQLiteLectureReviewCommandPersistence(self.connection),
        )
        result = service.admit_review_decision(
            candidate_id=self.candidate.identity.value,
            decision_kind="reject",
            actor=_ACTOR,
        )
        self.assertIs(result.position_outcome, AuthorityPositionOutcome.REUSED)
        self.assertEqual(result.position, winner.position)
        self.assertEqual(self._positions(), 2)

    def test_a_raced_position_holding_another_judgment_raises_the_conflict_error(self):
        first = self._judge()
        rejected = self._judge(decision_kind="reject")
        self._modify()

        class _Stale(SQLiteLectureReviewRepository):
            """Reports a stale head so the plan targets an already-taken position."""

            def head_position(self, candidate_id, actor):
                return first.position

        service = LectureReviewApplicationService(
            self.candidate_service,
            _Stale(self.connection),
            SQLiteLectureReviewCommandPersistence(self.connection),
        )
        with self.assertRaises(ReviewAuthorityConflictError):
            service.admit_review_decision(
                candidate_id=self.candidate.identity.value,
                decision_kind="modify",
                actor=_ACTOR,
                approved_range_start=0.0,
                approved_range_end=0.5,
                approved_label="trim_intro",
                approved_rationale=_APPROVED_RATIONALE,
            )
        stored = SQLiteLectureReviewRepository(self.connection).get_position(
            derive_authority_position_identity(
                self.candidate.identity, HumanActorReference(_ACTOR), 1
            )
        )
        self.assertEqual(stored.review_decision_id, rejected.decision.identity)
        self.assertEqual(self._positions(), 3)

    def test_a_competing_position_under_a_new_decision_writes_nothing_at_all(self):
        """The whole admission rolls back: no decision, no approval, no position."""

        first = self._judge()
        self._judge(decision_kind="reject")

        class _Stale(SQLiteLectureReviewRepository):
            def head_position(self, candidate_id, actor):
                return first.position

        service = LectureReviewApplicationService(
            self.candidate_service,
            _Stale(self.connection),
            SQLiteLectureReviewCommandPersistence(self.connection),
        )
        with self.assertRaises(PersistenceIdentityCollisionError):
            service.admit_review_decision(
                candidate_id=self.candidate.identity.value,
                decision_kind="modify",
                actor=_ACTOR,
                approved_range_start=0.0,
                approved_range_end=0.5,
                approved_label="trim_intro",
                approved_rationale=_APPROVED_RATIONALE,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_review_decisions"
            ).fetchone()[0],
            2,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_approved_edit_decisions"
            ).fetchone()[0],
            1,
        )
        self.assertEqual(self._positions(), 2)
        self.assertFalse(self.connection.in_transaction)

    def test_the_schema_enforces_one_position_per_scope_and_sequence(self):
        first = self._judge()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO lecture_review_authority_positions VALUES "
                "(?, ?, ?, ?, ?, ?, ?)",
                ("lecture-review-authority-position:" + "e" * 64,
                 self.candidate.identity.value, _ACTOR, 0,
                 first.decision.identity.value, None, 1),
            )

    def test_the_schema_refuses_a_first_position_that_supersedes_something(self):
        first = self._judge()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO lecture_review_authority_positions VALUES "
                "(?, ?, ?, ?, ?, ?, ?)",
                ("lecture-review-authority-position:" + "e" * 64,
                 self.candidate.identity.value, _OTHER_ACTOR, 0,
                 first.decision.identity.value, first.position.identity.value, 1),
            )

    def test_the_schema_refuses_a_later_position_without_a_previous_link(self):
        first = self._judge()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO lecture_review_authority_positions VALUES "
                "(?, ?, ?, ?, ?, ?, ?)",
                ("lecture-review-authority-position:" + "e" * 64,
                 self.candidate.identity.value, _ACTOR, 1,
                 first.decision.identity.value, None, 1),
            )

    def test_the_schema_refuses_an_empty_actor_a_negative_sequence_and_a_bad_version(
        self,
    ):
        first = self._judge()
        for actor, sequence, previous, version in (
            ("   ", 0, None, 1),
            (_OTHER_ACTOR, -1, None, 1),
            (_OTHER_ACTOR, 0, None, 2),
        ):
            with self.subTest(actor=actor, sequence=sequence, version=version):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        "INSERT INTO lecture_review_authority_positions VALUES "
                        "(?, ?, ?, ?, ?, ?, ?)",
                        ("lecture-review-authority-position:" + "e" * 64,
                         self.candidate.identity.value, actor, sequence,
                         first.decision.identity.value, previous, version),
                    )

    def test_the_schema_refuses_a_self_superseding_position(self):
        first = self._judge()
        identity = "lecture-review-authority-position:" + "e" * 64
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO lecture_review_authority_positions VALUES "
                "(?, ?, ?, ?, ?, ?, ?)",
                (identity, self.candidate.identity.value, _ACTOR, 1,
                 first.decision.identity.value, identity, 1),
            )

    def test_the_schema_refuses_an_unknown_candidate_or_decision_reference(self):
        first = self._judge()
        for candidate, decision in (
            ("lecture-analysis-edit-candidate:" + "f" * 64, first.decision.identity.value),
            (self.candidate.identity.value, "lecture-review-decision:" + "f" * 64),
        ):
            with self.subTest(candidate=candidate, decision=decision):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        "INSERT INTO lecture_review_authority_positions VALUES "
                        "(?, ?, ?, ?, ?, ?, ?)",
                        ("lecture-review-authority-position:" + "e" * 64,
                         candidate, _THIRD_ACTOR, 0, decision, None, 1),
                    )

    def test_the_relation_carries_no_per_decision_uniqueness(self):
        """AH-6 prohibits it: it would make reversal history unrepresentable."""

        definition = self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' "
            "AND name = 'lecture_review_authority_positions'"
        ).fetchone()[0]
        self.assertIn("UNIQUE (candidate_id, actor, sequence)", definition)
        for (sql,) in self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' "
            "AND tbl_name = 'lecture_review_authority_positions' AND sql IS NOT NULL"
        ).fetchall():
            with self.subTest(index=sql):
                self.assertNotIn("review_decision_id", sql or "")


class RepositoryTests(_Chain):
    def test_the_repository_exposes_no_mutation_method(self):
        repository = SQLiteLectureReviewRepository(self.connection)
        for forbidden in ("update", "delete", "remove", "save", "upsert", "replace",
                          "renumber", "supersede"):
            with self.subTest(method=forbidden):
                self.assertFalse(hasattr(repository, forbidden))

    def test_the_head_is_the_highest_sequence_and_not_the_latest_row(self):
        self._judge()
        second = self._judge(decision_kind="reject")
        repository = SQLiteLectureReviewRepository(self.connection)
        self.assertEqual(
            repository.head_position(self.candidate.identity, _ACTOR), second.position
        )
        self.assertIsNone(
            repository.head_position(self.candidate.identity, _OTHER_ACTOR)
        )

    def test_positions_are_listed_oldest_first(self):
        first = self._judge()
        second = self._judge(decision_kind="reject")
        repository = SQLiteLectureReviewRepository(self.connection)
        self.assertEqual(
            repository.list_positions(self.candidate.identity, _ACTOR),
            (first.position, second.position),
        )

    def test_actors_with_history_is_deterministic_and_not_a_ranking(self):
        self._judge(actor=_OTHER_ACTOR)
        self._judge()
        self._judge(actor=_THIRD_ACTOR)
        repository = SQLiteLectureReviewRepository(self.connection)
        actors = repository.actors_with_history(self.candidate.identity)
        self.assertEqual(actors, tuple(sorted(actors)))
        self.assertEqual(set(actors), {_ACTOR, _OTHER_ACTOR, _THIRD_ACTOR})

    def test_a_position_re_derives_from_its_stored_row(self):
        recorded = self._judge()
        candidate_id, actor, sequence = self.connection.execute(
            "SELECT candidate_id, actor, sequence FROM lecture_review_authority_positions"
        ).fetchone()
        self.assertEqual(
            derive_authority_position_identity(
                type(self.candidate.identity)(candidate_id),
                HumanActorReference(actor),
                sequence,
            ),
            recorded.position.identity,
        )

    def test_persistence_requires_the_released_schema_version(self):
        legacy = self.base / "legacy.sqlite3"
        connection = sqlite3.connect(legacy, isolation_level=None)
        connection.execute(
            "CREATE TABLE schema_metadata (singleton INTEGER PRIMARY KEY, version INTEGER)"
        )
        connection.execute("INSERT INTO schema_metadata VALUES (1, 51)")
        connection.close()
        opened = sqlite3.connect(legacy, isolation_level=None)
        try:
            with self.assertRaises(Exception):
                SQLiteLectureReviewRepository(opened)
        finally:
            opened.close()

    def test_restart_reconstructs_the_history_identically(self):
        self._judge()
        self._judge(decision_kind="reject")
        self._judge()
        self._judge(decision_kind="reject", actor=_OTHER_ACTOR)
        history = self.reviews.authority_history(self.candidate.identity.value, _ACTOR)
        current = self.reviews.current_review(self.candidate.identity.value, _ACTOR)
        observation = self.reviews.observe_candidate_authority(
            self.candidate.identity.value
        )
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            service = compose_sqlite_lecture_review_service(reopened)
            self.assertEqual(
                service.authority_history(self.candidate.identity.value, _ACTOR),
                history,
            )
            self.assertEqual(
                service.current_review(self.candidate.identity.value, _ACTOR), current
            )
            restarted = service.observe_candidate_authority(
                self.candidate.identity.value
            )
            self.assertIs(restarted.status, observation.status)
            self.assertIsNone(restarted.current)
        finally:
            reopened.close()

    def test_no_execution_legacy_or_domain_result_row_is_created(self):
        before = self.connection.execute(
            "SELECT COUNT(*) FROM domain_result_references"
        ).fetchone()[0]
        self._judge()
        self._judge(decision_kind="reject")
        self._judge()
        for table in ("edit_review_decisions", "approved_edit_decisions",
                      "processing_runs", "unit_executions"):
            with self.subTest(table=table):
                self.assertEqual(
                    self.connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0],
                    0,
                )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM domain_result_references"
            ).fetchone()[0],
            before,
        )

    def test_the_two_canonical_relations_gained_no_column(self):
        """AH-4: released identity composition and columns are untouched."""

        columns = {
            row[1] for row in self.connection.execute(
                "PRAGMA table_info(lecture_review_decisions)"
            ).fetchall()
        } | {
            row[1] for row in self.connection.execute(
                "PRAGMA table_info(lecture_approved_edit_decisions)"
            ).fetchall()
        }
        for forbidden in ("sequence", "ordinal", "previous_position_id",
                          "previous_decision_id", "status", "current", "stale",
                          "selected"):
            with self.subTest(column=forbidden):
                self.assertNotIn(forbidden, columns)


if __name__ == "__main__":
    unittest.main()
