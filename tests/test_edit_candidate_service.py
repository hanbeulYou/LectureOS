import unittest

from lectureos.application import (
    EditCandidateApplicationService,
    EditCandidateError,
    EditCandidateIdentityPlan,
    NormalizedCandidateResult,
    NormalizedEditCandidate,
)
from lectureos.application.edit_candidate import EDIT_CANDIDATE_RESULT_KIND
from lectureos.application.analysis_finding import AnalysisFinding
from lectureos.application.identities import (
    AnalysisFindingId,
    EditCandidateId,
    EligibleAnalysisInputId,
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

_MEDIA = SourceMediaId("media")
_TIMELINE = SourceTimelineId("timeline")
_OTHER_TIMELINE = SourceTimelineId("other-timeline")


def _finding(name="finding", located=True) -> AnalysisFinding:
    kwargs = dict(
        identity=AnalysisFindingId(name),
        domain_result_id=DomainResultId(f"{name}-result"),
        source_input_id=EligibleAnalysisInputId("input"),
        finding_type="low_educational_value",
        evidence="an off-topic aside appears mid-lecture",
        source_media_id=_MEDIA,
        source_timeline_id=_TIMELINE,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
    )
    if located:
        kwargs.update(range_start=1.0, range_end=2.0)
    return AnalysisFinding(**kwargs)


class EditCandidateServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="edit-candidate",
                capabilities=(CapabilityReference("lecture.edit_candidate"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("edit-candidate"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.findings = InMemoryRepository()
        self.finding = _finding()
        self.findings.save(self.finding)
        self.service = EditCandidateApplicationService(self.findings, self.execution)

    def _plans(self, *names):
        return tuple(
            EditCandidateIdentityPlan(
                candidate_id=EditCandidateId(name),
                candidate_result_id=DomainResultId(f"{name}-result"),
            )
            for name in names
        )

    def _result(self, *candidates, timeline=_TIMELINE):
        return NormalizedCandidateResult(
            source_timeline_id=timeline, candidates=candidates
        )

    def _candidate(self, candidate_type="review", start=0.0, end=5.0):
        return NormalizedEditCandidate(
            candidate_type=candidate_type,
            rationale="propose review of a possible non-lecture region",
            range_start=start,
            range_end=end,
        )

    def _evaluate(self, result, plans, **overrides):
        base = dict(
            source_finding_id=self.finding.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=result,
            identities=plans,
        )
        base.update(overrides)
        return self.service.evaluate_candidates(**base)

    def test_successful_admission_from_finding(self) -> None:
        prepared = self._evaluate(
            self._result(self._candidate(start=4.0, end=9.0)), self._plans("candidate-0")
        )
        self.assertEqual(len(prepared.candidates), 1)
        candidate = prepared.candidates[0].candidate
        self.assertEqual(candidate.source_finding_id, self.finding.identity)
        self.assertEqual(candidate.candidate_type, "review")
        self.assertEqual(candidate.range_start, 4.0)
        self.assertEqual(candidate.range_end, 9.0)
        self.assertEqual(candidate.source_media_id, _MEDIA)
        self.assertEqual(candidate.source_timeline_id, _TIMELINE)
        self.assertEqual(candidate.sequence, 0)
        reference = prepared.candidates[0].candidate_result
        self.assertEqual(reference.kind, EDIT_CANDIDATE_RESULT_KIND)
        self.assertEqual(reference.upstream_results, (self.finding.domain_result_id,))
        self.assertEqual(reference.source_timeline, _TIMELINE)

    def test_multiple_candidates_from_one_finding(self) -> None:
        prepared = self._evaluate(
            self._result(self._candidate("review", 0.0, 5.0), self._candidate("condense", 5.0, 9.0)),
            self._plans("candidate-0", "candidate-1"),
        )
        self.assertEqual([c.candidate.sequence for c in prepared.candidates], [0, 1])
        self.assertEqual(
            [c.candidate.candidate_type for c in prepared.candidates],
            ["review", "condense"],
        )

    def test_candidate_from_finding_without_range(self) -> None:
        # A Candidate carries a required range even when the anchoring Finding has none.
        non_located = _finding("finding-unlocated", located=False)
        self.findings.save(non_located)
        self.assertIsNone(non_located.range_start)
        prepared = self._evaluate(
            self._result(self._candidate(start=2.0, end=8.0)),
            self._plans("candidate-0"),
            source_finding_id=non_located.identity,
        )
        candidate = prepared.candidates[0].candidate
        self.assertEqual(candidate.range_start, 2.0)
        self.assertEqual(candidate.range_end, 8.0)

    def test_deterministic_construction(self) -> None:
        result = self._result(self._candidate())
        first = self._evaluate(result, self._plans("candidate-0"))
        second = self._evaluate(result, self._plans("candidate-0"))
        self.assertEqual(first, second)

    def test_unknown_finding_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._evaluate(
                self._result(self._candidate()),
                self._plans("candidate-0"),
                source_finding_id=AnalysisFindingId("missing"),
            )

    def test_requires_running_execution(self) -> None:
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(EditCandidateError):
            self._evaluate(self._result(self._candidate()), self._plans("candidate-0"))

    def test_mismatched_timeline_lineage_is_rejected(self) -> None:
        result = self._result(self._candidate(), timeline=_OTHER_TIMELINE)
        with self.assertRaises(EditCandidateError):
            self._evaluate(result, self._plans("candidate-0"))

    def test_identity_plan_count_must_match_candidates(self) -> None:
        result = self._result(self._candidate("review"), self._candidate("condense"))
        with self.assertRaises(EditCandidateError):
            self._evaluate(result, self._plans("candidate-0"))

    def test_empty_normalized_result_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._result()

    def test_invalid_candidate_type_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._candidate("Remove Clip")

    def test_blank_rationale_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NormalizedEditCandidate(
                candidate_type="review", rationale="  ", range_start=0.0, range_end=1.0
            )

    def test_invalid_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._candidate(start=5.0, end=1.0)

    def test_upstream_finding_not_mutated(self) -> None:
        before = self.findings.get(self.finding.identity)
        self._evaluate(self._result(self._candidate()), self._plans("candidate-0"))
        self.assertEqual(self.findings.get(self.finding.identity), before)

    def test_no_segment_dependency_in_provenance(self) -> None:
        prepared = self._evaluate(self._result(self._candidate()), self._plans("candidate-0"))
        candidate = prepared.candidates[0].candidate
        self.assertFalse(hasattr(candidate, "lecture_segment_id"))
        self.assertFalse(hasattr(candidate, "source_input_id"))
        self.assertEqual(
            prepared.candidates[0].candidate_result.upstream_results,
            (self.finding.domain_result_id,),
        )

    def test_record_without_persistence_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            self.service.record_candidates(
                source_finding_id=self.finding.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                result=self._result(self._candidate()),
                identities=self._plans("candidate-0"),
            )


if __name__ == "__main__":
    unittest.main()
