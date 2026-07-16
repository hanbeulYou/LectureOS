import unittest
from dataclasses import replace

from lectureos.application.identities import TranscriptCorrectionApplicationResultId
from lectureos.application.models import TranscriptCorrectionApplicationResult
from lectureos.application.transcript_correction import (
    TranscriptCorrectionApplicationError,
    TranscriptCorrectionApplicationService,
)
from lectureos.execution.identities import (
    ArtifactId,
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    ProcessingUnitId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import ExecutionIntent, ProcessingUnit
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
    StaleCandidateRecord,
    ReviewContext,
    ReviewDecision,
    ReviewItem,
)
from lectureos.review.service import ReviewService
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import (
    CorrectionCandidate,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptApplicability,
    TranscriptSegment,
    TranscriptValidation,
)
from lectureos.transcript.service import TranscriptService


class ApprovedTranscriptCorrectionApplicationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.execution = ExecutionService()
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("transcript.apply-correction"),
            purpose="apply approved transcript correction",
            capabilities=(CapabilityReference("transcript.correction"),),
            result_kinds=("corrected_transcript_revision",),
        )
        self.execution.register_unit(self.unit)
        self.run_id = ProcessingRunId("run-application")
        self.execution_id = UnitExecutionId("execution-application")
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("approved correction application"),
            working_context=WorkingContextReference("working-context"),
            unit_ids=(self.unit.identity,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit.identity,
        )
        self.transcript = TranscriptService(self.execution)
        self.review = ReviewService()
        self.source_media = SourceMediaId("media-application")
        self.timeline = SourceTimelineId("timeline-application")
        self.raw = self._create_raw()
        self.candidate = self._create_candidate()
        self.candidate_reference = self._register_review_item()
        self.actor = HumanActorReference("reviewer-application")
        self.decision, self.approved = self.review.record_accept(
            decision_id=ReviewDecisionId("decision-accept"),
            history_id=ReviewHistoryEntryId("history-accept"),
            approved_id=ApprovedDecisionId("approved-accept"),
            review_item_id=ReviewItemId("review-item"),
            actor=self.actor,
        )
        self.application = TranscriptCorrectionApplicationService(
            self.review, self.transcript, self.transcript
        )

    def test_accept_creates_corrected_revision(self) -> None:
        result = self._apply()
        self.assertIsNotNone(self.transcript.get_corrected_revision(result.created_revision_id))

    def test_revision_identity_differs_from_approved_decision(self) -> None:
        result = self._apply()
        self.assertNotEqual(result.created_revision_id.value, self.approved.identity.value)

    def test_revision_identity_differs_from_candidate(self) -> None:
        result = self._apply()
        self.assertNotEqual(result.created_revision_id.value, self.candidate.identity.value)

    def test_accept_preserves_candidate(self) -> None:
        before = self.transcript.get_candidate(self.candidate.identity)
        self._apply()
        self.assertEqual(before, self.transcript.get_candidate(self.candidate.identity))

    def test_accept_preserves_review_decision(self) -> None:
        before = self.review.get_decision(self.decision.identity)
        self._apply()
        self.assertEqual(before, self.review.get_decision(self.decision.identity))

    def test_accept_preserves_raw_transcript(self) -> None:
        before = self.transcript.get_raw_transcript(self.raw.identity)
        self._apply()
        self.assertEqual(before, self.transcript.get_raw_transcript(self.raw.identity))

    def test_accept_preserves_original_segment(self) -> None:
        before = self.transcript.get_segment(self.candidate.segment_id)
        self._apply()
        self.assertEqual(before, self.transcript.get_segment(self.candidate.segment_id))

    def test_accept_creates_replacement_segment(self) -> None:
        result = self._apply()
        segment = self.transcript.get_segment(result.created_segment_ids[0])
        self.assertEqual(self.candidate.proposed_text, segment.text)
        self.assertEqual(self.candidate.segment_id, segment.replaces_segment_id)

    def test_replacement_preserves_source_timeline(self) -> None:
        result = self._apply()
        segment = self.transcript.get_segment(result.created_segment_ids[0])
        self.assertEqual(self.timeline, segment.source_timeline_id)

    def test_new_revision_is_not_current(self) -> None:
        result = self._apply()
        revision = self.transcript.get_corrected_revision(result.created_revision_id)
        self.assertEqual(TranscriptApplicability.UNDETERMINED, revision.applicability)

    def test_new_revision_has_no_validation_approval(self) -> None:
        result = self._apply()
        revision = self.transcript.get_corrected_revision(result.created_revision_id)
        self.assertIsNone(revision.validation_id)

    def test_modify_applies_modification_text(self) -> None:
        application, modification, approved = self._modify_application()
        result = self._apply_with(application, approved.identity, suffix="modify")
        segment = self.transcript.get_segment(result.created_segment_ids[0])
        self.assertEqual(modification.modified_intent, segment.text)

    def test_modify_preserves_modification(self) -> None:
        application, modification, approved = self._modify_application()
        before = self.review.get_modification(modification.identity)
        self._apply_with(application, approved.identity, suffix="modify")
        self.assertEqual(before, self.review.get_modification(modification.identity))

    def test_modify_preserves_candidate(self) -> None:
        application, _, approved = self._modify_application()
        before = self.transcript.get_candidate(self.candidate.identity)
        self._apply_with(application, approved.identity, suffix="modify")
        self.assertEqual(before, self.transcript.get_candidate(self.candidate.identity))

    def test_reject_decision_cannot_be_applied(self) -> None:
        reject = self.review.record_reject(
            decision_id=ReviewDecisionId("decision-reject"),
            history_id=ReviewHistoryEntryId("history-reject"),
            review_item_id=ReviewItemId("review-item"),
            actor=self.actor,
        )
        forged = ApprovedDecision(
            identity=ApprovedDecisionId("approved-reject"),
            source_decision_id=reject.identity,
            source_candidate_id=self.candidate_reference.identity,
            actor=self.actor,
            approved_intent="forged",
        )
        self.review.approved_decisions.save(forged)
        with self.assertRaisesRegex(TranscriptCorrectionApplicationError, "Accept or Modify"):
            self._apply_with(self.application, forged.identity, suffix="reject")

    def test_candidate_without_approved_decision_cannot_be_applied(self) -> None:
        with self.assertRaisesRegex(KeyError, "unknown approved decision"):
            self._apply_with(
                self.application, ApprovedDecisionId("missing-approved"), suffix="missing"
            )

    def test_candidate_reference_mismatch_is_rejected(self) -> None:
        forged = replace(
            self.approved,
            identity=ApprovedDecisionId("approved-wrong-candidate"),
            source_candidate_id=CandidateReferenceId("other-candidate"),
        )
        self.review.approved_decisions.save(forged)
        with self.assertRaisesRegex(KeyError, "unknown source candidate"):
            self._apply_with(self.application, forged.identity, suffix="candidate-mismatch")

    def test_decision_reference_mismatch_is_rejected(self) -> None:
        forged = replace(
            self.approved,
            identity=ApprovedDecisionId("approved-wrong-decision"),
            source_decision_id=ReviewDecisionId("missing-decision"),
        )
        self.review.approved_decisions.save(forged)
        with self.assertRaisesRegex(KeyError, "unknown source review decision"):
            self._apply_with(self.application, forged.identity, suffix="decision-mismatch")

    def test_human_actor_mismatch_is_rejected(self) -> None:
        forged = replace(
            self.approved,
            identity=ApprovedDecisionId("approved-wrong-actor"),
            actor=HumanActorReference("another-reviewer"),
        )
        self.review.approved_decisions.save(forged)
        with self.assertRaisesRegex(TranscriptCorrectionApplicationError, "Human Actors differ"):
            self._apply_with(self.application, forged.identity, suffix="actor-mismatch")

    def test_missing_transcript_candidate_is_rejected(self) -> None:
        self.transcript.candidates._records.pop(self.candidate.identity)
        with self.assertRaisesRegex(KeyError, "unknown transcript correction candidate"):
            self._apply()

    def test_missing_target_transcript_is_rejected(self) -> None:
        self.transcript.raw_transcripts._records.pop(self.raw.identity)
        with self.assertRaisesRegex(KeyError, "unknown target raw transcript"):
            self._apply()

    def test_missing_segment_is_rejected(self) -> None:
        self.transcript.segments._records.pop(self.candidate.segment_id)
        with self.assertRaisesRegex(KeyError, "unknown target transcript segment"):
            self._apply()

    def test_other_transcript_segment_is_rejected(self) -> None:
        segment = self.transcript.get_segment(self.candidate.segment_id)
        self.transcript.segments.save(
            replace(segment, transcript_id=TranscriptId("other-transcript"))
        )
        with self.assertRaisesRegex(TranscriptCorrectionApplicationError, "another transcript"):
            self._apply()

    def test_source_timeline_mismatch_is_rejected(self) -> None:
        segment = self.transcript.get_segment(self.candidate.segment_id)
        self.transcript.segments.save(
            replace(segment, source_timeline_id=SourceTimelineId("other-timeline"))
        )
        with self.assertRaisesRegex(TranscriptCorrectionApplicationError, "timeline"):
            self._apply()

    def test_review_candidate_source_media_mismatch_is_rejected(self) -> None:
        self.review.candidates.save(
            replace(
                self.candidate_reference,
                source_media_id=SourceMediaId("other-media"),
            )
        )
        with self.assertRaisesRegex(TranscriptCorrectionApplicationError, "source media"):
            self._apply()

    def test_blocking_review_context_is_rejected(self) -> None:
        context = self.review.get_review_context(ReviewContextId("review-context"))
        self.review.contexts.save(replace(context, blocking_reason="evidence unavailable"))
        with self.assertRaisesRegex(TranscriptCorrectionApplicationError, "blocking condition"):
            self._apply()

    def test_stale_candidate_is_blocked(self) -> None:
        self.review.mark_candidate_stale(
            StaleCandidateRecord(
                identity=StaleCandidateRecordId("stale-application"),
                candidate_id=self.candidate_reference.identity,
                reason="upstream changed",
                related_decision_ids=(self.decision.identity,),
            )
        )
        with self.assertRaisesRegex(TranscriptCorrectionApplicationError, "stale"):
            self._apply()

    def test_unresolved_conflict_is_blocked(self) -> None:
        self.review.record_conflict(
            ReviewConflict(
                identity=ReviewConflictId("conflict-application"),
                description="upstream conflict",
                review_item_id=ReviewItemId("review-item"),
                decision_ids=(self.decision.identity,),
            )
        )
        with self.assertRaisesRegex(TranscriptCorrectionApplicationError, "unresolved"):
            self._apply()

    def test_pending_reconciliation_is_blocked(self) -> None:
        new_reference = replace(
            self.candidate_reference,
            identity=CandidateReferenceId("candidate-new"),
            domain_result_id=DomainResultId("candidate-new-result"),
        )
        self.review.register_candidate_reference(new_reference)
        self.review.record_reconciliation(
            CandidateReconciliation(
                identity=CandidateReconciliationId("reconciliation-application"),
                previous_candidate_id=self.candidate_reference.identity,
                new_candidate_id=new_reference.identity,
                relationship="reprocessed candidate",
                decision_ids=(self.decision.identity,),
            )
        )
        with self.assertRaisesRegex(TranscriptCorrectionApplicationError, "confirmation"):
            self._apply()

    def test_duplicate_application_returns_existing_result(self) -> None:
        first = self._apply()
        second = self._apply_with(
            self.application,
            self.approved.identity,
            suffix="different-identities",
        )
        self.assertEqual(first, second)
        self.assertEqual(1, len(self.transcript.revisions.all()))

    def test_result_can_be_queried_by_approved_decision(self) -> None:
        result = self._apply()
        self.assertEqual(
            result,
            self.application.get_application_result_for_approved_decision(
                self.approved.identity
            ),
        )

    def test_failed_application_leaves_no_new_segment(self) -> None:
        self.review.mark_candidate_stale(
            StaleCandidateRecord(
                identity=StaleCandidateRecordId("stale-no-segment"),
                candidate_id=self.candidate_reference.identity,
                reason="upstream changed",
            )
        )
        with self.assertRaises(TranscriptCorrectionApplicationError):
            self._apply()
        self.assertIsNone(self.transcript.get_segment(TranscriptSegmentId("segment-applied")))

    def test_failed_application_leaves_no_revision(self) -> None:
        self.transcript.segments._records.pop(self.candidate.segment_id)
        with self.assertRaises(KeyError):
            self._apply()
        self.assertIsNone(self.transcript.get_corrected_revision(TranscriptRevisionId("revision-applied")))

    def test_failed_application_leaves_no_result(self) -> None:
        self.transcript.segments._records.pop(self.candidate.segment_id)
        with self.assertRaises(KeyError):
            self._apply()
        self.assertIsNone(
            self.application.get_application_result(
                TranscriptCorrectionApplicationResultId("application-applied")
            )
        )

    def test_application_result_identity_differs_from_revision(self) -> None:
        result = self._apply()
        self.assertNotEqual(result.identity.value, result.created_revision_id.value)

    def test_application_result_is_not_review_decision(self) -> None:
        result = self._apply()
        self.assertNotIsInstance(result, ReviewDecision)

    def test_application_result_is_not_validation_result(self) -> None:
        result = self._apply()
        self.assertNotIsInstance(result, TranscriptValidation)
        self.assertNotIsInstance(result.identity, TranscriptValidationId)

    def test_application_has_no_human_decision_commands(self) -> None:
        for command in ("accept", "reject", "modify"):
            self.assertFalse(hasattr(self.application, command))

    def test_application_does_not_create_artifact(self) -> None:
        result = self._apply()
        self.assertNotIsInstance(result.identity, ArtifactId)
        self.assertFalse(hasattr(self.application, "create_artifact"))

    def test_transcript_service_does_not_create_approved_decision(self) -> None:
        self.assertFalse(hasattr(self.transcript, "record_accept"))
        self.assertFalse(hasattr(self.transcript, "create_approved_decision"))

    def test_review_service_does_not_create_revision(self) -> None:
        self.assertFalse(hasattr(self.review, "create_corrected_revision"))

    def test_unchanged_parent_segment_is_reused_without_overwrite(self) -> None:
        unchanged_id = self.raw.segment_ids[1]
        before = self.transcript.get_segment(unchanged_id)
        self._apply()
        self.assertEqual(before, self.transcript.get_segment(unchanged_id))

    def test_application_can_continue_from_corrected_revision_parent(self) -> None:
        first = self._apply()
        first_revision = self.transcript.get_corrected_revision(first.created_revision_id)
        first_segment_id = first.created_segment_ids[0]
        second_candidate = CorrectionCandidate(
            identity=CorrectionCandidateId("candidate-second-revision"),
            domain_result_id=DomainResultId("candidate-second-result"),
            transcript_id=self.raw.identity,
            segment_id=first_segment_id,
            proposed_text="안녕하십니까",
            rationale="second approved correction",
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            target_revision_id=first_revision.identity,
        )
        self.transcript.create_correction_candidate(second_candidate)
        second_reference = CandidateReference(
            identity=CandidateReferenceId(second_candidate.identity.value),
            kind="transcript_correction_candidate",
            source_domain="transcript",
            domain_result_id=second_candidate.domain_result_id,
            source_media_id=self.source_media,
            source_timeline_id=self.timeline,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            revision_reference=first_revision.identity.value,
        )
        self.review.register_candidate_reference(second_reference)
        second_context = ReviewContext(
            identity=ReviewContextId("review-context-second"),
            source_media_id=self.source_media,
            source_timeline_id=self.timeline,
            domain_result_references=(second_candidate.domain_result_id,),
        )
        self.review.create_review_context(second_context)
        second_item = ReviewItem(
            identity=ReviewItemId("review-item-second"),
            candidate_id=second_reference.identity,
            context_id=second_context.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.review.create_review_item(second_item)
        _, second_approved = self.review.record_accept(
            decision_id=ReviewDecisionId("decision-second-revision"),
            history_id=ReviewHistoryEntryId("history-second-revision"),
            approved_id=ApprovedDecisionId("approved-second-revision"),
            review_item_id=second_item.identity,
            actor=self.actor,
        )
        second_application = TranscriptCorrectionApplicationService(
            self.review, self.transcript, self.transcript
        )

        result = self._apply_with(
            second_application, second_approved.identity, suffix="second-revision"
        )

        revision = self.transcript.get_corrected_revision(result.created_revision_id)
        self.assertEqual(first_revision.identity, revision.parent_revision_id)
        self.assertIsNone(revision.parent_raw_transcript_id)
        self.assertEqual(self.raw.segment_ids[1], revision.segment_ids[1])
        self.assertEqual(first_segment_id, self.transcript.get_segment(
            result.created_segment_ids[0]
        ).replaces_segment_id)

    def test_candidate_execution_provenance_mismatch_is_rejected(self) -> None:
        self.review.candidates.save(
            replace(
                self.candidate_reference,
                run_id=ProcessingRunId("different-run"),
                unit_execution_id=UnitExecutionId("different-execution"),
            )
        )
        with self.assertRaisesRegex(
            TranscriptCorrectionApplicationError, "execution provenance"
        ):
            self._apply()

    def _create_raw(self):
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("provider-application"),
            source_media_id=self.source_media,
            source_timeline_id=self.timeline,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="test-provider",
            original_content="안녕 세계",
        )
        self.transcript.register_provider_result(provider)
        transcript_id = TranscriptId("raw-application")
        segments = (
            TranscriptSegment(
                identity=TranscriptSegmentId("segment-target"),
                transcript_id=transcript_id,
                source_timeline_id=self.timeline,
                text="안녕",
                source_order=0,
                start=0.0,
                end=1.0,
            ),
            TranscriptSegment(
                identity=TranscriptSegmentId("segment-unchanged"),
                transcript_id=transcript_id,
                source_timeline_id=self.timeline,
                text="세계",
                source_order=1,
                start=1.0,
                end=2.0,
            ),
        )
        raw = RawTranscript(
            identity=transcript_id,
            domain_result_id=DomainResultId("raw-result-application"),
            source_media_id=self.source_media,
            source_timeline_id=self.timeline,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=tuple(segment.identity for segment in segments),
        )
        self.transcript.create_raw_transcript(raw, segments)
        return raw

    def _create_candidate(self):
        candidate = CorrectionCandidate(
            identity=CorrectionCandidateId("candidate-application"),
            domain_result_id=DomainResultId("candidate-result-application"),
            transcript_id=self.raw.identity,
            segment_id=self.raw.segment_ids[0],
            proposed_text="안녕하세요",
            rationale="approved wording correction",
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.transcript.create_correction_candidate(candidate)
        return candidate

    def _register_review_item(self):
        reference = CandidateReference(
            identity=CandidateReferenceId(self.candidate.identity.value),
            kind="transcript_correction_candidate",
            source_domain="transcript",
            domain_result_id=self.candidate.domain_result_id,
            source_media_id=self.source_media,
            source_timeline_id=self.timeline,
            run_id=self.candidate.run_id,
            unit_execution_id=self.candidate.unit_execution_id,
        )
        self.review.register_candidate_reference(reference)
        context = ReviewContext(
            identity=ReviewContextId("review-context"),
            source_media_id=self.source_media,
            source_timeline_id=self.timeline,
            domain_result_references=(self.candidate.domain_result_id,),
        )
        self.review.create_review_context(context)
        self.review.create_review_item(
            ReviewItem(
                identity=ReviewItemId("review-item"),
                candidate_id=reference.identity,
                context_id=context.identity,
                run_id=self.candidate.run_id,
                unit_execution_id=self.candidate.unit_execution_id,
            )
        )
        return reference

    def _modify_application(self):
        decision, modification, approved = self.review.record_modify(
            decision_id=ReviewDecisionId("decision-modify"),
            modification_id=DecisionModificationId("modification-application"),
            history_id=ReviewHistoryEntryId("history-modify"),
            approved_id=ApprovedDecisionId("approved-modify"),
            review_item_id=ReviewItemId("review-item"),
            actor=self.actor,
            modified_intent="반갑습니다",
        )
        return (
            TranscriptCorrectionApplicationService(
                self.review, self.transcript, self.transcript
            ),
            modification,
            approved,
        )

    def _apply(self):
        return self._apply_with(self.application, self.approved.identity, suffix="applied")

    def _apply_with(self, application, approved_id, *, suffix):
        return application.apply_approved_transcript_correction(
            approved_decision_id=approved_id,
            application_result_id=TranscriptCorrectionApplicationResultId(
                f"application-{suffix}"
            ),
            revision_id=TranscriptRevisionId(f"revision-{suffix}"),
            revision_domain_result_id=DomainResultId(f"revision-result-{suffix}"),
            replacement_segment_id=TranscriptSegmentId(f"segment-{suffix}"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )


if __name__ == "__main__":
    unittest.main()
