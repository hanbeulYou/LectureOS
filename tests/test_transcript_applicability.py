import unittest
from dataclasses import replace

from lectureos.application.identities import TranscriptCorrectionApplicationResultId
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
from lectureos.execution.models import ExecutionIntent, DomainResultReference, ProcessingUnit
from lectureos.execution.service import ExecutionService
from lectureos.review.identities import ApprovedDecisionId, ReviewDecisionId
from lectureos.transcript.applicability import (
    CurrentTranscriptSelection,
    RevisionApplicabilityRecord,
    RevisionTarget,
    TranscriptApplicabilityIntegrityError,
    TranscriptApplicabilityKind,
    TranscriptApplicabilityService,
)
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptApplicabilityId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import (
    CorrectedTranscriptRevision,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
    TranscriptValidation,
)
from lectureos.transcript.service import TranscriptService


class TranscriptRevisionApplicabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.execution = ExecutionService()
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("transcript.applicability"),
            purpose="prepare transcript applicability fixtures",
            capabilities=(CapabilityReference("transcript.correction"),),
            result_kinds=("corrected_transcript_revision",),
        )
        self.execution.register_unit(self.unit)
        self.run_id = ProcessingRunId("run-applicability")
        self.execution_id = UnitExecutionId("execution-applicability")
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("applicability test"),
            working_context=WorkingContextReference("context-applicability"),
            unit_ids=(self.unit.identity,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit.identity,
        )
        self.transcript = TranscriptService(self.execution)
        self.context = WorkingContextReference("context-applicability")
        self.timeline = SourceTimelineId("timeline-applicability")
        self.raw = self._create_raw()
        self.first = self._create_revision("first", parent_raw=self.raw.identity)
        self.second = self._create_revision("second", parent_revision=self.first.identity)
        self.service = TranscriptApplicabilityService(self.transcript)
        self.raw_target = RevisionTarget(
            transcript_id=self.raw.identity,
            source_timeline_id=self.timeline,
        )
        self.first_target = RevisionTarget(
            transcript_id=self.raw.identity,
            source_timeline_id=self.timeline,
            revision_id=self.first.identity,
        )
        self.second_target = RevisionTarget(
            transcript_id=self.raw.identity,
            source_timeline_id=self.timeline,
            revision_id=self.second.identity,
        )

    def test_new_revision_registers_as_undetermined(self) -> None:
        record = self._register_undetermined()
        self.assertEqual(TranscriptApplicabilityKind.UNDETERMINED, record.kind)

    def test_revision_registration_does_not_select_current(self) -> None:
        self._register_undetermined()
        self.assertIsNone(self.service.get_current_revision(self.context, self.raw.identity))

    def test_current_revision_can_be_selected_explicitly(self) -> None:
        selection = self._select_first()
        self.assertEqual(TranscriptApplicabilityKind.CURRENT, selection.kind)
        self.assertEqual(self.first_target, selection.target)
        self.assertEqual(
            self.first_target,
            self.service.get_current_revision(self.context, self.raw.identity),
        )

    def test_current_selection_does_not_change_revision(self) -> None:
        before = self.transcript.get_corrected_revision(self.first.identity)
        self._select_first()
        self.assertEqual(before, self.transcript.get_corrected_revision(self.first.identity))

    def test_selection_and_revision_identity_are_distinct(self) -> None:
        selection = self._select_first()
        self.assertNotEqual(selection.identity.value, self.first.identity.value)

    def test_one_current_is_maintained_per_context_and_lineage(self) -> None:
        self._select_first()
        self._select_second()
        current = self.service.get_current_selection(self.context, self.raw.identity)
        self.assertEqual(self.second_target, current.target)

    def test_new_selection_does_not_overwrite_previous_selection(self) -> None:
        first = self._select_first()
        before = self.service.selections.get(first.identity)
        self._select_second()
        self.assertEqual(before, self.service.selections.get(first.identity))

    def test_previous_current_is_preserved_as_superseded(self) -> None:
        self._select_first()
        self._select_second()
        relationships = self.service.get_superseded_relationships(
            self.context, self.raw.identity
        )
        self.assertEqual(self.first_target, relationships[0].target)
        self.assertEqual(self.second_target, relationships[0].superseding_target)

    def test_superseded_revision_is_not_deleted(self) -> None:
        self._select_first()
        self._select_second()
        self.assertEqual(
            self.first, self.transcript.get_corrected_revision(self.first.identity)
        )

    def test_stale_marking_does_not_change_revision(self) -> None:
        before = self.transcript.get_corrected_revision(self.first.identity)
        self._mark_first_stale()
        self.assertEqual(before, self.transcript.get_corrected_revision(self.first.identity))

    def test_stale_marking_does_not_create_reject_decision(self) -> None:
        record = self._mark_first_stale()
        self.assertFalse(hasattr(record, "decision_kind"))
        self.assertFalse(hasattr(self.service, "reject"))

    def test_stale_revision_remains_in_history(self) -> None:
        stale = self._mark_first_stale()
        self.assertIn(stale, self.service.get_revision_history(self.context, self.first_target))

    def test_validation_success_does_not_select_current(self) -> None:
        validation = TranscriptValidation(
            identity=TranscriptValidationId("validation-applicability"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            structural_valid=True,
            timeline_traceable=True,
            provenance_complete=True,
            target_revision_id=self.first.identity,
        )
        self.transcript.record_validation(validation)
        self.assertIsNone(self.service.get_current_revision(self.context, self.raw.identity))

    def test_approved_decision_reference_does_not_select_current(self) -> None:
        self._register_undetermined(
            approved_id=ApprovedDecisionId("approved-applicability")
        )
        self.assertIsNone(self.service.get_current_revision(self.context, self.raw.identity))

    def test_application_result_reference_does_not_select_current(self) -> None:
        self._register_undetermined(
            application_id=TranscriptCorrectionApplicationResultId(
                "application-applicability"
            )
        )
        self.assertIsNone(self.service.get_current_revision(self.context, self.raw.identity))

    def test_newest_revision_is_not_automatically_current(self) -> None:
        self._register_undetermined(target=self.second_target)
        self.assertIsNone(self.service.get_current_revision(self.context, self.raw.identity))

    def test_late_revision_is_not_automatically_current(self) -> None:
        self._select_second()
        self._register_undetermined(target=self.first_target, suffix="late")
        self.assertEqual(
            self.second_target,
            self.service.get_current_revision(self.context, self.raw.identity),
        )

    def test_reprocessing_record_does_not_replace_current(self) -> None:
        self._select_first()
        self.service.record_reprocessing_relationship(
            identity=TranscriptApplicabilityId("reprocessing-stale"),
            working_context=self.context,
            target=self.first_target,
            reason="new processing run",
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.assertEqual(
            self.first_target,
            self.service.get_current_revision(self.context, self.raw.identity),
        )

    def test_unknown_revision_cannot_be_selected(self) -> None:
        with self.assertRaisesRegex(KeyError, "unknown corrected"):
            self.service.select_current_revision(
                identity=TranscriptApplicabilityId("selection-unknown"),
                working_context=self.context,
                target=replace(
                    self.first_target, revision_id=TranscriptRevisionId("missing")
                ),
                reason="invalid selection",
            )

    def test_other_lineage_cannot_be_superseded(self) -> None:
        other_raw = self._create_raw("other")
        other_revision = self._create_revision(
            "other", transcript_id=other_raw.identity, parent_raw=other_raw.identity
        )
        with self.assertRaisesRegex(ValueError, "another transcript lineage"):
            self.service.supersede_revision(
                identity=TranscriptApplicabilityId("supersede-other"),
                working_context=self.context,
                target=self.first_target,
                superseding_revision_id=other_revision.identity,
                reason="invalid lineage",
            )

    def test_revision_cannot_supersede_itself(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot supersede itself"):
            self.service.supersede_revision(
                identity=TranscriptApplicabilityId("supersede-self"),
                working_context=self.context,
                target=self.first_target,
                superseding_revision_id=self.first.identity,
                reason="invalid self relation",
            )

    def test_revision_can_be_explicitly_superseded(self) -> None:
        before = self.transcript.get_corrected_revision(self.first.identity)
        record = self.service.supersede_revision(
            identity=TranscriptApplicabilityId("supersede-explicit"),
            working_context=self.context,
            target=self.first_target,
            superseding_revision_id=self.second.identity,
            reason="explicit replacement relationship",
            source_application_result_id=TranscriptCorrectionApplicationResultId(
                "application-supersession"
            ),
        )
        self.assertEqual(TranscriptApplicabilityKind.SUPERSEDED, record.kind)
        self.assertEqual(self.first_target, record.target)
        self.assertEqual(self.second_target, record.superseding_target)
        self.assertEqual(
            before, self.transcript.get_corrected_revision(self.first.identity)
        )

    def test_duplicate_applicability_identity_is_rejected(self) -> None:
        self._register_undetermined()
        with self.assertRaisesRegex(ValueError, "identity already exists"):
            self._select_first(identity="applicability-undetermined")

    def test_conflicting_current_selections_are_detected(self) -> None:
        first = self._select_first()
        conflict = CurrentTranscriptSelection(
            identity=TranscriptApplicabilityId("selection-conflict"),
            working_context=self.context,
            target=self.second_target,
            reason="corrupt branch",
            sequence=first.sequence + 1,
            previous_selection_id=None,
        )
        self.service.selections.save(conflict)
        with self.assertRaises(TranscriptApplicabilityIntegrityError):
            self.service.get_current_selection(self.context, self.raw.identity)

    def test_conflict_does_not_return_arbitrary_revision(self) -> None:
        self.test_conflicting_current_selections_are_detected()

    def test_current_revision_can_be_absent(self) -> None:
        self.assertIsNone(self.service.get_current_selection(self.context, self.raw.identity))

    def test_raw_transcript_can_be_selected_current(self) -> None:
        selection = self.service.select_current_revision(
            identity=TranscriptApplicabilityId("selection-raw"),
            working_context=self.context,
            target=self.raw_target,
            reason="use preserved raw transcript",
        )
        self.assertEqual(self.raw_target, selection.target)

    def test_working_contexts_have_independent_current_selections(self) -> None:
        other_context = WorkingContextReference("context-other")
        self._select_first()
        other = self.service.select_current_revision(
            identity=TranscriptApplicabilityId("selection-other-context"),
            working_context=other_context,
            target=self.second_target,
            reason="independent context selection",
        )
        self.assertEqual(
            self.first_target,
            self.service.get_current_revision(self.context, self.raw.identity),
        )
        self.assertEqual(
            other.target,
            self.service.get_current_revision(other_context, self.raw.identity),
        )

    def test_selection_history_is_append_only(self) -> None:
        self._select_first()
        before = self.service.get_applicability_history(self.context, self.raw.identity)
        self._select_second()
        after = self.service.get_applicability_history(self.context, self.raw.identity)
        self.assertGreater(len(after), len(before))
        self.assertEqual(before[0], after[0])

    def test_past_selection_is_unchanged(self) -> None:
        first = self._select_first()
        self._select_second()
        self.assertEqual(first, self.service.selections.get(first.identity))

    def test_approved_decision_provenance_is_preserved(self) -> None:
        approved = ApprovedDecisionId("approved-selection")
        selection = self._select_first(approved_id=approved)
        self.assertEqual(approved, selection.source_approved_decision_id)

    def test_review_decision_provenance_is_preserved(self) -> None:
        selection = self._select_first()
        self.assertEqual(
            ReviewDecisionId("decision-selection"), selection.source_decision_id
        )

    def test_application_result_provenance_is_preserved(self) -> None:
        application = TranscriptCorrectionApplicationResultId("application-selection")
        selection = self._select_first(application_id=application)
        self.assertEqual(application, selection.source_application_result_id)

    def test_execution_provenance_is_preserved(self) -> None:
        selection = self._select_first(include_execution=True)
        self.assertEqual(self.run_id, selection.run_id)
        self.assertEqual(self.execution_id, selection.unit_execution_id)

    def test_source_timeline_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Source Timeline"):
            self.service.mark_historical(
                identity=TranscriptApplicabilityId("historical-wrong-timeline"),
                working_context=self.context,
                target=replace(
                    self.first_target,
                    source_timeline_id=SourceTimelineId("wrong-timeline"),
                ),
                reason="invalid timeline",
            )

    def test_current_revision_can_also_be_stale(self) -> None:
        self._select_first()
        self._mark_first_stale()
        self.assertEqual(
            self.first_target,
            self.service.get_current_revision(self.context, self.raw.identity),
        )
        self.assertIn(
            self.first_target,
            self.service.get_stale_revisions(self.context, self.raw.identity),
        )

    def test_stale_does_not_automatically_clear_current(self) -> None:
        self.test_current_revision_can_also_be_stale()

    def test_stale_target_requires_confirmation_for_selection(self) -> None:
        self._mark_first_stale()
        with self.assertRaisesRegex(ValueError, "Human confirmation"):
            self._select_first()
        selection = self._select_first(
            identity="selection-confirmed", human_confirmation=True
        )
        self.assertTrue(selection.human_confirmation)

    def test_superseded_revision_can_be_marked_historical(self) -> None:
        self._select_first()
        self._select_second()
        historical = self.service.mark_historical(
            identity=TranscriptApplicabilityId("historical-first"),
            working_context=self.context,
            target=self.first_target,
            reason="preserve prior selection",
        )
        self.assertEqual(TranscriptApplicabilityKind.HISTORICAL, historical.kind)

    def test_superseded_revision_can_be_reselected_explicitly(self) -> None:
        self._select_first()
        self._select_second()
        selection = self.service.select_current_revision(
            identity=TranscriptApplicabilityId("selection-first-again"),
            working_context=self.context,
            target=self.first_target,
            reason="explicit rollback selection",
            superseded_record_id=TranscriptApplicabilityId("superseded-second"),
        )
        self.assertEqual(self.first_target, selection.target)

    def test_historical_marking_does_not_delete_revision(self) -> None:
        before = self.transcript.get_corrected_revision(self.first.identity)
        self.service.mark_historical(
            identity=TranscriptApplicabilityId("historical-preserved"),
            working_context=self.context,
            target=self.first_target,
            reason="preserve provenance",
        )
        self.assertEqual(before, self.transcript.get_corrected_revision(self.first.identity))

    def test_rejected_command_leaves_no_partial_record(self) -> None:
        with self.assertRaisesRegex(ValueError, "Source Timeline"):
            self.service.select_current_revision(
                identity=TranscriptApplicabilityId("selection-not-saved"),
                working_context=self.context,
                target=replace(
                    self.first_target,
                    source_timeline_id=SourceTimelineId("wrong"),
                ),
                reason="invalid selection",
            )
        self.assertIsNone(
            self.service.selections.get(
                TranscriptApplicabilityId("selection-not-saved")
            )
        )
        self.assertEqual((), self.service.records.all())

    def test_service_does_not_modify_transcript_content(self) -> None:
        before = self.transcript.get_segment(self.first.segment_ids[0])
        self._select_first()
        self._mark_first_stale()
        self.assertEqual(before, self.transcript.get_segment(self.first.segment_ids[0]))

    def test_service_does_not_create_review_decision(self) -> None:
        self.assertFalse(hasattr(self.service, "accept"))
        self.assertFalse(hasattr(self.service, "record_reject"))

    def test_service_does_not_create_revision(self) -> None:
        self.assertFalse(hasattr(self.service, "create_corrected_revision"))

    def test_applicability_record_is_not_domain_result(self) -> None:
        record = self._register_undetermined()
        self.assertNotIsInstance(record, DomainResultReference)
        self.assertFalse(hasattr(record, "domain_result_id"))

    def _register_undetermined(
        self,
        *,
        target=None,
        suffix="undetermined",
        approved_id=None,
        application_id=None,
    ):
        return self.service.register_undetermined_revision(
            identity=TranscriptApplicabilityId(f"applicability-{suffix}"),
            working_context=self.context,
            target=target or self.first_target,
            reason="new revision awaits selection",
            source_approved_decision_id=approved_id,
            source_application_result_id=application_id,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )

    def _select_first(
        self,
        *,
        identity="selection-first",
        approved_id=None,
        application_id=None,
        include_execution=False,
        human_confirmation=False,
    ):
        return self.service.select_current_revision(
            identity=TranscriptApplicabilityId(identity),
            working_context=self.context,
            target=self.first_target,
            reason="explicit current selection",
            source_decision_id=ReviewDecisionId("decision-selection"),
            source_approved_decision_id=approved_id,
            source_application_result_id=application_id,
            run_id=self.run_id if include_execution else None,
            unit_execution_id=self.execution_id if include_execution else None,
            human_confirmation=human_confirmation,
        )

    def _select_second(self):
        previous = self.service.get_current_selection(self.context, self.raw.identity)
        return self.service.select_current_revision(
            identity=TranscriptApplicabilityId("selection-second"),
            working_context=self.context,
            target=self.second_target,
            reason="explicit replacement selection",
            superseded_record_id=(
                TranscriptApplicabilityId("superseded-first")
                if previous is not None and previous.target != self.second_target
                else None
            ),
        )

    def _mark_first_stale(self):
        return self.service.mark_revision_stale(
            identity=TranscriptApplicabilityId("stale-first"),
            working_context=self.context,
            target=self.first_target,
            reason="upstream changed",
        )

    def _create_raw(self, suffix="main"):
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId(f"provider-{suffix}"),
            source_media_id=SourceMediaId(f"media-{suffix}"),
            source_timeline_id=SourceTimelineId(
                f"timeline-{suffix}" if suffix != "main" else self.timeline.value
            ),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="test-provider",
            original_content="원문",
        )
        self.transcript.register_provider_result(provider)
        transcript_id = TranscriptId(f"raw-{suffix}")
        segment = TranscriptSegment(
            identity=TranscriptSegmentId(f"segment-{suffix}"),
            transcript_id=transcript_id,
            source_timeline_id=provider.source_timeline_id,
            text="원문",
            source_order=0,
            start=0.0,
            end=1.0,
        )
        raw = RawTranscript(
            identity=transcript_id,
            domain_result_id=DomainResultId(f"raw-result-{suffix}"),
            source_media_id=provider.source_media_id,
            source_timeline_id=provider.source_timeline_id,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(segment.identity,),
        )
        self.transcript.create_raw_transcript(raw, (segment,))
        return raw

    def _create_revision(
        self,
        suffix,
        *,
        transcript_id=None,
        parent_raw=None,
        parent_revision=None,
    ):
        transcript_id = transcript_id or self.raw.identity
        raw = self.transcript.get_raw_transcript(transcript_id)
        segment = TranscriptSegment(
            identity=TranscriptSegmentId(f"revision-segment-{suffix}"),
            transcript_id=transcript_id,
            source_timeline_id=raw.source_timeline_id,
            text=f"수정 {suffix}",
            source_order=0,
            start=0.0,
            end=1.0,
        )
        revision = CorrectedTranscriptRevision(
            identity=TranscriptRevisionId(f"revision-{suffix}"),
            transcript_id=transcript_id,
            domain_result_id=DomainResultId(f"revision-result-{suffix}"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(segment.identity,),
            parent_raw_transcript_id=parent_raw,
            parent_revision_id=parent_revision,
        )
        self.transcript.create_corrected_revision(revision, (segment,))
        return revision


if __name__ == "__main__":
    unittest.main()
