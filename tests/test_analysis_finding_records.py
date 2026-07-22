import dataclasses
import unittest

from lectureos.application.analysis_finding import (
    AnalysisFinding,
    require_canonical_finding_type,
)
from lectureos.application.identities import (
    AnalysisFindingId,
    EligibleAnalysisInputId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)


def _finding(**overrides) -> AnalysisFinding:
    base = dict(
        identity=AnalysisFindingId("finding-0"),
        domain_result_id=DomainResultId("finding-0-result"),
        source_input_id=EligibleAnalysisInputId("input"),
        finding_type="terminology_drift",
        evidence="the speaker misnames the theorem",
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
    )
    base.update(overrides)
    return AnalysisFinding(**base)


class AnalysisFindingRecordTests(unittest.TestCase):
    def test_valid_canonical_finding(self) -> None:
        finding = _finding(confidence=0.7, range_start=1.0, range_end=2.0)
        self.assertEqual(finding.source_input_id, EligibleAnalysisInputId("input"))
        self.assertEqual(finding.finding_type, "terminology_drift")

    def test_record_is_immutable(self) -> None:
        finding = _finding()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            finding.finding_type = "other"  # type: ignore[misc]

    def test_equal_records_are_equal(self) -> None:
        self.assertEqual(_finding(), _finding())

    def test_required_anchor_is_present(self) -> None:
        # The anchor to exactly one Eligible Analysis Input is a mandatory field.
        with self.assertRaises(TypeError):
            AnalysisFinding(
                identity=AnalysisFindingId("finding-0"),
                domain_result_id=DomainResultId("finding-0-result"),
                finding_type="terminology_drift",
                evidence="evidence",
                source_media_id=SourceMediaId("media"),
                source_timeline_id=SourceTimelineId("timeline"),
                run_id=ProcessingRunId("run"),
                unit_execution_id=UnitExecutionId("execution"),
                sequence=0,
            )

    def test_empty_finding_type_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _finding(finding_type="  ")

    def test_non_canonical_finding_type_is_rejected(self) -> None:
        for junk in ("Possible Error", "TERM", "term drift", "0type", "term-drift"):
            with self.subTest(junk=junk):
                with self.assertRaises(ValueError):
                    require_canonical_finding_type(junk)

    def test_canonical_finding_type_is_accepted(self) -> None:
        for token in ("term", "terminology_drift", "missing_definition", "t9"):
            with self.subTest(token=token):
                self.assertEqual(require_canonical_finding_type(token), token)

    def test_empty_evidence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _finding(evidence="   ")

    def test_negative_sequence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _finding(sequence=-1)

    def test_valid_confidence_and_uncertainty(self) -> None:
        finding = _finding(confidence=0.0, uncertainty=1.0)
        self.assertEqual(finding.confidence, 0.0)
        self.assertEqual(finding.uncertainty, 1.0)

    def test_out_of_range_confidence_is_rejected(self) -> None:
        for value in (-0.1, 1.1, float("inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _finding(confidence=value)

    def test_finding_without_confidence_or_uncertainty(self) -> None:
        finding = _finding()
        self.assertIsNone(finding.confidence)
        self.assertIsNone(finding.uncertainty)

    def test_finding_without_time_range(self) -> None:
        finding = _finding()
        self.assertIsNone(finding.range_start)
        self.assertIsNone(finding.range_end)

    def test_valid_single_time_range(self) -> None:
        finding = _finding(range_start=1.5, range_end=1.5)
        self.assertEqual(finding.range_start, 1.5)
        self.assertEqual(finding.range_end, 1.5)

    def test_partial_time_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _finding(range_start=1.0)
        with self.assertRaises(ValueError):
            _finding(range_end=1.0)

    def test_inverted_time_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _finding(range_start=2.0, range_end=1.0)

    def test_negative_time_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _finding(range_start=-1.0, range_end=1.0)

    def test_no_segment_or_multi_range_fields_exist(self) -> None:
        field_names = set(AnalysisFinding.__dataclass_fields__)
        for forbidden in (
            "segment_id",
            "lecture_segment_id",
            "ranges",
            "time_ranges",
            "edit_candidate_id",
            "review_item_id",
        ):
            self.assertNotIn(forbidden, field_names)


if __name__ == "__main__":
    unittest.main()
