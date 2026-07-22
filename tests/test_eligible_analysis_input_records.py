import unittest

from lectureos.application import (
    EligibleAnalysisInput,
    LectureAnalysisEligibility,
    LectureAnalysisInputIdentityPlan,
    ReadinessOutcome,
    eligibility_for_readiness_outcome,
)
from lectureos.application.identities import (
    EligibleAnalysisInputId,
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


def _input(**overrides) -> EligibleAnalysisInput:
    base = dict(
        identity=EligibleAnalysisInputId("input"),
        domain_result_id=DomainResultId("input-result"),
        source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
        readiness_outcome=ReadinessOutcome.READY,
        eligibility=LectureAnalysisEligibility.ELIGIBLE,
        source_selection_id=TranscriptCurrentSelectionId("selection"),
        source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
        source_decision_id=TranscriptReviewDecisionId("decision"),
        review_item_id=ReviewItemId("item"),
        candidate_reference_id=CandidateReferenceId("reference"),
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("revision"),
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        validation_id=TranscriptValidationId("validation"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="validated selected transcript is an eligible lecture analysis input",
    )
    base.update(overrides)
    return EligibleAnalysisInput(**base)


class EligibilityMappingTests(unittest.TestCase):
    def test_deterministic_mapping(self) -> None:
        self.assertIs(
            eligibility_for_readiness_outcome(ReadinessOutcome.READY),
            LectureAnalysisEligibility.ELIGIBLE,
        )
        self.assertIs(
            eligibility_for_readiness_outcome(ReadinessOutcome.NOT_READY),
            LectureAnalysisEligibility.NOT_ELIGIBLE,
        )


class EligibleAnalysisInputTests(unittest.TestCase):
    def test_valid_eligible(self) -> None:
        self.assertIs(_input().eligibility, LectureAnalysisEligibility.ELIGIBLE)

    def test_valid_not_eligible(self) -> None:
        record = _input(
            readiness_outcome=ReadinessOutcome.NOT_READY,
            eligibility=LectureAnalysisEligibility.NOT_ELIGIBLE,
        )
        self.assertIs(record.eligibility, LectureAnalysisEligibility.NOT_ELIGIBLE)

    def test_eligibility_must_match_readiness(self) -> None:
        with self.assertRaises(ValueError):
            _input(readiness_outcome=ReadinessOutcome.NOT_READY)
        with self.assertRaises(ValueError):
            _input(
                readiness_outcome=ReadinessOutcome.READY,
                eligibility=LectureAnalysisEligibility.NOT_ELIGIBLE,
            )

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _input(reason="  ")

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _input(sequence=-1)

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _input(sequence=0, previous_input_id=EligibleAnalysisInputId("earlier"))

    def test_later_may_reference_previous(self) -> None:
        record = _input(sequence=1, previous_input_id=EligibleAnalysisInputId("earlier"))
        self.assertEqual(record.previous_input_id, EligibleAnalysisInputId("earlier"))


class IdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = LectureAnalysisInputIdentityPlan(
            input_id=EligibleAnalysisInputId("input"),
            input_result_id=DomainResultId("input-result"),
        )
        self.assertEqual(plan.input_id, EligibleAnalysisInputId("input"))


if __name__ == "__main__":
    unittest.main()
