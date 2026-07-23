import dataclasses
import unittest

from lectureos.application.lecture_segment import LectureSegment
from lectureos.application.identities import (
    EligibleAnalysisInputId,
    LectureSegmentId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)


def _segment(**overrides) -> LectureSegment:
    base = dict(
        identity=LectureSegmentId("segment-0"),
        domain_result_id=DomainResultId("segment-0-result"),
        source_input_id=EligibleAnalysisInputId("input"),
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        range_start=0.0,
        range_end=5.0,
    )
    base.update(overrides)
    return LectureSegment(**base)


class LectureSegmentRecordTests(unittest.TestCase):
    def test_valid_canonical_segment(self) -> None:
        segment = _segment()
        self.assertEqual(segment.source_input_id, EligibleAnalysisInputId("input"))
        self.assertEqual(segment.range_start, 0.0)
        self.assertEqual(segment.range_end, 5.0)

    def test_record_is_immutable(self) -> None:
        segment = _segment()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            segment.range_start = 1.0  # type: ignore[misc]

    def test_equal_records_are_equal(self) -> None:
        self.assertEqual(_segment(), _segment())

    def test_caller_owned_identity(self) -> None:
        segment = _segment(identity=LectureSegmentId("caller-chosen"))
        self.assertEqual(segment.identity, LectureSegmentId("caller-chosen"))

    def test_required_anchor_is_present(self) -> None:
        # The anchor to exactly one Eligible Analysis Input is a mandatory field.
        with self.assertRaises(TypeError):
            LectureSegment(
                identity=LectureSegmentId("segment-0"),
                domain_result_id=DomainResultId("segment-0-result"),
                source_media_id=SourceMediaId("media"),
                source_timeline_id=SourceTimelineId("timeline"),
                run_id=ProcessingRunId("run"),
                unit_execution_id=UnitExecutionId("execution"),
                sequence=0,
                range_start=0.0,
                range_end=5.0,
            )

    def test_negative_sequence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _segment(sequence=-1)

    def test_required_time_range(self) -> None:
        # Range is mandatory: omitting either bound is a construction error.
        with self.assertRaises(TypeError):
            LectureSegment(
                identity=LectureSegmentId("segment-0"),
                domain_result_id=DomainResultId("segment-0-result"),
                source_input_id=EligibleAnalysisInputId("input"),
                source_media_id=SourceMediaId("media"),
                source_timeline_id=SourceTimelineId("timeline"),
                run_id=ProcessingRunId("run"),
                unit_execution_id=UnitExecutionId("execution"),
                sequence=0,
                range_start=0.0,
            )

    def test_valid_point_and_whole_recording_ranges(self) -> None:
        self.assertEqual(_segment(range_start=3.0, range_end=3.0).range_start, 3.0)
        self.assertEqual(_segment(range_start=0.0, range_end=9999.0).range_end, 9999.0)

    def test_inverted_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _segment(range_start=5.0, range_end=1.0)

    def test_negative_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _segment(range_start=-1.0, range_end=1.0)

    def test_non_finite_range_is_rejected(self) -> None:
        for value in (float("inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _segment(range_start=0.0, range_end=value)

    def test_provider_independence_no_provider_or_semantic_fields(self) -> None:
        field_names = set(LectureSegment.__dataclass_fields__)
        for forbidden in (
            # provider metadata
            "model",
            "prompt",
            "provider",
            "raw",
            "tokens",
            "response",
            # deferred semantics / concepts
            "label",
            "segment_label",
            "confidence",
            "uncertainty",
            "rationale",
            "status",
            "replaces_segment_id",
            "previous_segment_id",
            "parent_segment_id",
            "ranges",
        ):
            self.assertNotIn(forbidden, field_names)


if __name__ == "__main__":
    unittest.main()
