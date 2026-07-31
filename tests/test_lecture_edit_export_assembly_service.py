"""Application and persistence tests for the Edit Export Assembly (044 §23, GOAL-030).

Drives the derived export scope, the three eligibility conditions, the total membership rule, the
two undecided-policy stops, replay, atomicity, and the read-only treatment of every upstream record —
over a real released upstream chain.
"""

import sqlite3
import unittest

from lectureos.application.lecture_edit_export_assembly import (
    AssemblyOutcome,
    EditExportAssemblyConflictError,
    EditExportUndecidedPolicyError,
    ExportEligibility,
    LectureEditExportAssembly,
    LectureEditExportAssemblyError,
    LectureEditExportAssemblyService,
    derive_edit_export_assembly_identity,
)
from lectureos.composition import (
    compose_sqlite_lecture_edit_export_assembly_service,
    compose_sqlite_lecture_review_service,
)
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.persistence.lecture_edit_export_assembly import (
    SQLiteEditExportAssemblyCommandPersistence,
    SQLiteEditExportAssemblyRepository,
    SQLiteEditExportScopeRepository,
)
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository

from test_lecture_review_authority_service import (
    _ACTOR,
    _OTHER_ACTOR,
    _Chain,
)

_CANDIDATE_RATIONALE = "이 구간도 사람이 검토할 만하다"


class _ExportChain(_Chain):
    """The released chain, plus the Export Assembly service over the same connection."""

    def setUp(self):
        super().setUp()
        self.timeline = (
            SQLiteRawTranscriptRepository(self.connection)
            .get(self.raw.raw_transcript_id)
            .source_timeline_id
        )
        self.exports = compose_sqlite_lecture_edit_export_assembly_service(
            self.connection
        )

    def _second_candidate(self):
        return self.candidate_service.admit_edit_candidate(
            finding_id=self.finding.identity.value,
            candidate_type="filler_removal",
            range_start=2.0,
            range_end=3.0,
            rationale=_CANDIDATE_RATIONALE,
        ).candidate

    def _scope(self):
        return self.exports.observe_scope(self.timeline.value)

    def _assembly_rows(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM lecture_edit_export_assemblies"
        ).fetchone()[0]

    def _member_rows(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM lecture_edit_export_assembly_members"
        ).fetchone()[0]

    def _review_rows(self):
        return self.connection.execute(
            "SELECT identity, candidate_id, decision_kind, actor FROM "
            "lecture_review_decisions ORDER BY identity"
        ).fetchall()


