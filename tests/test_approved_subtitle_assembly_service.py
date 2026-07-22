import unittest

from lectureos.application import (
    RULE_OVERLAP_ADJACENT,
    SubtitleApprovedAssemblyError,
    SubtitleApprovedAssemblyIdentityPlan,
    SubtitleApprovedSubtitleAssemblyService,
    SubtitleApprovedUnitOrigin,
    SubtitleExportEligibility,
    SubtitleFinalOutcome,
    SubtitleFinalSubtitle,
    SubtitleReadingRevision,
    SubtitleReadingUnit,
    SubtitleTimedUnit,
    SubtitleTimeRevision,
    SubtitleTimingStatus,
    applied_outcome_for_kind,
    final_outcome_for_applied_outcome,
)
from lectureos.application.identities import (
    SubtitleApprovedDocumentId,
    SubtitleApprovedUnitId,
    SubtitleCandidateCueId,
    SubtitleCandidateId,
    SubtitleDecisionRevisionId,
    SubtitleFinalSubtitleId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleTranscriptIntakeId,
    SubtitleValidationFindingId,
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
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

MEDIA = SourceMediaId("media")
TIMELINE = SourceTimelineId("timeline")
TIME_REVISION = SubtitleTimeRevisionId("time")
READING_REVISION = SubtitleReadingRevisionId("reading")


class _FakeTimeQuery:
    def __init__(self, revision, units) -> None:
        self._revision = revision
        self._units = {unit.identity: unit for unit in units}

    def get(self, identity):
        return self._revision if identity == self._revision.identity else None

    def get_unit(self, identity):
        return self._units.get(identity)


class _FakeReadingQuery:
    def __init__(self, revision, units) -> None:
        self._revision = revision
        self._units = {unit.identity: unit for unit in units}

    def get(self, identity):
        return self._revision if identity == self._revision.identity else None

    def get_unit(self, identity):
        return self._units.get(identity)


class _FakeFinalQuery:
    def __init__(self, finals) -> None:
        self._finals = tuple(finals)

    def list_for_time_revision(self, identity):
        return tuple(f for f in self._finals if f.source_time_revision_id == identity)


class _FakeDecisionQuery:
    def __init__(self, ids) -> None:
        self._ids = set(ids)

    def get(self, identity):
        return object() if identity in self._ids else None


def _timed_unit(order, reading_unit_id, *, anchored=True):
    return SubtitleTimedUnit(
        identity=SubtitleTimedUnitId(f"timed-{order}"),
        time_revision_id=TIME_REVISION,
        source_reading_unit_id=SubtitleReadingUnitId(reading_unit_id),
        display_order=order,
        timing_status=(
            SubtitleTimingStatus.ANCHORED if anchored else SubtitleTimingStatus.UNRESOLVED
        ),
        source_timeline_id=TIMELINE if anchored else None,
        start=float(order) if anchored else None,
        end=float(order) + 1.0 if anchored else None,
    )


def _reading_unit(name, lines):
    return SubtitleReadingUnit(
        identity=SubtitleReadingUnitId(name),
        reading_revision_id=READING_REVISION,
        source_cue_ids=(SubtitleCandidateCueId(f"{name}-cue"),),
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("transcript-revision"),
        lines=lines,
        display_order=0,
        source_timeline_id=TIMELINE,
        start=0.0,
        end=1.0,
    )


def _time_revision(unit_ids):
    return SubtitleTimeRevision(
        identity=TIME_REVISION,
        domain_result_id=DomainResultId("time-result"),
        source_reading_revision_id=READING_REVISION,
        source_candidate_id=SubtitleCandidateId("candidate"),
        source_intake_id=SubtitleTranscriptIntakeId("intake"),
        source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
        source_selection_id=TranscriptCurrentSelectionId("selection"),
        source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
        source_decision_id=TranscriptReviewDecisionId("decision"),
        review_item_id=ReviewItemId("item"),
        candidate_reference_id=CandidateReferenceId("reference"),
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("transcript-revision"),
        source_media_id=MEDIA,
        source_timeline_id=TIMELINE,
        validation_id=__import__(
            "lectureos.transcript.identities", fromlist=["TranscriptValidationId"]
        ).TranscriptValidationId("transcript-validation"),
        timed_unit_ids=tuple(unit_ids),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="time",
    )


def _reading_revision(unit_ids):
    return SubtitleReadingRevision(
        identity=READING_REVISION,
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
        source_revision_id=TranscriptRevisionId("transcript-revision"),
        source_media_id=MEDIA,
        source_timeline_id=TIMELINE,
        validation_id=__import__(
            "lectureos.transcript.identities", fromlist=["TranscriptValidationId"]
        ).TranscriptValidationId("transcript-validation"),
        unit_ids=tuple(unit_ids),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="reading",
    )


def _final(name, kind, target_unit, *, applied_text=None, sequence=0):
    applied_outcome = applied_outcome_for_kind(kind)
    return SubtitleFinalSubtitle(
        identity=SubtitleFinalSubtitleId(name),
        domain_result_id=DomainResultId(f"{name}-result"),
        source_decision_revision_id=SubtitleDecisionRevisionId(f"{name}-revision"),
        decision_kind=kind,
        applied_outcome=applied_outcome,
        final_outcome=final_outcome_for_applied_outcome(applied_outcome),
        source_review_decision_id=SubtitleReviewDecisionId(f"{name}-decision"),
        review_item_id=ReviewItemId(f"{name}-item"),
        candidate_reference_id=CandidateReferenceId("reference"),
        source_preparation_id=SubtitleReviewPreparationId("preparation"),
        source_validation_id=SubtitleValidationId("validation"),
        source_time_revision_id=TIME_REVISION,
        source_reading_revision_id=READING_REVISION,
        source_candidate_id=SubtitleCandidateId("candidate"),
        source_finding_id=SubtitleValidationFindingId(f"{name}-finding"),
        rule=RULE_OVERLAP_ADJACENT,
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("transcript-revision"),
        source_media_id=MEDIA,
        source_timeline_id=TIMELINE,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=sequence,
        reason="final",
        target_timed_unit_id=SubtitleTimedUnitId(target_unit),
        applied_text=applied_text,
    )


class ApprovedSubtitleAssemblyServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="approved-assembly",
                capabilities=(CapabilityReference("subtitle.export"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("approved-assembly"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        # three units: 0, 1, 2 -> reading r0, r1, r2
        self.timed_units = [
            _timed_unit(0, "r0"),
            _timed_unit(1, "r1"),
            _timed_unit(2, "r2"),
        ]
        self.reading_units = [
            _reading_unit("r0", ("첫 자막",)),
            _reading_unit("r1", ("둘째 자막",)),
            _reading_unit("r2", ("셋째 자막",)),
        ]
        self.time_ids = [u.identity for u in self.timed_units]

    def _service(self, finals, decision_ids=None):
        if decision_ids is None:
            decision_ids = [f.source_decision_revision_id for f in finals]
        return SubtitleApprovedSubtitleAssemblyService(
            _FakeTimeQuery(_time_revision(self.time_ids), self.timed_units),
            _FakeReadingQuery(_reading_revision([u.identity for u in self.reading_units]), self.reading_units),
            _FakeFinalQuery(finals),
            _FakeDecisionQuery(decision_ids),
            self.execution,
        )

    def _plan(self):
        return SubtitleApprovedAssemblyIdentityPlan(
            document_id=SubtitleApprovedDocumentId("document"),
            document_result_id=DomainResultId("document-result"),
            unit_ids=(
                SubtitleApprovedUnitId("a0"),
                SubtitleApprovedUnitId("a1"),
                SubtitleApprovedUnitId("a2"),
            ),
        )

    def _assemble(self, service):
        return service.assemble(
            source_time_revision_id=TIME_REVISION,
            source_reading_revision_id=READING_REVISION,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )

    def test_accept_modify_reject_and_untouched(self) -> None:
        finals = [
            _final("accept", DecisionKind.ACCEPT, "timed-0"),
            _final("modify", DecisionKind.MODIFY, "timed-1", applied_text="고친 자막"),
            _final("reject", DecisionKind.REJECT, "timed-2"),
        ]
        # note: unit 2 rejected -> omitted; no finding on any other unit; all three units decided
        prepared = self._assemble(self._service(finals))
        document = prepared.document
        self.assertIs(document.eligibility, SubtitleExportEligibility.ELIGIBLE)
        self.assertEqual(document.omitted_unit_count, 1)
        self.assertEqual(len(prepared.units), 2)  # unit 2 omitted
        accepted, modified = prepared.units
        self.assertIs(accepted.origin, SubtitleApprovedUnitOrigin.ACCEPTED)
        self.assertEqual(accepted.lines, ("첫 자막",))
        self.assertIs(modified.origin, SubtitleApprovedUnitOrigin.MODIFIED)
        self.assertEqual(modified.lines, ("고친 자막",))
        # order preserved from timed units
        self.assertEqual(accepted.display_order, 0)
        self.assertEqual(modified.display_order, 1)
        self.assertEqual(document.approved_unit_ids, (accepted.identity, modified.identity))
        self.assertEqual(prepared.document_result.kind, "subtitle_approved_document")
        self.assertEqual(
            prepared.document_result.upstream_results, (DomainResultId("time-result"),)
        )

    def test_untouched_units_keep_original_text(self) -> None:
        # no finalized decisions at all -> zero-finding document, all untouched
        prepared = self._assemble(self._service([]))
        document = prepared.document
        self.assertIs(document.eligibility, SubtitleExportEligibility.ELIGIBLE)
        self.assertEqual(len(prepared.units), 3)
        self.assertTrue(
            all(u.origin is SubtitleApprovedUnitOrigin.UNTOUCHED for u in prepared.units)
        )
        self.assertTrue(all(u.source_final_subtitle_id is None for u in prepared.units))
        self.assertEqual(document.omitted_unit_count, 0)

    def test_current_finalization_wins_by_sequence(self) -> None:
        finals = [
            _final("reject", DecisionKind.REJECT, "timed-0", sequence=0),
            _final("modify", DecisionKind.MODIFY, "timed-0", applied_text="다시 고침", sequence=1),
        ]
        prepared = self._assemble(self._service(finals))
        # unit 0 has both a reject (seq 0) and a later modify (seq 1) -> modify wins -> included
        unit0 = prepared.units[0]
        self.assertIs(unit0.origin, SubtitleApprovedUnitOrigin.MODIFIED)
        self.assertEqual(unit0.lines, ("다시 고침",))
        self.assertEqual(prepared.document.omitted_unit_count, 0)

    def test_ineligible_when_included_unit_lacks_timing(self) -> None:
        self.timed_units[1] = _timed_unit(1, "r1", anchored=False)
        prepared = self._assemble(self._service([]))
        self.assertIs(prepared.document.eligibility, SubtitleExportEligibility.INELIGIBLE)
        self.assertIsNotNone(prepared.document.ineligibility_reason)
        self.assertEqual(prepared.units, ())
        self.assertEqual(prepared.document.approved_unit_ids, ())

    def test_ineligible_when_final_provenance_mismatches(self) -> None:
        bad = _final("bad", DecisionKind.ACCEPT, "timed-0")
        object.__setattr__(bad, "source_reading_revision_id", SubtitleReadingRevisionId("other"))
        prepared = self._assemble(self._service([bad]))
        self.assertIs(prepared.document.eligibility, SubtitleExportEligibility.INELIGIBLE)
        self.assertEqual(prepared.units, ())

    def test_ineligible_when_final_targets_foreign_unit(self) -> None:
        stray = _final("stray", DecisionKind.ACCEPT, "timed-99")
        prepared = self._assemble(self._service([stray]))
        self.assertIs(prepared.document.eligibility, SubtitleExportEligibility.INELIGIBLE)

    def test_ineligible_when_decision_revision_unresolved(self) -> None:
        final = _final("accept", DecisionKind.ACCEPT, "timed-0")
        prepared = self._assemble(self._service([final], decision_ids=[]))
        self.assertIs(prepared.document.eligibility, SubtitleExportEligibility.INELIGIBLE)

    def test_unknown_time_revision_raises(self) -> None:
        service = self._service([])
        with self.assertRaises(KeyError):
            service.assemble(
                source_time_revision_id=SubtitleTimeRevisionId("missing"),
                source_reading_revision_id=READING_REVISION,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_identity_plan_count_must_match(self) -> None:
        service = self._service([])
        plan = SubtitleApprovedAssemblyIdentityPlan(
            document_id=SubtitleApprovedDocumentId("document"),
            document_result_id=DomainResultId("document-result"),
            unit_ids=(SubtitleApprovedUnitId("only-one"),),
        )
        with self.assertRaises(SubtitleApprovedAssemblyError):
            service.assemble(
                source_time_revision_id=TIME_REVISION,
                source_reading_revision_id=READING_REVISION,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=plan,
            )

    def test_requires_running_execution(self) -> None:
        service = self._service([])
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(SubtitleApprovedAssemblyError):
            self._assemble(service)

    def test_deterministic_construction(self) -> None:
        finals = [_final("modify", DecisionKind.MODIFY, "timed-1", applied_text="고친 자막")]
        service = self._service(finals)
        self.assertEqual(self._assemble(service), self._assemble(service))

    def test_record_without_persistence_raises(self) -> None:
        service = self._service([])
        with self.assertRaises(RuntimeError):
            service.record_assembly(
                source_time_revision_id=TIME_REVISION,
                source_reading_revision_id=READING_REVISION,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
