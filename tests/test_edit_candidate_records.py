import dataclasses
import unittest

from lectureos.application.edit_candidate import (
    EditCandidate,
    require_canonical_candidate_type,
)
from lectureos.application.identities import (
    AnalysisFindingId,
    EditCandidateId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)


def _candidate(**overrides) -> EditCandidate:
    base = dict(
        identity=EditCandidateId("candidate-0"),
        domain_result_id=DomainResultId("candidate-0-result"),
        source_finding_id=AnalysisFindingId("finding"),
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        candidate_type="review",
        rationale="propose human review of a possible non-lecture region",
        range_start=0.0,
        range_end=5.0,
    )
    base.update(overrides)
    return EditCandidate(**base)


class EditCandidateRecordTests(unittest.TestCase):
    def test_valid_canonical_candidate(self) -> None:
        candidate = _candidate()
        self.assertEqual(candidate.source_finding_id, AnalysisFindingId("finding"))
        self.assertEqual(candidate.candidate_type, "review")
        self.assertEqual(candidate.range_start, 0.0)
        self.assertEqual(candidate.range_end, 5.0)

    def test_record_is_immutable(self) -> None:
        candidate = _candidate()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            candidate.candidate_type = "condense"  # type: ignore[misc]

    def test_equal_records_are_equal(self) -> None:
        self.assertEqual(_candidate(), _candidate())

    def test_caller_owned_identity(self) -> None:
        candidate = _candidate(identity=EditCandidateId("caller-chosen"))
        self.assertEqual(candidate.identity, EditCandidateId("caller-chosen"))

    def test_required_finding_anchor(self) -> None:
        with self.assertRaises(TypeError):
            EditCandidate(
                identity=EditCandidateId("candidate-0"),
                domain_result_id=DomainResultId("candidate-0-result"),
                source_media_id=SourceMediaId("media"),
                source_timeline_id=SourceTimelineId("timeline"),
                run_id=ProcessingRunId("run"),
                unit_execution_id=UnitExecutionId("execution"),
                sequence=0,
                candidate_type="review",
                rationale="reason",
                range_start=0.0,
                range_end=5.0,
            )

    def test_required_candidate_type(self) -> None:
        with self.assertRaises(ValueError):
            _candidate(candidate_type="  ")

    def test_non_canonical_candidate_type_is_rejected(self) -> None:
        for junk in ("Remove", "REVIEW", "remove clip", "0type", "re-move", "Possible (0.8)"):
            with self.subTest(junk=junk):
                with self.assertRaises(ValueError):
                    require_canonical_candidate_type(junk)

    def test_canonical_candidate_type_is_accepted(self) -> None:
        for token in ("review", "condense", "condense_repetition", "t9"):
            with self.subTest(token=token):
                self.assertEqual(require_canonical_candidate_type(token), token)

    def test_required_non_empty_rationale(self) -> None:
        with self.assertRaises(ValueError):
            _candidate(rationale="   ")

    def test_negative_sequence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _candidate(sequence=-1)

    def test_required_range(self) -> None:
        with self.assertRaises(TypeError):
            EditCandidate(
                identity=EditCandidateId("candidate-0"),
                domain_result_id=DomainResultId("candidate-0-result"),
                source_finding_id=AnalysisFindingId("finding"),
                source_media_id=SourceMediaId("media"),
                source_timeline_id=SourceTimelineId("timeline"),
                run_id=ProcessingRunId("run"),
                unit_execution_id=UnitExecutionId("execution"),
                sequence=0,
                candidate_type="review",
                rationale="reason",
                range_start=0.0,
            )

    def test_zero_duration_and_whole_recording_ranges_valid(self) -> None:
        self.assertEqual(_candidate(range_start=3.0, range_end=3.0).range_start, 3.0)
        self.assertEqual(_candidate(range_start=0.0, range_end=9999.0).range_end, 9999.0)

    def test_inverted_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _candidate(range_start=5.0, range_end=1.0)

    def test_negative_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _candidate(range_start=-1.0, range_end=1.0)

    def test_non_finite_range_is_rejected(self) -> None:
        for value in (float("inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _candidate(range_start=0.0, range_end=value)

    def test_provider_independence_and_no_deferred_fields(self) -> None:
        field_names = set(EditCandidate.__dataclass_fields__)
        for forbidden in (
            # provider metadata
            "model",
            "prompt",
            "provider",
            "raw",
            "tokens",
            "response",
            "explanation",
            # Review / decision state
            "status",
            "review_id",
            "review_item_id",
            "approved_edit_decision_id",
            "accepted",
            "rejected",
            "modified",
            # revision / lifecycle
            "revision",
            "supersedes",
            "replaces_candidate_id",
            "stale",
            "current",
            # deferred payload
            "confidence",
            "uncertainty",
            "priority",
            "severity",
            "expected_time_savings",
            "segment_label",
            "lecture_segment_id",
            "source_input_id",
            "structured_evidence",
            "source_text",
            "replacement_text",
            "proposed_treatment",
            "operation",
            "ranges",
        ):
            self.assertNotIn(forbidden, field_names)


if __name__ == "__main__":
    unittest.main()