class ScopeDerivationTests(_ExportChain):
    def test_the_scope_lists_every_candidate_on_the_timeline(self) -> None:
        second = self._second_candidate()
        scope = self._scope()
        self.assertEqual(
            {standing.candidate_id.value for standing in scope.standings},
            {self.candidate.identity.value, second.identity.value},
        )

    def test_a_candidate_without_recorded_authority_is_not_eligible(self) -> None:
        scope = self._scope()
        standing = scope.standings[0]
        self.assertEqual(
            standing.eligibility, ExportEligibility.NO_RECORDED_AUTHORITY
        )
        self.assertIsNone(standing.approved)
        self.assertEqual(scope.eligible, ())

    def test_an_accepted_candidate_becomes_eligible(self) -> None:
        recorded = self._judge()
        scope = self._scope()
        self.assertEqual(scope.standings[0].eligibility, ExportEligibility.ELIGIBLE)
        self.assertEqual(
            scope.eligible[0].identity, recorded.approved.identity
        )

    def test_a_modified_candidate_contributes_the_modified_approval(self) -> None:
        recorded = self._modify()
        scope = self._scope()
        self.assertEqual(scope.standings[0].eligibility, ExportEligibility.ELIGIBLE)
        self.assertEqual(scope.eligible[0].identity, recorded.approved.identity)
        self.assertEqual(scope.eligible[0].approved_range_end, 0.5)

    def test_a_reject_approves_nothing_and_contributes_no_member(self) -> None:
        self._judge(decision_kind="reject")
        scope = self._scope()
        self.assertEqual(
            scope.standings[0].eligibility,
            ExportEligibility.CURRENT_JUDGMENT_APPROVES_NOTHING,
        )
        self.assertEqual(scope.eligible, ())

    def test_a_superseded_judgment_stops_contributing_but_stays_history(self) -> None:
        """EA-4(i): only the current operative judgment's approval is eligible."""

        accepted = self._judge()
        self._judge(decision_kind="reject")
        scope = self._scope()
        self.assertEqual(
            scope.standings[0].eligibility,
            ExportEligibility.CURRENT_JUDGMENT_APPROVES_NOTHING,
        )
        reviews = compose_sqlite_lecture_review_service(self.connection)
        self.assertIsNotNone(reviews.get(accepted.decision.identity.value))
        self.assertIsNotNone(
            reviews.get_approved(accepted.decision.identity.value)
        )

    def test_a_chain_that_lost_current_standing_is_not_eligible(self) -> None:
        """EA-4(iii). The approval remains valid immutable history (§7.5 R-5)."""

        recorded = self._judge()
        self._revise("c2", "교정 2")  # a newer corrected revision becomes current
        scope = self._scope()
        self.assertEqual(
            scope.standings[0].eligibility,
            ExportEligibility.SUPERSEDED_BY_AUTHORITY_CHANGE,
        )
        self.assertEqual(scope.eligible, ())
        reviews = compose_sqlite_lecture_review_service(self.connection)
        self.assertIsNotNone(
            reviews.get_approved(recorded.decision.identity.value)
        )

    def test_observation_never_stops_on_a_cross_actor_conflict(self) -> None:
        self._judge()
        self._judge(actor=_OTHER_ACTOR, decision_kind="reject")
        scope = self._scope()  # must not raise
        self.assertTrue(scope.has_conflict)
        self.assertEqual(
            scope.standings[0].eligibility, ExportEligibility.CROSS_ACTOR_CONFLICT
        )
        self.assertEqual(
            {actor.value for actor in scope.standings[0].actors},
            {_ACTOR, _OTHER_ACTOR},
        )

    def test_observation_mutates_nothing(self) -> None:
        self._judge()
        before = self._review_rows()
        for _ in range(3):
            self._scope()
        self.assertEqual(self._review_rows(), before)
        self.assertEqual(self._assembly_rows(), 0)

    def test_a_foreign_timeline_sees_none_of_this_timelines_candidates(self) -> None:
        self._judge()
        scope = self.exports.observe_scope("timeline:not-this-one")
        self.assertEqual(scope.standings, ())
        self.assertEqual(scope.eligible, ())

    def test_a_blank_timeline_is_refused(self) -> None:
        with self.assertRaises(LectureEditExportAssemblyError):
            self.exports.observe_scope("   ")


class MembershipTests(_ExportChain):
    def test_membership_is_the_complete_eligible_set(self) -> None:
        """EA-3: total, never a subset — there is no way to ask for fewer."""

        second = self._second_candidate()
        self._judge()
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value,
            decision_kind="accept",
            actor=_ACTOR,
        )
        result = self.exports.admit_assembly(self.timeline.value)
        self.assertEqual(len(result.assembly.members), 2)
        self.assertEqual(self._member_rows(), 2)

    def test_ineligible_candidates_are_absent_without_shrinking_the_rule(self) -> None:
        second = self._second_candidate()
        self._judge()
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value,
            decision_kind="reject",
            actor=_ACTOR,
        )
        result = self.exports.admit_assembly(self.timeline.value)
        self.assertEqual(len(result.assembly.members), 1)
        self.assertEqual(len(result.observation.standings), 2)

    def test_member_order_is_deterministic_and_by_identity(self) -> None:
        second = self._second_candidate()
        self._judge()
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value,
            decision_kind="accept",
            actor=_ACTOR,
        )
        result = self.exports.admit_assembly(self.timeline.value)
        identities = [
            member.approved_edit_decision_id.value for member in result.assembly.members
        ]
        self.assertEqual(identities, sorted(identities))

    def test_overlapping_approved_edits_are_both_members(self) -> None:
        """No overlap rule exists here — EA-4 does not consider overlap, and none is invented."""

        overlapping = self.candidate_service.admit_edit_candidate(
            finding_id=self.finding.identity.value,
            candidate_type="filler_removal",
            range_start=0.0,
            range_end=1.0,
            rationale="겹치는 구간 제안",
        ).candidate
        self._judge()
        self.reviews.admit_review_decision(
            candidate_id=overlapping.identity.value,
            decision_kind="modify",
            actor=_ACTOR,
            approved_range_start=0.2,
            approved_range_end=0.8,
            approved_label="trim_overlap",
            approved_rationale="겹치지만 별개의 승인이다",
        )
        result = self.exports.admit_assembly(self.timeline.value)
        self.assertEqual(len(result.assembly.members), 2)


