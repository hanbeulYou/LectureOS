import unittest

from lectureos.application import (
    SubtitleCandidateCue,
    SubtitleReadingRevision,
    SubtitleReadingUnit,
    SubtitleTimeIdentityPlan,
    SubtitleTimeRepresentationError,
    SubtitleTimeRepresentationService,
    SubtitleTimingStatus,
)
from lectureos.application.identities import (
    SubtitleCandidateCueId,
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


class _FakeReadingQuery:
    def __init__(self, revision, units) -> None:
        self._revision = revision
        self._units = {unit.identity: unit for unit in units}

    def get(self, identity):
        return self._revision if identity == self._revision.identity else None

    def get_unit(self, identity):
        return self._units.get(identity)


class _FakeCueQuery:
    def __init__(self, cues) -> None:
        self._cues = {cue.identity: cue for cue in cues}

    def get_cue(self, identity):
        return self._cues.get(identity)


class SubtitleTimeRepresentationServiceTests(unittest.TestCase):
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
                purpose="timing",
                capabilities=(CapabilityReference("subtitle.timing"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("timing"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )

    def _cue(self, name, start, end, timeline_id="timeline") -> SubtitleCandidateCue:
        return SubtitleCandidateCue(
            identity=SubtitleCandidateCueId(name),
            candidate_id=SubtitleCandidateId("candidate"),
            source_transcript_id=self.transcript_id,
            source_revision_id=self.revision_id,
            source_segment_ids=(TranscriptSegmentId(f"seg-{name}"),),
            text=name,
            display_order=0,
            source_timeline_id=SourceTimelineId(timeline_id) if timeline_id else None,
            start=start,
            end=end,
        )

    def _reading_unit(self, name, cue_ids, order) -> SubtitleReadingUnit:
        return SubtitleReadingUnit(
            identity=SubtitleReadingUnitId(name),
            reading_revision_id=SubtitleReadingRevisionId("reading"),
            source_cue_ids=tuple(SubtitleCandidateCueId(c) for c in cue_ids),
            source_transcript_id=self.transcript_id,
            source_revision_id=self.revision_id,
            lines=(name,),
            display_order=order,
            source_timeline_id=self.timeline_id,
            start=0.0,
            end=1.0,
        )

    def _reading_revision(self, unit_ids) -> SubtitleReadingRevision:
        return SubtitleReadingRevision(
            identity=SubtitleReadingRevisionId("reading"),
            domain_result_id=DomainResultId("reading-result"),
            source_candidate_id=SubtitleCandidateId("candidate"),
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
            unit_ids=tuple(SubtitleReadingUnitId(u) for u in unit_ids),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="reading",
        )

    def _service(self, revision, units, cues):
        return SubtitleTimeRepresentationService(
            _FakeReadingQuery(revision, units), _FakeCueQuery(cues), self.execution
        )

    def _plan(self, name="time", units=1) -> SubtitleTimeIdentityPlan:
        return SubtitleTimeIdentityPlan(
            time_revision_id=SubtitleTimeRevisionId(name),
            time_result_id=DomainResultId(f"{name}-result"),
            timed_unit_ids=tuple(SubtitleTimedUnitId(f"timed-{i}") for i in range(units)),
        )

    def _compose(self, service, plan):
        return service.compose_timing(
            source_reading_revision_id=SubtitleReadingRevisionId("reading"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=plan,
        )

    def test_one_to_one_anchors_cue_range_and_merged_anchors_span(self) -> None:
        cues = [
            self._cue("cue-0", 0.0, 1.0),
            self._cue("cue-1", 1.0, 2.0),
        ]
        # unit A: one-to-one over cue-0; unit B: merged over cue-0 + cue-1
        units = [
            self._reading_unit("ru-0", ["cue-0"], 0),
            self._reading_unit("ru-1", ["cue-0", "cue-1"], 1),
        ]
        revision = self._reading_revision(["ru-0", "ru-1"])
        service = self._service(revision, units, cues)
        prepared = self._compose(service, self._plan(units=2))

        self.assertEqual(len(prepared.units), 2)
        one = prepared.units[0]
        merged = prepared.units[1]
        self.assertIs(one.timing_status, SubtitleTimingStatus.ANCHORED)
        self.assertEqual((one.start, one.end), (0.0, 1.0))  # cue range
        self.assertIs(merged.timing_status, SubtitleTimingStatus.ANCHORED)
        self.assertEqual((merged.start, merged.end), (0.0, 2.0))  # minimal enclosing span
        self.assertEqual(merged.source_timeline_id, self.timeline_id)
        # display order preserved from the reading units; each references its reading unit
        self.assertEqual([u.display_order for u in prepared.units], [0, 1])
        self.assertEqual(
            [u.source_reading_unit_id for u in prepared.units],
            [SubtitleReadingUnitId("ru-0"), SubtitleReadingUnitId("ru-1")],
        )
        # lineage carried; result upstream = reading revision result
        self.assertEqual(prepared.revision.source_reading_revision_id, revision.identity)
        self.assertEqual(prepared.revision.source_candidate_id, SubtitleCandidateId("candidate"))
        self.assertEqual(prepared.revision_result.kind, "subtitle_time_revision")
        self.assertEqual(
            prepared.revision_result.upstream_results, (revision.domain_result_id,)
        )

    def test_untimed_cue_yields_unresolved(self) -> None:
        cues = [self._cue("cue-u", None, None, timeline_id=None)]
        units = [self._reading_unit("ru-0", ["cue-u"], 0)]
        service = self._service(self._reading_revision(["ru-0"]), units, cues)
        prepared = self._compose(service, self._plan())
        self.assertIs(prepared.units[0].timing_status, SubtitleTimingStatus.UNRESOLVED)
        self.assertIsNone(prepared.units[0].start)
        self.assertIsNone(prepared.units[0].source_timeline_id)

    def test_merged_across_different_timelines_yields_unresolved(self) -> None:
        cues = [
            self._cue("cue-0", 0.0, 1.0, timeline_id="timeline"),
            self._cue("cue-1", 1.0, 2.0, timeline_id="other-timeline"),
        ]
        units = [self._reading_unit("ru-0", ["cue-0", "cue-1"], 0)]
        service = self._service(self._reading_revision(["ru-0"]), units, cues)
        prepared = self._compose(service, self._plan())
        self.assertIs(prepared.units[0].timing_status, SubtitleTimingStatus.UNRESOLVED)

    def test_partially_timed_aggregate(self) -> None:
        cues = [
            self._cue("cue-0", 0.0, 1.0),
            self._cue("cue-u", None, None, timeline_id=None),
        ]
        units = [
            self._reading_unit("ru-0", ["cue-0"], 0),
            self._reading_unit("ru-1", ["cue-u"], 1),
        ]
        service = self._service(self._reading_revision(["ru-0", "ru-1"]), units, cues)
        prepared = self._compose(service, self._plan(units=2))
        self.assertEqual(
            [u.timing_status for u in prepared.units],
            [SubtitleTimingStatus.ANCHORED, SubtitleTimingStatus.UNRESOLVED],
        )

    def test_identity_plan_unit_count_must_match(self) -> None:
        cues = [self._cue("cue-0", 0.0, 1.0)]
        units = [self._reading_unit("ru-0", ["cue-0"], 0)]
        service = self._service(self._reading_revision(["ru-0"]), units, cues)
        with self.assertRaises(SubtitleTimeRepresentationError):
            self._compose(service, self._plan(units=2))

    def test_unknown_reading_revision_raises(self) -> None:
        service = self._service(self._reading_revision(["ru-0"]), [], [])
        with self.assertRaises(KeyError):
            service.compose_timing(
                source_reading_revision_id=SubtitleReadingRevisionId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_unknown_cue_raises(self) -> None:
        units = [self._reading_unit("ru-0", ["cue-missing"], 0)]
        service = self._service(self._reading_revision(["ru-0"]), units, [])
        with self.assertRaises(KeyError):
            self._compose(service, self._plan())

    def test_requires_running_execution(self) -> None:
        cues = [self._cue("cue-0", 0.0, 1.0)]
        units = [self._reading_unit("ru-0", ["cue-0"], 0)]
        service = self._service(self._reading_revision(["ru-0"]), units, cues)
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(SubtitleTimeRepresentationError):
            self._compose(service, self._plan())

    def test_deterministic_construction(self) -> None:
        cues = [self._cue("cue-0", 0.0, 1.0)]
        units = [self._reading_unit("ru-0", ["cue-0"], 0)]
        service = self._service(self._reading_revision(["ru-0"]), units, cues)
        self.assertEqual(
            self._compose(service, self._plan()), self._compose(service, self._plan())
        )

    def test_record_without_persistence_raises(self) -> None:
        cues = [self._cue("cue-0", 0.0, 1.0)]
        units = [self._reading_unit("ru-0", ["cue-0"], 0)]
        service = self._service(self._reading_revision(["ru-0"]), units, cues)
        with self.assertRaises(RuntimeError):
            service.record_timing(
                source_reading_revision_id=SubtitleReadingRevisionId("reading"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
