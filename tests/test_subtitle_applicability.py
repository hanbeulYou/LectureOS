import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from lectureos.application.identities import SubtitleDecisionApplicationResultId
from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    PluginReference,
    ProcessingRunId,
    ProcessingUnitId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import DomainResultReference, ExecutionIntent, ProcessingUnit
from lectureos.execution.service import ExecutionService
from lectureos.review.identities import HumanActorReference, ReviewItemId
from lectureos.review.service import ReviewService
from lectureos.subtitle.applicability import (
    SubtitleApplicabilityDimension,
    SubtitleApplicabilityEvidence,
    SubtitleApplicabilityIntegrityError,
    SubtitleApplicabilityService,
    SubtitleConditionReason,
    SubtitleConditionState,
    SubtitleRevisionApplicabilityRecord,
    SubtitleSelectionReason,
    SubtitleSelectionState,
)
from lectureos.subtitle.identities import (
    SubtitleCandidateId,
    SubtitleCueId,
    SubtitleId,
    SubtitleRevisionApplicabilityId,
    SubtitleRevisionId,
)
from lectureos.subtitle.models import SubtitleCandidate, SubtitleCue, SubtitleRevision
from lectureos.subtitle.service import SubtitleService
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import (
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)
from lectureos.transcript.service import TranscriptService


