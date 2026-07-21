import unittest

from lectureos.application import (
    ReadinessOutcome,
    SubtitleIntakeIdentityPlan,
    SubtitleIntakeOutcome,
    SubtitleTranscriptIntake,
    intake_for_readiness_outcome,
)
from lectureos.application.identities import (
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)


def _intake(**overrides) -> SubtitleTranscriptIntake:
    base = dict(
        identity=SubtitleTranscriptIntakeId("intake"),
        domain_result_id=DomainResultId("intake-result"),
        source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
        readiness_outcome=ReadinessOutcome.READY,
        outcome=SubtitleIntakeOutcome.ELIGIBLE,
        source_selection_id=TranscriptCurrentSelectionId("selection"),
        source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
        source_decision_id=TranscriptReviewDecisionId("decision"),
        review_item_id=ReviewItemId("item"),
        candidate_reference_id=CandidateReferenceId("candidate"),
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("revision"),
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        validation_id=TranscriptValidationId("validation"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="ready transcript is eligible for subtitle work",
    )
    base.update(overrides)
    return SubtitleTranscriptIntake(**base)


class IntakeMappingTests(unittest.TestCase):
    def test_deterministic_mapping(self) -> None:
        self.assertIs(
            intake_for_readiness_outcome(ReadinessOutcome.READY),
            SubtitleIntakeOutcome.ELIGIBLE,
        )
        self.assertIs(
            intake_for_readiness_outcome(ReadinessOutcome.NOT_READY),
            SubtitleIntakeOutcome.NOT_ELIGIBLE,
        )


class SubtitleTranscriptIntakeRecordTests(unittest.TestCase):
    def test_valid_eligible(self) -> None:
        self.assertIs(_intake().outcome, SubtitleIntakeOutcome.ELIGIBLE)

    def test_valid_not_eligible(self) -> None:
        record = _intake(
            readiness_outcome=ReadinessOutcome.NOT_READY,
            outcome=SubtitleIntakeOutcome.NOT_ELIGIBLE,
            reason="transcript is not ready",
        )
        self.assertIs(record.outcome, SubtitleIntakeOutcome.NOT_ELIGIBLE)

    def test_outcome_must_match_readiness(self) -> None:
        with self.assertRaises(ValueError):
            _intake(
                readiness_outcome=ReadinessOutcome.NOT_READY,
                outcome=SubtitleIntakeOutcome.ELIGIBLE,
            )
        with self.assertRaises(ValueError):
            _intake(
                readiness_outcome=ReadinessOutcome.READY,
                outcome=SubtitleIntakeOutcome.NOT_ELIGIBLE,
            )

    def test_eligible_requires_ready(self) -> None:
        # The mapping guard already forbids this pairing; confirm it raises.
        with self.assertRaises(ValueError):
            _intake(
                readiness_outcome=ReadinessOutcome.NOT_READY,
                outcome=SubtitleIntakeOutcome.ELIGIBLE,
            )

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _intake(sequence=-1)

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _intake(reason="   ")

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _intake(
                sequence=0,
                previous_intake_id=SubtitleTranscriptIntakeId("earlier"),
            )

    def test_later_may_reference_previous(self) -> None:
        record = _intake(
            sequence=1, previous_intake_id=SubtitleTranscriptIntakeId("earlier")
        )
        self.assertEqual(
            record.previous_intake_id, SubtitleTranscriptIntakeId("earlier")
        )


class SubtitleIntakeIdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = SubtitleIntakeIdentityPlan(
            intake_id=SubtitleTranscriptIntakeId("intake"),
            intake_result_id=DomainResultId("intake-result"),
        )
        self.assertEqual(plan.intake_id, SubtitleTranscriptIntakeId("intake"))


if __name__ == "__main__":
    unittest.main()