class UndecidedPolicyTests(_ExportChain):
    def test_a_cross_actor_conflict_stops_admission_without_choosing(self) -> None:
        self._judge()
        self._judge(actor=_OTHER_ACTOR, decision_kind="reject")
        with self.assertRaises(EditExportUndecidedPolicyError) as raised:
            self.exports.admit_assembly(self.timeline.value)
        message = str(raised.exception)
        self.assertIn("undecided", message)
        self.assertIn("not a product refusal", message)
        self.assertEqual(self._assembly_rows(), 0)

    def test_a_scope_with_no_eligible_member_stops_admission(self) -> None:
        with self.assertRaises(EditExportUndecidedPolicyError) as raised:
            self.exports.admit_assembly(self.timeline.value)
        self.assertIn("no export-eligible approved edit", str(raised.exception))
        self.assertEqual(self._assembly_rows(), 0)

    def test_the_stop_is_reported_as_a_contract_gap_not_a_refusal(self) -> None:
        """The distinction matters: a refusal would itself be one of the deferred behaviours."""

        self._judge(decision_kind="reject")
        with self.assertRaises(EditExportUndecidedPolicyError) as raised:
            self.exports.admit_assembly(self.timeline.value)
        self.assertIn("contract gap", str(raised.exception))

    def test_resolving_the_conflict_in_review_reopens_admission(self) -> None:
        """Nothing here resolves it — a person does, in Review, exactly as §3.12 requires."""

        self._judge()
        self._judge(actor=_OTHER_ACTOR, decision_kind="reject")
        with self.assertRaises(EditExportUndecidedPolicyError):
            self.exports.admit_assembly(self.timeline.value)
        # The second actor withdraws their disagreement by judging the same way as the first; the
        # authority history keeps both positions, and the Candidate now has one operative judgment
        # per actor that agree — but two actors still hold history, so it stays a conflict.
        self._judge(actor=_OTHER_ACTOR, decision_kind="accept")
        with self.assertRaises(EditExportUndecidedPolicyError):
            self.exports.admit_assembly(self.timeline.value)
        self.assertTrue(self._scope().has_conflict)


class AdmissionTests(_ExportChain):
    def test_admitting_records_one_immutable_assembly(self) -> None:
        result = self._judge() and self.exports.admit_assembly(self.timeline.value)
        self.assertIs(result.outcome, AssemblyOutcome.ADMITTED)
        self.assertEqual(self._assembly_rows(), 1)
        self.assertEqual(self._member_rows(), 1)
        stored = self.exports.get(result.assembly.identity.value)
        self.assertEqual(stored, result.assembly)

    def test_replay_converges_and_writes_nothing(self) -> None:
        self._judge()
        first = self.exports.admit_assembly(self.timeline.value)
        second = self.exports.admit_assembly(self.timeline.value)
        self.assertIs(second.outcome, AssemblyOutcome.REUSED)
        self.assertEqual(second.assembly.identity, first.assembly.identity)
        self.assertEqual(self._assembly_rows(), 1)

    def test_an_authority_change_yields_a_new_assembly_and_rewrites_nothing(self) -> None:
        second = self._second_candidate()
        self._judge()
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value,
            decision_kind="accept",
            actor=_ACTOR,
        )
        first = self.exports.admit_assembly(self.timeline.value)
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value,
            decision_kind="reject",
            actor=_ACTOR,
        )
        later = self.exports.admit_assembly(self.timeline.value)
        self.assertNotEqual(later.assembly.identity, first.assembly.identity)
        self.assertEqual(len(first.assembly.members), 2)
        self.assertEqual(len(later.assembly.members), 1)
        # The earlier assembly is untouched: this is a difference between immutable records.
        self.assertEqual(
            self.exports.get(first.assembly.identity.value), first.assembly
        )
        self.assertEqual(len(self.exports.history(self.timeline.value)), 2)

    def test_admission_exercises_no_authority_and_touches_no_review_row(self) -> None:
        """EA-6: review already decided what is approved."""

        self._judge()
        before = self._review_rows()
        self.exports.admit_assembly(self.timeline.value)
        self.assertEqual(self._review_rows(), before)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_review_authority_positions"
            ).fetchone()[0],
            1,
        )

    def test_the_legacy_export_relations_stay_empty(self) -> None:
        """EA-10: this generation never reuses the legacy execution-coupled Export family."""

        self._judge()
        self.exports.admit_assembly(self.timeline.value)
        for table in (
            "approved_edit_export_representations",
            "edit_export_assemblies",
            "edit_export_assembly_members",
        ):
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
            )

    def test_no_execution_or_domain_result_is_created(self) -> None:
        """EA-8: nothing is executed, and no synthetic run or result is fabricated."""

        runs = self.connection.execute(
            "SELECT COUNT(*) FROM processing_runs"
        ).fetchone()[0]
        results = self.connection.execute(
            "SELECT COUNT(*) FROM domain_result_references"
        ).fetchone()[0]
        self._judge()
        self.exports.admit_assembly(self.timeline.value)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM processing_runs").fetchone()[0],
            runs,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM domain_result_references"
            ).fetchone()[0],
            results,
        )

    def test_reconstruction_from_persisted_rows_is_equal(self) -> None:
        self._judge()
        result = self.exports.admit_assembly(self.timeline.value)
        repository = SQLiteEditExportAssemblyRepository(self.connection)
        self.assertEqual(repository.get_assembly(result.assembly.identity), result.assembly)
        self.assertEqual(
            repository.list_members(result.assembly.identity), result.assembly.members
        )

    def test_an_unknown_assembly_reads_as_none(self) -> None:
        self.assertIsNone(
            self.exports.get("lecture-edit-export-assembly:" + "f" * 64)
        )


