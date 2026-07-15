"""Structural Transcript validation without semantic or approval decisions."""

from math import isfinite

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import ProcessingRunId, UnitExecutionId
from lectureos.execution.models import ProcessingState
from lectureos.execution.repositories import InMemoryRepository

from .boundaries import TranscriptValidationStoreBoundary
from .identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationFindingId,
    TranscriptValidationId,
)
from .models import (
    CorrectedTranscriptRevision,
    RawTranscript,
    TranscriptSegment,
    TranscriptValidation,
    TranscriptValidationFinding,
)


class TranscriptValidationService:
    """Calculates and persists structural findings as separate execution records."""

    def __init__(
        self,
        transcript_store: TranscriptValidationStoreBoundary,
        execution_query: ExecutionQueryBoundary,
        *,
        findings: InMemoryRepository | None = None,
    ) -> None:
        self._transcript_query = transcript_store
        self._validation_store = transcript_store
        self._execution_query = execution_query
        self.findings = findings or InMemoryRepository()

    def validate_raw_transcript(
        self,
        *,
        validation_id: TranscriptValidationId,
        transcript_id: TranscriptId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
    ) -> TranscriptValidation:
        self._require_new_validation(validation_id)
        self._require_validation_execution(run_id, unit_execution_id)
        transcript = self._transcript_query.get_raw_transcript(transcript_id)
        if transcript is None:
            raise KeyError("unknown raw transcript")

        builder = _ValidationBuilder(validation_id, transcript.identity)
        self._validate_segment_references(
            builder,
            transcript.identity,
            transcript.source_timeline_id,
            transcript.segment_ids,
        )
        self._validate_raw_provenance(builder, transcript)
        self._validate_execution_provenance(
            builder,
            transcript.run_id,
            transcript.unit_execution_id,
            "raw transcript",
        )
        validation = builder.build(
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            target_transcript_id=transcript.identity,
        )
        self._persist(validation, builder.findings)
        return validation

    def validate_corrected_revision(
        self,
        *,
        validation_id: TranscriptValidationId,
        revision_id: TranscriptRevisionId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
    ) -> TranscriptValidation:
        self._require_new_validation(validation_id)
        self._require_validation_execution(run_id, unit_execution_id)
        revision = self._transcript_query.get_corrected_revision(revision_id)
        if revision is None:
            raise KeyError("unknown corrected transcript revision")

        builder = _ValidationBuilder(
            validation_id,
            revision.transcript_id,
            revision_id=revision.identity,
        )
        raw = self._transcript_query.get_raw_transcript(revision.transcript_id)
        if raw is None:
            builder.add(
                "parent_revision_inconsistent",
                "corrected revision lineage has no raw transcript",
            )
            expected_timeline = None
        else:
            expected_timeline = raw.source_timeline_id

        self._validate_segment_references(
            builder,
            revision.transcript_id,
            expected_timeline,
            revision.segment_ids,
        )
        self._validate_revision_parent(builder, revision, raw)
        self._validate_revision_provenance(builder, revision, raw)
        self._validate_execution_provenance(
            builder,
            revision.run_id,
            revision.unit_execution_id,
            "corrected transcript revision",
        )
        validation = builder.build(
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            target_revision_id=revision.identity,
        )
        self._persist(validation, builder.findings)
        return validation

    def get_validation(
        self, identity: TranscriptValidationId
    ) -> TranscriptValidation | None:
        return self._transcript_query.get_validation(identity)

    def get_validation_finding(
        self, identity: TranscriptValidationFindingId
    ) -> TranscriptValidationFinding | None:
        return self.findings.get(identity)

    def get_validation_findings(
        self, validation_id: TranscriptValidationId
    ) -> tuple[TranscriptValidationFinding, ...]:
        return tuple(
            finding
            for finding in self.findings.all()
            if finding.validation_id == validation_id
        )

    def _validate_segment_references(
        self,
        builder: "_ValidationBuilder",
        transcript_id: TranscriptId,
        expected_timeline,
        segment_ids,
    ) -> tuple[TranscriptSegment, ...]:
        seen = set()
        segments: list[TranscriptSegment] = []
        for segment_id in segment_ids:
            if segment_id in seen:
                builder.segment_references_complete = False
                builder.add(
                    "duplicate_segment_reference",
                    "transcript references the same segment more than once",
                    segment_id=segment_id,
                )
                continue
            seen.add(segment_id)
            segment = self._transcript_query.get_segment(segment_id)
            if segment is None:
                builder.segment_references_complete = False
                builder.add(
                    "missing_segment",
                    "transcript references a segment that does not exist",
                    segment_id=segment_id,
                )
                continue
            segments.append(segment)
            if segment.transcript_id != transcript_id:
                builder.segment_references_complete = False
                builder.add(
                    "segment_lineage_mismatch",
                    "segment belongs to a different transcript lineage",
                    segment=segment,
                )
            if (
                expected_timeline is not None
                and segment.source_timeline_id is not None
                and segment.source_timeline_id != expected_timeline
            ):
                builder.timeline_traceable = False
                builder.source_consistent = False
                builder.add(
                    "timeline_mismatch",
                    "segment source timeline does not match transcript lineage",
                    segment=segment,
                )
            self._validate_time_range(builder, segment)

        self._validate_source_order(builder, segments)
        self._validate_timeline_order(builder, segments)
        return tuple(segments)

    @staticmethod
    def _validate_time_range(
        builder: "_ValidationBuilder", segment: TranscriptSegment
    ) -> None:
        start = segment.start
        end = segment.end
        has_any_time = start is not None or end is not None
        invalid = False
        if has_any_time and segment.source_timeline_id is None:
            invalid = True
        if (start is None) != (end is None):
            invalid = True
        if start is not None and end is not None:
            if not isfinite(start) or not isfinite(end):
                invalid = True
            elif start < 0 or end < 0 or start > end:
                invalid = True
        if invalid:
            builder.time_ranges_valid = False
            builder.timeline_traceable = False
            builder.add(
                "segment_time_range_invalid",
                "segment has an invalid source time range",
                segment=segment,
            )

    @staticmethod
    def _validate_source_order(
        builder: "_ValidationBuilder", segments: list[TranscriptSegment]
    ) -> None:
        orders = [segment.source_order for segment in segments]
        invalid_segments = [segment for segment in segments if segment.source_order < 0]
        if invalid_segments:
            builder.source_order_valid = False
            for segment in invalid_segments:
                builder.add(
                    "segment_source_order_invalid",
                    "segment source order must not be negative",
                    segment=segment,
                )
        if len(set(orders)) != len(orders):
            builder.source_order_valid = False
            builder.add(
                "duplicate_segment_source_order",
                "transcript segments contain duplicate source order values",
            )
        if orders != sorted(orders):
            builder.source_order_valid = False
            builder.add(
                "segment_reference_order_mismatch",
                "segment reference order conflicts with source order",
            )

    @staticmethod
    def _validate_timeline_order(
        builder: "_ValidationBuilder", segments: list[TranscriptSegment]
    ) -> None:
        timed = [
            segment
            for segment in segments
            if segment.start is not None
            and segment.end is not None
            and isfinite(segment.start)
            and isfinite(segment.end)
        ]
        for previous, current in zip(timed, timed[1:]):
            if current.start < previous.start:
                builder.timeline_order_valid = False
                builder.add(
                    "segment_timeline_order_invalid",
                    "segment start times move backward in reference order",
                    segment=current,
                )
            if current.start < previous.end:
                builder.overlap_detected = True
                builder.add(
                    "segment_time_overlap",
                    "segment time ranges overlap; policy requires later validation",
                    blocking=False,
                    segment=current,
                )

    def _validate_raw_provenance(
        self, builder: "_ValidationBuilder", transcript: RawTranscript
    ) -> None:
        provider = self._transcript_query.get_provider_result(transcript.provider_result_id)
        if provider is None:
            builder.provenance_complete = False
            builder.add(
                "provider_result_missing",
                "raw transcript provider result does not exist",
            )
        elif (
            provider.source_media_id != transcript.source_media_id
            or provider.source_timeline_id != transcript.source_timeline_id
        ):
            builder.source_consistent = False
            builder.add(
                "source_media_mismatch",
                "raw transcript source context differs from provider result",
            )

        result = self._transcript_query.get_domain_result_reference(
            transcript.domain_result_id
        )
        if result is None:
            builder.provenance_complete = False
            builder.add(
                "domain_result_reference_missing",
                "raw transcript has no Domain Result reference",
            )
        elif (
            result.source_media != transcript.source_media_id
            or result.source_timeline != transcript.source_timeline_id
        ):
            builder.source_consistent = False
            builder.add(
                "source_media_mismatch",
                "Domain Result source context differs from raw transcript",
            )

    def _validate_revision_provenance(
        self,
        builder: "_ValidationBuilder",
        revision: CorrectedTranscriptRevision,
        raw: RawTranscript | None,
    ) -> None:
        if not revision.correction_candidate_ids and revision.decision_reference is None:
            builder.provenance_complete = False
            builder.add(
                "correction_provenance_incomplete",
                "corrected revision has no candidate or Human Decision provenance",
            )
        for candidate_id in revision.correction_candidate_ids:
            candidate = self._transcript_query.get_candidate(candidate_id)
            if candidate is None or candidate.transcript_id != revision.transcript_id:
                builder.provenance_complete = False
                builder.add(
                    "correction_provenance_incomplete",
                    "corrected revision references an unavailable correction candidate",
                )

        result = self._transcript_query.get_domain_result_reference(
            revision.domain_result_id
        )
        if result is None:
            builder.provenance_complete = False
            builder.add(
                "domain_result_reference_missing",
                "corrected revision has no Domain Result reference",
            )
        elif raw is not None:
            if (
                result.source_media != raw.source_media_id
                or result.source_timeline != raw.source_timeline_id
            ):
                builder.source_consistent = False
                builder.add(
                    "source_media_mismatch",
                    "corrected revision moves to a different source lineage",
                )

    def _validate_revision_parent(
        self,
        builder: "_ValidationBuilder",
        revision: CorrectedTranscriptRevision,
        raw: RawTranscript | None,
    ) -> None:
        parent_count = sum(
            parent is not None
            for parent in (
                revision.parent_raw_transcript_id,
                revision.parent_revision_id,
            )
        )
        if parent_count != 1:
            builder.parent_consistent = False
            builder.add(
                "parent_revision_inconsistent",
                "corrected revision must reference exactly one parent",
            )
            return

        if revision.parent_raw_transcript_id is not None:
            parent_raw = self._transcript_query.get_raw_transcript(
                revision.parent_raw_transcript_id
            )
            if parent_raw is None or parent_raw.identity != revision.transcript_id:
                builder.parent_consistent = False
                builder.add(
                    "parent_revision_inconsistent",
                    "corrected revision raw parent is unavailable or outside its lineage",
                )
            return

        if revision.parent_revision_id == revision.identity:
            builder.parent_consistent = False
            builder.add(
                "revision_cycle",
                "corrected revision cannot be its own parent",
            )
            return

        seen = {revision.identity}
        parent_id = revision.parent_revision_id
        reached_raw = False
        while parent_id is not None:
            if parent_id in seen:
                builder.parent_consistent = False
                builder.add(
                    "revision_cycle",
                    "corrected revision parent chain contains a cycle",
                )
                return
            seen.add(parent_id)
            parent = self._transcript_query.get_corrected_revision(parent_id)
            if parent is None:
                builder.parent_consistent = False
                builder.add(
                    "parent_revision_inconsistent",
                    "corrected revision parent does not exist",
                )
                return
            if sum(
                candidate is not None
                for candidate in (
                    parent.parent_raw_transcript_id,
                    parent.parent_revision_id,
                )
            ) != 1:
                builder.parent_consistent = False
                builder.add(
                    "parent_revision_inconsistent",
                    "corrected revision parent chain contains an invalid parent relation",
                )
                return
            if parent.transcript_id != revision.transcript_id:
                builder.parent_consistent = False
                builder.add(
                    "parent_revision_inconsistent",
                    "corrected revision parent belongs to a different lineage",
                )
                return
            if parent.parent_raw_transcript_id is not None:
                reached_raw = (
                    raw is not None
                    and parent.parent_raw_transcript_id == raw.identity
                )
                break
            parent_id = parent.parent_revision_id

        if not reached_raw:
            builder.parent_consistent = False
            builder.add(
                "parent_revision_inconsistent",
                "corrected revision parent chain does not reach its raw transcript",
            )

    def _validate_execution_provenance(
        self,
        builder: "_ValidationBuilder",
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        label: str,
    ) -> None:
        run = self._execution_query.get_run(run_id)
        execution = self._execution_query.get_unit_execution(unit_execution_id)
        if run is None or execution is None or execution.run_id != run_id:
            builder.provenance_complete = False
            builder.add(
                "execution_provenance_incomplete",
                f"{label} has incomplete Processing Run or Unit Execution provenance",
            )

    def _require_validation_execution(
        self, run_id: ProcessingRunId, unit_execution_id: UnitExecutionId
    ) -> None:
        run = self._execution_query.get_run(run_id)
        execution = self._execution_query.get_unit_execution(unit_execution_id)
        if (
            run is None
            or execution is None
            or execution.run_id != run_id
            or execution.state is not ProcessingState.RUNNING
        ):
            raise ValueError("validation requires a running unit execution")

    def _persist(
        self,
        validation: TranscriptValidation,
        findings: tuple[TranscriptValidationFinding, ...],
    ) -> None:
        self._require_new_validation(validation.identity)
        for finding in findings:
            if self.findings.get(finding.identity) is not None:
                raise ValueError("transcript validation finding identity already exists")
        for finding in findings:
            self.findings.save(finding)
        self._validation_store.record_validation(validation)

    def _require_new_validation(self, validation_id: TranscriptValidationId) -> None:
        if self._transcript_query.get_validation(validation_id) is not None:
            raise ValueError("transcript validation identity already exists")


