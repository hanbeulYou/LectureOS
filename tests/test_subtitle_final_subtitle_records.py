import unittest

from lectureos.application import (
    RULE_OVERLAP_ADJACENT,
    SubtitleAppliedOutcome,
    SubtitleFinalOutcome,
    SubtitleFinalSubtitle,
    SubtitleFinalSubtitleIdentityPlan,
    final_outcome_for_applied_outcome,
)
from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleDecisionRevisionId,
    SubtitleFinalSubtitleId,
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


def _final(**overrides) -> SubtitleFinalSubtitle:
    base = dict(
        identity=SubtitleFinalSubtitleId("final"),
        domain_result_id=DomainResultId("final-result"),
        source_decision_revision_id=SubtitleDecisionRevisionId("revision"),
        decision_kind=DecisionKind.ACCEPT,
        applied_outcome=SubtitleAppliedOutcome.ACCEPTED,
        final_outcome=SubtitleFinalOutcome.FINAL,
        source_review_decision_id=SubtitleReviewDecisionId("decision"),
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
        reason="selected the authoritative final subtitle representation",
        target_timed_unit_id=SubtitleTimedUnitId("timed"),
    )
    base.update(overrides)
    return SubtitleFinalSubtitle(**base)


class FinalOutcomeMappingTests(unittest.TestCase):
    def test_deterministic_selection(self) -> None:
        self.assertIs(
            final_outcome_for_applied_outcome(SubtitleAppliedOutcome.ACCEPTED),
            SubtitleFinalOutcome.FINAL,
        )
        self.assertIs(
            final_outcome_for_applied_outcome(SubtitleAppliedOutcome.MODIFIED),
            SubtitleFinalOutcome.FINAL,
        )
        self.assertIs(
            final_outcome_for_applied_outcome(SubtitleAppliedOutcome.REJECTED),
            SubtitleFinalOutcome.NOT_FINAL,
        )


class SubtitleFinalSubtitleTests(unittest.TestCase):
    def test_valid_accept_is_final(self) -> None:
        self.assertIs(_final().final_outcome, SubtitleFinalOutcome.FINAL)

    def test_valid_reject_is_not_final(self) -> None:
        final = _final(
            decision_kind=DecisionKind.REJECT,
            applied_outcome=SubtitleAppliedOutcome.REJECTED,
            final_outcome=SubtitleFinalOutcome.NOT_FINAL,
        )
        self.assertIs(final.final_outcome, SubtitleFinalOutcome.NOT_FINAL)

    def test_valid_modify_is_final_with_text(self) -> None:
        final = _final(
            decision_kind=DecisionKind.MODIFY,
            applied_outcome=SubtitleAppliedOutcome.MODIFIED,
            final_outcome=SubtitleFinalOutcome.FINAL,
            applied_text="corrected line",
        )
        self.assertIs(final.final_outcome, SubtitleFinalOutcome.FINAL)
        self.assertEqual(final.applied_text, "corrected line")

    def test_applied_outcome_must_match_kind(self) -> None:
        with self.assertRaises(ValueError):
            _final(
                decision_kind=DecisionKind.REJECT,
                applied_outcome=SubtitleAppliedOutcome.ACCEPTED,
            )

    def test_final_outcome_must_match_applied_outcome(self) -> None:
        with self.assertRaises(ValueError):
            _final(final_outcome=SubtitleFinalOutcome.NOT_FINAL)
        with self.assertRaises(ValueError):
            _final(
                decision_kind=DecisionKind.REJECT,
                applied_outcome=SubtitleAppliedOutcome.REJECTED,
                final_outcome=SubtitleFinalOutcome.FINAL,
            )

    def test_modified_requires_applied_text(self) -> None:
        with self.assertRaises(ValueError):
            _final(
                decision_kind=DecisionKind.MODIFY,
                applied_outcome=SubtitleAppliedOutcome.MODIFIED,
                final_outcome=SubtitleFinalOutcome.FINAL,
            )
        with self.assertRaises(ValueError):
            _final(
                decision_kind=DecisionKind.MODIFY,
                applied_outcome=SubtitleAppliedOutcome.MODIFIED,
                final_outcome=SubtitleFinalOutcome.FINAL,
                applied_text="  ",
            )

    def test_accept_reject_must_not_carry_applied_text(self) -> None:
        with self.assertRaises(ValueError):
            _final(applied_text="x")
        with self.assertRaises(ValueError):
            _final(
                decision_kind=DecisionKind.REJECT,
                applied_outcome=SubtitleAppliedOutcome.REJECTED,
                final_outcome=SubtitleFinalOutcome.NOT_FINAL,
                applied_text="x",
            )

    def test_final_level_null_target_allowed(self) -> None:
        self.assertIsNone(_final(target_timed_unit_id=None).target_timed_unit_id)

    def test_rule_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _final(rule="  ")

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _final(reason="  ")

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _final(sequence=-1)

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _final(sequence=0, previous_final_id=SubtitleFinalSubtitleId("earlier"))

    def test_later_may_reference_previous(self) -> None:
        final = _final(sequence=1, previous_final_id=SubtitleFinalSubtitleId("earlier"))
        self.assertEqual(final.previous_final_id, SubtitleFinalSubtitleId("earlier"))


class SubtitleFinalSubtitleIdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = SubtitleFinalSubtitleIdentityPlan(
            final_id=SubtitleFinalSubtitleId("final"),
            final_result_id=DomainResultId("final-result"),
        )
        self.assertEqual(plan.final_id, SubtitleFinalSubtitleId("final"))


if __name__ == "__main__":
    unittest.main()
