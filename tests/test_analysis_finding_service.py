import unittest

from lectureos.application import (
    AnalysisFindingApplicationService,
    AnalysisFindingError,
    AnalysisFindingIdentityPlan,
    LectureAnalysisEligibility,
    NormalizedAnalysisFinding,
    NormalizedAnalysisResult,
)
from lectureos.application.analysis_finding import ANALYSIS_FINDING_RESULT_KIND
from lectureos.application.identities import (
    AnalysisFindingId,
    EligibleAnalysisInputId,
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
    if eligible:
        outcome = ReadinessOutcome.READY
        eligibility = LectureAnalysisEligibility.ELIGIBLE
        timeline = _TIMELINE
    else:
        outcome = ReadinessOutcome.NOT_READY
        eligibility = LectureAnalysisEligibility.NOT_ELIGIBLE
        timeline = _TIMELINE
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
        source_timeline_id=timeline,
        validation_id=TranscriptValidationId("validation"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="derived",
    )


class AnalysisFindingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="analysis-finding",
                capabilities=(CapabilityReference("lecture.analysis"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("analysis-finding"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.inputs = InMemoryRepository()
        self.eligible = _eligible_input()
        self.inputs.save(self.eligible)
        self.service = AnalysisFindingApplicationService(self.inputs, self.execution)

    def _plans(self, *names):
        return tuple(
            AnalysisFindingIdentityPlan(
                finding_id=AnalysisFindingId(name),
                finding_result_id=DomainResultId(f"{name}-result"),
            )
            for name in names
        )

    def _result(self, *findings, timeline=_TIMELINE):
        return NormalizedAnalysisResult(source_timeline_id=timeline, findings=findings)

    def _finding(self, finding_type="terminology_drift", **overrides):
        base = dict(finding_type=finding_type, evidence="the speaker misnames the theorem")
        base.update(overrides)
        return NormalizedAnalysisFinding(**base)

    def _evaluate(self, result, plans, **overrides):
        base = dict(
            source_input_id=self.eligible.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=result,
            identities=plans,
        )
        base.update(overrides)
        return self.service.evaluate_findings(**base)

    def test_successful_admission_from_eligible_input(self) -> None:
        result = self._result(self._finding(confidence=0.8, range_start=1.0, range_end=2.0))
        prepared = self._evaluate(result, self._plans("finding-0"))
        self.assertEqual(len(prepared.findings), 1)
        finding = prepared.findings[0].finding
        self.assertEqual(finding.source_input_id, self.eligible.identity)
        self.assertEqual(finding.finding_type, "terminology_drift")
        self.assertEqual(finding.evidence, "the speaker misnames the theorem")
        self.assertEqual(finding.confidence, 0.8)
        self.assertEqual(finding.range_start, 1.0)
        self.assertEqual(finding.range_end, 2.0)
        self.assertEqual(finding.source_media_id, _MEDIA)
        self.assertEqual(finding.source_timeline_id, _TIMELINE)
        self.assertEqual(finding.sequence, 0)
        reference = prepared.findings[0].finding_result
        self.assertEqual(reference.kind, ANALYSIS_FINDING_RESULT_KIND)
        self.assertEqual(reference.upstream_results, (self.eligible.domain_result_id,))
        self.assertEqual(reference.source_timeline, _TIMELINE)

    def test_multiple_findings_get_ordered_sequences(self) -> None:
        result = self._result(
            self._finding("terminology_drift"),
            self._finding("missing_definition"),
        )
        prepared = self._evaluate(result, self._plans("finding-0", "finding-1"))
        self.assertEqual(
            [f.finding.sequence for f in prepared.findings], [0, 1]
        )
        self.assertEqual(
            [f.finding.finding_type for f in prepared.findings],
            ["terminology_drift", "missing_definition"],
        )

    def test_finding_without_confidence_or_range_is_admitted(self) -> None:
        prepared = self._evaluate(self._result(self._finding()), self._plans("finding-0"))
        finding = prepared.findings[0].finding
        self.assertIsNone(finding.confidence)
        self.assertIsNone(finding.uncertainty)
        self.assertIsNone(finding.range_start)
        self.assertIsNone(finding.range_end)

    def test_uncertainty_only_is_admitted(self) -> None:
        prepared = self._evaluate(
            self._result(self._finding(uncertainty=0.4)), self._plans("finding-0")
        )
        self.assertEqual(prepared.findings[0].finding.uncertainty, 0.4)

    def test_deterministic_construction(self) -> None:
        result = self._result(self._finding(confidence=0.5))
        first = self._evaluate(result, self._plans("finding-0"))
        second = self._evaluate(result, self._plans("finding-0"))
        self.assertEqual(first, second)

    def test_not_eligible_input_is_rejected(self) -> None:
        not_eligible = _eligible_input("input-not-eligible", eligible=False)
        self.inputs.save(not_eligible)
        with self.assertRaises(AnalysisFindingError):
            self._evaluate(
                self._result(self._finding()),
                self._plans("finding-0"),
                source_input_id=not_eligible.identity,
            )

    def test_unknown_input_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._evaluate(
                self._result(self._finding()),
                self._plans("finding-0"),
                source_input_id=EligibleAnalysisInputId("missing"),
            )

    def test_requires_running_execution(self) -> None:
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(AnalysisFindingError):
            self._evaluate(self._result(self._finding()), self._plans("finding-0"))

    def test_mismatched_timeline_lineage_is_rejected(self) -> None:
        result = self._result(self._finding(), timeline=_OTHER_TIMELINE)
        with self.assertRaises(AnalysisFindingError):
            self._evaluate(result, self._plans("finding-0"))

    def test_identity_plan_count_must_match_findings(self) -> None:
        result = self._result(self._finding("a"), self._finding("b"))
        with self.assertRaises(AnalysisFindingError):
            self._evaluate(result, self._plans("finding-0"))

    def test_empty_normalized_result_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._result()

    def test_invalid_finding_type_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._finding("Possible Error (0.83)")

    def test_invalid_evidence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._finding(evidence="   ")

    def test_invalid_confidence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._finding(confidence=1.5)

    def test_invalid_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._finding(range_start=3.0, range_end=1.0)

    def test_no_provider_specific_data_on_canonical_record(self) -> None:
        prepared = self._evaluate(self._result(self._finding()), self._plans("finding-0"))
        finding = prepared.findings[0].finding
        field_names = set(type(finding).__dataclass_fields__)
        for forbidden in ("model", "prompt", "provider", "raw", "tokens", "response"):
            self.assertNotIn(forbidden, field_names)

    def test_record_without_persistence_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            self.service.record_findings(
                source_input_id=self.eligible.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                result=self._result(self._finding()),
                identities=self._plans("finding-0"),
            )


if __name__ == "__main__":
    unittest.main()
