import unittest
from dataclasses import replace

from lectureos.application.identities import (
    SubtitleDecisionApplicationResultId,
    SubtitleTextReplacementId,
)
from lectureos.application.models import SubtitleTextReplacement
from lectureos.application.subtitle_decision import (
    SubtitleDecisionApplicationError,
    SubtitleDecisionApplicationService,
)
from lectureos.application.subtitle_review import SubtitleReviewIntegrationService
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
from lectureos.review.identities import (
    ApprovedDecisionId,
    CandidateReconciliationId,
    CandidateReferenceId,
    DecisionModificationId,
    HumanActorReference,
    ReviewConflictId,
    ReviewContextId,
    ReviewDecisionId,
    ReviewHistoryEntryId,
    ReviewItemId,
    StaleCandidateRecordId,
)
from lectureos.review.models import (
    ApprovedDecision,
    CandidateReconciliation,
    DecisionKind,
    ReviewConflict,
    ReviewDecision,
    StaleCandidateRecord,
)
from lectureos.review.service import ReviewService
from lectureos.subtitle.identities import (
    SubtitleCandidateId,
    SubtitleCueId,
    SubtitleId,
    SubtitleRevisionId,
)
from lectureos.subtitle.models import SubtitleApplicability, SubtitleCandidate, SubtitleCue
from lectureos.subtitle.service import SubtitleService
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import ProviderTranscriptResult, RawTranscript, TranscriptSegment
from lectureos.transcript.service import TranscriptService


