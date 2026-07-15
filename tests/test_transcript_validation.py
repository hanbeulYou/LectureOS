import unittest
from dataclasses import fields

from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    ProcessingUnitId,
    ReviewDecisionId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import DomainResultReference, ExecutionIntent, ProcessingUnit
from lectureos.execution.service import ExecutionService
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
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
)
from lectureos.transcript.service import TranscriptService
from lectureos.transcript.validation import TranscriptValidationService


class TranscriptStructuralValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.execution = ExecutionService()
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("transcript.validation"),
            purpose="validate transcript structure",
            capabilities=(CapabilityReference("transcript.validation"),),
        )
        self.execution.register_unit(self.unit)
        self.run_id = ProcessingRunId("run-validation")
        self.execution_id = UnitExecutionId("execution-validation")
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("transcript structural validation"),
            working_context=WorkingContextReference("work-validation"),
            unit_ids=(self.unit.identity,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit.identity,
        )
        self.transcripts = TranscriptService(self.execution)
        self.validation = TranscriptValidationService(
            self.transcripts,
            self.execution,
        )
        self.source_media_id = SourceMediaId("media-validation")
        self.source_timeline_id = SourceTimelineId("timeline-validation")
        self.provider_result = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("provider-validation"),
            source_media_id=self.source_media_id,
            source_timeline_id=self.source_timeline_id,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="validation-provider",
            original_content="검증할 원본",
        )
        self.raw = self._create_raw()

    def test_valid_raw_transcript_passes_structural_validation(self) -> None:
        result = self._validate_raw()
        self.assertTrue(result.structural_valid)
        self.assertTrue(result.timeline_traceable)
        self.assertTrue(result.provenance_complete)
        self.assertEqual((), result.finding_ids)

    def test_validation_identity_is_separate_from_raw_transcript(self) -> None:
        result = self._validate_raw()
        self.assertNotEqual(result.identity, self.raw.identity)

    def test_validation_does_not_change_raw_transcript(self) -> None:
        before = self.transcripts.get_raw_transcript(self.raw.identity)
        self._validate_raw()
        self.assertEqual(before, self.transcripts.get_raw_transcript(self.raw.identity))

    def test_validation_does_not_change_segment(self) -> None:
        segment_id = self.raw.segment_ids[0]
        before = self.transcripts.get_segment(segment_id)
        self._validate_raw()
        self.assertEqual(before, self.transcripts.get_segment(segment_id))

    def test_validation_detects_negative_segment_time(self) -> None:
        self._replace_first_segment(start=-1.0)
        result = self._validate_raw()
        self.assertFalse(result.time_ranges_valid)
        self.assertIn("segment_time_range_invalid", self._rules(result))

    def test_validation_detects_start_after_end(self) -> None:
        self._replace_first_segment(start=2.0, end=1.0)
        result = self._validate_raw()
        self.assertFalse(result.time_ranges_valid)

    def test_validation_detects_non_finite_time_range(self) -> None:
        self._replace_first_segment(end=float("inf"))
        result = self._validate_raw()
        self.assertFalse(result.time_ranges_valid)

    def test_validation_detects_timed_segment_without_timeline(self) -> None:
        self._replace_first_segment(source_timeline_id=None)
        result = self._validate_raw()
        self.assertFalse(result.timeline_traceable)
        self.assertFalse(result.time_ranges_valid)

    def test_validation_allows_untimed_segment_without_timeline(self) -> None:
        self._replace_first_segment(
            source_timeline_id=None,
            start=None,
            end=None,
        )
        result = self._validate_raw()
        self.assertTrue(result.structural_valid)
        self.assertTrue(result.time_ranges_valid)

    def test_validation_detects_duplicate_segment_reference(self) -> None:
        malformed = _unsafe_replace(
            self.raw,
            segment_ids=(self.raw.segment_ids[0], self.raw.segment_ids[0]),
        )
        self.transcripts.raw_transcripts.save(malformed)
        result = self._validate_raw()
        self.assertFalse(result.segment_references_complete)
        self.assertIn("duplicate_segment_reference", self._rules(result))

    def test_validation_detects_missing_segment_reference(self) -> None:
        malformed = _unsafe_replace(
            self.raw,
            segment_ids=(TranscriptSegmentId("missing-segment"),),
        )
        self.transcripts.raw_transcripts.save(malformed)
        result = self._validate_raw()
        self.assertFalse(result.segment_references_complete)
        self.assertIn("missing_segment", self._rules(result))

    def test_validation_detects_segment_from_another_transcript_lineage(self) -> None:
        self._replace_first_segment(transcript_id=TranscriptId("other-transcript"))
        result = self._validate_raw()
        self.assertFalse(result.segment_references_complete)
        self.assertIn("segment_lineage_mismatch", self._rules(result))

    def test_validation_detects_segment_timeline_mismatch(self) -> None:
        self._replace_first_segment(
            source_timeline_id=SourceTimelineId("other-timeline")
        )
        result = self._validate_raw()
        self.assertFalse(result.source_consistent)
        self.assertIn("timeline_mismatch", self._rules(result))

    def test_validation_detects_raw_source_media_mismatch(self) -> None:
        malformed = _unsafe_replace(
            self.raw,
            source_media_id=SourceMediaId("other-media"),
        )
        self.transcripts.raw_transcripts.save(malformed)
        result = self._validate_raw()
        self.assertFalse(result.source_consistent)
        self.assertIn("source_media_mismatch", self._rules(result))

    def test_validation_detects_duplicate_source_order(self) -> None:
        self._add_second_segment(source_order=0)
        result = self._validate_raw()
        self.assertFalse(result.source_order_valid)
        self.assertIn("duplicate_segment_source_order", self._rules(result))

    def test_validation_detects_reference_and_source_order_mismatch(self) -> None:
        self._add_second_segment(source_order=1)
        malformed = _unsafe_replace(
            self.raw,
            segment_ids=(self.raw.segment_ids[1], self.raw.segment_ids[0]),
        )
        self.transcripts.raw_transcripts.save(malformed)
        result = self._validate_raw()
        self.assertFalse(result.source_order_valid)
        self.assertIn("segment_reference_order_mismatch", self._rules(result))

    def test_validation_detects_timeline_order_independently(self) -> None:
        self._add_second_segment(source_order=1)
        first = self.transcripts.get_segment(self.raw.segment_ids[0])
        second = self.transcripts.get_segment(self.raw.segment_ids[1])
        self.transcripts.segments.save(_unsafe_replace(first, start=2.0, end=3.0))
        self.transcripts.segments.save(
            _unsafe_replace(second, start=1.0, end=1.5)
        )
        result = self._validate_raw()
        self.assertTrue(result.source_order_valid)
        self.assertFalse(result.timeline_order_valid)
        self.assertIn("segment_timeline_order_invalid", self._rules(result))

    def test_validation_reports_overlap_as_non_blocking_warning(self) -> None:
        self._add_second_segment(source_order=1)
        second = self.transcripts.get_segment(self.raw.segment_ids[1])
        self.transcripts.segments.save(
            _unsafe_replace(second, start=0.5, end=1.5)
        )
        result = self._validate_raw()
        findings = self.validation.get_validation_findings(result.identity)
        overlap = next(
            finding for finding in findings if finding.rule == "segment_time_overlap"
        )
        self.assertTrue(result.structural_valid)
        self.assertTrue(result.overlap_detected)
        self.assertTrue(result.has_warnings)
        self.assertFalse(overlap.blocking)

    def test_validation_detects_missing_provider_result(self) -> None:
        malformed = _unsafe_replace(
            self.raw,
            provider_result_id=ProviderTranscriptResultId("missing-provider"),
        )
        self.transcripts.raw_transcripts.save(malformed)
        result = self._validate_raw()
        self.assertFalse(result.provenance_complete)
        self.assertIn("provider_result_missing", self._rules(result))

    def test_validation_detects_missing_domain_result_reference(self) -> None:
        malformed = _unsafe_replace(
            self.raw,
            domain_result_id=DomainResultId("missing-domain-result"),
        )
        self.transcripts.raw_transcripts.save(malformed)
        result = self._validate_raw()
        self.assertFalse(result.provenance_complete)
        self.assertIn("domain_result_reference_missing", self._rules(result))

    def test_validation_detects_missing_execution_provenance(self) -> None:
        malformed = _unsafe_replace(
            self.raw,
            run_id=ProcessingRunId("missing-run"),
            unit_execution_id=UnitExecutionId("missing-execution"),
        )
        self.transcripts.raw_transcripts.save(malformed)
        result = self._validate_raw()
        self.assertFalse(result.provenance_complete)
        self.assertIn("execution_provenance_incomplete", self._rules(result))

    def test_validation_detects_missing_revision_parent(self) -> None:
        revision = self._seed_revision(
            parent_raw_transcript_id=None,
            parent_revision_id=TranscriptRevisionId("missing-parent"),
        )
        result = self._validate_revision(revision)
        self.assertFalse(result.parent_consistent)
        self.assertIn("parent_revision_inconsistent", self._rules(result))

    def test_validation_detects_both_raw_and_revision_parents(self) -> None:
        revision = self._seed_revision()
        malformed = _unsafe_replace(
            revision,
            parent_revision_id=TranscriptRevisionId("another-parent"),
        )
        self.transcripts.revisions.save(malformed)
        result = self._validate_revision(malformed)
        self.assertFalse(result.parent_consistent)

    def test_validation_detects_self_parent_revision(self) -> None:
        revision = self._seed_revision()
        malformed = _unsafe_replace(
            revision,
            parent_raw_transcript_id=None,
            parent_revision_id=revision.identity,
        )
        self.transcripts.revisions.save(malformed)
        result = self._validate_revision(malformed)
        self.assertIn("revision_cycle", self._rules(result))

    def test_validation_detects_revision_cycle(self) -> None:
        first = self._seed_revision(identity="revision-cycle-a")
        second = self._seed_revision(identity="revision-cycle-b")
        first = _unsafe_replace(
            first,
            parent_raw_transcript_id=None,
            parent_revision_id=second.identity,
        )
        second = _unsafe_replace(
            second,
            parent_raw_transcript_id=None,
            parent_revision_id=first.identity,
        )
        self.transcripts.revisions.save(first)
        self.transcripts.revisions.save(second)
        result = self._validate_revision(first)
        self.assertIn("revision_cycle", self._rules(result))

    def test_validation_detects_revision_source_lineage_change(self) -> None:
        revision = self._seed_revision()
        result_reference = self.transcripts.get_domain_result_reference(
            revision.domain_result_id
        )
        self.transcripts.domain_results.save(
            _unsafe_replace(
                result_reference,
                source_timeline=SourceTimelineId("other-timeline"),
            )
        )
        result = self._validate_revision(revision)
        self.assertFalse(result.source_consistent)
        self.assertIn("source_media_mismatch", self._rules(result))

    def test_valid_corrected_revision_passes_structural_validation(self) -> None:
        revision = self._seed_revision()
        result = self._validate_revision(revision)
        self.assertTrue(result.structural_valid)
        self.assertTrue(result.parent_consistent)
        self.assertTrue(result.provenance_complete)

    def test_validation_detects_missing_correction_provenance(self) -> None:
        revision = self._seed_revision()
        malformed = _unsafe_replace(revision, decision_reference=None)
        self.transcripts.revisions.save(malformed)
        result = self._validate_revision(malformed)
        self.assertFalse(result.provenance_complete)
        self.assertIn("correction_provenance_incomplete", self._rules(result))

    def test_validation_failure_does_not_create_human_approval(self) -> None:
        self._replace_first_segment(start=-1.0)
        result = self._validate_raw()
        self.assertFalse(result.structural_valid)
        self.assertFalse(hasattr(result, "approved"))

    def test_validation_service_has_no_human_decision_operations(self) -> None:
        self.assertFalse(hasattr(self.validation, "accept"))
        self.assertFalse(hasattr(self.validation, "reject"))
        self.assertFalse(hasattr(self.validation, "modify"))

    def test_validation_is_not_stored_as_domain_result(self) -> None:
        result = self._validate_raw()
        self.assertIsNone(
            self.transcripts.get_domain_result_reference(
                DomainResultId(result.identity.value)
            )
        )

    def test_duplicate_validation_identity_is_rejected(self) -> None:
        validation_id = TranscriptValidationId("validation-duplicate")
        self._validate_raw(validation_id)
        with self.assertRaisesRegex(ValueError, "validation identity already exists"):
            self._validate_raw(validation_id)

    def test_validation_error_leaves_no_partial_validation_records(self) -> None:
        validation_id = TranscriptValidationId("validation-interrupted")
        original = self.transcripts.get_segment

        def fail_to_read_segment(_identity):
            raise RuntimeError("repository read failed")

        self.transcripts.get_segment = fail_to_read_segment
        try:
            with self.assertRaisesRegex(RuntimeError, "repository read failed"):
                self._validate_raw(validation_id)
        finally:
            self.transcripts.get_segment = original

        self.assertIsNone(self.validation.get_validation(validation_id))
        self.assertEqual((), self.validation.get_validation_findings(validation_id))

    def test_invalid_validation_execution_leaves_no_orphan_findings(self) -> None:
        validation_id = TranscriptValidationId("validation-invalid-execution")
        self.execution.record_results(
            self.execution_id,
            (
                DomainResultReference(
                    DomainResultId("validation-execution-result"),
                    "validation_execution_marker",
                ),
            ),
        )

        with self.assertRaisesRegex(
            ValueError, "validation requires a running unit execution"
        ):
            self._validate_raw(validation_id)

        self.assertIsNone(self.validation.get_validation(validation_id))
        self.assertEqual((), self.validation.get_validation_findings(validation_id))

        retry_execution_id = UnitExecutionId("execution-validation-retry")
        self.execution.start_unit_execution(
            execution_id=retry_execution_id,
            run_id=self.run_id,
            unit_id=self.unit.identity,
        )
        result = self.validation.validate_raw_transcript(
            validation_id=validation_id,
            transcript_id=self.raw.identity,
            run_id=self.run_id,
            unit_execution_id=retry_execution_id,
        )
        self.assertEqual(validation_id, result.identity)

    def test_revalidation_preserves_previous_validation(self) -> None:
        first = self._validate_raw(TranscriptValidationId("validation-first"))
        second = self._validate_raw(TranscriptValidationId("validation-second"))
        self.assertNotEqual(first.identity, second.identity)
        self.assertEqual(first, self.validation.get_validation(first.identity))
        self.assertEqual(second, self.validation.get_validation(second.identity))

    def _create_raw(self) -> RawTranscript:
        self.transcripts.register_provider_result(self.provider_result)
        transcript_id = TranscriptId("raw-validation")
        segment = TranscriptSegment(
            identity=TranscriptSegmentId("segment-validation-0"),
            transcript_id=transcript_id,
            source_timeline_id=self.source_timeline_id,
            text="검증할 발화",
            source_order=0,
            start=0.0,
            end=1.0,
        )
        raw = RawTranscript(
            identity=transcript_id,
            domain_result_id=DomainResultId("raw-domain-validation"),
            source_media_id=self.source_media_id,
            source_timeline_id=self.source_timeline_id,
            provider_result_id=self.provider_result.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(segment.identity,),
        )
        self.transcripts.create_raw_transcript(raw, (segment,))
        return raw

    def _validate_raw(
        self, validation_id: TranscriptValidationId | None = None
    ):
        return self.validation.validate_raw_transcript(
            validation_id=validation_id or TranscriptValidationId("validation-raw"),
            transcript_id=self.raw.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )

    def _validate_revision(self, revision: CorrectedTranscriptRevision):
        return self.validation.validate_corrected_revision(
            validation_id=TranscriptValidationId(
                f"validation-{revision.identity.value}"
            ),
            revision_id=revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )

    def _rules(self, validation) -> set[str]:
        return {
            finding.rule
            for finding in self.validation.get_validation_findings(validation.identity)
        }

    def _replace_first_segment(self, **changes) -> None:
        segment = self.transcripts.get_segment(self.raw.segment_ids[0])
        self.transcripts.segments.save(_unsafe_replace(segment, **changes))

    def _add_second_segment(self, *, source_order: int) -> None:
        second = TranscriptSegment(
            identity=TranscriptSegmentId("segment-validation-1"),
            transcript_id=self.raw.identity,
            source_timeline_id=self.source_timeline_id,
            text="두 번째 발화",
            source_order=source_order,
            start=2.0,
            end=3.0,
        )
        self.transcripts.segments.save(second)
        self.raw = _unsafe_replace(
            self.raw,
            segment_ids=self.raw.segment_ids + (second.identity,),
        )
        self.transcripts.raw_transcripts.save(self.raw)

    def _seed_revision(
        self,
        *,
        identity: str = "revision-validation",
        parent_raw_transcript_id: TranscriptId | None = None,
        parent_revision_id: TranscriptRevisionId | None = None,
    ) -> CorrectedTranscriptRevision:
        revision_id = TranscriptRevisionId(identity)
        revision = CorrectedTranscriptRevision(
            identity=revision_id,
            transcript_id=self.raw.identity,
            domain_result_id=DomainResultId(f"domain-{identity}"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=self.raw.segment_ids,
            parent_raw_transcript_id=(
                self.raw.identity
                if parent_raw_transcript_id is None and parent_revision_id is None
                else parent_raw_transcript_id
            ),
            parent_revision_id=parent_revision_id,
            decision_reference=ReviewDecisionId(f"decision-{identity}"),
        )
        self.transcripts.revisions.save(revision)
        self.transcripts.domain_results.save(
            DomainResultReference(
                identity=revision.domain_result_id,
                kind="corrected_transcript_revision",
                source_media=self.source_media_id,
                source_timeline=self.source_timeline_id,
                upstream_results=(self.raw.domain_result_id,),
            )
        )
        return revision


def _unsafe_replace(record, **changes):
    """Build malformed persisted fixtures without weakening production constructors."""

    replacement = object.__new__(type(record))
    for field in fields(record):
        object.__setattr__(
            replacement,
            field.name,
            changes.get(field.name, getattr(record, field.name)),
        )
    return replacement


if __name__ == "__main__":
    unittest.main()
