import unittest

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
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import (
    CorrectionCandidate,
    CorrectedTranscriptRevision,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptApplicability,
    TranscriptSegment,
    TranscriptValidation,
)
from lectureos.transcript.service import TranscriptService


class TranscriptFoundationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.execution = ExecutionService()
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("transcript.normalize"),
            purpose="normalize a provider transcript result",
            capabilities=(CapabilityReference("speech.transcription"),),
            result_kinds=("raw_transcript",),
        )
        self.execution.register_unit(self.unit)
        self.run_id = ProcessingRunId("run-transcript")
        self.execution_id = UnitExecutionId("execution-transcript")
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("transcript foundation test"),
            working_context=WorkingContextReference("work-transcript"),
            unit_ids=(self.unit.identity,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit.identity,
        )
        self.service = TranscriptService(self.execution)
        self.source_media_id = SourceMediaId("media-1")
        self.source_timeline_id = SourceTimelineId("timeline-1")
        self.provider_result = self._provider_result()

    def test_provider_transcript_result_can_be_stored(self) -> None:
        self.service.register_provider_result(self.provider_result)
        self.assertEqual(
            self.provider_result,
            self.service.get_provider_result(self.provider_result.identity),
        )

    def test_provider_result_and_raw_transcript_identities_are_distinct(self) -> None:
        raw, segments = self._register_and_build_raw()
        self.assertNotEqual(self.provider_result.identity, raw.identity)
        self.assertNotEqual(self.provider_result.identity.value, raw.identity.value)
        self.service.create_raw_transcript(raw, segments)

    def test_raw_transcript_references_source_media_and_timeline(self) -> None:
        raw = self._create_raw()
        self.assertEqual(self.source_media_id, raw.source_media_id)
        self.assertEqual(self.source_timeline_id, raw.source_timeline_id)

    def test_raw_creation_does_not_change_provider_result(self) -> None:
        self.service.register_provider_result(self.provider_result)
        before = self.service.get_provider_result(self.provider_result.identity)
        raw, segments = self._build_raw()
        self.service.create_raw_transcript(raw, segments)
        self.assertEqual(before, self.service.get_provider_result(self.provider_result.identity))
        self.assertFalse(before.normalized)

    def test_segment_rejects_start_after_end(self) -> None:
        with self.assertRaisesRegex(ValueError, "start must not be after end"):
            self._segment(start=2.0, end=1.0)

    def test_timed_segment_requires_source_timeline(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires a source timeline"):
            TranscriptSegment(
                identity=TranscriptSegmentId("segment-without-timeline"),
                transcript_id=TranscriptId("raw-transcript-1"),
                source_timeline_id=None,
                text="시간 정보가 있는 발화",
                source_order=0,
                start=0.0,
                end=1.0,
            )

    def test_raw_and_corrected_revision_identities_are_distinct(self) -> None:
        raw = self._create_raw()
        revision, segments = self._build_revision(raw)
        self.service.create_corrected_revision(revision, segments)
        self.assertNotEqual(raw.identity, revision.identity)
        self.assertNotEqual(raw.domain_result_id, revision.domain_result_id)

    def test_revision_creation_does_not_change_parent(self) -> None:
        raw = self._create_raw()
        before = self.service.get_raw_transcript(raw.identity)
        revision, segments = self._build_revision(raw)
        self.service.create_corrected_revision(revision, segments)
        self.assertEqual(before, self.service.get_raw_transcript(raw.identity))

    def test_new_revision_is_not_automatically_current_or_approved(self) -> None:
        raw = self._create_raw()
        revision, segments = self._build_revision(raw)
        self.service.create_corrected_revision(revision, segments)
        stored = self.service.get_corrected_revision(revision.identity)
        self.assertEqual(TranscriptApplicability.UNDETERMINED, stored.applicability)
        self.assertIsNone(stored.decision_reference)

    def test_candidate_creation_does_not_change_transcript_text(self) -> None:
        raw = self._create_raw()
        segment_id = raw.segment_ids[0]
        before = self.service.get_segment(segment_id)
        candidate = self._candidate(raw, segment_id)
        self.service.create_correction_candidate(candidate)
        self.assertEqual(before, self.service.get_segment(segment_id))

    def test_candidate_is_not_revision_or_review_decision(self) -> None:
        raw = self._create_raw()
        candidate = self._candidate(raw, raw.segment_ids[0])
        self.service.create_correction_candidate(candidate)
        self.assertIsInstance(candidate, CorrectionCandidate)
        self.assertNotIsInstance(candidate, CorrectedTranscriptRevision)
        self.assertFalse(hasattr(candidate, "decision"))

    def test_validation_has_identity_separate_from_transcript(self) -> None:
        raw = self._create_raw()
        validation = self._validation(raw)
        self.service.record_validation(validation)
        self.assertNotEqual(validation.identity, raw.identity)
        self.assertIsNone(
            self.service.get_domain_result_reference(DomainResultId(validation.identity.value))
        )

    def test_validation_success_does_not_create_human_approval(self) -> None:
        raw = self._create_raw()
        validation = self._validation(raw)
        self.service.record_validation(validation)
        stored = self.service.get_validation(validation.identity)
        self.assertTrue(stored.structural_valid)
        self.assertFalse(hasattr(stored, "approved"))
        self.assertFalse(hasattr(self.service, "accept"))

    def test_duplicate_raw_transcript_identity_is_rejected(self) -> None:
        raw = self._create_raw()
        duplicate_segments = (
            self._segment(
                identity="segment-duplicate",
                transcript_id=raw.identity,
                text="duplicate",
            ),
        )
        duplicate = RawTranscript(
            identity=raw.identity,
            domain_result_id=DomainResultId("raw-result-duplicate"),
            source_media_id=raw.source_media_id,
            source_timeline_id=raw.source_timeline_id,
            provider_result_id=raw.provider_result_id,
            run_id=raw.run_id,
            unit_execution_id=raw.unit_execution_id,
            segment_ids=(duplicate_segments[0].identity,),
        )
        with self.assertRaisesRegex(ValueError, "raw transcript identity already exists"):
            self.service.create_raw_transcript(duplicate, duplicate_segments)

    def test_revision_requires_existing_parent(self) -> None:
        raw = self._create_raw()
        revision, segments = self._build_revision(raw)
        missing_parent = CorrectedTranscriptRevision(
            identity=revision.identity,
            transcript_id=revision.transcript_id,
            domain_result_id=revision.domain_result_id,
            run_id=revision.run_id,
            unit_execution_id=revision.unit_execution_id,
            segment_ids=revision.segment_ids,
            parent_revision_id=TranscriptRevisionId("missing-revision"),
        )
        with self.assertRaisesRegex(KeyError, "unknown corrected transcript revision"):
            self.service.create_corrected_revision(missing_parent, segments)

    def test_candidate_requires_existing_segment(self) -> None:
        raw = self._create_raw()
        candidate = self._candidate(raw, TranscriptSegmentId("missing-segment"))
        with self.assertRaisesRegex(KeyError, "unknown transcript segment"):
            self.service.create_correction_candidate(candidate)

    def test_transcript_result_references_run_and_unit_execution(self) -> None:
        raw = self._create_raw()
        self.assertEqual(self.run_id, raw.run_id)
        self.assertEqual(self.execution_id, raw.unit_execution_id)
        reference = self.service.get_domain_result_reference(raw.domain_result_id)
        self.assertEqual(self.source_media_id, reference.source_media)
        self.assertEqual(self.source_timeline_id, reference.source_timeline)

    def test_transcript_service_has_no_human_decision_operations(self) -> None:
        self.assertFalse(hasattr(self.service, "accept"))
        self.assertFalse(hasattr(self.service, "reject"))
        self.assertFalse(hasattr(self.service, "modify"))

    def _provider_result(self) -> ProviderTranscriptResult:
        return ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("provider-result-1"),
            source_media_id=self.source_media_id,
            source_timeline_id=self.source_timeline_id,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="test-provider",
            original_content="original provider content",
        )

    def _register_and_build_raw(
        self,
    ) -> tuple[RawTranscript, tuple[TranscriptSegment, ...]]:
        self.service.register_provider_result(self.provider_result)
        return self._build_raw()

    def _build_raw(self) -> tuple[RawTranscript, tuple[TranscriptSegment, ...]]:
        transcript_id = TranscriptId("raw-transcript-1")
        segments = (self._segment(transcript_id=transcript_id),)
        raw = RawTranscript(
            identity=transcript_id,
            domain_result_id=DomainResultId("raw-result-1"),
            source_media_id=self.source_media_id,
            source_timeline_id=self.source_timeline_id,
            provider_result_id=self.provider_result.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=tuple(segment.identity for segment in segments),
        )
        return raw, segments

    def _create_raw(self) -> RawTranscript:
        raw, segments = self._register_and_build_raw()
        self.service.create_raw_transcript(raw, segments)
        return raw

    def _segment(
        self,
        *,
        identity: str = "segment-1",
        transcript_id: TranscriptId | None = None,
        text: str = "안녕하세요",
        start: float | None = 0.0,
        end: float | None = 1.0,
    ) -> TranscriptSegment:
        return TranscriptSegment(
            identity=TranscriptSegmentId(identity),
            transcript_id=transcript_id or TranscriptId("raw-transcript-1"),
            source_timeline_id=self.source_timeline_id,
            text=text,
            source_order=0,
            start=start,
            end=end,
        )

    def _build_revision(
        self, raw: RawTranscript
    ) -> tuple[CorrectedTranscriptRevision, tuple[TranscriptSegment, ...]]:
        segments = (
            self._segment(
                identity="segment-corrected",
                transcript_id=raw.identity,
                text="안녕하세요.",
            ),
        )
        revision = CorrectedTranscriptRevision(
            identity=TranscriptRevisionId("revision-1"),
            transcript_id=raw.identity,
            domain_result_id=DomainResultId("corrected-result-1"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=tuple(segment.identity for segment in segments),
            parent_raw_transcript_id=raw.identity,
        )
        return revision, segments

    def _candidate(
        self, raw: RawTranscript, segment_id: TranscriptSegmentId
    ) -> CorrectionCandidate:
        return CorrectionCandidate(
            identity=CorrectionCandidateId("candidate-1"),
            domain_result_id=DomainResultId("candidate-result-1"),
            transcript_id=raw.identity,
            segment_id=segment_id,
            proposed_text="안녕하세요.",
            rationale="문장 부호 후보",
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )

    def _validation(self, raw: RawTranscript) -> TranscriptValidation:
        return TranscriptValidation(
            identity=TranscriptValidationId("validation-1"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            target_transcript_id=raw.identity,
            structural_valid=True,
            timeline_traceable=True,
            provenance_complete=True,
            ordering_valid=True,
        )


if __name__ == "__main__":
    unittest.main()
