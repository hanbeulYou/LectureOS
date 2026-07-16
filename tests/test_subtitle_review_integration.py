import unittest
from dataclasses import replace

from lectureos.application.subtitle_review import (
    SUBTITLE_CANDIDATE_KIND,
    SubtitleReviewIntegrationError,
    SubtitleReviewIntegrationService,
)
from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    ProcessingUnitId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import (
    DomainResultReference,
    ExecutionIntent,
    ProcessingUnit,
)
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
    CandidateReconciliation,
    CandidateReference,
    DecisionKind,
    ReviewConflict,
    StaleCandidateRecord,
)
from lectureos.review.service import ReviewService
from lectureos.subtitle.identities import (
    SubtitleCandidateId,
    SubtitleCueId,
    SubtitleId,
    SubtitleRevisionId,
    SubtitleValidationId,
)
from lectureos.subtitle.models import (
    SubtitleCandidate,
    SubtitleCue,
    SubtitleRevision,
)
from lectureos.subtitle.service import SubtitleService
from lectureos.subtitle.validation import SubtitleValidationService
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import (
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)
from lectureos.transcript.service import TranscriptService


class SubtitleCandidateReviewIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.execution = ExecutionService()
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("subtitle.review"),
            purpose="subtitle review integration",
            capabilities=(CapabilityReference("subtitle.generation"),),
            result_kinds=("subtitle_candidate",),
        )
        self.execution.register_unit(self.unit)
        self.run_id = ProcessingRunId("subtitle-review-run")
        self.execution_id = UnitExecutionId("subtitle-review-execution")
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("subtitle review tests"),
            working_context=WorkingContextReference("subtitle-review-context"),
            unit_ids=(self.unit.identity,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit.identity,
        )
        self.media = SourceMediaId("subtitle-review-media")
        self.timeline = SourceTimelineId("subtitle-review-timeline")
        self.transcript = TranscriptService(self.execution)
        self.raw, self.segment = self._create_raw()
        self.subtitle = SubtitleService(self.transcript, self.execution)
        self.validation = SubtitleValidationService(
            self.subtitle, self.transcript, self.execution
        )
        self.review = ReviewService()
        self.integration = SubtitleReviewIntegrationService(
            self.subtitle, self.review, self.review, self.execution
        )
        self.candidate, self.cue = self._create_candidate("one")
        self.item = self._create_review_item(self.candidate)
        self.actor = HumanActorReference("subtitle-reviewer")

    def test_subtitle_candidate_creates_review_item(self):
        self.assertEqual(self.item, self.review.get_review_item(self.item.identity))

    def test_candidate_and_review_item_identities_are_distinct(self):
        self.assertNotEqual(type(self.candidate.identity), type(self.item.identity))
        self.assertNotEqual(self.candidate.identity.value, self.item.identity.value)

    def test_candidate_reference_kind_is_stable(self):
        reference = self._reference(self.candidate)
        self.assertEqual(SUBTITLE_CANDIDATE_KIND, reference.kind)
        self.assertEqual("subtitle", reference.source_domain)

    def test_candidate_reference_preserves_source_and_execution_provenance(self):
        reference = self._reference(self.candidate)
        self.assertEqual(self.media, reference.source_media_id)
        self.assertEqual(self.timeline, reference.source_timeline_id)
        self.assertEqual(self.run_id, reference.run_id)
        self.assertEqual(self.execution_id, reference.unit_execution_id)

    def test_candidate_reference_preserves_transcript_reference(self):
        reference = self._reference(self.candidate)
        self.assertEqual(
            f"transcript:{self.raw.identity.value}",
            reference.revision_reference,
        )

    def test_review_creation_preserves_candidate_cue_and_transcript(self):
        candidate_before = self.subtitle.get_candidate(self.candidate.identity)
        cue_before = self.subtitle.get_cue(self.cue.identity)
        transcript_before = self.transcript.get_raw_transcript(self.raw.identity)
        self.assertEqual(candidate_before, self.subtitle.get_candidate(self.candidate.identity))
        self.assertEqual(cue_before, self.subtitle.get_cue(self.cue.identity))
        self.assertEqual(
            transcript_before, self.transcript.get_raw_transcript(self.raw.identity)
        )

    def test_unknown_subtitle_candidate_is_rejected(self):
        with self.assertRaisesRegex(KeyError, "unknown Subtitle Candidate"):
            self.integration.create_subtitle_review_item(
                candidate_id=SubtitleCandidateId("missing"),
                review_item_id=ReviewItemId("missing-item"),
                review_context_id=ReviewContextId("missing-context"),
            )

    def test_existing_wrong_candidate_kind_is_rejected(self):
        candidate, _ = self._create_candidate("wrong-kind")
        self.review.register_candidate_reference(
            CandidateReference(
                identity=CandidateReferenceId(candidate.identity.value),
                kind="transcript_correction_candidate",
                source_domain="transcript",
                domain_result_id=candidate.domain_result_id,
                source_media_id=candidate.source_media_id,
                source_timeline_id=candidate.source_timeline_id,
                run_id=candidate.run_id,
                unit_execution_id=candidate.unit_execution_id,
            )
        )
        with self.assertRaisesRegex(
            SubtitleReviewIntegrationError, "does not match"
        ):
            self._create_review_item(candidate)

    def test_domain_result_reference_mismatch_is_rejected(self):
        candidate, _ = self._create_candidate("domain-mismatch")
        self.subtitle.domain_results.save(
            DomainResultReference(
                identity=candidate.domain_result_id,
                kind="subtitle_revision",
                source_media=candidate.source_media_id,
                source_timeline=candidate.source_timeline_id,
            )
        )
        with self.assertRaisesRegex(
            SubtitleReviewIntegrationError, "Domain Result"
        ):
            self._create_review_item(candidate)

    def test_source_timeline_mismatch_is_rejected(self):
        candidate, _ = self._create_candidate("timeline-mismatch")
        self.subtitle.domain_results.save(
            DomainResultReference(
                identity=candidate.domain_result_id,
                kind=SUBTITLE_CANDIDATE_KIND,
                source_media=candidate.source_media_id,
                source_timeline=SourceTimelineId("wrong"),
            )
        )
        with self.assertRaisesRegex(
            SubtitleReviewIntegrationError, "Source Timeline"
        ):
            self._create_review_item(candidate)

    def test_run_and_unit_provenance_mismatch_is_rejected(self):
        candidate, _ = self._create_candidate("execution-mismatch")
        self.subtitle.candidates.save(
            replace(
                candidate,
                run_id=ProcessingRunId("wrong-run"),
                unit_execution_id=UnitExecutionId("wrong-execution"),
            )
        )
        with self.assertRaisesRegex(
            SubtitleReviewIntegrationError, "execution provenance"
        ):
            self._create_review_item(candidate)

    def test_review_context_references_cue_and_transcript_evidence(self):
        context = self.review.get_review_context(self.item.context_id)
        self.assertIn(f"subtitle_cue:{self.cue.identity.value}", context.evidence_references)
        self.assertIn(
            f"transcript_segment:{self.segment.identity.value}",
            context.evidence_references,
        )
        self.assertIn(
            f"transcript:{self.raw.identity.value}", context.evidence_references
        )

    def test_review_context_references_validation_and_findings(self):
        candidate, _ = self._create_candidate("validated")
        validation = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("subtitle-review-validation"),
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.subtitle.candidates.save(
            replace(candidate, validation_id=validation.identity)
        )
        item = self._create_review_item(candidate)
        context = self.review.get_review_context(item.context_id)
        self.assertIn(
            f"subtitle_validation:{validation.identity.value}",
            context.validation_references,
        )

    def test_blocking_validation_is_exposed_without_automatic_reject(self):
        candidate, cue = self._create_candidate("blocking")
        object.__setattr__(cue, "start", -1.0)
        validation = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("subtitle-review-blocking"),
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.subtitle.candidates.save(
            replace(candidate, validation_id=validation.identity)
        )
        item = self._create_review_item(candidate)
        context = self.review.get_review_context(item.context_id)
        self.assertIsNotNone(context.blocking_reason)
        self.assertTrue(
            any(
                reference.startswith("subtitle_validation_finding:")
                for reference in context.validation_references
            )
        )
        self.assertEqual((), self.review.get_review_history(item.identity))

    def test_validation_success_does_not_create_accept(self):
        self.assertEqual((), self.review.get_review_history(self.item.identity))
        self.assertEqual((), self.review.approved_decisions.all())

    def test_accept_creates_decision_and_approved_decision_only(self):
        decision, approved = self._accept()
        self.assertEqual(DecisionKind.ACCEPT, decision.kind)
        self.assertEqual(decision.identity, approved.source_decision_id)
        self.assertEqual(self.actor, decision.actor)
        self.assertEqual((), self.subtitle.revisions.all())

    def test_accept_preserves_candidate_and_does_not_create_final_or_artifact(self):
        before = self.subtitle.get_candidate(self.candidate.identity)
        self._accept()
        self.assertEqual(before, self.subtitle.get_candidate(self.candidate.identity))
        self.assertFalse(hasattr(self.review, "create_final_subtitle"))
        self.assertFalse(hasattr(self.review, "create_artifact"))

    def test_reject_creates_decision_without_approval_or_deletion(self):
        candidate_before = self.subtitle.get_candidate(self.candidate.identity)
        cue_before = self.subtitle.get_cue(self.cue.identity)
        decision = self.review.record_reject(
            decision_id=ReviewDecisionId("subtitle-reject"),
            history_id=ReviewHistoryEntryId("subtitle-reject-history"),
            review_item_id=self.item.identity,
            actor=self.actor,
        )
        self.assertEqual(DecisionKind.REJECT, decision.kind)
        self.assertEqual((), self.review.approved_decisions.all())
        self.assertEqual(candidate_before, self.subtitle.get_candidate(self.candidate.identity))
        self.assertEqual(cue_before, self.subtitle.get_cue(self.cue.identity))

    def test_modify_creates_modification_without_subtitle_revision(self):
        before = self.subtitle.get_candidate(self.candidate.identity)
        decision, modification, approved = self.review.record_modify(
            decision_id=ReviewDecisionId("subtitle-modify"),
            modification_id=DecisionModificationId("subtitle-modification"),
            history_id=ReviewHistoryEntryId("subtitle-modify-history"),
            approved_id=ApprovedDecisionId("subtitle-modify-approved"),
            review_item_id=self.item.identity,
            actor=self.actor,
            modified_intent="change cue text and timing intent",
        )
        self.assertEqual(DecisionKind.MODIFY, decision.kind)
        self.assertEqual(modification.identity, approved.modification_id)
        self.assertEqual(before, self.subtitle.get_candidate(self.candidate.identity))
        self.assertEqual((), self.subtitle.revisions.all())

    def test_approved_decision_identities_are_not_subtitle_records(self):
        _, approved = self._accept()
        self.assertNotEqual(type(approved.identity), SubtitleCandidateId)
        self.assertNotEqual(type(approved.identity), SubtitleRevisionId)
        self.assertFalse(hasattr(approved, "final_subtitle_id"))

    def test_stale_preserves_decision_and_does_not_reject(self):
        decision, _ = self._accept()
        before = self.review.get_decision(decision.identity)
        record = StaleCandidateRecord(
            identity=StaleCandidateRecordId("subtitle-stale"),
            candidate_id=self._reference(self.candidate).identity,
            reason="source Transcript changed",
            related_decision_ids=(decision.identity,),
        )
        self.integration.mark_subtitle_candidate_stale(record)
        self.assertEqual(before, self.review.get_decision(decision.identity))
        self.assertEqual(DecisionKind.ACCEPT, before.kind)

    def test_stale_accept_is_not_applied_to_new_candidate(self):
        decision, _ = self._accept()
        self.integration.mark_subtitle_candidate_stale(
            StaleCandidateRecord(
                identity=StaleCandidateRecordId("subtitle-stale-new"),
                candidate_id=self._reference(self.candidate).identity,
                reason="candidate regenerated",
                related_decision_ids=(decision.identity,),
            )
        )
        new_candidate, _ = self._create_candidate("new")
        self._create_review_item(new_candidate)
        new_reference = self._reference(new_candidate)
        self.assertEqual(
            (),
            tuple(
                approved
                for approved in self.review.approved_decisions.all()
                if approved.source_candidate_id == new_reference.identity
            ),
        )

    def test_conflict_preserves_decision(self):
        decision, _ = self._accept()
        before = self.review.get_decision(decision.identity)
        conflict = ReviewConflict(
            identity=ReviewConflictId("subtitle-conflict"),
            description="Subtitle Cue evidence changed",
            review_item_id=self.item.identity,
            decision_ids=(decision.identity,),
        )
        self.integration.record_subtitle_review_conflict(conflict)
        self.assertEqual(before, self.review.get_decision(decision.identity))

    def test_reconciliation_preserves_candidates_and_does_not_approve_new(self):
        decision, _ = self._accept()
        old_before = self.subtitle.get_candidate(self.candidate.identity)
        new_candidate, _ = self._create_candidate("reconciled")
        self._create_review_item(new_candidate)
        new_before = self.subtitle.get_candidate(new_candidate.identity)
        reconciliation = CandidateReconciliation(
            identity=CandidateReconciliationId("subtitle-reconciliation"),
            previous_candidate_id=self._reference(self.candidate).identity,
            new_candidate_id=self._reference(new_candidate).identity,
            relationship="regenerated subtitle candidate",
            decision_ids=(decision.identity,),
        )
        self.integration.reconcile_subtitle_candidates(reconciliation)
        self.assertEqual(old_before, self.subtitle.get_candidate(self.candidate.identity))
        self.assertEqual(new_before, self.subtitle.get_candidate(new_candidate.identity))
        self.assertEqual(
            (),
            tuple(
                approved
                for approved in self.review.approved_decisions.all()
                if approved.source_candidate_id == self._reference(new_candidate).identity
            ),
        )

    def test_duplicate_review_item_is_rejected_without_partial_context(self):
        candidate, _ = self._create_candidate("duplicate-item")
        duplicate_item_id = self.item.identity
        context_id = ReviewContextId("duplicate-item-context")
        with self.assertRaisesRegex(
            SubtitleReviewIntegrationError, "review item identity"
        ):
            self.integration.create_subtitle_review_item(
                candidate_id=candidate.identity,
                review_item_id=duplicate_item_id,
                review_context_id=context_id,
            )
        self.assertIsNone(self.review.get_review_context(context_id))
        self.assertEqual((), self.integration.get_review_items_for_subtitle_candidate(
            candidate.identity
        ))

    def test_duplicate_context_is_rejected_without_partial_review_item(self):
        candidate, _ = self._create_candidate("duplicate-context")
        item_id = ReviewItemId("duplicate-context-item")
        with self.assertRaisesRegex(
            SubtitleReviewIntegrationError, "review context identity"
        ):
            self.integration.create_subtitle_review_item(
                candidate_id=candidate.identity,
                review_item_id=item_id,
                review_context_id=self.item.context_id,
            )
        self.assertIsNone(self.review.get_review_item(item_id))

    def test_invalid_validation_reference_leaves_no_partial_review_records(self):
        candidate, _ = self._create_candidate("invalid-validation")
        self.subtitle.candidates.save(
            replace(
                candidate,
                validation_id=SubtitleValidationId("missing-validation"),
            )
        )
        item_id = ReviewItemId("invalid-validation-item")
        context_id = ReviewContextId("invalid-validation-context")
        with self.assertRaisesRegex(
            SubtitleReviewIntegrationError, "Validation"
        ):
            self.integration.create_subtitle_review_item(
                candidate_id=candidate.identity,
                review_item_id=item_id,
                review_context_id=context_id,
            )
        self.assertIsNone(
            self.review.get_candidate_reference(
                CandidateReferenceId(candidate.identity.value)
            )
        )
        self.assertIsNone(self.review.get_review_context(context_id))
        self.assertIsNone(self.review.get_review_item(item_id))

    def test_query_returns_review_items_and_history_for_candidate(self):
        self._accept()
        self.assertEqual(
            (self.review.get_review_item(self.item.identity),),
            self.integration.get_review_items_for_subtitle_candidate(
                self.candidate.identity
            ),
        )
        history = self.integration.get_subtitle_candidate_review_history(
            self.candidate.identity
        )
        self.assertEqual(1, len(history))

    def test_services_keep_human_and_application_boundaries_separate(self):
        for command in ("accept", "reject", "modify"):
            self.assertFalse(hasattr(self.subtitle, command))
            self.assertFalse(hasattr(self.integration, command))
        self.assertFalse(hasattr(self.review, "create_subtitle_revision"))
        self.assertFalse(hasattr(self.review, "create_final_subtitle"))

    def _accept(self):
        return self.review.record_accept(
            decision_id=ReviewDecisionId("subtitle-accept"),
            history_id=ReviewHistoryEntryId("subtitle-accept-history"),
            approved_id=ApprovedDecisionId("subtitle-accept-approved"),
            review_item_id=self.item.identity,
            actor=self.actor,
        )

    def _reference(self, candidate):
        return self.review.get_candidate_reference(
            CandidateReferenceId(candidate.identity.value)
        )

    def _create_review_item(self, candidate):
        return self.integration.create_subtitle_review_item(
            candidate_id=candidate.identity,
            review_item_id=ReviewItemId(f"review-item-{candidate.identity.value}"),
            review_context_id=ReviewContextId(
                f"review-context-{candidate.identity.value}"
            ),
        )

    def _create_raw(self):
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("subtitle-review-provider"),
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="provider",
            original_content="검토할 자막",
        )
        self.transcript.register_provider_result(provider)
        transcript_id = TranscriptId("subtitle-review-transcript")
        segment = TranscriptSegment(
            identity=TranscriptSegmentId("subtitle-review-segment"),
            transcript_id=transcript_id,
            source_timeline_id=self.timeline,
            text="검토할 자막",
            source_order=0,
            start=0.0,
            end=1.0,
        )
        raw = RawTranscript(
            identity=transcript_id,
            domain_result_id=DomainResultId("subtitle-review-transcript-result"),
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(segment.identity,),
        )
        self.transcript.create_raw_transcript(raw, (segment,))
        return raw, segment

    def _create_candidate(self, suffix):
        subtitle_id = SubtitleId(f"subtitle-review-{suffix}")
        cue = SubtitleCue(
            identity=SubtitleCueId(f"subtitle-review-cue-{suffix}"),
            subtitle_id=subtitle_id,
            source_timeline_id=self.timeline,
            start=0.0,
            end=1.0,
            text="검토할 자막",
            display_order=0,
            source_segment_ids=(self.segment.identity,),
            source_transcript_id=self.raw.identity,
        )
        candidate = SubtitleCandidate(
            identity=SubtitleCandidateId(f"subtitle-review-candidate-{suffix}"),
            subtitle_id=subtitle_id,
            domain_result_id=DomainResultId(
                f"subtitle-review-candidate-{suffix}-result"
            ),
            source_transcript_id=self.raw.identity,
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            cue_ids=(cue.identity,),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.subtitle.create_candidate(candidate, (cue,))
        return candidate, cue


if __name__ == "__main__":
    unittest.main()
