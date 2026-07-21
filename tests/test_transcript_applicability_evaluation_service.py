import unittest
from datetime import datetime, timezone

from lectureos.application import (
    ApplicabilityEvaluationIdentityPlan,
    ApplicabilityOutcome,
    TranscriptApplicabilityEvaluationError,
    TranscriptApplicabilityEvaluationService,
)
from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.application.transcript_review_decision import TranscriptReviewDecision
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
    ReviewItemId,
)
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptRevisionId

WHEN = datetime(2026, 7, 22, 13, 0, tzinfo=timezone.utc)


class TranscriptApplicabilityEvaluationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        capability = CapabilityReference("transcript.correction")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(identity=unit_id, purpose="apply", capabilities=(capability,))
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("apply"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.decisions = InMemoryRepository()
        self.service = TranscriptApplicabilityEvaluationService(
            self.decisions, self.execution
        )

    def _decision(self, name="decision", kind=DecisionKind.ACCEPT) -> TranscriptReviewDecision:
        modified = "revised" if kind is DecisionKind.MODIFY else None
        decision = TranscriptReviewDecision(
            identity=TranscriptReviewDecisionId(name),
            domain_result_id=DomainResultId(f"{name}-result"),
            review_item_id=ReviewItemId("item-0"),
            candidate_reference_id=CandidateReferenceId("candidate-0"),
            source_revision_id=TranscriptRevisionId("revision"),
            reviewer=HumanActorReference("reviewer"),
            kind=kind,
            decided_at=WHEN,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            modified_text=modified,
        )
        self.decisions.save(decision)
        return decision

    def _plan(self, name="evaluation") -> ApplicabilityEvaluationIdentityPlan:
        return ApplicabilityEvaluationIdentityPlan(
            evaluation_id=TranscriptApplicabilityEvaluationId(name),
            evaluation_result_id=DomainResultId(f"{name}-result"),
        )

    def _evaluate(self, decision, **overrides):
        base = dict(
            source_decision_id=decision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        base.update(overrides)
        return self.service.evaluate_applicability(**base)

    def test_accept_derives_applicable_with_full_linkage(self) -> None:
        decision = self._decision(kind=DecisionKind.ACCEPT)
        prepared = self._evaluate(decision)
        evaluation = prepared.evaluation
        self.assertIs(evaluation.outcome, ApplicabilityOutcome.APPLICABLE)
        self.assertIs(evaluation.decision_kind, DecisionKind.ACCEPT)
        self.assertEqual(evaluation.source_decision_id, decision.identity)
        self.assertEqual(evaluation.review_item_id, ReviewItemId("item-0"))
        self.assertEqual(
            evaluation.candidate_reference_id, CandidateReferenceId("candidate-0")
        )
        self.assertEqual(evaluation.source_revision_id, TranscriptRevisionId("revision"))
        self.assertEqual(evaluation.run_id, self.run_id)
        self.assertEqual(evaluation.unit_execution_id, self.execution_id)
        self.assertEqual(
            prepared.evaluation_result.kind, "transcript_applicability_evaluation"
        )
        self.assertEqual(
            prepared.evaluation_result.upstream_results,
            (decision.domain_result_id,),
        )

    def test_reject_derives_not_applicable(self) -> None:
        decision = self._decision(name="reject", kind=DecisionKind.REJECT)
        prepared = self._evaluate(decision)
        self.assertIs(prepared.evaluation.outcome, ApplicabilityOutcome.NOT_APPLICABLE)

    def test_modify_derives_superseded(self) -> None:
        decision = self._decision(name="modify", kind=DecisionKind.MODIFY)
        prepared = self._evaluate(decision)
        self.assertIs(
            prepared.evaluation.outcome,
            ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION,
        )

    def test_deterministic_construction(self) -> None:
        decision = self._decision()
        self.assertEqual(self._evaluate(decision), self._evaluate(decision))

    def test_unknown_decision_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.service.evaluate_applicability(
                source_decision_id=TranscriptReviewDecisionId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_requires_running_execution(self) -> None:
        decision = self._decision()
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(TranscriptApplicabilityEvaluationError):
            self._evaluate(decision)

    def test_record_without_persistence_raises(self) -> None:
        decision = self._decision()
        with self.assertRaises(RuntimeError):
            self.service.record_evaluation(
                source_decision_id=decision.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
