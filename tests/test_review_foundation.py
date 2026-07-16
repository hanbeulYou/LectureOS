import unittest

from lectureos.execution.identities import (
    ArtifactId,
    DomainResultId,
    PluginReference,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.execution.service import ExecutionService
from lectureos.review.identities import (
    ApprovedDecisionId,
    CandidateReconciliationId,
    CandidateReferenceId,
    DecisionModificationId,
    HumanActorReference,
    ReviewConflictId,
    ReviewContextId,
    ReviewDecisionId,
    ReviewHistoryEntryId,
    ReviewItemId,
    StaleCandidateRecordId,
)
from lectureos.review.models import (
    ApprovedDecision,
    CandidateReconciliation,
    CandidateReference,
    DecisionKind,
    ReviewConflict,
    ReviewContext,
    ReviewItem,
    StaleCandidateRecord,
)
from lectureos.review.service import ReviewService
from lectureos.transcript.identities import CorrectionCandidateId, TranscriptValidationId
from lectureos.transcript.service import TranscriptService


class ReviewDomainFoundationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ReviewService()
        self.candidate = CandidateReference(
            identity=CandidateReferenceId("correction-candidate-1"),
            kind="transcript_correction_candidate",
            source_domain="transcript",
            domain_result_id=DomainResultId("candidate-result-1"),
            source_media_id=SourceMediaId("media-1"),
            source_timeline_id=SourceTimelineId("timeline-1"),
            run_id=ProcessingRunId("run-1"),
            unit_execution_id=UnitExecutionId("execution-1"),
        )
        self.context = ReviewContext(
            identity=ReviewContextId("context-1"),
            source_media_id=self.candidate.source_media_id,
            source_timeline_id=self.candidate.source_timeline_id,
            domain_result_references=(self.candidate.domain_result_id,),
            evidence_references=("candidate rationale",),
        )
        self.item = ReviewItem(
            identity=ReviewItemId("item-1"),
            candidate_id=self.candidate.identity,
            context_id=self.context.identity,
            run_id=self.candidate.run_id,
            unit_execution_id=self.candidate.unit_execution_id,
        )
        self.actor = HumanActorReference("reviewer-1")
        self.service.register_candidate_reference(self.candidate)
        self.service.create_review_context(self.context)
        self.service.create_review_item(self.item)

    def test_correction_candidate_reference_creates_review_item(self) -> None:
        self.assertEqual(self.item, self.service.get_review_item(self.item.identity))
        self.assertEqual("transcript_correction_candidate", self.candidate.kind)

    def test_review_item_and_candidate_identities_are_distinct(self) -> None:
        self.assertNotEqual(self.item.identity.value, self.candidate.identity.value)
        self.assertNotEqual(type(self.item.identity), type(self.candidate.identity))

    def test_review_item_creation_does_not_change_candidate(self) -> None:
        self.assertEqual(self.candidate, self.service.get_candidate_reference(self.candidate.identity))

    def test_accept_creates_human_decision(self) -> None:
        decision, _ = self._accept()
        self.assertEqual(DecisionKind.ACCEPT, decision.kind)
        self.assertEqual(self.actor, decision.actor)

    def test_accept_does_not_change_candidate(self) -> None:
        before = self.service.get_candidate_reference(self.candidate.identity)
        self._accept()
        self.assertEqual(before, self.service.get_candidate_reference(self.candidate.identity))

    def test_accept_creates_separate_approved_decision(self) -> None:
        decision, approved = self._accept()
        self.assertIsInstance(approved, ApprovedDecision)
        self.assertEqual(decision.identity, approved.source_decision_id)

    def test_decision_and_approved_identity_are_distinct(self) -> None:
        decision, approved = self._accept()
        self.assertNotEqual(decision.identity.value, approved.identity.value)
        self.assertNotEqual(type(decision.identity), type(approved.identity))

    def test_reject_creates_decision_without_approval(self) -> None:
        decision = self._reject()
        self.assertEqual(DecisionKind.REJECT, decision.kind)
        self.assertEqual((), self.service.approved_decisions.all())

    def test_reject_does_not_delete_candidate(self) -> None:
        self._reject()
        self.assertEqual(self.candidate, self.service.get_candidate_reference(self.candidate.identity))

    def test_modify_creates_separate_modification(self) -> None:
        decision, modification, _ = self._modify()
        self.assertEqual(decision.identity, modification.decision_id)
        self.assertEqual("replace greeting", modification.modified_intent)

    def test_modify_preserves_original_candidate(self) -> None:
        before = self.service.get_candidate_reference(self.candidate.identity)
        self._modify()
        self.assertEqual(before, self.service.get_candidate_reference(self.candidate.identity))

    def test_modify_creates_approved_decision(self) -> None:
        _, modification, approved = self._modify()
        self.assertEqual(modification.identity, approved.modification_id)

    def test_empty_human_actor_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "identity must not be empty"):
            HumanActorReference(" ")

    def test_unknown_review_item_cannot_receive_decision(self) -> None:
        with self.assertRaisesRegex(KeyError, "unknown review item"):
            self.service.record_reject(
                decision_id=ReviewDecisionId("unknown-item-decision"),
                history_id=ReviewHistoryEntryId("unknown-item-history"),
                review_item_id=ReviewItemId("missing"),
                actor=self.actor,
            )

    def test_duplicate_decision_identity_is_rejected(self) -> None:
        self._reject()
        with self.assertRaisesRegex(ValueError, "review decision identity already exists"):
            self.service.record_reject(
                decision_id=ReviewDecisionId("decision-reject"),
                history_id=ReviewHistoryEntryId("history-new"),
                review_item_id=self.item.identity,
                actor=self.actor,
            )

    def test_duplicate_approved_identity_is_rejected(self) -> None:
        self._accept()
        with self.assertRaisesRegex(ValueError, "approved decision identity already exists"):
            self.service.record_accept(
                decision_id=ReviewDecisionId("decision-new"),
                history_id=ReviewHistoryEntryId("history-new"),
                approved_id=ApprovedDecisionId("approved-accept"),
                review_item_id=self.item.identity,
                actor=self.actor,
            )
        self.assertIsNone(self.service.get_decision(ReviewDecisionId("decision-new")))

    def test_duplicate_history_is_rejected_before_decision_persistence(self) -> None:
        self._reject()
        with self.assertRaisesRegex(ValueError, "review history entry identity already exists"):
            self.service.record_accept(
                decision_id=ReviewDecisionId("decision-not-saved"),
                history_id=ReviewHistoryEntryId("history-reject"),
                approved_id=ApprovedDecisionId("approved-not-saved"),
                review_item_id=self.item.identity,
                actor=self.actor,
            )
        self.assertIsNone(self.service.get_decision(ReviewDecisionId("decision-not-saved")))
        self.assertIsNone(self.service.get_approved_decision(ApprovedDecisionId("approved-not-saved")))

    def test_stale_record_preserves_decision(self) -> None:
        decision, _ = self._accept()
        before = self.service.get_decision(decision.identity)
        stale = self._mark_stale((decision.identity,))
        self.assertEqual(before, self.service.get_decision(decision.identity))
        self.assertEqual(stale, self.service.get_stale_record(stale.identity))

    def test_stale_candidate_is_not_automatically_rejected(self) -> None:
        self._mark_stale()
        self.assertEqual((), self.service.decisions.all())

    def test_stale_accept_is_not_applied_to_new_candidate(self) -> None:
        decision, _ = self._accept()
        self._mark_stale((decision.identity,))
        new_candidate = self._register_new_candidate()
        self.assertEqual((), tuple(
            approved for approved in self.service.approved_decisions.all()
            if approved.source_candidate_id == new_candidate.identity
        ))

    def test_conflict_does_not_change_decision(self) -> None:
        decision, _ = self._accept()
        before = self.service.get_decision(decision.identity)
        conflict = ReviewConflict(
            identity=ReviewConflictId("conflict-1"),
            description="candidate context changed",
            review_item_id=self.item.identity,
            decision_ids=(decision.identity,),
        )
        self.service.record_conflict(conflict)
        self.assertEqual(before, self.service.get_decision(decision.identity))

    def test_reconciliation_preserves_candidates_and_decision(self) -> None:
        decision, _ = self._accept()
        new_candidate = self._register_new_candidate()
        old_before = self.service.get_candidate_reference(self.candidate.identity)
        decision_before = self.service.get_decision(decision.identity)
        self._reconcile(new_candidate, (decision.identity,))
        self.assertEqual(old_before, self.service.get_candidate_reference(self.candidate.identity))
        self.assertEqual(decision_before, self.service.get_decision(decision.identity))

    def test_reconciliation_does_not_approve_new_candidate(self) -> None:
        new_candidate = self._register_new_candidate()
        self._reconcile(new_candidate)
        self.assertEqual((), self.service.approved_decisions.all())

    def test_review_service_does_not_create_transcript_revision(self) -> None:
        self.assertFalse(hasattr(self.service, "create_corrected_revision"))

    def test_review_service_does_not_create_artifact(self) -> None:
        self.assertFalse(hasattr(self.service, "create_artifact"))
        _, approved = self._accept()
        self.assertNotIsInstance(approved.identity, ArtifactId)

    def test_processing_service_has_no_human_decision_commands(self) -> None:
        processing = ExecutionService()
        for command in ("accept", "reject", "modify"):
            self.assertFalse(hasattr(processing, command))

    def test_transcript_service_has_no_human_decision_commands(self) -> None:
        for command in ("accept", "reject", "modify"):
            self.assertFalse(hasattr(TranscriptService, command))

    def test_review_decision_is_not_domain_result(self) -> None:
        decision, _ = self._accept()
        self.assertNotIsInstance(decision, DomainResultReference)
        self.assertFalse(hasattr(decision, "domain_result_id"))

    def test_approved_decision_is_not_artifact(self) -> None:
        _, approved = self._accept()
        self.assertFalse(hasattr(approved, "artifact_id"))
        self.assertNotIsInstance(approved.identity, ArtifactId)

    def test_validation_identity_cannot_be_used_as_decision_identity(self) -> None:
        validation_id = TranscriptValidationId("validation-1")
        with self.assertRaises(TypeError):
            self.service.record_reject(
                decision_id=validation_id,  # type: ignore[arg-type]
                history_id=ReviewHistoryEntryId("history-validation"),
                review_item_id=self.item.identity,
                actor=self.actor,
            )

    def test_plugin_reference_cannot_act_as_human(self) -> None:
        with self.assertRaisesRegex(TypeError, "cannot exercise Human Authority"):
            self.service.record_reject(
                decision_id=ReviewDecisionId("plugin-decision"),
                history_id=ReviewHistoryEntryId("plugin-history"),
                review_item_id=self.item.identity,
                actor=PluginReference("plugin-1"),  # type: ignore[arg-type]
            )

    def test_history_appends_without_rewriting_previous_entry(self) -> None:
        first = self._reject()
        before = self.service.get_review_history(self.item.identity)
        second, _ = self.service.record_accept(
            decision_id=ReviewDecisionId("decision-second"),
            history_id=ReviewHistoryEntryId("history-second"),
            approved_id=ApprovedDecisionId("approved-second"),
            review_item_id=self.item.identity,
            actor=self.actor,
        )
        history = self.service.get_review_history(self.item.identity)
        self.assertEqual(before[0], history[0])
        self.assertEqual((first.identity, second.identity), tuple(entry.decision_id for entry in history))
        self.assertEqual(history[0].identity, history[1].previous_entry_id)

    def test_candidate_reference_preserves_correction_candidate_identity(self) -> None:
        upstream_id = CorrectionCandidateId(self.candidate.identity.value)
        self.assertEqual(upstream_id.value, self.candidate.identity.value)
        self.assertNotEqual(type(upstream_id), type(self.candidate.identity))

    def test_candidate_requires_complete_execution_provenance(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires run and unit execution"):
            CandidateReference(
                identity=CandidateReferenceId("incomplete"),
                kind="edit_candidate",
                source_domain="lecture_intelligence",
                run_id=ProcessingRunId("run-only"),
            )

    def test_new_review_item_cannot_claim_existing_decisions(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot contain review history"):
            self.service.create_review_item(
                ReviewItem(
                    identity=ReviewItemId("item-prepopulated"),
                    candidate_id=self.candidate.identity,
                    context_id=self.context.identity,
                    decision_references=(ReviewDecisionId("unrecorded"),),
                )
            )

    def _accept(self):
        return self.service.record_accept(
            decision_id=ReviewDecisionId("decision-accept"),
            history_id=ReviewHistoryEntryId("history-accept"),
            approved_id=ApprovedDecisionId("approved-accept"),
            review_item_id=self.item.identity,
            actor=self.actor,
        )

    def _reject(self):
        return self.service.record_reject(
            decision_id=ReviewDecisionId("decision-reject"),
            history_id=ReviewHistoryEntryId("history-reject"),
            review_item_id=self.item.identity,
            actor=self.actor,
        )

    def _modify(self):
        return self.service.record_modify(
            decision_id=ReviewDecisionId("decision-modify"),
            modification_id=DecisionModificationId("modification-1"),
            history_id=ReviewHistoryEntryId("history-modify"),
            approved_id=ApprovedDecisionId("approved-modify"),
            review_item_id=self.item.identity,
            actor=self.actor,
            modified_intent="replace greeting",
        )

    def _mark_stale(self, decisions=()):
        record = StaleCandidateRecord(
            identity=StaleCandidateRecordId("stale-1"),
            candidate_id=self.candidate.identity,
            reason="upstream transcript changed",
            related_decision_ids=decisions,
            changed_upstream_references=(DomainResultId("new-transcript"),),
        )
        self.service.mark_candidate_stale(record)
        return record

    def _register_new_candidate(self):
        candidate = CandidateReference(
            identity=CandidateReferenceId("correction-candidate-2"),
            kind=self.candidate.kind,
            source_domain=self.candidate.source_domain,
            domain_result_id=DomainResultId("candidate-result-2"),
            run_id=ProcessingRunId("run-2"),
            unit_execution_id=UnitExecutionId("execution-2"),
        )
        self.service.register_candidate_reference(candidate)
        return candidate

    def _reconcile(self, new_candidate, decisions=()):
        reconciliation = CandidateReconciliation(
            identity=CandidateReconciliationId("reconciliation-1"),
            previous_candidate_id=self.candidate.identity,
            new_candidate_id=new_candidate.identity,
            relationship="reprocessed alternative",
            decision_ids=decisions,
        )
        self.service.record_reconciliation(reconciliation)
        return reconciliation


if __name__ == "__main__":
    unittest.main()
