import unittest

from lectureos.application import (
    RULE_OVERLAP_ADJACENT,
    SubtitleAppliedOutcome,
    SubtitleDecisionRevision,
    SubtitleDecisionRevisionIdentityPlan,
    applied_outcome_for_kind,
)
from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleDecisionRevisionId,
    SubtitleReadingRevisionId,
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId


def _revision(**overrides) -> SubtitleDecisionRevision:
    base = dict(
        identity=SubtitleDecisionRevisionId("revision"),
        domain_result_id=DomainResultId("revision-result"),
        source_review_decision_id=SubtitleReviewDecisionId("decision"),
        decision_kind=DecisionKind.ACCEPT,
        outcome=SubtitleAppliedOutcome.ACCEPTED,
        review_item_id=ReviewItemId("item"),
        candidate_reference_id=CandidateReferenceId("reference"),
        source_preparation_id=SubtitleReviewPreparationId("preparation"),
        source_validation_id=SubtitleValidationId("validation"),
        source_time_revision_id=SubtitleTimeRevisionId("time"),
        source_reading_revision_id=SubtitleReadingRevisionId("reading"),
        source_candidate_id=SubtitleCandidateId("candidate"),
        source_finding_id=SubtitleValidationFindingId("finding"),
        rule=RULE_OVERLAP_ADJACENT,
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("transcript-revision"),
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="applied review decision into next subtitle revision",
        target_timed_unit_id=SubtitleTimedUnitId("timed"),
    )
    base.update(overrides)
    return SubtitleDecisionRevision(**base)


class AppliedOutcomeTests(unittest.TestCase):
    def test_deterministic_mapping(self) -> None:
        self.assertIs(applied_outcome_for_kind(DecisionKind.ACCEPT), SubtitleAppliedOutcome.ACCEPTED)
        self.assertIs(applied_outcome_for_kind(DecisionKind.REJECT), SubtitleAppliedOutcome.REJECTED)
        self.assertIs(applied_outcome_for_kind(DecisionKind.MODIFY), SubtitleAppliedOutcome.MODIFIED)


class SubtitleDecisionRevisionTests(unittest.TestCase):
    def test_valid_accept(self) -> None:
        self.assertIs(_revision().outcome, SubtitleAppliedOutcome.ACCEPTED)

    def test_valid_reject(self) -> None:
        revision = _revision(decision_kind=DecisionKind.REJECT, outcome=SubtitleAppliedOutcome.REJECTED)
        self.assertIs(revision.outcome, SubtitleAppliedOutcome.REJECTED)

    def test_valid_modify_with_text(self) -> None:
        revision = _revision(
            decision_kind=DecisionKind.MODIFY,
            outcome=SubtitleAppliedOutcome.MODIFIED,
            applied_text="corrected line",
        )
        self.assertEqual(revision.applied_text, "corrected line")

    def test_outcome_must_match_kind(self) -> None:
        with self.assertRaises(ValueError):
            _revision(decision_kind=DecisionKind.REJECT, outcome=SubtitleAppliedOutcome.ACCEPTED)

    def test_modified_requires_applied_text(self) -> None:
        with self.assertRaises(ValueError):
            _revision(decision_kind=DecisionKind.MODIFY, outcome=SubtitleAppliedOutcome.MODIFIED)
        with self.assertRaises(ValueError):
            _revision(
                decision_kind=DecisionKind.MODIFY,
                outcome=SubtitleAppliedOutcome.MODIFIED,
                applied_text="  ",
            )

    def test_accept_reject_must_not_carry_applied_text(self) -> None:
        with self.assertRaises(ValueError):
            _revision(applied_text="x")
        with self.assertRaises(ValueError):
            _revision(
                decision_kind=DecisionKind.REJECT,
                outcome=SubtitleAppliedOutcome.REJECTED,
                applied_text="x",
            )

    def test_revision_level_null_target_allowed(self) -> None:
        self.assertIsNone(_revision(target_timed_unit_id=None).target_timed_unit_id)

    def test_rule_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _revision(rule="  ")

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _revision(reason="  ")

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _revision(sequence=-1)

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _revision(
                sequence=0, previous_revision_id=SubtitleDecisionRevisionId("earlier")
            )

    def test_later_may_reference_previous(self) -> None:
        revision = _revision(
            sequence=1, previous_revision_id=SubtitleDecisionRevisionId("earlier")
        )
        self.assertEqual(
            revision.previous_revision_id, SubtitleDecisionRevisionId("earlier")
        )


class SubtitleDecisionRevisionIdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = SubtitleDecisionRevisionIdentityPlan(
            revision_id=SubtitleDecisionRevisionId("revision"),
            revision_result_id=DomainResultId("revision-result"),
        )
        self.assertEqual(plan.revision_id, SubtitleDecisionRevisionId("revision"))


if __name__ == "__main__":
    unittest.main()