class SubtitleRevisionApplicabilityTest(unittest.TestCase):
    def setUp(self):
        self.execution = ExecutionService()
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("subtitle.applicability"),
            purpose="prepare Subtitle applicability fixtures",
            capabilities=(CapabilityReference("subtitle.applicability"),),
            result_kinds=("subtitle_revision",),
        )
        self.execution.register_unit(self.unit)
        self.context = WorkingContextReference("subtitle-context")
        self.run_id, self.execution_id = self._start_execution("main", self.context)
        self.timeline = SourceTimelineId("subtitle-applicability-timeline")
        self.media = SourceMediaId("subtitle-applicability-media")
        self.transcript = TranscriptService(self.execution)
        self.raw, self.segment = self._create_raw()
        self.subtitle = SubtitleService(self.transcript, self.execution)
        self.candidate, self.cue = self._create_candidate()
        self.first = self._create_revision("first")
        self.second = self._create_revision("second")
        self.service = SubtitleApplicabilityService(self.subtitle, self.execution)
        self.actor = HumanActorReference("subtitle-selector")

    def test_selection_and_condition_are_independent_dimensions(self):
        current = self._select(self.first)
        stale = self._stale(self.first)
        self.assertEqual(SubtitleApplicabilityDimension.SELECTION, current.dimension)
        self.assertEqual(SubtitleApplicabilityDimension.CONDITION, stale.dimension)
        self.assertEqual(self.first.identity, self.service.get_current_revision(
            self.context, self.first.subtitle_id
        ))
        self.assertTrue(self.service.is_revision_stale(
            self.context, self.first.identity
        ))

    def test_applicability_is_separate_append_only_and_preserves_revision(self):
        before = self.subtitle.get_revision(self.first.identity)
        current = self._select(self.first)
        historical = self._historical(self.first)
        self.assertNotEqual(self.first.identity.value, current.identity.value)
        self.assertEqual(before, self.subtitle.get_revision(self.first.identity))
        self.assertEqual(current, self.service.selection_records.get(current.identity))
        self.assertEqual(
            (current, historical),
            self.service.get_revision_selection_history(
                self.context, self.first.identity
            ),
        )
        self.assertIsInstance(current.recorded_at, datetime)

    def test_revision_creation_does_not_select_current(self):
        self.assertIsNone(
            self.service.get_current_revision(self.context, self.first.subtitle_id)
        )

    def test_new_current_supersedes_existing_current_in_one_chain(self):
        first = self._select(self.first)
        second = self._select(
            self.second,
            identity="current-second",
            superseded_identity="superseded-first",
        )
        history = self.service.get_scope_selection_history(
            self.context, self.first.subtitle_id
        )
        self.assertEqual(
            (
                SubtitleSelectionState.CURRENT,
                SubtitleSelectionState.SUPERSEDED,
                SubtitleSelectionState.CURRENT,
            ),
            tuple(record.selection_state for record in history),
        )
        self.assertEqual(first.identity, history[1].previous_record_id)
        self.assertEqual(history[1].identity, second.previous_record_id)
        self.assertEqual(
            self.second.identity,
            self.service.get_current_revision(self.context, self.first.subtitle_id),
        )

    def test_reselecting_same_current_is_idempotent(self):
        first = self._select(self.first)
        repeated = self._select(self.first, identity="unused-current-id")
        self.assertEqual(first, repeated)
        self.assertEqual(
            1,
            len(self.service.get_scope_selection_history(
                self.context, self.first.subtitle_id
            )),
        )

    def test_current_can_be_absent_and_historical_can_remove_current(self):
        self.assertIsNone(
            self.service.get_current_revision(self.context, self.first.subtitle_id)
        )
        self._select(self.first)
        self._historical(self.first)
        self.assertIsNone(
            self.service.get_current_revision(self.context, self.first.subtitle_id)
        )

    def test_multiple_current_corruption_is_not_hidden(self):
        self._select(self.first)
        corrupt = SubtitleRevisionApplicabilityRecord(
            identity=SubtitleRevisionApplicabilityId("corrupt-current"),
            dimension=SubtitleApplicabilityDimension.SELECTION,
            working_context=self.context,
            subtitle_id=self.second.subtitle_id,
            revision_id=self.second.identity,
            actor=self.actor,
            recorded_at=datetime.now(timezone.utc),
            sequence=1,
            selection_state=SubtitleSelectionState.CURRENT,
            selection_reason=SubtitleSelectionReason.MANUAL_SELECTION,
        )
        self.service.selection_records.save(corrupt)
        with self.assertRaises(SubtitleApplicabilityIntegrityError):
            self.service.get_current_revision(self.context, self.first.subtitle_id)

    def test_superseded_and_historical_revisions_can_be_reselected(self):
        self._select(self.first)
        self._select(
            self.second,
            identity="current-second",
            superseded_identity="superseded-first",
        )
        reselected = self._select(
            self.first,
            identity="current-first-again",
            superseded_identity="superseded-second",
            reason=SubtitleSelectionReason.REACTIVATION,
        )
        self.assertEqual(SubtitleSelectionState.CURRENT, reselected.selection_state)
        self._historical(self.first)
        historical_reselected = self._select(
            self.first,
            identity="current-after-history",
            reason=SubtitleSelectionReason.REACTIVATION,
        )
        self.assertEqual(
            SubtitleSelectionState.CURRENT,
            historical_reselected.selection_state,
        )

    def test_stale_revision_requires_acknowledgment_and_remains_stale(self):
        self._stale(self.first)
        with self.assertRaisesRegex(ValueError, "acknowledgment"):
            self._select(self.first)
        selected = self._select(
            self.first,
            identity="current-stale-confirmed",
            stale_condition_acknowledged=True,
        )
        self.assertTrue(selected.stale_condition_acknowledged)
        self.assertTrue(self.service.is_revision_stale(
            self.context, self.first.identity
        ))

    def test_existing_current_marked_stale_requires_acknowledgment_on_reselection(self):
        current = self._select(self.first)
        self._stale(self.first)
        with self.assertRaisesRegex(ValueError, "acknowledgment"):
            self._select(self.first, identity="repeat-current")
        repeated = self._select(
            self.first,
            identity="repeat-current-confirmed",
            stale_condition_acknowledged=True,
        )
        self.assertEqual(current, repeated)
        self.assertTrue(self.service.is_revision_stale(
            self.context, self.first.identity
        ))

    def test_stale_command_is_idempotent_and_does_not_change_selection(self):
        self._select(self.first)
        stale = self._stale(self.first)
        repeated = self._stale(self.first, identity="unused-stale")
        self.assertEqual(stale, repeated)
        self.assertEqual(
            self.first.identity,
            self.service.get_current_revision(self.context, self.first.subtitle_id),
        )

    def test_selection_and_condition_chains_do_not_mix(self):
        current = self._select(self.first)
        stale_first = self._stale(self.first)
        stale_second = self._stale(self.second, identity="stale-second")
        self.assertIsNone(current.previous_record_id)
        self.assertIsNone(stale_first.previous_record_id)
        self.assertEqual(stale_first.identity, stale_second.previous_record_id)
        self.assertEqual(
            current,
            self.service.get_latest_scope_selection(
                self.context, self.first.subtitle_id
            ),
        )
        self.assertEqual(
            stale_second,
            self.service.get_latest_scope_condition(
                self.context, self.first.subtitle_id
            ),
        )
        self.assertEqual(
            (current, stale_first),
            self.service.get_revision_applicability_history(
                self.context, self.first.identity
            ),
        )

    def test_explicit_superseded_and_historical_transitions_are_idempotent(self):
        superseded = self._superseded(self.first)
        self.assertEqual(
            superseded,
            self._superseded(self.first, identity="unused-superseded"),
        )
        historical = self._historical(self.first)
        self.assertEqual(
            historical,
            self._historical(self.first, identity="unused-historical"),
        )
        self.assertEqual(
            (
                SubtitleSelectionState.SUPERSEDED,
                SubtitleSelectionState.HISTORICAL,
            ),
            tuple(
                record.selection_state
                for record in self.service.get_revision_selection_history(
                    self.context, self.first.identity
                )
            ),
        )

    def test_human_actor_is_required_for_all_commands(self):
        commands = (
            lambda: self._select(self.first, actor=PluginReference("plugin")),
            lambda: self._stale(self.first, actor=PluginReference("plugin")),
            lambda: self._historical(self.first, actor=PluginReference("plugin")),
            lambda: self._superseded(self.first, actor=PluginReference("plugin")),
        )
        for command in commands:
            with self.subTest(command=command):
                with self.assertRaisesRegex(TypeError, "Human Actor"):
                    command()
                self._assert_no_records()

    def test_working_context_mismatch_is_rejected_for_all_states(self):
        other = WorkingContextReference("other-context")
        commands = (
            lambda: self._select(self.first, working_context=other),
            lambda: self._stale(self.first, working_context=other),
            lambda: self._historical(self.first, working_context=other),
            lambda: self._superseded(self.first, working_context=other),
        )
        for command in commands:
            with self.subTest(command=command):
                with self.assertRaisesRegex(ValueError, "Working Context"):
                    command()
                self._assert_no_records()

    def test_revision_from_another_context_cannot_enter_scope(self):
        other_context = WorkingContextReference("other-context")
        other_run, other_execution = self._start_execution("other", other_context)
        revision = self._create_revision(
            "other-context", run_id=other_run, execution_id=other_execution
        )
        with self.assertRaisesRegex(ValueError, "Working Context"):
            self._select(revision)
        self._assert_no_records()

    def test_other_reason_requires_note(self):
        with self.assertRaisesRegex(ValueError, "non-empty note"):
            self._stale(self.first, reason=SubtitleConditionReason.OTHER)
        self._assert_no_records()
        record = self._stale(
            self.first,
            reason=SubtitleConditionReason.OTHER,
            reason_note="manual upstream investigation",
        )
        self.assertEqual("manual upstream investigation", record.reason_note)

    def test_execution_evidence_is_optional_but_mismatch_is_rejected(self):
        manual = self._select(self.first)
        self.assertIsNone(manual.evidence.run_id)
        preserved = self._historical(
            self.second,
            evidence=SubtitleApplicabilityEvidence(
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
            ),
        )
        self.assertEqual(self.run_id, preserved.evidence.run_id)
        bad = SubtitleApplicabilityEvidence(
            run_id=self.run_id,
            unit_execution_id=UnitExecutionId("missing"),
        )
        with self.assertRaisesRegex(ValueError, "Execution evidence"):
            self._historical(self.second, evidence=bad)
        self.assertEqual(
            2,
            len(
                self.service.get_scope_selection_history(
                    self.context, self.first.subtitle_id
                )
            ),
        )

    def test_selection_reason_must_match_transition(self):
        with self.assertRaisesRegex(ValueError, "current-selection reason"):
            self._select(
                self.first,
                reason=SubtitleSelectionReason.MANUAL_HISTORICAL,
            )
        with self.assertRaisesRegex(ValueError, "manual_historical"):
            self.service.mark_revision_historical(
                identity=SubtitleRevisionApplicabilityId("bad-historical-reason"),
                working_context=self.context,
                revision_id=self.first.identity,
                actor=self.actor,
                reason=SubtitleSelectionReason.MANUAL_SELECTION,
            )
        with self.assertRaisesRegex(ValueError, "replacement_selection"):
            self.service.mark_revision_superseded(
                identity=SubtitleRevisionApplicabilityId("bad-superseded-reason"),
                working_context=self.context,
                revision_id=self.first.identity,
                actor=self.actor,
                reason=SubtitleSelectionReason.REACTIVATION,
            )
        with self.assertRaisesRegex(ValueError, "typed reason"):
            self.service.mark_revision_stale(
                identity=SubtitleRevisionApplicabilityId("untyped-stale-reason"),
                working_context=self.context,
                revision_id=self.first.identity,
                actor=self.actor,
                reason="manual_stale",  # type: ignore[arg-type]
            )
        self._assert_no_records()

    def test_unverifiable_application_or_review_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Application Result evidence"):
            self._select(
                self.first,
                evidence=SubtitleApplicabilityEvidence(
                    application_result_id=SubtitleDecisionApplicationResultId("missing")
                ),
            )
        self._assert_no_records()
        review_service = SubtitleApplicabilityService(
            self.subtitle,
            self.execution,
            review_query=ReviewService(),
        )
        with self.assertRaisesRegex(ValueError, "Review Item evidence"):
            review_service.select_current_revision(
                identity=SubtitleRevisionApplicabilityId("review-evidence-current"),
                working_context=self.context,
                revision_id=self.first.identity,
                actor=self.actor,
                reason=SubtitleSelectionReason.MANUAL_SELECTION,
                evidence=SubtitleApplicabilityEvidence(
                    review_item_id=ReviewItemId("missing")
                ),
            )
        self.assertEqual((), review_service.selection_records.all())

    def test_unknown_revision_and_duplicate_identity_leave_no_partial_records(self):
        with self.assertRaisesRegex(KeyError, "unknown Subtitle Revision"):
            self._select(
                replace(self.first, identity=SubtitleRevisionId("missing"))
            )
        self._assert_no_records()
        self._select(self.first)
        with self.assertRaisesRegex(ValueError, "identity already exists"):
            self._historical(self.second, identity="current-first")
        self.assertIsNone(
            self.service.get_latest_selection(self.context, self.second.identity)
        )

    def test_failed_current_change_does_not_partially_supersede(self):
        first = self._select(self.first)
        with self.assertRaisesRegex(ValueError, "superseded record identity"):
            self._select(self.second, identity="current-second")
        self.assertEqual(
            first,
            self.service.get_latest_selection(self.context, self.first.identity),
        )
        self.assertIsNone(
            self.service.get_latest_selection(self.context, self.second.identity)
        )

    def test_records_do_not_create_final_export_or_revision(self):
        before = self.subtitle.get_lineage(self.first.subtitle_id)
        record = self._select(self.first)
        self.assertEqual(before, self.subtitle.get_lineage(self.first.subtitle_id))
        self.assertFalse(hasattr(record, "final_subtitle_id"))
        self.assertFalse(hasattr(record, "artifact_id"))
        self.assertFalse(hasattr(self.service, "create_revision"))
        self.assertNotIsInstance(record, DomainResultReference)

    def test_applicability_uses_public_boundaries_not_cross_domain_repositories(self):
        source = Path("src/lectureos/subtitle/applicability.py").read_text()
        self.assertNotIn("lectureos.review.repositories", source)
        self.assertNotIn("lectureos.execution.repositories", source)

    def _select(
        self,
        revision,
        *,
        identity="current-first",
        superseded_identity=None,
        working_context=None,
        actor=None,
        reason=SubtitleSelectionReason.MANUAL_SELECTION,
        stale_condition_acknowledged=False,
        evidence=SubtitleApplicabilityEvidence(),
    ):
        return self.service.select_current_revision(
            identity=SubtitleRevisionApplicabilityId(identity),
            superseded_identity=(
                SubtitleRevisionApplicabilityId(superseded_identity)
                if superseded_identity
                else None
            ),
            working_context=working_context or self.context,
            revision_id=revision.identity,
            actor=actor or self.actor,
            reason=reason,
            stale_condition_acknowledged=stale_condition_acknowledged,
            evidence=evidence,
        )

    def _stale(
        self,
        revision,
        *,
        identity="stale-first",
        working_context=None,
        actor=None,
        reason=SubtitleConditionReason.MANUAL_STALE,
        reason_note=None,
    ):
        return self.service.mark_revision_stale(
            identity=SubtitleRevisionApplicabilityId(identity),
            working_context=working_context or self.context,
            revision_id=revision.identity,
            actor=actor or self.actor,
            reason=reason,
            reason_note=reason_note,
        )

    def _historical(
        self,
        revision,
        *,
        identity="historical-first",
        working_context=None,
        actor=None,
        evidence=SubtitleApplicabilityEvidence(),
    ):
        return self.service.mark_revision_historical(
            identity=SubtitleRevisionApplicabilityId(identity),
            working_context=working_context or self.context,
            revision_id=revision.identity,
            actor=actor or self.actor,
            reason=SubtitleSelectionReason.MANUAL_HISTORICAL,
            evidence=evidence,
        )

    def _superseded(
        self,
        revision,
        *,
        identity="superseded-first",
        working_context=None,
        actor=None,
    ):
        return self.service.mark_revision_superseded(
            identity=SubtitleRevisionApplicabilityId(identity),
            working_context=working_context or self.context,
            revision_id=revision.identity,
            actor=actor or self.actor,
            reason=SubtitleSelectionReason.REPLACEMENT_SELECTION,
        )

    def _assert_no_records(self):
        self.assertEqual((), self.service.selection_records.all())
        self.assertEqual((), self.service.condition_records.all())

    def _start_execution(self, suffix, context):
        run_id = ProcessingRunId(f"subtitle-applicability-run-{suffix}")
        execution_id = UnitExecutionId(f"subtitle-applicability-execution-{suffix}")
        self.execution.start_run(
            run_id=run_id,
            intent=ExecutionIntent("Subtitle applicability test"),
            working_context=context,
            unit_ids=(self.unit.identity,),
        )
        self.execution.start_unit_execution(
            execution_id=execution_id,
            run_id=run_id,
            unit_id=self.unit.identity,
        )
        return run_id, execution_id

    def _create_raw(self):
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("subtitle-applicability-provider"),
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="provider",
            original_content="자막 원문",
        )
        self.transcript.register_provider_result(provider)
        transcript_id = TranscriptId("subtitle-applicability-transcript")
        segment = TranscriptSegment(
            identity=TranscriptSegmentId("subtitle-applicability-segment"),
            transcript_id=transcript_id,
            source_timeline_id=self.timeline,
            text="자막 원문",
            source_order=0,
            start=0.0,
            end=1.0,
        )
        raw = RawTranscript(
            identity=transcript_id,
            domain_result_id=DomainResultId("subtitle-applicability-transcript-result"),
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(segment.identity,),
        )
        self.transcript.create_raw_transcript(raw, (segment,))
        return raw, segment

    def _create_candidate(self):
        subtitle_id = SubtitleId("subtitle-applicability-lineage")
        cue = SubtitleCue(
            identity=SubtitleCueId("subtitle-applicability-cue"),
            subtitle_id=subtitle_id,
            source_timeline_id=self.timeline,
            start=0.0,
            end=1.0,
            text="자막 원문",
            display_order=0,
            source_segment_ids=(self.segment.identity,),
            source_transcript_id=self.raw.identity,
        )
        candidate = SubtitleCandidate(
            identity=SubtitleCandidateId("subtitle-applicability-candidate"),
            subtitle_id=subtitle_id,
            domain_result_id=DomainResultId("subtitle-applicability-candidate-result"),
            source_transcript_id=self.raw.identity,
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            cue_ids=(cue.identity,),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.subtitle.create_candidate(candidate, (cue,))
        return candidate, cue

    def _create_revision(self, suffix, *, run_id=None, execution_id=None):
        revision = SubtitleRevision(
            identity=SubtitleRevisionId(f"subtitle-applicability-{suffix}"),
            subtitle_id=self.candidate.subtitle_id,
            domain_result_id=DomainResultId(
                f"subtitle-applicability-{suffix}-result"
            ),
            cue_ids=(self.cue.identity,),
            run_id=run_id or self.run_id,
            unit_execution_id=execution_id or self.execution_id,
            parent_candidate_id=self.candidate.identity,
            modification_provenance=f"revision {suffix}",
        )
        self.subtitle.create_revision(revision, (self.cue,))
        return revision


if __name__ == "__main__":
    unittest.main()
