import unittest

from lectureos.application import (
    SubtitleReadingIdentityPlan,
    SubtitleReadingRevision,
    SubtitleReadingUnit,
    compose_reading_lines,
)
from lectureos.application.identities import (
    SubtitleCandidateCueId,
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
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


def _unit(**overrides) -> SubtitleReadingUnit:
    base = dict(
        identity=SubtitleReadingUnitId("unit-0"),
        reading_revision_id=SubtitleReadingRevisionId("reading"),
        source_cue_ids=(SubtitleCandidateCueId("cue-0"),),
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("revision"),
        lines=("one",),
        display_order=0,
        source_timeline_id=SourceTimelineId("timeline"),
        start=0.0,
        end=1.0,
    )
    base.update(overrides)
    return SubtitleReadingUnit(**base)


def _revision(**overrides) -> SubtitleReadingRevision:
    base = dict(
        identity=SubtitleReadingRevisionId("reading"),
        domain_result_id=DomainResultId("reading-result"),
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
        unit_ids=(SubtitleReadingUnitId("unit-0"),),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="baseline reading revision derived from candidate",
    )
    base.update(overrides)
    return SubtitleReadingRevision(**base)


class ComposeReadingLinesTests(unittest.TestCase):
    def test_single_line_is_normalized_not_copied(self) -> None:
        self.assertEqual(compose_reading_lines("  hello   world  "), ("hello world",))

    def test_existing_hard_line_structure_is_preserved(self) -> None:
        self.assertEqual(compose_reading_lines("line one\nline two"), ("line one", "line two"))

    def test_empty_lines_are_dropped(self) -> None:
        self.assertEqual(compose_reading_lines("a\n\n   \nb"), ("a", "b"))

    def test_deterministic(self) -> None:
        self.assertEqual(compose_reading_lines("x  y"), compose_reading_lines("x  y"))


class SubtitleReadingUnitTests(unittest.TestCase):
    def test_valid_timed_unit(self) -> None:
        self.assertEqual(_unit().display_order, 0)

    def test_untimed_unit_allowed(self) -> None:
        unit = _unit(source_timeline_id=None, start=None, end=None)
        self.assertIsNone(unit.start)

    def test_multi_line_unit(self) -> None:
        unit = _unit(lines=("line one", "line two"))
        self.assertEqual(len(unit.lines), 2)

    def test_merge_many_cues_to_one_unit(self) -> None:
        unit = _unit(
            source_cue_ids=(
                SubtitleCandidateCueId("cue-0"),
                SubtitleCandidateCueId("cue-1"),
            )
        )
        self.assertEqual(len(unit.source_cue_ids), 2)

    def test_requires_a_source_cue(self) -> None:
        with self.assertRaises(ValueError):
            _unit(source_cue_ids=())

    def test_source_cues_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            _unit(
                source_cue_ids=(
                    SubtitleCandidateCueId("cue-0"),
                    SubtitleCandidateCueId("cue-0"),
                )
            )

    def test_requires_a_line(self) -> None:
        with self.assertRaises(ValueError):
            _unit(lines=())

    def test_blank_line_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _unit(lines=("ok", "   "))

    def test_display_order_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _unit(display_order=-1)

    def test_partial_time_range_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _unit(start=0.0, end=None)

    def test_timed_unit_requires_timeline(self) -> None:
        with self.assertRaises(ValueError):
            _unit(source_timeline_id=None)

    def test_start_after_end_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _unit(start=2.0, end=1.0)


class SubtitleReadingRevisionTests(unittest.TestCase):
    def test_valid_revision(self) -> None:
        self.assertEqual(len(_revision().unit_ids), 1)

    def test_split_one_cue_to_many_units(self) -> None:
        # Two distinct reading units that both trace to the same source cue.
        revision = _revision(
            unit_ids=(
                SubtitleReadingUnitId("unit-0"),
                SubtitleReadingUnitId("unit-1"),
            )
        )
        first = _unit()
        second = _unit(
            identity=SubtitleReadingUnitId("unit-1"),
            lines=("two",),
            display_order=1,
            start=1.0,
            end=2.0,
        )
        self.assertEqual(len(revision.unit_ids), 2)
        self.assertEqual(first.source_cue_ids, second.source_cue_ids)

    def test_requires_a_unit(self) -> None:
        with self.assertRaises(ValueError):
            _revision(unit_ids=())

    def test_unit_ids_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            _revision(
                unit_ids=(
                    SubtitleReadingUnitId("unit-0"),
                    SubtitleReadingUnitId("unit-0"),
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
                previous_reading_revision_id=SubtitleReadingRevisionId("earlier"),
            )

    def test_later_may_reference_previous(self) -> None:
        revision = _revision(
            sequence=1,
            previous_reading_revision_id=SubtitleReadingRevisionId("earlier"),
        )
        self.assertEqual(
            revision.previous_reading_revision_id,
            SubtitleReadingRevisionId("earlier"),
        )


class SubtitleReadingIdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = SubtitleReadingIdentityPlan(
            reading_revision_id=SubtitleReadingRevisionId("reading"),
            reading_result_id=DomainResultId("reading-result"),
            unit_ids=(SubtitleReadingUnitId("unit-0"),),
        )
        self.assertEqual(len(plan.unit_ids), 1)

    def test_requires_unit_ids(self) -> None:
        with self.assertRaises(ValueError):
            SubtitleReadingIdentityPlan(
                reading_revision_id=SubtitleReadingRevisionId("reading"),
                reading_result_id=DomainResultId("reading-result"),
                unit_ids=(),
            )

    def test_unit_ids_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            SubtitleReadingIdentityPlan(
                reading_revision_id=SubtitleReadingRevisionId("reading"),
                reading_result_id=DomainResultId("reading-result"),
                unit_ids=(
                    SubtitleReadingUnitId("unit-0"),
                    SubtitleReadingUnitId("unit-0"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
