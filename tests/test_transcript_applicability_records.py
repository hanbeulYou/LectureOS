import unittest

from lectureos.application import (
    ApplicabilityEvaluationIdentityPlan,
    ApplicabilityOutcome,
    TranscriptApplicabilityEvaluation,
    outcome_for_decision_kind,
)
from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptRevisionId


def _evaluation(**overrides) -> TranscriptApplicabilityEvaluation:
    base = dict(
        identity=TranscriptApplicabilityEvaluationId("evaluation"),
        domain_result_id=DomainResultId("evaluation-result"),
        source_decision_id=TranscriptReviewDecisionId("decision"),
        decision_kind=DecisionKind.ACCEPT,
        outcome=ApplicabilityOutcome.APPLICABLE,
        review_item_id=ReviewItemId("item"),
        candidate_reference_id=CandidateReferenceId("candidate"),
        source_revision_id=TranscriptRevisionId("revision"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="accepted revision is applicable",
    )
    base.update(overrides)
    return TranscriptApplicabilityEvaluation(**base)


class OutcomeMappingTests(unittest.TestCase):
    def test_deterministic_mapping(self) -> None:
        self.assertIs(
            outcome_for_decision_kind(DecisionKind.ACCEPT),
            ApplicabilityOutcome.APPLICABLE,
        )
        self.assertIs(
            outcome_for_decision_kind(DecisionKind.REJECT),
            ApplicabilityOutcome.NOT_APPLICABLE,
        )
        self.assertIs(
            outcome_for_decision_kind(DecisionKind.MODIFY),
            ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION,
        )


class TranscriptApplicabilityEvaluationRecordTests(unittest.TestCase):
    def test_valid_accept_evaluation(self) -> None:
        evaluation = _evaluation()
        self.assertIs(evaluation.outcome, ApplicabilityOutcome.APPLICABLE)

    def test_reject_and_modify_evaluations(self) -> None:
        reject = _evaluation(
            decision_kind=DecisionKind.REJECT,
            outcome=ApplicabilityOutcome.NOT_APPLICABLE,
            reason="rejected revision is not applicable",
        )
        self.assertIs(reject.outcome, ApplicabilityOutcome.NOT_APPLICABLE)
        modify = _evaluation(
            decision_kind=DecisionKind.MODIFY,
            outcome=ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION,
            reason="modified revision is superseded",
        )
        self.assertIs(modify.outcome, ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION)

    def test_outcome_must_match_decision_kind(self) -> None:
        with self.assertRaises(ValueError):
            _evaluation(
                decision_kind=DecisionKind.REJECT,
                outcome=ApplicabilityOutcome.APPLICABLE,
            )
        with self.assertRaises(ValueError):
            _evaluation(
                decision_kind=DecisionKind.ACCEPT,
                outcome=ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION,
            )

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _evaluation(sequence=-1)

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _evaluation(reason="   ")

    def test_first_evaluation_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _evaluation(
                sequence=0,
                previous_evaluation_id=TranscriptApplicabilityEvaluationId("earlier"),
            )

    def test_later_evaluation_may_reference_previous(self) -> None:
        evaluation = _evaluation(
            sequence=1,
            previous_evaluation_id=TranscriptApplicabilityEvaluationId("earlier"),
        )
        self.assertEqual(
            evaluation.previous_evaluation_id,
            TranscriptApplicabilityEvaluationId("earlier"),
        )


class ApplicabilityEvaluationIdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = ApplicabilityEvaluationIdentityPlan(
            evaluation_id=TranscriptApplicabilityEvaluationId("evaluation"),
            evaluation_result_id=DomainResultId("evaluation-result"),
        )
        self.assertEqual(
            plan.evaluation_id, TranscriptApplicabilityEvaluationId("evaluation")
        )


if __name__ == "__main__":
    unittest.main()
