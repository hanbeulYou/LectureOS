import unittest

from lectureos.application import (
    ReviewPreparationIdentityPlan,
    ReviewPreparationTargetIdentityPlan,
    TranscriptReviewPreparationError,
    TranscriptReviewPreparationService,
)
from lectureos.application.identities import TranscriptReviewPreparationId
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
from lectureos.execution.models import ExecutionIntent, ProcessingUnit
from lectureos.execution.service import ExecutionService
from lectureos.review.identities import (
    CandidateReferenceId,
    ReviewContextId,
    ReviewItemId,
)
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import (
    CorrectedTranscriptRevision,
    CorrectionCandidate,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)
from lectureos.transcript.service import TranscriptService


class TranscriptReviewPreparationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.unit_id = ProcessingUnitId("unit")
        self.media_id = SourceMediaId("media")
        self.timeline_id = SourceTimelineId("timeline")
        self.capability = CapabilityReference("transcript.correction")
        self.execution = ExecutionService()
        self.execution.register_unit(
            ProcessingUnit(
                identity=self.unit_id,
                purpose="prepare review",
                capabilities=(self.capability,),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("prepare review"),
            working_context=WorkingContextReference("context"),
            unit_ids=(self.unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit_id,
        )
        self.transcripts = TranscriptService(self.execution)
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("provider"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="provider:model",
            original_content="source",
        )
        self.raw = RawTranscript(
            identity=TranscriptId("raw"),
            domain_result_id=DomainResultId("raw-result"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(TranscriptSegmentId("segment-0"), TranscriptSegmentId("segment-1")),
        )
        self.segments = (
            TranscriptSegment(
                identity=self.raw.segment_ids[0],
                transcript_id=self.raw.identity,
                source_timeline_id=self.timeline_id,
                text="one",
                source_order=0,
                start=0.0,
                end=1.0,
            ),
            TranscriptSegment(
                identity=self.raw.segment_ids[1],
                transcript_id=self.raw.identity,
                source_timeline_id=self.timeline_id,
                text="two",
                source_order=1,
                start=1.0,
                end=2.0,
            ),
        )
        self.transcripts.register_provider_result(provider)
        self.transcripts.create_raw_transcript(self.raw, self.segments)
        for index, segment in enumerate(self.segments):
            self.transcripts.create_correction_candidate(
                CorrectionCandidate(
                    identity=CorrectionCandidateId(f"candidate-{index}"),
                    domain_result_id=DomainResultId(f"candidate-result-{index}"),
                    transcript_id=self.raw.identity,
                    segment_id=segment.identity,
                    proposed_text=f"corrected {index}",
                    rationale="recognition",
                    run_id=self.run_id,
                    unit_execution_id=self.execution_id,
                )
            )
        self.revision = CorrectedTranscriptRevision(
            identity=TranscriptRevisionId("revision"),
            transcript_id=self.raw.identity,
            domain_result_id=DomainResultId("revision-result"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=self.raw.segment_ids,
            parent_raw_transcript_id=self.raw.identity,
            correction_candidate_ids=(
                CorrectionCandidateId("candidate-0"),
                CorrectionCandidateId("candidate-1"),
            ),
        )
        self.transcripts.create_corrected_revision(self.revision, self.segments)
        self.service = TranscriptReviewPreparationService(self.transcripts, self.execution)

    def _plan(self, count=2) -> ReviewPreparationIdentityPlan:
        return ReviewPreparationIdentityPlan(
            preparation_id=TranscriptReviewPreparationId("prep"),
            preparation_result_id=DomainResultId("prep-result"),
            context_id=ReviewContextId("context"),
            targets=tuple(
                ReviewPreparationTargetIdentityPlan(
                    candidate_reference_id=CandidateReferenceId(f"candidate-{index}"),
                    review_item_id=ReviewItemId(f"item-{index}"),
                )
                for index in range(count)
            ),
        )

    def test_prepares_exact_canonical_review_records(self) -> None:
        prepared = self.service.prepare_review(
            revision_id=self.revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        preparation = prepared.preparation
        self.assertEqual(preparation.item_count, 2)
        self.assertEqual(
            preparation.ordered_item_ids,
            (ReviewItemId("item-0"), ReviewItemId("item-1")),
        )
        self.assertEqual(
            preparation.candidate_reference_ids,
            (CandidateReferenceId("candidate-0"), CandidateReferenceId("candidate-1")),
        )
        self.assertEqual(preparation.source_revision_id, self.revision.identity)
        self.assertEqual(preparation.source_transcript_id, self.raw.identity)
        self.assertEqual(preparation.source_media_id, self.media_id)
        self.assertTrue(preparation.structural_valid)
        self.assertTrue(preparation.provenance_complete)
        self.assertTrue(preparation.ordering_valid)
        self.assertEqual(
            tuple(group.group_key for group in preparation.groups),
            ("segment-0", "segment-1"),
        )
        self.assertEqual(
            tuple(group.review_item_ids for group in preparation.groups),
            ((ReviewItemId("item-0"),), (ReviewItemId("item-1"),)),
        )
        self.assertEqual(
            prepared.preparation_result.kind, "transcript_review_preparation"
        )
        self.assertEqual(
            prepared.preparation_result.upstream_results,
            (self.revision.domain_result_id,),
        )
        self.assertEqual(
            prepared.context.domain_result_references,
            (
                self.revision.domain_result_id,
                DomainResultId("candidate-result-0"),
                DomainResultId("candidate-result-1"),
            ),
        )
        self.assertIsNone(prepared.context.blocking_reason)
        for reference in prepared.candidate_references:
            self.assertEqual(reference.kind, "transcript_correction_candidate")
            self.assertEqual(reference.source_domain, "transcript")
            self.assertEqual(reference.source_media_id, self.media_id)
            self.assertEqual(reference.applicability, "undetermined")
        for item in prepared.review_items:
            self.assertEqual(item.context_id, ReviewContextId("context"))
            self.assertEqual(item.decision_references, ())
            self.assertEqual(item.stale_references, ())
            self.assertEqual(item.conflict_references, ())

    def test_generation_is_deterministic(self) -> None:
        first = self.service.prepare_review(
            revision_id=self.revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        second = self.service.prepare_review(
            revision_id=self.revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        self.assertEqual(first, second)

    def test_prepare_persists_nothing(self) -> None:
        self.service.prepare_review(
            revision_id=self.revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        self.assertIsNone(
            self.transcripts.get_domain_result_reference(DomainResultId("prep-result"))
        )

    def test_unknown_revision_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.service.prepare_review(
                revision_id=TranscriptRevisionId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_target_count_must_match_candidates(self) -> None:
        with self.assertRaises(TranscriptReviewPreparationError):
            self.service.prepare_review(
                revision_id=self.revision.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(1),
            )

    def test_candidate_reference_identity_must_equal_candidate(self) -> None:
        plan = ReviewPreparationIdentityPlan(
            preparation_id=TranscriptReviewPreparationId("prep"),
            preparation_result_id=DomainResultId("prep-result"),
            context_id=ReviewContextId("context"),
            targets=(
                ReviewPreparationTargetIdentityPlan(
                    candidate_reference_id=CandidateReferenceId("wrong-0"),
                    review_item_id=ReviewItemId("item-0"),
                ),
                ReviewPreparationTargetIdentityPlan(
                    candidate_reference_id=CandidateReferenceId("candidate-1"),
                    review_item_id=ReviewItemId("item-1"),
                ),
            ),
        )
        with self.assertRaises(TranscriptReviewPreparationError):
            self.service.prepare_review(
                revision_id=self.revision.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=plan,
            )

    def test_requires_running_execution(self) -> None:
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(TranscriptReviewPreparationError):
            self.service.prepare_review(
                revision_id=self.revision.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_rejects_duplicate_result_identity(self) -> None:
        plan = ReviewPreparationIdentityPlan(
            preparation_id=TranscriptReviewPreparationId("prep"),
            preparation_result_id=DomainResultId("revision-result"),
            context_id=ReviewContextId("context"),
            targets=self._plan().targets,
        )
        with self.assertRaises(TranscriptReviewPreparationError):
            self.service.prepare_review(
                revision_id=self.revision.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=plan,
            )


if __name__ == "__main__":
    unittest.main()
