import unittest
from dataclasses import replace

from lectureos.application import (
    ReviewItemGroup,
    ReviewPreparationIdentityPlan,
    ReviewPreparationTargetIdentityPlan,
    TranscriptReviewPreparation,
)
from lectureos.application.identities import TranscriptReviewPreparationId
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
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId


def _preparation(**overrides) -> TranscriptReviewPreparation:
    items = (ReviewItemId("item-0"), ReviewItemId("item-1"))
    base = dict(
        identity=TranscriptReviewPreparationId("prep"),
        domain_result_id=DomainResultId("prep-result"),
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("revision"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        context_id=ReviewContextId("context"),
        candidate_reference_ids=(
            CandidateReferenceId("candidate-0"),
            CandidateReferenceId("candidate-1"),
        ),
        ordered_item_ids=items,
        groups=(
            ReviewItemGroup("segment-0", (items[0],)),
            ReviewItemGroup("segment-1", (items[1],)),
        ),
        item_count=2,
        structural_valid=True,
        provenance_complete=True,
        ordering_valid=True,
    )
    base.update(overrides)
    return TranscriptReviewPreparation(**base)


class ReviewItemGroupTests(unittest.TestCase):
    def test_rejects_blank_key_and_empty_membership(self) -> None:
        with self.assertRaises(ValueError):
            ReviewItemGroup(" ", (ReviewItemId("item-0"),))
        with self.assertRaises(ValueError):
            ReviewItemGroup("segment-0", ())

    def test_rejects_repeated_member(self) -> None:
        item = ReviewItemId("item-0")
        with self.assertRaises(ValueError):
            ReviewItemGroup("segment-0", (item, item))


class TranscriptReviewPreparationTests(unittest.TestCase):
    def test_valid_preparation_round_trips(self) -> None:
        preparation = _preparation()
        self.assertEqual(preparation.item_count, 2)
        self.assertEqual(len(preparation.groups), 2)

    def test_requires_at_least_one_item(self) -> None:
        with self.assertRaises(ValueError):
            _preparation(
                item_count=0,
                ordered_item_ids=(),
                candidate_reference_ids=(),
                groups=(),
            )

    def test_counts_must_match(self) -> None:
        with self.assertRaises(ValueError):
            _preparation(item_count=3)
        with self.assertRaises(ValueError):
            _preparation(
                candidate_reference_ids=(CandidateReferenceId("candidate-0"),)
            )

    def test_ordered_items_must_be_unique(self) -> None:
        duplicated = (ReviewItemId("item-0"), ReviewItemId("item-0"))
        with self.assertRaises(ValueError):
            _preparation(
                ordered_item_ids=duplicated,
                groups=(ReviewItemGroup("segment-0", (ReviewItemId("item-0"),)),),
            )

    def test_grouped_items_must_match_ordered_items(self) -> None:
        items = (ReviewItemId("item-0"), ReviewItemId("item-1"))
        with self.assertRaises(ValueError):
            _preparation(
                ordered_item_ids=items,
                groups=(
                    ReviewItemGroup("segment-0", (items[0],)),
                    ReviewItemGroup("segment-x", (ReviewItemId("item-9"),)),
                ),
            )

    def test_requires_at_least_one_group(self) -> None:
        with self.assertRaises(ValueError):
            _preparation(groups=())


class ReviewPreparationIdentityPlanTests(unittest.TestCase):
    def _target(self, index: int) -> ReviewPreparationTargetIdentityPlan:
        return ReviewPreparationTargetIdentityPlan(
            candidate_reference_id=CandidateReferenceId(f"candidate-{index}"),
            review_item_id=ReviewItemId(f"item-{index}"),
        )

    def _plan(self, targets) -> ReviewPreparationIdentityPlan:
        return ReviewPreparationIdentityPlan(
            preparation_id=TranscriptReviewPreparationId("prep"),
            preparation_result_id=DomainResultId("prep-result"),
            context_id=ReviewContextId("context"),
            targets=targets,
        )

    def test_requires_targets(self) -> None:
        with self.assertRaises(ValueError):
            self._plan(())

    def test_rejects_duplicate_candidate_reference(self) -> None:
        target = self._target(0)
        with self.assertRaises(ValueError):
            self._plan((target, replace(target, review_item_id=ReviewItemId("item-1"))))

    def test_rejects_duplicate_review_item(self) -> None:
        target = self._target(0)
        with self.assertRaises(ValueError):
            self._plan(
                (
                    target,
                    replace(
                        target,
                        candidate_reference_id=CandidateReferenceId("candidate-1"),
                    ),
                )
            )

    def test_accepts_unique_targets(self) -> None:
        plan = self._plan((self._target(0), self._target(1)))
        self.assertEqual(len(plan.targets), 2)


if __name__ == "__main__":
    unittest.main()
