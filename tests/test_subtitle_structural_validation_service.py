import unittest

from lectureos.application import (
    RULE_ORDERING_NON_MONOTONIC,
    RULE_OVERLAP_ADJACENT,
    RULE_PROVENANCE_READING_REVISION_MISSING,
    RULE_TIMELINE_MISMATCH,
    RULE_UNRESOLVED_TIMING,
    SubtitleReadingRevision,
    SubtitleStructuralValidationError,
    SubtitleStructuralValidationService,
    SubtitleTimedUnit,
    SubtitleTimeRevision,
    SubtitleTimingStatus,
    SubtitleValidationCategory,
    SubtitleValidationIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleTranscriptIntakeId,
    SubtitleValidationId,
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
    TranscriptValidationId,
)

TIMELINE = SourceTimelineId("timeline")

_LINEAGE = dict(
    source_candidate_id=SubtitleCandidateId("candidate"),
    source_intake_id=SubtitleTranscriptIntakeId("intake"),
    source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
    source_selection_id=TranscriptCurrentSelectionId("selection"),
    source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
    source_decision_id=TranscriptReviewDecisionId("decision"),
    review_item_id=ReviewItemId("item-0"),
    candidate_reference_id=CandidateReferenceId("candidate-0"),
    source_transcript_id=TranscriptId("raw"),
    source_revision_id=TranscriptRevisionId("revision"),
    source_media_id=SourceMediaId("media"),
    source_timeline_id=TIMELINE,
)


class _FakeTimeQuery:
    def __init__(self, revision, units) -> None:
        self._revision = revision
        self._units = {unit.identity: unit for unit in units}

    def get(self, identity):
        return self._revision if identity == self._revision.identity else None

    def get_unit(self, identity):
        return self._units.get(identity)


class _FakeReadingQuery:
    def __init__(self, revision) -> None:
        self._revision = revision

    def get(self, identity):
        if self._revision is None or identity != self._revision.identity:
            return None
        return self._revision


class SubtitleStructuralValidationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="validation",
                capabilities=(CapabilityReference("subtitle.validation"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("validation"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )

    def _timed(self, name, reading_unit, order, status, start, end, timeline=TIMELINE):
        return SubtitleTimedUnit(
            identity=SubtitleTimedUnitId(name),
            time_revision_id=SubtitleTimeRevisionId("time"),
            source_reading_unit_id=SubtitleReadingUnitId(reading_unit),
            display_order=order,
            timing_status=status,
            source_timeline_id=timeline,
            start=start,
            end=end,
        )

    def _time_revision(self, timed_units, reading_id="reading"):
        return SubtitleTimeRevision(
            identity=SubtitleTimeRevisionId("time"),
            domain_result_id=DomainResultId("time-result"),
            source_reading_revision_id=SubtitleReadingRevisionId(reading_id),
            validation_id=TranscriptValidationId("transcript-validation"),
            timed_unit_ids=tuple(u.identity for u in timed_units),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="time",
            **_LINEAGE,
        )

    def _reading_revision(self, unit_names, reading_id="reading"):
        return SubtitleReadingRevision(
            identity=SubtitleReadingRevisionId(reading_id),
            domain_result_id=DomainResultId("reading-result"),
            validation_id=TranscriptValidationId("transcript-validation"),
            unit_ids=tuple(SubtitleReadingUnitId(n) for n in unit_names),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="reading",
            **_LINEAGE,
        )

    def _service(self, timed_units, reading_revision):
        return SubtitleStructuralValidationService(
            _FakeTimeQuery(self._time_revision(timed_units), timed_units),
            _FakeReadingQuery(reading_revision),
            self.execution,
        )

    def _plan(self, name="validation"):
        return SubtitleValidationIdentityPlan(
            validation_id=SubtitleValidationId(name),
            validation_result_id=DomainResultId(f"{name}-result"),
        )

    def _validate(self, service):
        return service.validate_timing(
            source_time_revision_id=SubtitleTimeRevisionId("time"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )

    def test_clean_revision_is_structurally_valid_with_no_findings(self) -> None:
        units = [
            self._timed("t-0", "ru-0", 0, SubtitleTimingStatus.ANCHORED, 0.0, 1.0),
            self._timed("t-1", "ru-1", 1, SubtitleTimingStatus.ANCHORED, 1.0, 2.0),
        ]
        prepared = self._validate(self._service(units, self._reading_revision(["ru-0", "ru-1"])))
        self.assertTrue(prepared.validation.structural_valid)
        self.assertEqual(prepared.findings, ())
        self.assertEqual(
            prepared.validation_result.upstream_results, (DomainResultId("time-result"),)
        )
        self.assertEqual(prepared.validation_result.kind, "subtitle_validation")
        # carried lineage
        self.assertEqual(
            prepared.validation.source_time_revision_id, SubtitleTimeRevisionId("time")
        )
        self.assertEqual(
            prepared.validation.source_transcript_validation_id,
            TranscriptValidationId("transcript-validation"),
        )

    def test_overlap_produces_overlap_finding(self) -> None:
        units = [
            self._timed("t-0", "ru-0", 0, SubtitleTimingStatus.ANCHORED, 0.0, 2.0),
            self._timed("t-1", "ru-1", 1, SubtitleTimingStatus.ANCHORED, 1.0, 3.0),
        ]
        prepared = self._validate(self._service(units, self._reading_revision(["ru-0", "ru-1"])))
        self.assertFalse(prepared.validation.structural_valid)
        self.assertFalse(prepared.validation.time_consistent)
        overlap = [f for f in prepared.findings if f.rule == RULE_OVERLAP_ADJACENT]
        self.assertEqual(len(overlap), 1)
        self.assertIs(overlap[0].category, SubtitleValidationCategory.OVERLAP)
        self.assertEqual(overlap[0].target_timed_unit_id, SubtitleTimedUnitId("t-1"))

    def test_out_of_order_produces_ordering_finding(self) -> None:
        units = [
            self._timed("t-0", "ru-0", 0, SubtitleTimingStatus.ANCHORED, 5.0, 6.0),
            self._timed("t-1", "ru-1", 1, SubtitleTimingStatus.ANCHORED, 0.0, 1.0),
        ]
        prepared = self._validate(self._service(units, self._reading_revision(["ru-0", "ru-1"])))
        self.assertFalse(prepared.validation.ordering_consistent)
        ordering = [f for f in prepared.findings if f.rule == RULE_ORDERING_NON_MONOTONIC]
        self.assertEqual(len(ordering), 1)
        self.assertIs(ordering[0].category, SubtitleValidationCategory.ORDERING)

    def test_unresolved_unit_produces_finding(self) -> None:
        units = [
            self._timed("t-0", "ru-0", 0, SubtitleTimingStatus.ANCHORED, 0.0, 1.0),
            SubtitleTimedUnit(
                identity=SubtitleTimedUnitId("t-1"),
                time_revision_id=SubtitleTimeRevisionId("time"),
                source_reading_unit_id=SubtitleReadingUnitId("ru-1"),
                display_order=1,
                timing_status=SubtitleTimingStatus.UNRESOLVED,
            ),
        ]
        prepared = self._validate(self._service(units, self._reading_revision(["ru-0", "ru-1"])))
        self.assertFalse(prepared.validation.timeline_traceable)
        unresolved = [f for f in prepared.findings if f.rule == RULE_UNRESOLVED_TIMING]
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0].target_timed_unit_id, SubtitleTimedUnitId("t-1"))

    def test_timeline_mismatch_produces_finding(self) -> None:
        units = [
            self._timed(
                "t-0", "ru-0", 0, SubtitleTimingStatus.ANCHORED, 0.0, 1.0,
                timeline=SourceTimelineId("other"),
            ),
        ]
        prepared = self._validate(self._service(units, self._reading_revision(["ru-0"])))
        mismatch = [f for f in prepared.findings if f.rule == RULE_TIMELINE_MISMATCH]
        self.assertEqual(len(mismatch), 1)
        self.assertIs(
            mismatch[0].category, SubtitleValidationCategory.TIMELINE_TRACEABILITY
        )

    def test_missing_reading_revision_produces_provenance_finding(self) -> None:
        units = [self._timed("t-0", "ru-0", 0, SubtitleTimingStatus.ANCHORED, 0.0, 1.0)]
        prepared = self._validate(self._service(units, None))
        self.assertFalse(prepared.validation.provenance_complete)
        provenance = [
            f for f in prepared.findings if f.rule == RULE_PROVENANCE_READING_REVISION_MISSING
        ]
        self.assertEqual(len(provenance), 1)
        self.assertIsNone(provenance[0].target_timed_unit_id)

    def test_deterministic_construction(self) -> None:
        units = [self._timed("t-0", "ru-0", 0, SubtitleTimingStatus.ANCHORED, 0.0, 1.0)]
        service = self._service(units, self._reading_revision(["ru-0"]))
        self.assertEqual(self._validate(service), self._validate(service))

    def test_unknown_time_revision_raises(self) -> None:
        units = [self._timed("t-0", "ru-0", 0, SubtitleTimingStatus.ANCHORED, 0.0, 1.0)]
        service = self._service(units, self._reading_revision(["ru-0"]))
        with self.assertRaises(KeyError):
            service.validate_timing(
                source_time_revision_id=SubtitleTimeRevisionId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_requires_running_execution(self) -> None:
        units = [self._timed("t-0", "ru-0", 0, SubtitleTimingStatus.ANCHORED, 0.0, 1.0)]
        service = self._service(units, self._reading_revision(["ru-0"]))
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(SubtitleStructuralValidationError):
            self._validate(service)

    def test_record_without_persistence_raises(self) -> None:
        units = [self._timed("t-0", "ru-0", 0, SubtitleTimingStatus.ANCHORED, 0.0, 1.0)]
        service = self._service(units, self._reading_revision(["ru-0"]))
        with self.assertRaises(RuntimeError):
            service.record_validation(
                source_time_revision_id=SubtitleTimeRevisionId("time"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
