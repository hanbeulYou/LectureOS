import unittest

from lectureos.application import (
    SubtitleCandidate,
    SubtitleCandidateCue,
    SubtitleReadingIdentityPlan,
    SubtitleReadingRepresentationError,
    SubtitleReadingRepresentationService,
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
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    ProcessingUnitId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import ExecutionIntent, ProcessingUnit
from lectureos.execution.service import ExecutionService
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)


class _FakeCandidateQuery:
    def __init__(self, candidate, cues) -> None:
        self._candidate = candidate
        self._cues = {cue.identity: cue for cue in cues}

    def get(self, identity):
        return self._candidate if identity == self._candidate.identity else None

    def get_cue(self, identity):
        return self._cues.get(identity)


class SubtitleReadingRepresentationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.media_id = SourceMediaId("media")
        self.timeline_id = SourceTimelineId("timeline")
        self.transcript_id = TranscriptId("raw")
        self.revision_id = TranscriptRevisionId("revision")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="reading",
                capabilities=(CapabilityReference("subtitle.reading"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("reading"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.cue_ids = (
            SubtitleCandidateCueId("cue-0"),
            SubtitleCandidateCueId("cue-1"),
        )
        self.cues = (
            self._cue(self.cue_ids[0], "  hello   world  ", 0, 0.0, 1.0),
            self._cue(self.cue_ids[1], "line one\nline two", 1, 1.0, 2.0),
        )
        self.candidate = self._candidate(self.cue_ids)
        self.query = _FakeCandidateQuery(self.candidate, self.cues)
        self.service = SubtitleReadingRepresentationService(self.query, self.execution)

    def _cue(self, identity, text, order, start, end, timeline=True) -> SubtitleCandidateCue:
        return SubtitleCandidateCue(
            identity=identity,
            candidate_id=SubtitleCandidateId("candidate"),
            source_transcript_id=self.transcript_id,
            source_revision_id=self.revision_id,
            source_segment_ids=(TranscriptSegmentId(f"seg-{order}"),),
            text=text,
            display_order=order,
            source_timeline_id=self.timeline_id if timeline else None,
            start=start,
            end=end,
        )

    def _candidate(self, cue_ids) -> SubtitleCandidate:
        return SubtitleCandidate(
            identity=SubtitleCandidateId("candidate"),
            domain_result_id=DomainResultId("candidate-result"),
            source_intake_id=SubtitleTranscriptIntakeId("intake"),
            source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
            source_selection_id=TranscriptCurrentSelectionId("selection"),
            source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
            source_decision_id=TranscriptReviewDecisionId("decision"),
            review_item_id=ReviewItemId("item-0"),
            candidate_reference_id=CandidateReferenceId("candidate-0"),
            source_transcript_id=self.transcript_id,
            source_revision_id=self.revision_id,
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            validation_id=TranscriptValidationId("validation"),
            cue_ids=cue_ids,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="candidate",
        )

    def _plan(self, name="reading", units=2) -> SubtitleReadingIdentityPlan:
        return SubtitleReadingIdentityPlan(
            reading_revision_id=SubtitleReadingRevisionId(name),
            reading_result_id=DomainResultId(f"{name}-result"),
            unit_ids=tuple(SubtitleReadingUnitId(f"unit-{i}") for i in range(units)),
        )

    def _compose(self, **overrides):
        base = dict(
            source_candidate_id=self.candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        base.update(overrides)
        return self.service.compose_reading(**base)

    def test_composes_one_unit_per_cue_with_normalized_lines_and_lineage(self) -> None:
        prepared = self._compose()
        revision = prepared.revision
        self.assertEqual(len(prepared.units), 2)
        self.assertEqual(
            revision.unit_ids, tuple(u.identity for u in prepared.units)
        )
        self.assertEqual(revision.source_candidate_id, self.candidate.identity)
        self.assertEqual(revision.source_revision_id, self.revision_id)
        self.assertEqual(revision.source_media_id, self.media_id)
        self.assertEqual(revision.validation_id, TranscriptValidationId("validation"))
        self.assertEqual(revision.review_item_id, ReviewItemId("item-0"))
        # deterministic meaning-preserving normalization, not a pure copy
        self.assertEqual(prepared.units[0].lines, ("hello world",))
        self.assertEqual(prepared.units[1].lines, ("line one", "line two"))
        # each unit traces to its ordered source cue; timing inherited from the cue
        self.assertEqual(
            [u.source_cue_ids for u in prepared.units],
            [(self.cue_ids[0],), (self.cue_ids[1],)],
        )
        self.assertEqual([u.display_order for u in prepared.units], [0, 1])
        self.assertEqual((prepared.units[0].start, prepared.units[0].end), (0.0, 1.0))
        self.assertEqual(prepared.revision_result.kind, "subtitle_reading_revision")
        self.assertEqual(
            prepared.revision_result.upstream_results,
            (self.candidate.domain_result_id,),
        )

    def test_untimed_cue_yields_untimed_unit(self) -> None:
        cues = (
            self._cue(self.cue_ids[0], "one", 0, None, None, timeline=False),
            self._cue(self.cue_ids[1], "two", 1, None, None, timeline=False),
        )
        self.service = SubtitleReadingRepresentationService(
            _FakeCandidateQuery(self.candidate, cues), self.execution
        )
        prepared = self._compose()
        self.assertIsNone(prepared.units[0].start)
        self.assertIsNone(prepared.units[0].source_timeline_id)

    def test_identity_plan_unit_count_must_match(self) -> None:
        with self.assertRaises(SubtitleReadingRepresentationError):
            self._compose(identities=self._plan(units=1))

    def test_unknown_candidate_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.service.compose_reading(
                source_candidate_id=SubtitleCandidateId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_requires_running_execution(self) -> None:
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(SubtitleReadingRepresentationError):
            self._compose()

    def test_deterministic_construction(self) -> None:
        self.assertEqual(self._compose(), self._compose())

    def test_record_without_persistence_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            self.service.record_reading(
                source_candidate_id=self.candidate.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