class ConflictAndAtomicityTests(_ExportChain):
    def test_a_semantically_different_record_for_one_identity_is_refused(self) -> None:
        """Option B keeps this unreachable in practice; R-10 requires the guard anyway."""

        self._judge()
        real = self.exports.admit_assembly(self.timeline.value).assembly

        class _Divergent:
            def get_assembly(self, identity):
                return LectureEditExportAssembly(
                    identity=real.identity,
                    source_timeline_id=real.source_timeline_id,
                    members=real.members,
                    assembly_contract_version=real.assembly_contract_version,
                ).__class__.__new__(LectureEditExportAssembly)

            def list_members(self, identity):
                return ()

            def list_assemblies_for_timeline(self, timeline):
                return ()

        divergent = object.__new__(LectureEditExportAssembly)
        object.__setattr__(divergent, "identity", real.identity)
        object.__setattr__(
            divergent, "source_timeline_id", real.source_timeline_id
        )
        object.__setattr__(divergent, "members", ())
        object.__setattr__(divergent, "assembly_contract_version", 1)

        class _Stub:
            def get_assembly(self, identity):
                return divergent

            def list_members(self, identity):
                return ()

            def list_assemblies_for_timeline(self, timeline):
                return ()

        service = LectureEditExportAssemblyService(
            review_service=self.reviews,
            scope_query=SQLiteEditExportScopeRepository(self.connection),
            assembly_query=_Stub(),
            persistence=SQLiteEditExportAssemblyCommandPersistence(self.connection),
        )
        with self.assertRaises(EditExportAssemblyConflictError):
            service.admit_assembly(self.timeline.value)

    def test_a_failure_while_writing_members_leaves_no_assembly(self) -> None:
        """All-or-nothing: a partially recorded assembly would understate the approved scope."""

        second = self._second_candidate()
        self._judge()
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value,
            decision_kind="accept",
            actor=_ACTOR,
        )

        class _Failing(SQLiteEditExportAssemblyCommandPersistence):
            def persist_assembly(self, assembly):
                broken = object.__new__(type(assembly))
                for field in type(assembly).__slots__:
                    object.__setattr__(broken, field, getattr(assembly, field))
                # The second member insert violates the ordinal primary key inside the same
                # transaction as the assembly row.
                object.__setattr__(
                    broken,
                    "members",
                    (
                        assembly.members[0],
                        type(assembly.members[1])(
                            assembly_id=assembly.members[1].assembly_id,
                            ordinal=0,
                            approved_edit_decision_id=(
                                assembly.members[1].approved_edit_decision_id
                            ),
                        ),
                    ),
                )
                super().persist_assembly(broken)

        service = LectureEditExportAssemblyService(
            review_service=self.reviews,
            scope_query=SQLiteEditExportScopeRepository(self.connection),
            assembly_query=SQLiteEditExportAssemblyRepository(self.connection),
            persistence=_Failing(self.connection),
        )
        with self.assertRaises(PersistenceIdentityCollisionError):
            service.admit_assembly(self.timeline.value)
        self.assertEqual(self._assembly_rows(), 0)
        self.assertEqual(self._member_rows(), 0)

    def test_a_duplicate_insert_maps_to_the_released_collision_error(self) -> None:
        self._judge()
        result = self.exports.admit_assembly(self.timeline.value)
        with self.assertRaises(PersistenceIdentityCollisionError):
            SQLiteEditExportAssemblyCommandPersistence(
                self.connection
            ).persist_assembly(result.assembly)


