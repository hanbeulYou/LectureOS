import unittest

from lectureos.application import (
    LectureAnalysisEligibility,
    LectureAnalysisInputError,
    LectureAnalysisInputIdentityPlan,
    LectureAnalysisInputService,
    ReadinessOutcome,
    evaluate_readiness_outcome,
)
from lectureos.application.identities import (
    EligibleAnalysisInputId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.application.transcript_applicability_evaluation import ApplicabilityOutcome
from lectureos.application.transcript_current_selection import CurrentSelectionOutcome
from lectureos.application.transcript_readiness_evaluation import (
    TranscriptReadinessEvaluation,
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
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import (
    CorrectedTranscriptRevision,
    CorrectionCandidate,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)
from lectureos.transcript.service import TranscriptService


class LectureAnalysisInputServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.media_id = SourceMediaId("media")
        self.timeline_id = SourceTimelineId("timeline")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="analysis-input",
                capabilities=(CapabilityReference("lecture.analysis"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("analysis-input"),
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
        self.readiness = InMemoryRepository()
        self.service = LectureAnalysisInputService(
            self.readiness, self.transcripts, self.execution
        )

    def _readiness(self, name="readiness", ready=True) -> TranscriptReadinessEvaluation:
        if ready:
            selection_outcome = CurrentSelectionOutcome.SELECTED
            applicability_outcome = ApplicabilityOutcome.APPLICABLE
        else:
            selection_outcome = CurrentSelectionOutcome.NOT_SELECTED
            applicability_outcome = ApplicabilityOutcome.NOT_APPLICABLE
        outcome, reason_code = evaluate_readiness_outcome(
            selection_outcome=selection_outcome,
            applicability_outcome=applicability_outcome,
            structural_valid=True,
        )
        record = TranscriptReadinessEvaluation(
            identity=TranscriptReadinessEvaluationId(name),
            domain_result_id=DomainResultId(f"{name}-result"),
            source_selection_id=TranscriptCurrentSelectionId("selection"),
            selection_outcome=selection_outcome,
            source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
            applicability_outcome=applicability_outcome,
            source_decision_id=TranscriptReviewDecisionId("decision"),
            review_item_id=ReviewItemId("item-0"),
            candidate_reference_id=CandidateReferenceId("candidate-0"),
            source_revision_id=self.revision.identity,
            validation_id=TranscriptValidationId("validation"),
            structural_valid=True,
            outcome=outcome,
            reason_code=reason_code,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="derived",
        )
        self.readiness.save(record)
        return record

    def _plan(self, name="input") -> LectureAnalysisInputIdentityPlan:
        return LectureAnalysisInputIdentityPlan(
            input_id=EligibleAnalysisInputId(name),
            input_result_id=DomainResultId(f"{name}-result"),
        )

    def _evaluate(self, readiness, **overrides):
        base = dict(
            source_readiness_id=readiness.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        base.update(overrides)
        return self.service.evaluate_input(**base)

    def test_ready_is_eligible_with_full_provenance(self) -> None:
        readiness = self._readiness(ready=True)
        prepared = self._evaluate(readiness)
        record = prepared.eligible_input
        self.assertIs(record.eligibility, LectureAnalysisEligibility.ELIGIBLE)
        self.assertIs(record.readiness_outcome, ReadinessOutcome.READY)
        self.assertEqual(record.source_readiness_id, readiness.identity)
        self.assertEqual(record.source_selection_id, TranscriptCurrentSelectionId("selection"))
        self.assertEqual(record.source_decision_id, TranscriptReviewDecisionId("decision"))
        self.assertEqual(record.review_item_id, ReviewItemId("item-0"))
        self.assertEqual(record.candidate_reference_id, CandidateReferenceId("candidate-0"))
        self.assertEqual(record.source_transcript_id, self.raw.identity)
        self.assertEqual(record.source_revision_id, self.revision.identity)
        self.assertEqual(record.source_media_id, self.media_id)
        self.assertEqual(record.source_timeline_id, self.timeline_id)
        self.assertEqual(record.validation_id, TranscriptValidationId("validation"))
        self.assertEqual(prepared.input_result.kind, "eligible_analysis_input")
        self.assertEqual(
            prepared.input_result.upstream_results, (readiness.domain_result_id,)
        )

    def test_not_ready_is_not_eligible(self) -> None:
        readiness = self._readiness(name="not-ready", ready=False)
        prepared = self._evaluate(readiness)
        self.assertIs(
            prepared.eligible_input.eligibility, LectureAnalysisEligibility.NOT_ELIGIBLE
        )

    def test_deterministic_construction(self) -> None:
        readiness = self._readiness()
        self.assertEqual(self._evaluate(readiness), self._evaluate(readiness))

    def test_unknown_readiness_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.service.evaluate_input(
                source_readiness_id=TranscriptReadinessEvaluationId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_requires_running_execution(self) -> None:
        readiness = self._readiness()
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(LectureAnalysisInputError):
            self._evaluate(readiness)

    def test_record_without_persistence_raises(self) -> None:
        readiness = self._readiness()
        with self.assertRaises(RuntimeError):
            self.service.record_input(
                source_readiness_id=readiness.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
