import unittest

from lectureos.application import (
    ApplicabilityOutcome,
    CurrentSelectionIdentityPlan,
    CurrentSelectionOutcome,
    TranscriptCurrentSelectionError,
    TranscriptCurrentSelectionService,
)
from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReviewDecisionId,
)
from lectureos.application.transcript_applicability_evaluation import (
    TranscriptApplicabilityEvaluation,
    outcome_for_decision_kind,
)
from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import ExecutionIntent, ProcessingUnit
from lectureos.execution.repositories import InMemoryRepository
from lectureos.execution.service import ExecutionService
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptRevisionId


class TranscriptCurrentSelectionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        capability = CapabilityReference("transcript.correction")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(identity=unit_id, purpose="select", capabilities=(capability,))
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("select"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.evaluations = InMemoryRepository()
        self.service = TranscriptCurrentSelectionService(
            self.evaluations, self.execution
        )

    def _evaluation(
        self, name="evaluation", kind=DecisionKind.ACCEPT
    ) -> TranscriptApplicabilityEvaluation:
        evaluation = TranscriptApplicabilityEvaluation(
            identity=TranscriptApplicabilityEvaluationId(name),
            domain_result_id=DomainResultId(f"{name}-result"),
            source_decision_id=TranscriptReviewDecisionId("decision"),
            decision_kind=kind,
            outcome=outcome_for_decision_kind(kind),
            review_item_id=ReviewItemId("item-0"),
            candidate_reference_id=CandidateReferenceId("candidate-0"),
            source_revision_id=TranscriptRevisionId("revision"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="derived",
        )
        self.evaluations.save(evaluation)
        return evaluation

    def _plan(self, name="selection") -> CurrentSelectionIdentityPlan:
        return CurrentSelectionIdentityPlan(
            selection_id=TranscriptCurrentSelectionId(name),
            selection_result_id=DomainResultId(f"{name}-result"),
        )

    def _select(self, evaluation, **overrides):
        base = dict(
            source_applicability_id=evaluation.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        base.update(overrides)
        return self.service.evaluate_selection(**base)

    def test_applicable_is_selected_with_full_linkage(self) -> None:
        evaluation = self._evaluation(kind=DecisionKind.ACCEPT)
        prepared = self._select(evaluation)
        selection = prepared.selection
        self.assertIs(selection.outcome, CurrentSelectionOutcome.SELECTED)
        self.assertIs(selection.applicability_outcome, ApplicabilityOutcome.APPLICABLE)
        self.assertEqual(selection.source_applicability_id, evaluation.identity)
        self.assertEqual(selection.source_decision_id, TranscriptReviewDecisionId("decision"))
        self.assertEqual(selection.review_item_id, ReviewItemId("item-0"))
        self.assertEqual(
            selection.candidate_reference_id, CandidateReferenceId("candidate-0")
        )
        self.assertEqual(selection.source_revision_id, TranscriptRevisionId("revision"))
        self.assertEqual(selection.run_id, self.run_id)
        self.assertEqual(selection.unit_execution_id, self.execution_id)
        self.assertEqual(
            prepared.selection_result.kind, "transcript_current_selection"
        )
        self.assertEqual(
            prepared.selection_result.upstream_results,
            (evaluation.domain_result_id,),
        )

    def test_rejected_is_not_selected(self) -> None:
        evaluation = self._evaluation(name="reject", kind=DecisionKind.REJECT)
        prepared = self._select(evaluation)
        self.assertIs(prepared.selection.outcome, CurrentSelectionOutcome.NOT_SELECTED)

    def test_modified_is_not_selected(self) -> None:
        evaluation = self._evaluation(name="modify", kind=DecisionKind.MODIFY)
        prepared = self._select(evaluation)
        self.assertIs(prepared.selection.outcome, CurrentSelectionOutcome.NOT_SELECTED)

    def test_deterministic_construction(self) -> None:
        evaluation = self._evaluation()
        self.assertEqual(self._select(evaluation), self._select(evaluation))

    def test_unknown_evaluation_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.service.evaluate_selection(
                source_applicability_id=TranscriptApplicabilityEvaluationId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_requires_running_execution(self) -> None:
        evaluation = self._evaluation()
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(TranscriptCurrentSelectionError):
            self._select(evaluation)

    def test_record_without_persistence_raises(self) -> None:
        evaluation = self._evaluation()
        with self.assertRaises(RuntimeError):
            self.service.record_selection(
                source_applicability_id=evaluation.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