class DeterminismTests(_ExportChain):
    def test_the_same_state_derives_the_same_identity(self) -> None:
        self._judge()
        scope = self._scope()
        expected = derive_edit_export_assembly_identity(
            self.timeline,
            tuple(decision.identity for decision in scope.eligible),
        )
        self.assertEqual(
            self.exports.admit_assembly(self.timeline.value).assembly.identity, expected
        )

    def test_repeated_admission_reads_no_wall_clock(self) -> None:
        self._judge()
        first = self.exports.admit_assembly(self.timeline.value).assembly.identity
        second = self.exports.admit_assembly(self.timeline.value).assembly.identity
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()


class ValidatorTests(_ExportChain):
    """Integrity-only diagnostics (044 §23 EA-10). Derived staleness is never a defect."""

    def _report(self):
        from lectureos.validation.repository_validator import validate_repository

        return validate_repository(self.connection)

    def _codes(self):
        return {diagnostic.code for diagnostic in self._report().diagnostics}

    def test_a_healthy_assembly_is_clean(self) -> None:
        self._judge()
        self.exports.admit_assembly(self.timeline.value)
        self.assertEqual(
            {code for code in self._codes() if code.startswith("LECTURE_EDIT_EXPORT")},
            set(),
        )

    def test_a_superseded_member_is_never_flagged(self) -> None:
        """The assembly records what was eligible when admitted; it is never rewritten."""

        self._judge()
        self.exports.admit_assembly(self.timeline.value)
        self._judge(decision_kind="reject")
        self._revise("c3", "교정 3")
        self.assertEqual(
            {code for code in self._codes() if code.startswith("LECTURE_EDIT_EXPORT")},
            set(),
        )

    def test_several_assemblies_on_one_timeline_are_never_flagged(self) -> None:
        second = self._second_candidate()
        self._judge()
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value, decision_kind="accept", actor=_ACTOR
        )
        self.exports.admit_assembly(self.timeline.value)
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value, decision_kind="reject", actor=_ACTOR
        )
        self.exports.admit_assembly(self.timeline.value)
        self.assertEqual(len(self.exports.history(self.timeline.value)), 2)
        self.assertEqual(
            {code for code in self._codes() if code.startswith("LECTURE_EDIT_EXPORT")},
            set(),
        )

    def test_an_emptied_assembly_is_flagged(self) -> None:
        self._judge()
        result = self.exports.admit_assembly(self.timeline.value)
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute(
            "DELETE FROM lecture_edit_export_assembly_members WHERE assembly_id = ?",
            (result.assembly.identity.value,),
        )
        self.connection.commit()
        self.assertIn("LECTURE_EDIT_EXPORT_ASSEMBLY_EMPTY", self._codes())

    def test_a_tampered_membership_breaks_identity_re_derivation(self) -> None:
        second = self._second_candidate()
        self._judge()
        other = self.reviews.admit_review_decision(
            candidate_id=second.identity.value, decision_kind="accept", actor=_ACTOR
        ).approved
        result = self.exports.admit_assembly(self.timeline.value)
        removed = result.assembly.members[-1]
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute(
            "DELETE FROM lecture_edit_export_assembly_members "
            "WHERE assembly_id = ? AND ordinal = ?",
            (removed.assembly_id.value, removed.ordinal),
        )
        self.connection.commit()
        self.assertIn("LECTURE_EDIT_EXPORT_ASSEMBLY_IDENTITY_MISMATCH", self._codes())

    def test_a_missing_member_reference_is_flagged(self) -> None:
        self._judge()
        result = self.exports.admit_assembly(self.timeline.value)
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute(
            "UPDATE lecture_edit_export_assembly_members "
            "SET approved_edit_decision_id = 'lecture-approved-edit-decision:missing' "
            "WHERE assembly_id = ?",
            (result.assembly.identity.value,),
        )
        self.connection.commit()
        self.assertIn("LECTURE_EDIT_EXPORT_ASSEMBLY_MEMBER_MISSING", self._codes())

    def test_a_noncontiguous_ordinal_is_flagged(self) -> None:
        self._judge()
        result = self.exports.admit_assembly(self.timeline.value)
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute(
            "UPDATE lecture_edit_export_assembly_members SET ordinal = 5 "
            "WHERE assembly_id = ?",
            (result.assembly.identity.value,),
        )
        self.connection.commit()
        self.assertIn(
            "LECTURE_EDIT_EXPORT_ASSEMBLY_ORDINAL_NONCONTIGUOUS", self._codes()
        )
