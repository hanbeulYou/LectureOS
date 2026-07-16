import unittest
from dataclasses import replace

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
from lectureos.subtitle.identities import (
    SubtitleCandidateId,
    SubtitleCueId,
    SubtitleId,
    SubtitleRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from lectureos.subtitle.models import (
    SubtitleApplicability,
    SubtitleCandidate,
    SubtitleCue,
    SubtitleRevision,
)
from lectureos.subtitle.service import SubtitleService
from lectureos.subtitle.validation import SubtitleValidationService
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import (
    CorrectedTranscriptRevision,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)
from lectureos.transcript.service import TranscriptService


class SubtitleDomainFoundationTest(unittest.TestCase):
    def setUp(self):
        self.execution = ExecutionService()
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("subtitle.foundation"),
            purpose="subtitle foundation",
            capabilities=(CapabilityReference("subtitle.generation"),),
            result_kinds=("subtitle_candidate", "subtitle_revision"),
        )
        self.execution.register_unit(self.unit)
        self.run_id = ProcessingRunId("run-subtitle")
        self.execution_id = UnitExecutionId("execution-subtitle")
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("subtitle tests"),
            working_context=WorkingContextReference("subtitle-context"),
            unit_ids=(self.unit.identity,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit.identity,
        )
        self.transcript = TranscriptService(self.execution)
        self.media = SourceMediaId("media-subtitle")
        self.timeline = SourceTimelineId("timeline-subtitle")
        self.raw = self._create_raw()
        self.subtitle = SubtitleService(self.transcript, self.execution)
        self.validation = SubtitleValidationService(
            self.subtitle, self.transcript, self.execution
        )

    def test_candidate_can_be_created_from_transcript(self):
        candidate = self._create_candidate()
        self.assertEqual(candidate, self.subtitle.get_candidate(candidate.identity))

    def test_transcript_and_candidate_identities_differ(self):
        candidate = self._create_candidate()
        self.assertNotEqual(candidate.identity.value, self.raw.identity.value)

    def test_transcript_segment_and_cue_identities_differ(self):
        candidate = self._create_candidate()
        cue = self.subtitle.get_cue(candidate.cue_ids[0])
        self.assertNotEqual(cue.identity.value, self.raw.segment_ids[0].value)

    def test_candidate_references_transcript_and_source(self):
        candidate = self._create_candidate()
        self.assertEqual(self.raw.identity, candidate.source_transcript_id)
        self.assertEqual(self.media, candidate.source_media_id)
        self.assertEqual(self.timeline, candidate.source_timeline_id)

    def test_candidate_can_reference_corrected_transcript_revision(self):
        transcript_revision = self._create_transcript_revision()
        candidate, cues = self._build_candidate("corrected")
        candidate = replace(candidate, source_revision_id=transcript_revision.identity)
        cues = tuple(
            replace(cue, source_revision_id=transcript_revision.identity)
            for cue in cues
        )
        self.subtitle.create_candidate(candidate, cues)
        self.assertEqual(
            transcript_revision.identity,
            self.subtitle.get_candidate(candidate.identity).source_revision_id,
        )
        reference = self.subtitle.get_domain_result_reference(candidate.domain_result_id)
        self.assertEqual(
            (transcript_revision.domain_result_id,),
            reference.upstream_results,
        )

    def test_candidate_rejects_source_media_mismatch(self):
        candidate, cues = self._build_candidate("media-mismatch")
        candidate = replace(candidate, source_media_id=SourceMediaId("wrong"))
        with self.assertRaisesRegex(ValueError, "source media"):
            self.subtitle.create_candidate(candidate, cues)

    def test_candidate_preserves_transcript_and_segment(self):
        raw_before = self.transcript.get_raw_transcript(self.raw.identity)
        segment_before = self.transcript.get_segment(self.raw.segment_ids[0])
        self._create_candidate()
        self.assertEqual(raw_before, self.transcript.get_raw_transcript(self.raw.identity))
        self.assertEqual(segment_before, self.transcript.get_segment(self.raw.segment_ids[0]))

    def test_invalid_cue_ranges_are_rejected(self):
        for start, end, message in (
            (2.0, 1.0, "start must not be after"),
            (-1.0, 1.0, "must not be negative"),
            (float("inf"), 1.0, "must be finite"),
        ):
            with self.subTest(start=start):
                with self.assertRaisesRegex(ValueError, message):
                    self._cue(start=start, end=end)

    def test_cue_requires_source_timeline_and_segment(self):
        with self.assertRaisesRegex(ValueError, "Source Timeline"):
            self._cue(source_timeline_id=None)
        with self.assertRaisesRegex(ValueError, "requires a source"):
            self._cue(source_segment_ids=())

    def test_cue_rejects_negative_display_order(self):
        with self.assertRaisesRegex(ValueError, "display order"):
            self._cue(display_order=-1)

    def test_cue_rejects_empty_display_text(self):
        with self.assertRaisesRegex(ValueError, "text must not be empty"):
            self._cue(text=" ")

    def test_missing_or_other_lineage_segment_is_rejected(self):
        candidate, cues = self._build_candidate()
        with self.assertRaisesRegex(KeyError, "unknown source"):
            self.subtitle.create_candidate(
                candidate,
                (replace(cues[0], source_segment_ids=(TranscriptSegmentId("missing"),)),),
            )
        foreign = self._create_foreign_raw()
        candidate, cues = self._build_candidate("other")
        with self.assertRaisesRegex(ValueError, "another Transcript lineage"):
            self.subtitle.create_candidate(
                candidate,
                (replace(cues[0], source_segment_ids=(foreign.segment_ids[0],)),),
            )

    def test_timeline_mismatch_is_rejected(self):
        candidate, cues = self._build_candidate()
        with self.assertRaisesRegex(ValueError, "Source Timeline"):
            self.subtitle.create_candidate(
                candidate,
                (replace(cues[0], source_timeline_id=SourceTimelineId("wrong")),),
            )

    def test_duplicate_cue_and_candidate_identity_are_rejected(self):
        candidate = self._create_candidate()
        with self.assertRaisesRegex(ValueError, "candidate identity"):
            self.subtitle.create_candidate(candidate, tuple(
                self.subtitle.get_cue(x) for x in candidate.cue_ids
            ))

    def test_candidate_is_not_final_or_human_decision(self):
        candidate = self._create_candidate()
        self.assertFalse(hasattr(candidate, "final"))
        self.assertFalse(hasattr(candidate, "decision"))
        self.assertEqual(SubtitleApplicability.UNDETERMINED, candidate.applicability)

    def test_revision_can_be_created_without_changing_parent(self):
        candidate = self._create_candidate()
        before = self.subtitle.get_candidate(candidate.identity)
        revision = self._create_revision(candidate)
        self.assertEqual(before, self.subtitle.get_candidate(candidate.identity))
        self.assertNotEqual(revision.identity.value, candidate.identity.value)

    def test_later_revision_does_not_change_previous(self):
        candidate = self._create_candidate()
        first = self._create_revision(candidate)
        before = self.subtitle.get_revision(first.identity)
        self._create_revision(first, suffix="second")
        self.assertEqual(before, self.subtitle.get_revision(first.identity))

    def test_revision_requires_exactly_one_existing_parent(self):
        with self.assertRaisesRegex(ValueError, "exactly one parent"):
            SubtitleRevision(
                identity=SubtitleRevisionId("invalid-both"),
                subtitle_id=SubtitleId("subtitle-1"),
                domain_result_id=DomainResultId("invalid-both-result"),
                cue_ids=(),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                parent_candidate_id=SubtitleCandidateId("candidate"),
                parent_revision_id=SubtitleRevisionId("revision"),
            )
        revision = SubtitleRevision(
            identity=SubtitleRevisionId("missing-parent"),
            subtitle_id=SubtitleId("subtitle-1"),
            domain_result_id=DomainResultId("missing-parent-result"),
            cue_ids=(),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            parent_candidate_id=SubtitleCandidateId("missing"),
        )
        with self.assertRaisesRegex(KeyError, "unknown parent"):
            self.subtitle.create_revision(revision, ())

    def test_self_parent_and_duplicate_revision_are_rejected(self):
        candidate = self._create_candidate()
        first = self._create_revision(candidate)
        with self.assertRaisesRegex(ValueError, "own parent"):
            self.subtitle.create_revision(
                replace(
                    first,
                    identity=SubtitleRevisionId("self-parent"),
                    domain_result_id=DomainResultId("self-parent-result"),
                    parent_candidate_id=None,
                    parent_revision_id=SubtitleRevisionId("self-parent"),
                ),
                tuple(self.subtitle.get_cue(x) for x in first.cue_ids),
            )
        with self.assertRaisesRegex(ValueError, "revision identity"):
            self.subtitle.create_revision(
                first, tuple(self.subtitle.get_cue(x) for x in first.cue_ids)
            )

    def test_revision_is_not_current_or_final(self):
        revision = self._create_revision(self._create_candidate())
        self.assertEqual(SubtitleApplicability.UNDETERMINED, revision.applicability)
        self.assertFalse(hasattr(revision, "final"))

    def test_revision_references_execution_and_domain_result(self):
        revision = self._create_revision(self._create_candidate())
        reference = self.subtitle.get_domain_result_reference(revision.domain_result_id)
        self.assertEqual(self.run_id, revision.run_id)
        self.assertEqual(self.execution_id, revision.unit_execution_id)
        self.assertEqual("subtitle_revision", reference.kind)

    def test_unknown_parent_revision_is_rejected(self):
        revision = SubtitleRevision(
            identity=SubtitleRevisionId("revision-unknown-parent"),
            subtitle_id=SubtitleId("subtitle-one"),
            domain_result_id=DomainResultId("revision-unknown-parent-result"),
            cue_ids=(),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            parent_revision_id=SubtitleRevisionId("unknown"),
        )
        with self.assertRaisesRegex(KeyError, "unknown parent"):
            self.subtitle.create_revision(revision, ())

    def test_validation_is_separate_and_does_not_approve(self):
        candidate = self._create_candidate()
        validation = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("validation-valid"),
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.assertNotEqual(validation.identity.value, candidate.identity.value)
        self.assertTrue(validation.structural_valid)
        self.assertFalse(hasattr(validation, "approved"))
        self.assertIsNone(
            self.subtitle.get_domain_result_reference(
                DomainResultId(validation.identity.value)
            )
        )

    def test_validation_does_not_mutate_records(self):
        candidate = self._create_candidate()
        cue_before = self.subtitle.get_cue(candidate.cue_ids[0])
        candidate_before = self.subtitle.get_candidate(candidate.identity)
        self.validation.validate_candidate(
            validation_id=SubtitleValidationId("validation-preserve"),
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.assertEqual(cue_before, self.subtitle.get_cue(cue_before.identity))
        self.assertEqual(candidate_before, self.subtitle.get_candidate(candidate.identity))

    def test_revision_validation_is_separate_and_non_mutating(self):
        revision = self._create_revision(self._create_candidate())
        before = self.subtitle.get_revision(revision.identity)
        validation = self.validation.validate_revision(
            validation_id=SubtitleValidationId("validation-revision"),
            revision_id=revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.assertTrue(validation.structural_valid)
        self.assertEqual(before, self.subtitle.get_revision(revision.identity))
        self.assertEqual(revision.identity, validation.target_revision_id)

    def test_validation_detects_duplicate_order_missing_reference_and_duplicate_reference(self):
        candidate = self._create_candidate(two_cues=True)
        second = self.subtitle.get_cue(candidate.cue_ids[1])
        self.subtitle.cues.save(replace(second, display_order=0))
        malformed = replace(
            candidate,
            cue_ids=(candidate.cue_ids[0], candidate.cue_ids[0], SubtitleCueId("missing")),
        )
        self.subtitle.candidates.save(malformed)
        result = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("validation-malformed"),
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        rules = {self.subtitle.get_validation_finding(x).rule for x in result.finding_ids}
        self.assertIn("duplicate_cue_reference", rules)
        self.assertIn("missing_cue", rules)

    def test_validation_detects_duplicate_display_order(self):
        candidate = self._create_candidate(two_cues=True)
        second = self.subtitle.get_cue(candidate.cue_ids[1])
        self.subtitle.cues.save(replace(second, display_order=0))
        result = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("validation-order"),
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        rules = {self.subtitle.get_validation_finding(x).rule for x in result.finding_ids}
        self.assertIn("duplicate_display_order", rules)
        self.assertFalse(result.ordering_consistent)

    def test_validation_detects_cue_source_lineage_mismatch(self):
        candidate = self._create_candidate()
        cue = self.subtitle.get_cue(candidate.cue_ids[0])
        self.subtitle.cues.save(
            replace(cue, source_transcript_id=TranscriptId("wrong-lineage"))
        )
        result = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("validation-lineage"),
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        rules = {self.subtitle.get_validation_finding(x).rule for x in result.finding_ids}
        self.assertIn("lineage_mismatch", rules)
        self.assertFalse(result.provenance_complete)

    def test_validation_detects_non_finite_and_negative_legacy_time(self):
        candidate = self._create_candidate()
        cue = self.subtitle.get_cue(candidate.cue_ids[0])
        object.__setattr__(cue, "start", -1.0)
        object.__setattr__(cue, "end", float("inf"))
        result = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("validation-legacy-time"),
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        rules = {self.subtitle.get_validation_finding(x).rule for x in result.finding_ids}
        self.assertIn("invalid_time_range", rules)
        self.assertFalse(result.structural_valid)

    def test_validation_detects_missing_execution_provenance(self):
        candidate = self._create_candidate()
        malformed = replace(
            candidate,
            run_id=ProcessingRunId("missing-run"),
            unit_execution_id=UnitExecutionId("missing-execution"),
        )
        self.subtitle.candidates.save(malformed)
        result = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("validation-provenance"),
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        rules = {self.subtitle.get_validation_finding(x).rule for x in result.finding_ids}
        self.assertIn("provenance_incomplete", rules)
        self.assertFalse(result.provenance_complete)

    def test_validation_detects_revision_cycle(self):
        candidate = self._create_candidate()
        first = self._create_revision(candidate)
        second = self._create_revision(first, suffix="cycle-second")
        self.subtitle.revisions.save(
            replace(first, parent_candidate_id=None, parent_revision_id=second.identity)
        )
        result = self.validation.validate_revision(
            validation_id=SubtitleValidationId("validation-cycle"),
            revision_id=second.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        rules = {self.subtitle.get_validation_finding(x).rule for x in result.finding_ids}
        self.assertIn("parent_inconsistent", rules)
        self.assertFalse(result.structural_valid)

    def test_validation_failure_does_not_partially_persist_findings(self):
        candidate = self._create_candidate()
        validation_id = SubtitleValidationId("validation-invalid-execution")
        with self.assertRaises(KeyError):
            self.validation.validate_candidate(
                validation_id=validation_id,
                candidate_id=candidate.identity,
                run_id=ProcessingRunId("missing"),
                unit_execution_id=UnitExecutionId("missing"),
            )
        self.assertIsNone(self.subtitle.get_validation(validation_id))
        self.assertIsNone(
            self.subtitle.get_validation_finding(
                self._validation_finding_id(validation_id, 0)
            )
        )

    def test_validation_identity_cannot_overwrite_existing_result(self):
        candidate = self._create_candidate()
        validation_id = SubtitleValidationId("validation-duplicate")
        first = self.validation.validate_candidate(
            validation_id=validation_id,
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        with self.assertRaisesRegex(ValueError, "identity already exists"):
            self.validation.validate_candidate(
                validation_id=validation_id,
                candidate_id=candidate.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
            )
        self.assertEqual(first, self.subtitle.get_validation(validation_id))

    def test_overlap_and_gap_are_non_blocking_warnings(self):
        candidate = self._create_candidate(two_cues=True)
        second = self.subtitle.get_cue(candidate.cue_ids[1])
        self.subtitle.cues.save(replace(second, start=0.5))
        result = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("validation-overlap"),
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.assertTrue(result.has_warnings)
        self.assertTrue(result.structural_valid)

    def test_gap_is_non_blocking_warning(self):
        candidate = self._create_candidate(two_cues=True)
        second = self.subtitle.get_cue(candidate.cue_ids[1])
        self.subtitle.cues.save(replace(second, start=1.5, end=2.5))
        result = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("validation-gap"),
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        rules = {self.subtitle.get_validation_finding(x).rule for x in result.finding_ids}
        self.assertIn("cue_gap", rules)
        self.assertTrue(result.structural_valid)

    def test_validation_detects_cue_reference_order_mismatch(self):
        candidate = self._create_candidate(two_cues=True)
        self.subtitle.candidates.save(
            replace(candidate, cue_ids=tuple(reversed(candidate.cue_ids)))
        )
        result = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("validation-reference-order"),
            candidate_id=candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        rules = {self.subtitle.get_validation_finding(x).rule for x in result.finding_ids}
        self.assertIn("display_order_mismatch", rules)
        self.assertFalse(result.ordering_consistent)

    def test_provenance_and_execution_are_preserved(self):
        candidate = self._create_candidate()
        reference = self.subtitle.get_domain_result_reference(candidate.domain_result_id)
        self.assertEqual(self.run_id, candidate.run_id)
        self.assertEqual(self.execution_id, candidate.unit_execution_id)
        self.assertEqual((self.raw.domain_result_id,), reference.upstream_results)

    def test_services_have_no_review_export_or_final_commands(self):
        for command in ("accept", "reject", "modify", "approve", "finalize", "export"):
            self.assertFalse(hasattr(self.subtitle, command))

    def test_failed_candidate_creation_leaves_no_partial_records(self):
        candidate, cues = self._build_candidate("partial")
        bad = replace(cues[0], source_timeline_id=SourceTimelineId("wrong"))
        with self.assertRaises(ValueError):
            self.subtitle.create_candidate(candidate, (bad,))
        self.assertIsNone(self.subtitle.get_candidate(candidate.identity))
        self.assertIsNone(self.subtitle.get_cue(bad.identity))

    def test_invalid_execution_leaves_no_partial_candidate(self):
        candidate, cues = self._build_candidate("invalid-execution")
        candidate = replace(
            candidate,
            run_id=ProcessingRunId("missing"),
            unit_execution_id=UnitExecutionId("missing"),
        )
        with self.assertRaises(KeyError):
            self.subtitle.create_candidate(candidate, cues)
        self.assertIsNone(self.subtitle.get_candidate(candidate.identity))
        self.assertIsNone(self.subtitle.get_cue(cues[0].identity))

    def test_failed_revision_creation_leaves_no_partial_records(self):
        candidate = self._create_candidate()
        revision = SubtitleRevision(
            identity=SubtitleRevisionId("revision-partial"),
            subtitle_id=candidate.subtitle_id,
            domain_result_id=DomainResultId("revision-partial-result"),
            cue_ids=(SubtitleCueId("revision-partial-cue"),),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            parent_candidate_id=candidate.identity,
        )
        cue = replace(
            self.subtitle.get_cue(candidate.cue_ids[0]),
            identity=SubtitleCueId("revision-partial-cue"),
            source_timeline_id=SourceTimelineId("wrong"),
        )
        with self.assertRaises(ValueError):
            self.subtitle.create_revision(revision, (cue,))
        self.assertIsNone(self.subtitle.get_revision(revision.identity))
        self.assertIsNone(self.subtitle.get_cue(cue.identity))

    def _create_raw(self):
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("provider-subtitle"),
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="provider",
            original_content="첫째 둘째",
        )
        self.transcript.register_provider_result(provider)
        transcript_id = TranscriptId("raw-subtitle")
        segments = (
            TranscriptSegment(
                identity=TranscriptSegmentId("segment-one"),
                transcript_id=transcript_id,
                source_timeline_id=self.timeline,
                text="첫째",
                source_order=0,
                start=0.0,
                end=1.0,
            ),
            TranscriptSegment(
                identity=TranscriptSegmentId("segment-two"),
                transcript_id=transcript_id,
                source_timeline_id=self.timeline,
                text="둘째",
                source_order=1,
                start=1.0,
                end=2.0,
            ),
        )
        raw = RawTranscript(
            identity=transcript_id,
            domain_result_id=DomainResultId("raw-subtitle-result"),
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=tuple(x.identity for x in segments),
        )
        self.transcript.create_raw_transcript(raw, segments)
        return raw

    def _create_foreign_raw(self):
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("provider-subtitle-foreign"),
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="provider",
            original_content="다른 발화",
        )
        self.transcript.register_provider_result(provider)
        transcript_id = TranscriptId("raw-subtitle-foreign")
        segment = TranscriptSegment(
            identity=TranscriptSegmentId("segment-foreign"),
            transcript_id=transcript_id,
            source_timeline_id=self.timeline,
            text="다른 발화",
            source_order=0,
            start=0.0,
            end=1.0,
        )
        raw = RawTranscript(
            identity=transcript_id,
            domain_result_id=DomainResultId("raw-subtitle-foreign-result"),
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(segment.identity,),
        )
        self.transcript.create_raw_transcript(raw, (segment,))
        return raw

    def _create_transcript_revision(self):
        revision = CorrectedTranscriptRevision(
            identity=TranscriptRevisionId("transcript-revision-subtitle"),
            domain_result_id=DomainResultId("transcript-revision-subtitle-result"),
            transcript_id=self.raw.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=self.raw.segment_ids,
            parent_raw_transcript_id=self.raw.identity,
        )
        segments = tuple(
            self.transcript.get_segment(identity) for identity in self.raw.segment_ids
        )
        self.transcript.create_corrected_revision(revision, segments)
        return revision

    def _cue(self, **changes):
        values = dict(
            identity=SubtitleCueId("cue-one"),
            subtitle_id=SubtitleId("subtitle-one"),
            source_timeline_id=self.timeline,
            start=0.0,
            end=1.0,
            text="첫째",
            display_order=0,
            source_segment_ids=(self.raw.segment_ids[0],),
            source_transcript_id=self.raw.identity,
        )
        values.update(changes)
        return SubtitleCue(**values)

    def _build_candidate(self, suffix="one", two_cues=False):
        subtitle_id = SubtitleId(f"subtitle-{suffix}")
        cues = [
            replace(
                self._cue(),
                identity=SubtitleCueId(f"cue-{suffix}-one"),
                subtitle_id=subtitle_id,
            )
        ]
        if two_cues:
            cues.append(
                SubtitleCue(
                    identity=SubtitleCueId(f"cue-{suffix}-two"),
                    subtitle_id=subtitle_id,
                    source_timeline_id=self.timeline,
                    start=1.0,
                    end=2.0,
                    text="둘째",
                    display_order=1,
                    source_segment_ids=(self.raw.segment_ids[1],),
                    source_transcript_id=self.raw.identity,
                )
            )
        candidate = SubtitleCandidate(
            identity=SubtitleCandidateId(f"candidate-{suffix}"),
            subtitle_id=subtitle_id,
            domain_result_id=DomainResultId(f"candidate-{suffix}-result"),
            source_transcript_id=self.raw.identity,
            source_media_id=self.media,
            source_timeline_id=self.timeline,
            cue_ids=tuple(x.identity for x in cues),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        return candidate, tuple(cues)

    def _create_candidate(self, two_cues=False):
        candidate, cues = self._build_candidate(two_cues=two_cues)
        self.subtitle.create_candidate(candidate, cues)
        return candidate

    def _create_revision(self, parent, suffix="first"):
        source_cues = tuple(self.subtitle.get_cue(x) for x in parent.cue_ids)
        cues = tuple(
            replace(
                cue,
                identity=SubtitleCueId(f"revision-{suffix}-{index}"),
                text=f"{cue.text} 수정",
            )
            for index, cue in enumerate(source_cues)
        )
        revision = SubtitleRevision(
            identity=SubtitleRevisionId(f"revision-{suffix}"),
            subtitle_id=parent.subtitle_id,
            domain_result_id=DomainResultId(f"revision-{suffix}-result"),
            cue_ids=tuple(x.identity for x in cues),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            parent_candidate_id=parent.identity
            if isinstance(parent, SubtitleCandidate)
            else None,
            parent_revision_id=parent.identity
            if isinstance(parent, SubtitleRevision)
            else None,
            modification_provenance="test revision",
        )
        self.subtitle.create_revision(revision, cues)
        return revision

    @staticmethod
    def _validation_finding_id(validation_id, index):
        return SubtitleValidationFindingId(f"{validation_id.value}:{index}")


if __name__ == "__main__":
    unittest.main()