class ApprovedSubtitleDecisionApplicationTest(unittest.TestCase):
    def setUp(self):
        self.execution = ExecutionService()
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("subtitle.application"),
            purpose="apply approved Subtitle decisions",
            capabilities=(CapabilityReference("subtitle.application"),),
            result_kinds=("subtitle_revision",),
        )
        self.execution.register_unit(self.unit)
        self.run_id = ProcessingRunId("subtitle-application-run")
        self.execution_id = UnitExecutionId("subtitle-application-execution")
        self.working_context = WorkingContextReference("subtitle-application-context")
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("subtitle decision application tests"),
            working_context=self.working_context,
            unit_ids=(self.unit.identity,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit.identity,
        )
        self.media = SourceMediaId("subtitle-application-media")
        self.timeline = SourceTimelineId("subtitle-application-timeline")
        self.transcript = TranscriptService(self.execution)
        self.raw, self.segments = self._create_raw()
        self.subtitle = SubtitleService(self.transcript, self.execution)
        self.review = ReviewService()
        self.integration = SubtitleReviewIntegrationService(
            self.subtitle, self.review, self.review, self.execution
        )
        self.application = SubtitleDecisionApplicationService(
            self.review, self.subtitle, self.subtitle, self.execution
        )
        self.candidate, self.cues = self._create_candidate()
        self.item = self.integration.create_subtitle_review_item(
            candidate_id=self.candidate.identity,
            review_item_id=ReviewItemId("subtitle-application-item"),
            review_context_id=ReviewContextId("subtitle-application-review-context"),
        )
        self.actor = HumanActorReference("subtitle-application-reviewer")

    def test_accept_creates_new_subtitle_revision(self):
        _, approved = self._accept()
        result = self._apply(approved.identity)
        revision = self.subtitle.get_revision(result.created_revision_id)
        self.assertIsNotNone(revision)
        self.assertEqual(self.candidate.identity, revision.parent_candidate_id)
        self.assertEqual(self.candidate.cue_ids, revision.cue_ids)

    def test_accept_preserves_candidate_cues_decision_and_approval(self):
        decision, approved = self._accept()
        before = (
            self.subtitle.get_candidate(self.candidate.identity),
            tuple(self.subtitle.get_cue(cue.identity) for cue in self.cues),
            self.review.get_decision(decision.identity),
            self.review.get_approved_decision(approved.identity),
        )
        self._apply(approved.identity)
        after = (
            self.subtitle.get_candidate(self.candidate.identity),
            tuple(self.subtitle.get_cue(cue.identity) for cue in self.cues),
            self.review.get_decision(decision.identity),
            self.review.get_approved_decision(approved.identity),
        )
        self.assertEqual(before, after)

    def test_accept_does_not_create_final_applicability_or_current(self):
        _, approved = self._accept()
        result = self._apply(approved.identity)
        revision = self.subtitle.get_revision(result.created_revision_id)
        self.assertEqual(SubtitleApplicability.UNDETERMINED, revision.applicability)
        self.assertFalse(hasattr(revision, "final"))
        self.assertFalse(hasattr(self.application, "select_current"))

    def test_modify_creates_replacement_cue_and_revision(self):
        decision, modification, approved = self._modify()
        specification = SubtitleTextReplacement(
            identity=SubtitleTextReplacementId("subtitle-text-replacement"),
            modification_id=modification.identity,
            target_cue_id=self.cues[0].identity,
            replacement_text="수정된 첫 자막",
        )
        result = self._apply(
            approved.identity,
            text_replacement=specification,
            replacement_cue_id=SubtitleCueId("replacement-cue"),
        )
        replacement = self.subtitle.get_cue(result.replacement_cue_id)
        revision = self.subtitle.get_revision(result.created_revision_id)
        self.assertEqual("수정된 첫 자막", replacement.text)
        self.assertEqual(self.cues[0].identity, replacement.replaces_cue_id)
        self.assertEqual(
            (replacement.identity, self.cues[1].identity), revision.cue_ids
        )
        self.assertEqual(decision.identity, revision.decision_reference)

    def test_modify_preserves_timeline_order_sources_and_original_cue(self):
        _, modification, approved = self._modify()
        original = self.subtitle.get_cue(self.cues[0].identity)
        result = self._apply(
            approved.identity,
            text_replacement=SubtitleTextReplacement(
                identity=SubtitleTextReplacementId("replacement-spec"),
                modification_id=modification.identity,
                target_cue_id=original.identity,
                replacement_text="새 표시 문장",
            ),
            replacement_cue_id=SubtitleCueId("replacement-cue"),
        )
        replacement = self.subtitle.get_cue(result.replacement_cue_id)
        self.assertEqual(original, self.subtitle.get_cue(original.identity))
        for field in (
            "source_timeline_id",
            "start",
            "end",
            "display_order",
            "source_segment_ids",
            "source_transcript_id",
            "source_revision_id",
        ):
            self.assertEqual(getattr(original, field), getattr(replacement, field))
        self.assertNotEqual(original.identity, replacement.identity)

    def test_application_result_preserves_review_execution_and_working_context(self):
        decision, modification, approved = self._modify()
        result = self._apply(
            approved.identity,
            text_replacement=SubtitleTextReplacement(
                identity=SubtitleTextReplacementId("result-provenance-spec"),
                modification_id=modification.identity,
                target_cue_id=self.cues[0].identity,
                replacement_text="변경",
            ),
            replacement_cue_id=SubtitleCueId("result-provenance-cue"),
        )
        self.assertEqual(decision.identity, result.source_decision_id)
        self.assertEqual(self.item.identity, result.review_item_id)
        self.assertEqual(
            CandidateReferenceId(self.candidate.identity.value),
            result.candidate_reference_id,
        )
        self.assertEqual(approved.identity, result.approved_decision_id)
        self.assertEqual(self.working_context, result.working_context)
        self.assertEqual(self.run_id, result.run_id)
        self.assertEqual(self.execution_id, result.unit_execution_id)

    def test_reject_is_explicitly_not_applicable(self):
        decision = self.review.record_reject(
            decision_id=ReviewDecisionId("subtitle-reject"),
            history_id=ReviewHistoryEntryId("subtitle-reject-history"),
            review_item_id=self.item.identity,
            actor=self.actor,
        )
        approved = ApprovedDecision(
            identity=ApprovedDecisionId("malformed-reject-approval"),
            source_decision_id=decision.identity,
            source_candidate_id=decision.candidate_id,
            actor=decision.actor,
            approved_intent="reject",
        )
        self.review.approved_decisions.save(approved)
        before_history = self.review.get_review_history(self.item.identity)
        with self.assertRaisesRegex(
            SubtitleDecisionApplicationError, "Rejected Decision Not Applicable"
        ):
            self._apply(approved.identity)
        self.assertEqual(before_history, self.review.get_review_history(self.item.identity))
        self._assert_no_application_writes()

    def test_unknown_or_unapproved_decision_is_rejected_without_write(self):
        with self.assertRaisesRegex(KeyError, "unknown approved"):
            self._apply(ApprovedDecisionId("missing"))
        self._assert_no_application_writes()
        decision = ReviewDecision(
            identity=ReviewDecisionId("unapproved"),
            review_item_id=self.item.identity,
            candidate_id=CandidateReferenceId(self.candidate.identity.value),
            actor=self.actor,
            kind=DecisionKind.ACCEPT,
            sequence=0,
        )
        self.review.decisions.save(decision)
        with self.assertRaisesRegex(KeyError, "unknown approved"):
            self._apply(ApprovedDecisionId("still-missing"))
        self._assert_no_application_writes()

    def test_approval_decision_candidate_and_item_mismatch_are_rejected(self):
        decision, approved = self._accept()
        self.review.approved_decisions.save(
            replace(
                approved,
                source_candidate_id=CandidateReferenceId("other-candidate"),
            )
        )
        with self.assertRaisesRegex(KeyError, "Candidate Reference"):
            self._apply(approved.identity)
        self._assert_no_application_writes()
        self.review.approved_decisions.save(approved)
        self.review.items.save(
            replace(
                self.review.get_review_item(self.item.identity),
                candidate_id=CandidateReferenceId("other-candidate"),
            )
        )
        with self.assertRaisesRegex(
            SubtitleDecisionApplicationError, "Review Item"
        ):
            self._apply(approved.identity)
        self._assert_no_application_writes()

    def test_non_subtitle_candidate_reference_is_rejected(self):
        _, approved = self._accept()
        reference_id = CandidateReferenceId(self.candidate.identity.value)
        self.review.candidates.save(
            replace(
                self.review.get_candidate_reference(reference_id),
                kind="transcript_correction_candidate",
                source_domain="transcript",
            )
        )
        with self.assertRaisesRegex(
            SubtitleDecisionApplicationError, "only Subtitle Candidates"
        ):
            self._apply(approved.identity)
        self._assert_no_application_writes()

    def test_context_candidate_and_cue_mismatch_are_rejected(self):
        _, approved = self._accept()
        context = self.review.get_review_context(self.item.context_id)
        self.review.contexts.save(
            replace(context, domain_result_references=(DomainResultId("other"),))
        )
        with self.assertRaisesRegex(
            SubtitleDecisionApplicationError, "Candidate Domain Result"
        ):
            self._apply(approved.identity)
        self._assert_no_application_writes()
        self.review.contexts.save(
            replace(
                context,
                evidence_references=tuple(
                    value
                    for value in context.evidence_references
                    if value != f"subtitle_cue:{self.cues[0].identity.value}"
                ),
            )
        )
        with self.assertRaisesRegex(
            SubtitleDecisionApplicationError, "Cue evidence"
        ):
            self._apply(approved.identity)
        self._assert_no_application_writes()

    def test_source_timeline_and_candidate_execution_mismatch_are_rejected(self):
        _, approved = self._accept()
        reference_id = CandidateReferenceId(self.candidate.identity.value)
        reference = self.review.get_candidate_reference(reference_id)
        self.review.candidates.save(
            replace(reference, source_timeline_id=SourceTimelineId("wrong"))
        )
        with self.assertRaisesRegex(
            SubtitleDecisionApplicationError, "Source Timeline"
        ):
            self._apply(approved.identity)
        self._assert_no_application_writes()
        self.review.candidates.save(
            replace(
                reference,
                run_id=ProcessingRunId("wrong"),
                unit_execution_id=UnitExecutionId("wrong"),
            )
        )
        with self.assertRaisesRegex(
            SubtitleDecisionApplicationError, "execution provenance"
        ):
            self._apply(approved.identity)
        self._assert_no_application_writes()

    def test_candidate_cue_and_domain_result_provenance_mismatch_leave_no_write(self):
        _, approved = self._accept()
        original_cue = self.subtitle.get_cue(self.cues[0].identity)
        self.subtitle.cues.save(
            replace(
                original_cue,
                source_timeline_id=SourceTimelineId("wrong-cue-timeline"),
            )
        )
        with self.assertRaisesRegex(
            SubtitleDecisionApplicationError, "Cue Source Timeline"
        ):
            self._apply(approved.identity)
        self._assert_no_application_writes()

        self.subtitle.cues.save(original_cue)
        domain_result = self.subtitle.get_domain_result_reference(
            self.candidate.domain_result_id
        )
        self.subtitle.domain_results.save(
            replace(domain_result, source_timeline=SourceTimelineId("wrong-result"))
        )
        with self.assertRaisesRegex(
            SubtitleDecisionApplicationError, "Domain Result provenance"
        ):
            self._apply(approved.identity)
        self._assert_no_application_writes()

    def test_invalid_modification_link_target_and_text_leave_no_write(self):
        _, modification, approved = self._modify()
        cases = (
            SubtitleTextReplacement(
                identity=SubtitleTextReplacementId("wrong-link"),
                modification_id=DecisionModificationId("wrong"),
                target_cue_id=self.cues[0].identity,
                replacement_text="변경",
            ),
            SubtitleTextReplacement(
                identity=SubtitleTextReplacementId("wrong-target"),
                modification_id=modification.identity,
                target_cue_id=SubtitleCueId("outside"),
                replacement_text="변경",
            ),
        )
        for index, specification in enumerate(cases):
            with self.subTest(index=index):
                with self.assertRaises(SubtitleDecisionApplicationError):
                    self._apply(
                        approved.identity,
                        text_replacement=specification,
                        replacement_cue_id=SubtitleCueId(f"unused-{index}"),
                    )
                self._assert_no_application_writes()
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            SubtitleTextReplacement(
                identity=SubtitleTextReplacementId("empty"),
                modification_id=modification.identity,
                target_cue_id=self.cues[0].identity,
                replacement_text=" ",
            )

    def test_stale_conflict_and_confirmation_reconciliation_block_application(self):
        for condition in ("stale", "conflict", "reconciliation"):
            with self.subTest(condition=condition):
                self.setUp()
                _, approved = self._accept()
                candidate_reference_id = CandidateReferenceId(
                    self.candidate.identity.value
                )
                if condition == "stale":
                    self.review.mark_candidate_stale(
                        StaleCandidateRecord(
                            identity=StaleCandidateRecordId("application-stale"),
                            candidate_id=candidate_reference_id,
                            reason="upstream changed",
                        )
                    )
                elif condition == "conflict":
                    self.review.record_conflict(
                        ReviewConflict(
                            identity=ReviewConflictId("application-conflict"),
                            description="unresolved",
                            review_item_id=self.item.identity,
                        )
                    )
                else:
                    other, _ = self._create_candidate("other")
                    self.integration.create_subtitle_review_item(
                        candidate_id=other.identity,
                        review_item_id=ReviewItemId("other-item"),
                        review_context_id=ReviewContextId("other-context"),
                    )
                    self.review.record_reconciliation(
                        CandidateReconciliation(
                            identity=CandidateReconciliationId(
                                "application-reconciliation"
                            ),
                            previous_candidate_id=candidate_reference_id,
                            new_candidate_id=CandidateReferenceId(
                                other.identity.value
                            ),
                            relationship="replacement",
                        )
                    )
                with self.assertRaises(SubtitleDecisionApplicationError):
                    self._apply(approved.identity)
                self._assert_no_application_writes()

    def test_duplicate_success_returns_existing_result_without_new_revision(self):
        _, approved = self._accept()
        first = self._apply(approved.identity)
        revisions_before = self.subtitle.get_lineage(self.candidate.subtitle_id)[1]
        second = self.application.apply_approved_subtitle_decision(
            approved_decision_id=approved.identity,
            application_result_id=SubtitleDecisionApplicationResultId("second-result"),
            revision_id=SubtitleRevisionId("second-revision"),
            revision_domain_result_id=DomainResultId("second-revision-result"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.assertEqual(first, second)
        self.assertEqual(
            revisions_before,
            self.subtitle.get_lineage(self.candidate.subtitle_id)[1],
        )

    def test_identity_collision_is_rejected_before_persistence(self):
        _, modification, approved = self._modify()
        with self.assertRaisesRegex(ValueError, "Cue identity"):
            self._apply(
                approved.identity,
                text_replacement=SubtitleTextReplacement(
                    identity=SubtitleTextReplacementId("collision"),
                    modification_id=modification.identity,
                    target_cue_id=self.cues[0].identity,
                    replacement_text="변경",
                ),
                replacement_cue_id=self.cues[1].identity,
            )
        self._assert_no_application_writes()

    def test_application_layer_only_coordinates_domains(self):
        for command in ("accept", "reject", "modify", "select_current", "finalize", "export"):
            self.assertFalse(hasattr(self.application, command))
            self.assertFalse(hasattr(self.subtitle, command))
        self.assertFalse(hasattr(self.review, "create_subtitle_revision"))

    def _accept(self):
        return self.review.record_accept(
            decision_id=ReviewDecisionId("subtitle-accept-decision"),
            history_id=ReviewHistoryEntryId("subtitle-accept-history"),
            approved_id=ApprovedDecisionId("subtitle-accept-approved"),
            review_item_id=self.item.identity,
            actor=self.actor,
        )

    def _modify(self):
        return self.review.record_modify(
            decision_id=ReviewDecisionId("subtitle-modify-decision"),
            modification_id=DecisionModificationId("subtitle-modification"),
            history_id=ReviewHistoryEntryId("subtitle-modify-history"),
            approved_id=ApprovedDecisionId("subtitle-modify-approved"),
            review_item_id=self.item.identity,
            actor=self.actor,
            modified_intent="replace one Subtitle Cue text",
        )

    def _apply(
        self,
        approved_id,
        *,
        text_replacement=None,
        replacement_cue_id=None,
    ):
        return self.application.apply_approved_subtitle_decision(
            approved_decision_id=approved_id,
            application_result_id=SubtitleDecisionApplicationResultId(
                "subtitle-application-result"
            ),
            revision_id=SubtitleRevisionId("subtitle-applied-revision"),
            revision_domain_result_id=DomainResultId(
                "subtitle-applied-revision-result"
            ),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            text_replacement=text_replacement,
            replacement_cue_id=replacement_cue_id,
        )

    def _assert_no_application_writes(self):
        self.assertIsNone(
            self.subtitle.get_revision(SubtitleRevisionId("subtitle-applied-revision"))
        )
        self.assertIsNone(
            self.application.get_subtitle_application_result(
                SubtitleDecisionApplicationResultId("subtitle-application-result")
            )
        )

    def _create_raw(self):
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("subtitle-application-provider"),
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="provider",
            original_content="첫 자막 둘째 자막",
        )
        self.transcript.register_provider_result(provider)
        transcript_id = TranscriptId("subtitle-application-transcript")
        segments = (
            TranscriptSegment(
                identity=TranscriptSegmentId("subtitle-application-segment-1"),
                transcript_id=transcript_id,
                source_timeline_id=self.timeline,
                text="첫 자막",
                source_order=0,
                start=0.0,
                end=1.0,
            ),
            TranscriptSegment(
                identity=TranscriptSegmentId("subtitle-application-segment-2"),
                transcript_id=transcript_id,
                source_timeline_id=self.timeline,
                text="둘째 자막",
                source_order=1,
                start=1.0,
                end=2.0,
            ),
        )
        raw = RawTranscript(
            identity=transcript_id,
            domain_result_id=DomainResultId("subtitle-application-transcript-result"),
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=tuple(segment.identity for segment in segments),
        )
        self.transcript.create_raw_transcript(raw, segments)
        return raw, segments

    def _create_candidate(self, suffix="base"):
        subtitle_id = SubtitleId(f"subtitle-application-{suffix}")
        cues = tuple(
            SubtitleCue(
                identity=SubtitleCueId(f"subtitle-application-{suffix}-cue-{index}"),
                subtitle_id=subtitle_id,
                source_timeline_id=self.timeline,
                start=float(index),
                end=float(index + 1),
                text=segment.text,
                display_order=index,
                source_segment_ids=(segment.identity,),
                source_transcript_id=self.raw.identity,
            )
            for index, segment in enumerate(self.segments)
        )
        candidate = SubtitleCandidate(
            identity=SubtitleCandidateId(f"subtitle-application-{suffix}-candidate"),
            subtitle_id=subtitle_id,
            domain_result_id=DomainResultId(
                f"subtitle-application-{suffix}-candidate-result"
            ),
            source_transcript_id=self.raw.identity,
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            cue_ids=tuple(cue.identity for cue in cues),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.subtitle.create_candidate(candidate, cues)
        return candidate, cues


if __name__ == "__main__":
    unittest.main()
