import unittest

from lectureos.application import (
    ApplicabilityOutcome,
    CurrentSelectionOutcome,
    ReadinessEvaluationIdentityPlan,
    ReadinessOutcome,
    ReadinessReasonCode,
    TranscriptReadinessEvaluation,
    evaluate_readiness_outcome,
)
from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import TranscriptRevisionId, TranscriptValidationId


def _readiness(**overrides) -> TranscriptReadinessEvaluation:
    base = dict(
        identity=TranscriptReadinessEvaluationId("readiness"),
        domain_result_id=DomainResultId("readiness-result"),
        source_selection_id=TranscriptCurrentSelectionId("selection"),
        selection_outcome=CurrentSelectionOutcome.SELECTED,
        source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
        applicability_outcome=ApplicabilityOutcome.APPLICABLE,
        source_decision_id=TranscriptReviewDecisionId("decision"),
        review_item_id=ReviewItemId("item"),
        candidate_reference_id=CandidateReferenceId("candidate"),
        source_revision_id=TranscriptRevisionId("revision"),
        validation_id=TranscriptValidationId("validation"),
        structural_valid=True,
        outcome=ReadinessOutcome.READY,
        reason_code=ReadinessReasonCode.ALL_CONDITIONS_MET,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="all readiness conditions met",
    )
    base.update(overrides)
    return TranscriptReadinessEvaluation(**base)


class ReadinessMappingTests(unittest.TestCase):
    def test_selected_applicable_valid_is_ready(self) -> None:
        self.assertEqual(
            evaluate_readiness_outcome(
                selection_outcome=CurrentSelectionOutcome.SELECTED,
                applicability_outcome=ApplicabilityOutcome.APPLICABLE,
                structural_valid=True,
            ),
            (ReadinessOutcome.READY, ReadinessReasonCode.ALL_CONDITIONS_MET),
        )

    def test_selected_but_invalid_is_not_ready(self) -> None:
        self.assertEqual(
            evaluate_readiness_outcome(
                selection_outcome=CurrentSelectionOutcome.SELECTED,
                applicability_outcome=ApplicabilityOutcome.APPLICABLE,
                structural_valid=False,
            ),
            (
                ReadinessOutcome.NOT_READY,
                ReadinessReasonCode.STRUCTURAL_VALIDATION_FAILED,
            ),
        )

    def test_not_selected_reasons(self) -> None:
        self.assertEqual(
            evaluate_readiness_outcome(
                selection_outcome=CurrentSelectionOutcome.NOT_SELECTED,
                applicability_outcome=ApplicabilityOutcome.NOT_APPLICABLE,
                structural_valid=True,
            ),
            (ReadinessOutcome.NOT_READY, ReadinessReasonCode.NOT_APPLICABLE),
        )
        self.assertEqual(
            evaluate_readiness_outcome(
                selection_outcome=CurrentSelectionOutcome.NOT_SELECTED,
                applicability_outcome=ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION,
                structural_valid=True,
            ),
            (
                ReadinessOutcome.NOT_READY,
                ReadinessReasonCode.SUPERSEDED_BY_MODIFICATION,
            ),
        )


class TranscriptReadinessEvaluationRecordTests(unittest.TestCase):
    def test_valid_ready(self) -> None:
        self.assertIs(_readiness().outcome, ReadinessOutcome.READY)

    def test_valid_not_ready_variants(self) -> None:
        invalid = _readiness(
            structural_valid=False,
            outcome=ReadinessOutcome.NOT_READY,
            reason_code=ReadinessReasonCode.STRUCTURAL_VALIDATION_FAILED,
            reason="revision failed structural validation",
        )
        self.assertIs(invalid.outcome, ReadinessOutcome.NOT_READY)
        rejected = _readiness(
            selection_outcome=CurrentSelectionOutcome.NOT_SELECTED,
            applicability_outcome=ApplicabilityOutcome.NOT_APPLICABLE,
            outcome=ReadinessOutcome.NOT_READY,
            reason_code=ReadinessReasonCode.NOT_APPLICABLE,
            reason="revision is not applicable",
        )
        self.assertIs(rejected.outcome, ReadinessOutcome.NOT_READY)

    def test_ready_requires_selected(self) -> None:
        with self.assertRaises(ValueError):
            _readiness(
                selection_outcome=CurrentSelectionOutcome.NOT_SELECTED,
                applicability_outcome=ApplicabilityOutcome.NOT_APPLICABLE,
                outcome=ReadinessOutcome.READY,
                reason_code=ReadinessReasonCode.ALL_CONDITIONS_MET,
            )

    def test_ready_requires_structural_valid(self) -> None:
        with self.assertRaises(ValueError):
            _readiness(
                structural_valid=False,
                outcome=ReadinessOutcome.READY,
                reason_code=ReadinessReasonCode.ALL_CONDITIONS_MET,
            )

    def test_outcome_reason_must_match_deterministic_evaluation(self) -> None:
        with self.assertRaises(ValueError):
            _readiness(reason_code=ReadinessReasonCode.NOT_SELECTED)
        with self.assertRaises(ValueError):
            _readiness(
                outcome=ReadinessOutcome.NOT_READY,
                reason_code=ReadinessReasonCode.ALL_CONDITIONS_MET,
            )

    def test_not_ready_must_not_record_all_conditions_met(self) -> None:
        with self.assertRaises(ValueError):
            _readiness(
                selection_outcome=CurrentSelectionOutcome.NOT_SELECTED,
                applicability_outcome=ApplicabilityOutcome.NOT_APPLICABLE,
                outcome=ReadinessOutcome.NOT_READY,
                reason_code=ReadinessReasonCode.ALL_CONDITIONS_MET,
            )

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _readiness(sequence=-1)

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _readiness(reason="   ")

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _readiness(
                sequence=0,
                previous_readiness_id=TranscriptReadinessEvaluationId("earlier"),
            )


class ReadinessEvaluationIdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = ReadinessEvaluationIdentityPlan(
            readiness_id=TranscriptReadinessEvaluationId("readiness"),
            readiness_result_id=DomainResultId("readiness-result"),
            validation_id=TranscriptValidationId("validation"),
        )
        self.assertEqual(
            plan.readiness_id, TranscriptReadinessEvaluationId("readiness")
        )


if __name__ == "__main__":
    unittest.main()
