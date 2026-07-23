import unittest

from lectureos.application import (
    LectureAnalysisEligibility,
    LectureSegmentationApplicationService,
    LectureSegmentError,
    LectureSegmentIdentityPlan,
    NormalizedLectureSegment,
    NormalizedSegmentationResult,
)
from lectureos.application.lecture_segment import LECTURE_SEGMENT_RESULT_KIND
from lectureos.application.identities import (
    EligibleAnalysisInputId,
    LectureSegmentId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.application.lecture_analysis_input import EligibleAnalysisInput
from lectureos.application.transcript_readiness_evaluation import ReadinessOutcome
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
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)

_MEDIA = SourceMediaId("media")
_TIMELINE = SourceTimelineId("timeline")
_OTHER_TIMELINE = SourceTimelineId("other-timeline")


def _eligible_input(name="input", eligible=True) -> EligibleAnalysisInput:
    outcome = ReadinessOutcome.READY if eligible else ReadinessOutcome.NOT_READY
    eligibility = (
        LectureAnalysisEligibility.ELIGIBLE
        if eligible
        else LectureAnalysisEligibility.NOT_ELIGIBLE
    )
    return EligibleAnalysisInput(
        identity=EligibleAnalysisInputId(name),
        domain_result_id=DomainResultId(f"{name}-result"),
        source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
        readiness_outcome=outcome,
        eligibility=eligibility,
        source_selection_id=TranscriptCurrentSelectionId("selection"),
        source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
        source_decision_id=TranscriptReviewDecisionId("decision"),
        review_item_id=ReviewItemId("item-0"),
        candidate_reference_id=CandidateReferenceId("candidate-0"),
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("revision"),
        source_media_id=_MEDIA,
        source_timeline_id=_TIMELINE,
        validation_id=TranscriptValidationId("validation"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="derived",
    )


class LectureSegmentationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="lecture-segmentation",
                capabilities=(CapabilityReference("lecture.segmentation"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("lecture-segmentation"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.inputs = InMemoryRepository()
        self.eligible = _eligible_input()
        self.inputs.save(self.eligible)
        self.service = LectureSegmentationApplicationService(self.inputs, self.execution)

    def _plans(self, *names):
        return tuple(
            LectureSegmentIdentityPlan(
                segment_id=LectureSegmentId(name),
                segment_result_id=DomainResultId(f"{name}-result"),
            )
            for name in names
        )

    def _result(self, *segments, timeline=_TIMELINE):
        return NormalizedSegmentationResult(
            source_timeline_id=timeline, segments=segments
        )

    def _segment(self, start=0.0, end=5.0):
        return NormalizedLectureSegment(range_start=start, range_end=end)

    def _evaluate(self, result, plans, **overrides):
        base = dict(
            source_input_id=self.eligible.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=result,
            identities=plans,
        )
        base.update(overrides)
        return self.service.evaluate_segments(**base)

    def test_successful_admission_from_eligible_input(self) -> None:
        prepared = self._evaluate(
            self._result(self._segment(1.0, 2.0)), self._plans("segment-0")
        )
        self.assertEqual(len(prepared.segments), 1)
        segment = prepared.segments[0].segment
        self.assertEqual(segment.source_input_id, self.eligible.identity)
        self.assertEqual(segment.range_start, 1.0)
        self.assertEqual(segment.range_end, 2.0)
        self.assertEqual(segment.source_media_id, _MEDIA)
        self.assertEqual(segment.source_timeline_id, _TIMELINE)
        self.assertEqual(segment.sequence, 0)
        reference = prepared.segments[0].segment_result
        self.assertEqual(reference.kind, LECTURE_SEGMENT_RESULT_KIND)
        self.assertEqual(reference.upstream_results, (self.eligible.domain_result_id,))
        self.assertEqual(reference.source_timeline, _TIMELINE)

    def test_multiple_segments_get_ordered_sequences(self) -> None:
        prepared = self._evaluate(
            self._result(self._segment(0.0, 10.0), self._segment(10.0, 20.0)),
            self._plans("segment-0", "segment-1"),
        )
        self.assertEqual([s.segment.sequence for s in prepared.segments], [0, 1])

    def test_deterministic_construction(self) -> None:
        result = self._result(self._segment(0.0, 3.0))
        first = self._evaluate(result, self._plans("segment-0"))
        second = self._evaluate(result, self._plans("segment-0"))
        self.assertEqual(first, second)

    def test_provenance_inherited_from_input(self) -> None:
        prepared = self._evaluate(self._result(self._segment()), self._plans("segment-0"))
        segment = prepared.segments[0].segment
        self.assertEqual(segment.source_media_id, self.eligible.source_media_id)
        self.assertEqual(segment.source_timeline_id, self.eligible.source_timeline_id)

    def test_not_eligible_input_is_rejected(self) -> None:
        not_eligible = _eligible_input("input-not-eligible", eligible=False)
        self.inputs.save(not_eligible)
        with self.assertRaises(LectureSegmentError):
            self._evaluate(
                self._result(self._segment()),
                self._plans("segment-0"),
                source_input_id=not_eligible.identity,
            )

    def test_unknown_input_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._evaluate(
                self._result(self._segment()),
                self._plans("segment-0"),
                source_input_id=EligibleAnalysisInputId("missing"),
            )

    def test_requires_running_execution(self) -> None:
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(LectureSegmentError):
            self._evaluate(self._result(self._segment()), self._plans("segment-0"))

    def test_mismatched_timeline_lineage_is_rejected(self) -> None:
        result = self._result(self._segment(), timeline=_OTHER_TIMELINE)
        with self.assertRaises(LectureSegmentError):
            self._evaluate(result, self._plans("segment-0"))

    def test_identity_plan_count_must_match_segments(self) -> None:
        result = self._result(self._segment(0.0, 1.0), self._segment(1.0, 2.0))
        with self.assertRaises(LectureSegmentError):
            self._evaluate(result, self._plans("segment-0"))

    def test_empty_normalized_result_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._result()

    def test_invalid_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._segment(3.0, 1.0)

    def test_upstream_input_not_mutated(self) -> None:
        before = self.inputs.get(self.eligible.identity)
        self._evaluate(self._result(self._segment()), self._plans("segment-0"))
        self.assertEqual(self.inputs.get(self.eligible.identity), before)

    def test_record_without_persistence_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            self.service.record_segments(
                source_input_id=self.eligible.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                result=self._result(self._segment()),
                identities=self._plans("segment-0"),
            )


if __name__ == "__main__":
    unittest.main()
