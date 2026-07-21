import unittest

from lectureos.application import (
    SubtitleCandidate,
    SubtitleCandidateCue,
    SubtitleCandidateIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleCandidateCueId,
    SubtitleCandidateId,
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
    TranscriptSegmentId,
    TranscriptValidationId,
)


def _cue(**overrides) -> SubtitleCandidateCue:
    base = dict(
        identity=SubtitleCandidateCueId("cue-0"),
        candidate_id=SubtitleCandidateId("candidate"),
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("revision"),
        source_segment_ids=(TranscriptSegmentId("segment-0"),),
        text="one",
        display_order=0,
        source_timeline_id=SourceTimelineId("timeline"),
        start=0.0,
        end=1.0,
    )
    base.update(overrides)
    return SubtitleCandidateCue(**base)


def _candidate(**overrides) -> SubtitleCandidate:
    base = dict(
        identity=SubtitleCandidateId("candidate"),
        domain_result_id=DomainResultId("candidate-result"),
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
        cue_ids=(SubtitleCandidateCueId("cue-0"),),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="baseline subtitle candidate derived from eligible intake",
    )
    base.update(overrides)
    return SubtitleCandidate(**base)


class SubtitleCandidateCueTests(unittest.TestCase):
    def test_valid_timed_cue(self) -> None:
        self.assertEqual(_cue().display_order, 0)

    def test_untimed_cue_allowed(self) -> None:
        cue = _cue(source_timeline_id=None, start=None, end=None)
        self.assertIsNone(cue.start)

    def test_many_to_one_multi_segment_cue(self) -> None:
        cue = _cue(
            source_segment_ids=(
                TranscriptSegmentId("segment-0"),
                TranscriptSegmentId("segment-1"),
            )
        )
        self.assertEqual(len(cue.source_segment_ids), 2)

    def test_requires_a_source_segment(self) -> None:
        with self.assertRaises(ValueError):
            _cue(source_segment_ids=())

    def test_source_segments_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            _cue(
                source_segment_ids=(
                    TranscriptSegmentId("segment-0"),
                    TranscriptSegmentId("segment-0"),
                )
            )

    def test_text_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _cue(text="   ")

    def test_display_order_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _cue(display_order=-1)

    def test_partial_time_range_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _cue(start=0.0, end=None)

    def test_timed_cue_requires_timeline(self) -> None:
        with self.assertRaises(ValueError):
            _cue(source_timeline_id=None)

    def test_start_after_end_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _cue(start=2.0, end=1.0)


class SubtitleCandidateTests(unittest.TestCase):
    def test_valid_candidate(self) -> None:
        self.assertEqual(len(_candidate().cue_ids), 1)

    def test_one_to_many_multiple_cues_per_segment(self) -> None:
        # Two distinct cues that both trace to the same source segment.
        candidate = _candidate(
            cue_ids=(
                SubtitleCandidateCueId("cue-0"),
                SubtitleCandidateCueId("cue-1"),
            )
        )
        first = _cue()
        second = _cue(
            identity=SubtitleCandidateCueId("cue-1"),
            text="two",
            display_order=1,
            start=1.0,
            end=2.0,
        )
        self.assertEqual(len(candidate.cue_ids), 2)
        self.assertEqual(first.source_segment_ids, second.source_segment_ids)

    def test_requires_a_cue(self) -> None:
        with self.assertRaises(ValueError):
            _candidate(cue_ids=())

    def test_cue_ids_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            _candidate(
                cue_ids=(
                    SubtitleCandidateCueId("cue-0"),
                    SubtitleCandidateCueId("cue-0"),
                )
            )

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _candidate(sequence=-1)

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _candidate(reason="  ")

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _candidate(
                sequence=0, previous_candidate_id=SubtitleCandidateId("earlier")
            )

    def test_later_may_reference_previous(self) -> None:
        candidate = _candidate(
            sequence=1, previous_candidate_id=SubtitleCandidateId("earlier")
        )
        self.assertEqual(
            candidate.previous_candidate_id, SubtitleCandidateId("earlier")
        )


class SubtitleCandidateIdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = SubtitleCandidateIdentityPlan(
            candidate_id=SubtitleCandidateId("candidate"),
            candidate_result_id=DomainResultId("candidate-result"),
            cue_ids=(SubtitleCandidateCueId("cue-0"),),
        )
        self.assertEqual(len(plan.cue_ids), 1)

    def test_requires_cue_ids(self) -> None:
        with self.assertRaises(ValueError):
            SubtitleCandidateIdentityPlan(
                candidate_id=SubtitleCandidateId("candidate"),
                candidate_result_id=DomainResultId("candidate-result"),
                cue_ids=(),
            )

    def test_cue_ids_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            SubtitleCandidateIdentityPlan(
                candidate_id=SubtitleCandidateId("candidate"),
                candidate_result_id=DomainResultId("candidate-result"),
                cue_ids=(
                    SubtitleCandidateCueId("cue-0"),
                    SubtitleCandidateCueId("cue-0"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
