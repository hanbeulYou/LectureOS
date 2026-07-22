import unittest

from lectureos.application import (
    SubtitleTimeIdentityPlan,
    SubtitleTimeRevision,
    SubtitleTimedUnit,
    SubtitleTimingStatus,
)
from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
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


def _unit(**overrides) -> SubtitleTimedUnit:
    base = dict(
        identity=SubtitleTimedUnitId("timed-0"),
        time_revision_id=SubtitleTimeRevisionId("time"),
        source_reading_unit_id=SubtitleReadingUnitId("reading-unit-0"),
        display_order=0,
        timing_status=SubtitleTimingStatus.ANCHORED,
        source_timeline_id=SourceTimelineId("timeline"),
        start=0.0,
        end=1.0,
    )
    base.update(overrides)
    return SubtitleTimedUnit(**base)


def _revision(**overrides) -> SubtitleTimeRevision:
    base = dict(
        identity=SubtitleTimeRevisionId("time"),
        domain_result_id=DomainResultId("time-result"),
        source_reading_revision_id=SubtitleReadingRevisionId("reading"),
        source_candidate_id=SubtitleCandidateId("candidate"),
        source_intake_id=SubtitleTranscriptIntakeId("intake"),
        source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
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
        timed_unit_ids=(SubtitleTimedUnitId("timed-0"),),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="baseline time revision anchored from reading revision",
    )
    base.update(overrides)
    return SubtitleTimeRevision(**base)


class SubtitleTimedUnitTests(unittest.TestCase):
    def test_valid_anchored_unit(self) -> None:
        self.assertIs(_unit().timing_status, SubtitleTimingStatus.ANCHORED)

    def test_valid_unresolved_unit(self) -> None:
        unit = _unit(
            timing_status=SubtitleTimingStatus.UNRESOLVED,
            source_timeline_id=None,
            start=None,
            end=None,
        )
        self.assertIsNone(unit.start)

    def test_anchored_requires_full_range(self) -> None:
        with self.assertRaises(ValueError):
            _unit(start=None, end=None, source_timeline_id=None)
        with self.assertRaises(ValueError):
            _unit(start=0.0, end=None)
        with self.assertRaises(ValueError):
            _unit(source_timeline_id=None)

    def test_unresolved_must_not_carry_range(self) -> None:
        with self.assertRaises(ValueError):
            _unit(timing_status=SubtitleTimingStatus.UNRESOLVED)
        with self.assertRaises(ValueError):
            _unit(
                timing_status=SubtitleTimingStatus.UNRESOLVED,
                source_timeline_id=None,
                start=1.0,
                end=2.0,
            )

    def test_display_order_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _unit(display_order=-1)

    def test_start_after_end_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _unit(start=2.0, end=1.0)

    def test_negative_range_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _unit(start=-1.0, end=1.0)


class SubtitleTimeRevisionTests(unittest.TestCase):
    def test_valid_revision(self) -> None:
        self.assertEqual(len(_revision().timed_unit_ids), 1)

    def test_partially_timed_aggregate_allowed(self) -> None:
        # A revision may mix ANCHORED and UNRESOLVED timed units.
        revision = _revision(
            timed_unit_ids=(
                SubtitleTimedUnitId("timed-0"),
                SubtitleTimedUnitId("timed-1"),
            )
        )
        anchored = _unit()
        unresolved = _unit(
            identity=SubtitleTimedUnitId("timed-1"),
            display_order=1,
            timing_status=SubtitleTimingStatus.UNRESOLVED,
            source_timeline_id=None,
            start=None,
            end=None,
        )
        self.assertEqual(len(revision.timed_unit_ids), 2)
        self.assertIs(anchored.timing_status, SubtitleTimingStatus.ANCHORED)
        self.assertIs(unresolved.timing_status, SubtitleTimingStatus.UNRESOLVED)

    def test_requires_a_unit(self) -> None:
        with self.assertRaises(ValueError):
            _revision(timed_unit_ids=())

    def test_unit_ids_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            _revision(
                timed_unit_ids=(
                    SubtitleTimedUnitId("timed-0"),
                    SubtitleTimedUnitId("timed-0"),
                )
            )

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _revision(sequence=-1)

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _revision(reason="  ")

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _revision(
                sequence=0,
                previous_time_revision_id=SubtitleTimeRevisionId("earlier"),
            )

    def test_later_may_reference_previous(self) -> None:
        revision = _revision(
            sequence=1,
            previous_time_revision_id=SubtitleTimeRevisionId("earlier"),
        )
        self.assertEqual(
            revision.previous_time_revision_id, SubtitleTimeRevisionId("earlier")
        )


class SubtitleTimeIdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = SubtitleTimeIdentityPlan(
            time_revision_id=SubtitleTimeRevisionId("time"),
            time_result_id=DomainResultId("time-result"),
            timed_unit_ids=(SubtitleTimedUnitId("timed-0"),),
        )
        self.assertEqual(len(plan.timed_unit_ids), 1)

    def test_requires_unit_ids(self) -> None:
        with self.assertRaises(ValueError):
            SubtitleTimeIdentityPlan(
                time_revision_id=SubtitleTimeRevisionId("time"),
                time_result_id=DomainResultId("time-result"),
                timed_unit_ids=(),
            )

    def test_unit_ids_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            SubtitleTimeIdentityPlan(
                time_revision_id=SubtitleTimeRevisionId("time"),
                time_result_id=DomainResultId("time-result"),
                timed_unit_ids=(
                    SubtitleTimedUnitId("timed-0"),
                    SubtitleTimedUnitId("timed-0"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
