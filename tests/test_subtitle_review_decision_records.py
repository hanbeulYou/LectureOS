import unittest
from datetime import datetime, timezone

from lectureos.application import (
    RULE_OVERLAP_ADJACENT,
    SubtitleReviewDecision,
    SubtitleReviewDecisionIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimeRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.review.identities import (
    CandidateReferenceId,
    HumanActorReference,
    ReviewItemId,
)
from lectureos.review.models import DecisionKind

WHEN = datetime(2026, 7, 22, 21, 0, tzinfo=timezone.utc)
NAIVE = datetime(2026, 7, 22, 21, 0)


def _decision(**overrides) -> SubtitleReviewDecision:
    base = dict(
        identity=SubtitleReviewDecisionId("decision"),
        domain_result_id=DomainResultId("decision-result"),
        review_item_id=ReviewItemId("item"),
        candidate_reference_id=CandidateReferenceId("reference"),
        source_preparation_id=SubtitleReviewPreparationId("preparation"),
        source_validation_id=SubtitleValidationId("validation"),
        source_time_revision_id=SubtitleTimeRevisionId("time"),
        source_finding_id=SubtitleValidationFindingId("finding"),
        rule=RULE_OVERLAP_ADJACENT,
        reviewer=HumanActorReference("reviewer"),
        kind=DecisionKind.ACCEPT,
        decided_at=WHEN,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
    )
    base.update(overrides)
    return SubtitleReviewDecision(**base)


class SubtitleReviewDecisionTests(unittest.TestCase):
    def test_valid_accept(self) -> None:
        self.assertIs(_decision().kind, DecisionKind.ACCEPT)

    def test_valid_reject(self) -> None:
        self.assertIs(_decision(kind=DecisionKind.REJECT).kind, DecisionKind.REJECT)

    def test_valid_modify_with_text(self) -> None:
        decision = _decision(kind=DecisionKind.MODIFY, modified_text="corrected line")
        self.assertEqual(decision.modified_text, "corrected line")

    def test_modify_requires_text(self) -> None:
        with self.assertRaises(ValueError):
            _decision(kind=DecisionKind.MODIFY)
        with self.assertRaises(ValueError):
            _decision(kind=DecisionKind.MODIFY, modified_text="   ")

    def test_accept_reject_must_not_carry_text(self) -> None:
        with self.assertRaises(ValueError):
            _decision(kind=DecisionKind.ACCEPT, modified_text="x")
        with self.assertRaises(ValueError):
            _decision(kind=DecisionKind.REJECT, modified_text="x")

    def test_reviewer_must_be_human(self) -> None:
        with self.assertRaises(ValueError):
            _decision(reviewer="not-a-human-ref")

    def test_rule_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _decision(rule="  ")

    def test_timestamp_must_be_timezone_aware(self) -> None:
        with self.assertRaises(ValueError):
            _decision(decided_at=NAIVE)

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _decision(sequence=-1)

    def test_rationale_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _decision(rationale="  ")

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _decision(
                sequence=0, previous_decision_id=SubtitleReviewDecisionId("earlier")
            )

    def test_later_may_reference_previous(self) -> None:
        decision = _decision(
            sequence=1, previous_decision_id=SubtitleReviewDecisionId("earlier")
        )
        self.assertEqual(
            decision.previous_decision_id, SubtitleReviewDecisionId("earlier")
        )


class SubtitleReviewDecisionIdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = SubtitleReviewDecisionIdentityPlan(
            decision_id=SubtitleReviewDecisionId("decision"),
            decision_result_id=DomainResultId("decision-result"),
            decided_at=WHEN,
        )
        self.assertEqual(plan.decided_at, WHEN)

    def test_timestamp_must_be_timezone_aware(self) -> None:
        with self.assertRaises(ValueError):
            SubtitleReviewDecisionIdentityPlan(
                decision_id=SubtitleReviewDecisionId("decision"),
                decision_result_id=DomainResultId("decision-result"),
                decided_at=NAIVE,
            )


if __name__ == "__main__":
    unittest.main()
