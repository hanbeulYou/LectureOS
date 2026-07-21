import unittest
from datetime import datetime, timezone

from lectureos.application import (
    ReviewDecisionIdentityPlan,
    TranscriptReviewDecision,
)
from lectureos.application.identities import TranscriptReviewDecisionId
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
from lectureos.transcript.identities import TranscriptRevisionId

WHEN = datetime(2026, 7, 22, 9, 0, tzinfo=timezone.utc)


def _decision(**overrides) -> TranscriptReviewDecision:
    base = dict(
        identity=TranscriptReviewDecisionId("decision"),
        domain_result_id=DomainResultId("decision-result"),
        review_item_id=ReviewItemId("item"),
        candidate_reference_id=CandidateReferenceId("candidate"),
        source_revision_id=TranscriptRevisionId("revision"),
        reviewer=HumanActorReference("reviewer"),
        kind=DecisionKind.ACCEPT,
        decided_at=WHEN,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
    )
    base.update(overrides)
    return TranscriptReviewDecision(**base)


class TranscriptReviewDecisionRecordTests(unittest.TestCase):
    def test_valid_accept_decision(self) -> None:
        decision = _decision()
        self.assertIs(decision.kind, DecisionKind.ACCEPT)
        self.assertIsNone(decision.modified_text)

    def test_reviewer_must_be_human(self) -> None:
        with self.assertRaises(ValueError):
            _decision(reviewer="plain-string")

    def test_timestamp_must_be_timezone_aware(self) -> None:
        with self.assertRaises(ValueError):
            _decision(decided_at=datetime(2026, 7, 22, 9, 0))

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _decision(sequence=-1)

    def test_modify_requires_modified_text(self) -> None:
        with self.assertRaises(ValueError):
            _decision(kind=DecisionKind.MODIFY)
        with self.assertRaises(ValueError):
            _decision(kind=DecisionKind.MODIFY, modified_text="  ")
        ok = _decision(kind=DecisionKind.MODIFY, modified_text="corrected text")
        self.assertEqual(ok.modified_text, "corrected text")

    def test_accept_and_reject_forbid_modified_text(self) -> None:
        with self.assertRaises(ValueError):
            _decision(kind=DecisionKind.ACCEPT, modified_text="x")
        with self.assertRaises(ValueError):
            _decision(kind=DecisionKind.REJECT, modified_text="x")
        self.assertIsNone(_decision(kind=DecisionKind.REJECT).modified_text)

    def test_blank_rationale_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _decision(rationale="   ")
        self.assertEqual(_decision(rationale="valid").rationale, "valid")

    def test_first_decision_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _decision(
                sequence=0,
                previous_decision_id=TranscriptReviewDecisionId("earlier"),
            )

    def test_later_decision_may_reference_previous(self) -> None:
        decision = _decision(
            sequence=1,
            previous_decision_id=TranscriptReviewDecisionId("earlier"),
        )
        self.assertEqual(
            decision.previous_decision_id, TranscriptReviewDecisionId("earlier")
        )


class ReviewDecisionIdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = ReviewDecisionIdentityPlan(
            decision_id=TranscriptReviewDecisionId("decision"),
            decision_result_id=DomainResultId("decision-result"),
            decided_at=WHEN,
        )
        self.assertEqual(plan.decided_at, WHEN)

    def test_plan_timestamp_must_be_timezone_aware(self) -> None:
        with self.assertRaises(ValueError):
            ReviewDecisionIdentityPlan(
                decision_id=TranscriptReviewDecisionId("decision"),
                decision_result_id=DomainResultId("decision-result"),
                decided_at=datetime(2026, 7, 22, 9, 0),
            )


if __name__ == "__main__":
    unittest.main()
