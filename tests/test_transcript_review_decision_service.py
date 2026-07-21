import unittest
from datetime import datetime, timezone

from lectureos.application import (
    ReviewDecisionIdentityPlan,
    ReviewPreparationIdentityPlan,
    ReviewPreparationTargetIdentityPlan,
    TranscriptReviewDecisionError,
    TranscriptReviewDecisionService,
    TranscriptReviewPreparationService,
)
from lectureos.application.identities import (
    TranscriptReviewDecisionId,
    TranscriptReviewPreparationId,
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
from lectureos.execution.models import ExecutionIntent, ProcessingUnit
from lectureos.execution.repositories import InMemoryRepository
from lectureos.execution.service import ExecutionService
from lectureos.review.identities import (
    CandidateReferenceId,
    HumanActorReference,
    ReviewContextId,
    ReviewItemId,
)
from lectureos.review.models import DecisionKind
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

WHEN = datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)


class _PreparationStore:
    """Minimal in-memory durable-review query facade for the decision service."""

    def __init__(self) -> None:
        self.preparations = InMemoryRepository()
        self.items = InMemoryRepository()
        self.references = InMemoryRepository()

    def ingest(self, prepared) -> None:
        self.preparations.save(prepared.preparation)
        for item in prepared.review_items:
            self.items.save(item)
        for reference in prepared.candidate_references:
            self.references.save(reference)


class TranscriptReviewDecisionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.media_id = SourceMediaId("media")
        self.timeline_id = SourceTimelineId("timeline")
        capability = CapabilityReference("transcript.correction")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(identity=unit_id, purpose="review", capabilities=(capability,))
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("review"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
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
            segment_ids=(TranscriptSegmentId("segment-0"),),
        )
        segment = TranscriptSegment(
            identity=self.raw.segment_ids[0],
            transcript_id=self.raw.identity,
            source_timeline_id=self.timeline_id,
            text="one",
            source_order=0,
            start=0.0,
            end=1.0,
        )
        self.transcripts.register_provider_result(provider)
        self.transcripts.create_raw_transcript(self.raw, (segment,))
        self.transcripts.create_correction_candidate(
            CorrectionCandidate(
                identity=CorrectionCandidateId("candidate-0"),
                domain_result_id=DomainResultId("candidate-result-0"),
                transcript_id=self.raw.identity,
                segment_id=segment.identity,
                proposed_text="corrected",
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
            correction_candidate_ids=(CorrectionCandidateId("candidate-0"),),
        )
        self.transcripts.create_corrected_revision(self.revision, (segment,))
        preparation_service = TranscriptReviewPreparationService(
            self.transcripts, self.execution
        )
        prepared = preparation_service.prepare_review(
            revision_id=self.revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=ReviewPreparationIdentityPlan(
                preparation_id=TranscriptReviewPreparationId("prep"),
                preparation_result_id=DomainResultId("prep-result"),
                context_id=ReviewContextId("context"),
                targets=(
                    ReviewPreparationTargetIdentityPlan(
                        candidate_reference_id=CandidateReferenceId("candidate-0"),
                        review_item_id=ReviewItemId("item-0"),
                    ),
                ),
            ),
        )
        self.store = _PreparationStore()
        self.store.ingest(prepared)
        self.service = TranscriptReviewDecisionService(
            self.store.preparations,
            self.store.items,
            self.store.references,
            self.execution,
        )

    def _plan(self, name="decision") -> ReviewDecisionIdentityPlan:
        return ReviewDecisionIdentityPlan(
            decision_id=TranscriptReviewDecisionId(name),
            decision_result_id=DomainResultId(f"{name}-result"),
            decided_at=WHEN,
        )

    def _record(self, **overrides):
        base = dict(
            preparation_id=TranscriptReviewPreparationId("prep"),
            review_item_id=ReviewItemId("item-0"),
            reviewer=HumanActorReference("reviewer"),
            kind=DecisionKind.ACCEPT,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        base.update(overrides)
        return self.service.prepare_decision(**base)

    def test_accept_decision_records_full_provenance(self) -> None:
        prepared = self._record()
        decision = prepared.decision
        self.assertIs(decision.kind, DecisionKind.ACCEPT)
        self.assertEqual(decision.review_item_id, ReviewItemId("item-0"))
        self.assertEqual(
            decision.candidate_reference_id, CandidateReferenceId("candidate-0")
        )
        self.assertEqual(decision.source_revision_id, self.revision.identity)
        self.assertEqual(decision.reviewer, HumanActorReference("reviewer"))
        self.assertEqual(decision.decided_at, WHEN)
        self.assertEqual(decision.run_id, self.run_id)
        self.assertEqual(decision.unit_execution_id, self.execution_id)
        self.assertEqual(prepared.decision_result.kind, "transcript_review_decision")
        self.assertEqual(
            prepared.decision_result.upstream_results, (DomainResultId("prep-result"),)
        )

    def test_reject_decision(self) -> None:
        prepared = self._record(kind=DecisionKind.REJECT)
        self.assertIs(prepared.decision.kind, DecisionKind.REJECT)
        self.assertIsNone(prepared.decision.modified_text)

    def test_modify_decision_requires_text(self) -> None:
        with self.assertRaises(TranscriptReviewDecisionError):
            self._record(kind=DecisionKind.MODIFY)
        prepared = self._record(kind=DecisionKind.MODIFY, modified_text="human text")
        self.assertEqual(prepared.decision.modified_text, "human text")

    def test_accept_forbids_modified_text(self) -> None:
        with self.assertRaises(TranscriptReviewDecisionError):
            self._record(kind=DecisionKind.ACCEPT, modified_text="x")

    def test_non_human_reviewer_rejected(self) -> None:
        with self.assertRaises(TranscriptReviewDecisionError):
            self._record(reviewer="not-human")

    def test_deterministic_construction(self) -> None:
        self.assertEqual(self._record(), self._record())

    def test_unknown_preparation_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._record(preparation_id=TranscriptReviewPreparationId("missing"))

    def test_unknown_review_item_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._record(review_item_id=ReviewItemId("missing"))

    def test_requires_running_execution(self) -> None:
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(TranscriptReviewDecisionError):
            self._record()

    def test_prepare_does_not_persist(self) -> None:
        # No persistence configured; prepare must not attempt to write.
        self._record()
        # record_decision without persistence must fail explicitly.
        with self.assertRaises(RuntimeError):
            self.service.record_decision(
                preparation_id=TranscriptReviewPreparationId("prep"),
                review_item_id=ReviewItemId("item-0"),
                reviewer=HumanActorReference("reviewer"),
                kind=DecisionKind.ACCEPT,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
