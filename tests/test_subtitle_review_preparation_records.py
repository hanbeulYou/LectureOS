import unittest

from lectureos.application import (
    RULE_OVERLAP_ADJACENT,
    SubtitleReviewItemLink,
    SubtitleReviewPreparation,
    SubtitleReviewPreparationIdentityPlan,
    SubtitleReviewTargetIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleTranscriptIntakeId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
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
from lectureos.review.identities import (
    CandidateReferenceId,
    ReviewContextId,
    ReviewItemId,
)
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)


def _link(index=0) -> SubtitleReviewItemLink:
    return SubtitleReviewItemLink(
        review_item_id=ReviewItemId(f"item-{index}"),
        candidate_reference_id=CandidateReferenceId(f"reference-{index}"),
        source_finding_id=SubtitleValidationFindingId(f"finding-{index}"),
        rule=RULE_OVERLAP_ADJACENT,
        target_timed_unit_id=SubtitleTimedUnitId(f"timed-{index}"),
    )


def _preparation(**overrides) -> SubtitleReviewPreparation:
    links = overrides.pop("item_links", (_link(0),))
    base = dict(
        identity=SubtitleReviewPreparationId("preparation"),
        domain_result_id=DomainResultId("preparation-result"),
        source_validation_id=SubtitleValidationId("validation"),
        source_time_revision_id=SubtitleTimeRevisionId("time"),
        source_reading_revision_id=SubtitleReadingRevisionId("reading"),
        source_candidate_id=SubtitleCandidateId("candidate"),
        source_intake_id=SubtitleTranscriptIntakeId("intake"),
        source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
        source_selection_id=TranscriptCurrentSelectionId("selection"),
        source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
        source_decision_id=TranscriptReviewDecisionId("decision"),
        source_review_item_id=ReviewItemId("source-item"),
        source_candidate_reference_id=CandidateReferenceId("source-reference"),
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("revision"),
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        source_transcript_validation_id=TranscriptValidationId("transcript-validation"),
        context_id=ReviewContextId("context"),
        item_links=links,
        item_count=len(links),
        source_structural_valid=False,
        provenance_complete=True,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="review preparation for the validation findings",
    )
    base.update(overrides)
    return SubtitleReviewPreparation(**base)


class SubtitleReviewItemLinkTests(unittest.TestCase):
    def test_valid_link(self) -> None:
        self.assertEqual(_link().rule, RULE_OVERLAP_ADJACENT)

    def test_rule_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            SubtitleReviewItemLink(
                review_item_id=ReviewItemId("item"),
                candidate_reference_id=CandidateReferenceId("reference"),
                source_finding_id=SubtitleValidationFindingId("finding"),
                rule="  ",
            )

    def test_null_target_allowed(self) -> None:
        link = SubtitleReviewItemLink(
            review_item_id=ReviewItemId("item"),
            candidate_reference_id=CandidateReferenceId("reference"),
            source_finding_id=SubtitleValidationFindingId("finding"),
            rule=RULE_OVERLAP_ADJACENT,
            target_timed_unit_id=None,
        )
        self.assertIsNone(link.target_timed_unit_id)


class SubtitleReviewPreparationTests(unittest.TestCase):
    def test_valid_preparation(self) -> None:
        self.assertEqual(_preparation().item_count, 1)

    def test_empty_preparation_is_valid(self) -> None:
        preparation = _preparation(
            item_links=(), source_structural_valid=True
        )
        self.assertEqual(preparation.item_count, 0)
        self.assertEqual(preparation.item_links, ())

    def test_multiple_items(self) -> None:
        preparation = _preparation(item_links=(_link(0), _link(1)))
        self.assertEqual(preparation.item_count, 2)

    def test_item_count_must_match_links(self) -> None:
        with self.assertRaises(ValueError):
            _preparation(item_links=(_link(0),), item_count=2)

    def test_review_item_ids_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            _preparation(item_links=(_link(0), _link(0)))

    def test_source_finding_ids_must_be_unique(self) -> None:
        duplicate = SubtitleReviewItemLink(
            review_item_id=ReviewItemId("item-1"),
            candidate_reference_id=CandidateReferenceId("reference-1"),
            source_finding_id=SubtitleValidationFindingId("finding-0"),
            rule=RULE_OVERLAP_ADJACENT,
        )
        with self.assertRaises(ValueError):
            _preparation(item_links=(_link(0), duplicate))

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _preparation(sequence=-1)

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _preparation(reason="  ")

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _preparation(
                sequence=0,
                previous_preparation_id=SubtitleReviewPreparationId("earlier"),
            )

    def test_later_may_reference_previous(self) -> None:
        preparation = _preparation(
            sequence=1,
            previous_preparation_id=SubtitleReviewPreparationId("earlier"),
        )
        self.assertEqual(
            preparation.previous_preparation_id,
            SubtitleReviewPreparationId("earlier"),
        )


class SubtitleReviewPreparationIdentityPlanTests(unittest.TestCase):
    def test_valid_plan_with_targets(self) -> None:
        plan = SubtitleReviewPreparationIdentityPlan(
            preparation_id=SubtitleReviewPreparationId("preparation"),
            preparation_result_id=DomainResultId("preparation-result"),
            context_id=ReviewContextId("context"),
            targets=(
                SubtitleReviewTargetIdentityPlan(
                    candidate_reference_id=CandidateReferenceId("reference-0"),
                    review_item_id=ReviewItemId("item-0"),
                ),
            ),
        )
        self.assertEqual(len(plan.targets), 1)

    def test_empty_targets_allowed(self) -> None:
        plan = SubtitleReviewPreparationIdentityPlan(
            preparation_id=SubtitleReviewPreparationId("preparation"),
            preparation_result_id=DomainResultId("preparation-result"),
            context_id=ReviewContextId("context"),
        )
        self.assertEqual(plan.targets, ())

    def test_review_item_plan_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            SubtitleReviewPreparationIdentityPlan(
                preparation_id=SubtitleReviewPreparationId("preparation"),
                preparation_result_id=DomainResultId("preparation-result"),
                context_id=ReviewContextId("context"),
                targets=(
                    SubtitleReviewTargetIdentityPlan(
                        candidate_reference_id=CandidateReferenceId("reference-0"),
                        review_item_id=ReviewItemId("item-0"),
                    ),
                    SubtitleReviewTargetIdentityPlan(
                        candidate_reference_id=CandidateReferenceId("reference-1"),
                        review_item_id=ReviewItemId("item-0"),
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