class _ValidationBuilder:
    def __init__(
        self,
        validation_id: TranscriptValidationId,
        transcript_id: TranscriptId,
        *,
        revision_id: TranscriptRevisionId | None = None,
    ) -> None:
        self.validation_id = validation_id
        self.transcript_id = transcript_id
        self.revision_id = revision_id
        self.findings: tuple[TranscriptValidationFinding, ...] = ()
        self.timeline_traceable = True
        self.provenance_complete = True
        self.source_order_valid = True
        self.timeline_order_valid = True
        self.time_ranges_valid = True
        self.overlap_detected = False
        self.segment_references_complete = True
        self.source_consistent = True
        self.parent_consistent = True if revision_id is not None else None

    def add(
        self,
        rule: str,
        description: str,
        *,
        blocking: bool = True,
        segment: TranscriptSegment | None = None,
        segment_id=None,
    ) -> None:
        identity = TranscriptValidationFindingId(
            f"{self.validation_id.value}:finding:{len(self.findings)}"
        )
        self.findings += (
            TranscriptValidationFinding(
                identity=identity,
                validation_id=self.validation_id,
                rule=rule,
                description=description,
                blocking=blocking,
                transcript_id=self.transcript_id,
                revision_id=self.revision_id,
                segment_id=segment.identity if segment is not None else segment_id,
                start=segment.start if segment is not None else None,
                end=segment.end if segment is not None else None,
                source_order=segment.source_order if segment is not None else None,
            ),
        )

    def build(
        self,
        *,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        target_transcript_id: TranscriptId | None = None,
        target_revision_id: TranscriptRevisionId | None = None,
    ) -> TranscriptValidation:
        source_order_valid = self.source_order_valid
        timeline_order_valid = self.timeline_order_valid
        ordering_valid = source_order_valid and timeline_order_valid
        structural_valid = not any(finding.blocking for finding in self.findings)
        return TranscriptValidation(
            identity=self.validation_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            target_transcript_id=target_transcript_id,
            target_revision_id=target_revision_id,
            structural_valid=structural_valid,
            timeline_traceable=self.timeline_traceable,
            provenance_complete=self.provenance_complete,
            ordering_valid=ordering_valid,
            source_order_valid=source_order_valid,
            timeline_order_valid=timeline_order_valid,
            time_ranges_valid=self.time_ranges_valid,
            overlap_detected=self.overlap_detected,
            segment_references_complete=self.segment_references_complete,
            source_consistent=self.source_consistent,
            parent_consistent=self.parent_consistent,
            finding_ids=tuple(finding.identity for finding in self.findings),
            has_warnings=any(not finding.blocking for finding in self.findings),
        )
