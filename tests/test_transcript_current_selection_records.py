import unittest

from lectureos.application import (
    ApplicabilityOutcome,
    CurrentSelectionIdentityPlan,
    CurrentSelectionOutcome,
    TranscriptCurrentSelection,
    selection_for_applicability_outcome,
)
from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReviewDecisionId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import TranscriptRevisionId


def _selection(**overrides) -> TranscriptCurrentSelection:
    base = dict(
        identity=TranscriptCurrentSelectionId("selection"),
        domain_result_id=DomainResultId("selection-result"),
        source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
        applicability_outcome=ApplicabilityOutcome.APPLICABLE,
        outcome=CurrentSelectionOutcome.SELECTED,
        source_decision_id=TranscriptReviewDecisionId("decision"),
        review_item_id=ReviewItemId("item"),
        candidate_reference_id=CandidateReferenceId("candidate"),
        source_revision_id=TranscriptRevisionId("revision"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="applicable revision is currently selected",
    )
    base.update(overrides)
    return TranscriptCurrentSelection(**base)


class SelectionMappingTests(unittest.TestCase):
    def test_deterministic_mapping(self) -> None:
        self.assertIs(
            selection_for_applicability_outcome(ApplicabilityOutcome.APPLICABLE),
            CurrentSelectionOutcome.SELECTED,
        )
        self.assertIs(
            selection_for_applicability_outcome(ApplicabilityOutcome.NOT_APPLICABLE),
            CurrentSelectionOutcome.NOT_SELECTED,
        )
        self.assertIs(
            selection_for_applicability_outcome(
                ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION
            ),
            CurrentSelectionOutcome.NOT_SELECTED,
        )


class TranscriptCurrentSelectionRecordTests(unittest.TestCase):
    def test_valid_selected(self) -> None:
        selection = _selection()
        self.assertIs(selection.outcome, CurrentSelectionOutcome.SELECTED)

    def test_not_selected_outcomes(self) -> None:
        rejected = _selection(
            applicability_outcome=ApplicabilityOutcome.NOT_APPLICABLE,
            outcome=CurrentSelectionOutcome.NOT_SELECTED,
            reason="not applicable so not selected",
        )
        self.assertIs(rejected.outcome, CurrentSelectionOutcome.NOT_SELECTED)
        modified = _selection(
            applicability_outcome=ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION,
            outcome=CurrentSelectionOutcome.NOT_SELECTED,
            reason="superseded so not selected",
        )
        self.assertIs(modified.outcome, CurrentSelectionOutcome.NOT_SELECTED)

    def test_outcome_must_match_applicability(self) -> None:
        with self.assertRaises(ValueError):
            _selection(
                applicability_outcome=ApplicabilityOutcome.NOT_APPLICABLE,
                outcome=CurrentSelectionOutcome.SELECTED,
            )
        with self.assertRaises(ValueError):
            _selection(
                applicability_outcome=ApplicabilityOutcome.APPLICABLE,
                outcome=CurrentSelectionOutcome.NOT_SELECTED,
            )

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _selection(sequence=-1)

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _selection(reason="   ")

    def test_first_selection_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _selection(
                sequence=0,
                previous_selection_id=TranscriptCurrentSelectionId("earlier"),
            )

    def test_later_selection_may_reference_previous(self) -> None:
        selection = _selection(
            sequence=1,
            previous_selection_id=TranscriptCurrentSelectionId("earlier"),
        )
        self.assertEqual(
            selection.previous_selection_id,
            TranscriptCurrentSelectionId("earlier"),
        )


class CurrentSelectionIdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = CurrentSelectionIdentityPlan(
            selection_id=TranscriptCurrentSelectionId("selection"),
            selection_result_id=DomainResultId("selection-result"),
        )
        self.assertEqual(
            plan.selection_id, TranscriptCurrentSelectionId("selection")
        )


if __name__ == "__main__":
    unittest.main()
