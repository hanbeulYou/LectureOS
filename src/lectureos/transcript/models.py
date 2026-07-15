"""Immutable Transcript records and their provenance relationships."""

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from lectureos.execution.identities import (
    CapabilityReference,
    DiagnosticId,
    DomainResultId,
    PluginReference,
    ProcessingRunId,
    ReviewDecisionId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)

from .identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)


class TranscriptApplicability(str, Enum):
    UNDETERMINED = "undetermined"
    STALE = "stale"
    SUPERSEDED = "superseded"
    HISTORICAL = "historical"


@dataclass(frozen=True, slots=True)
class ProviderTranscriptResult:
    identity: ProviderTranscriptResultId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    capability: CapabilityReference
    provider_reference: str
    original_content: str
    plugin_reference: PluginReference | None = None
    diagnostic_references: tuple[DiagnosticId, ...] = ()
    uncertainty: float | None = None
    normalized: bool = False

    def __post_init__(self) -> None:
        if not self.provider_reference.strip():
            raise ValueError("provider reference must not be empty")
        if self.normalized:
            raise ValueError("provider transcript result must preserve pre-normalization state")


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """Implementation record for a source-timeline-aligned Transcript unit."""

    identity: TranscriptSegmentId
    transcript_id: TranscriptId
    source_timeline_id: SourceTimelineId | None
    text: str
    source_order: int
    start: float | None = None
    end: float | None = None
    speaker_label: str | None = None
    confidence: float | None = None
    uncertainty: float | None = None

    def __post_init__(self) -> None:
        if self.source_order < 0:
            raise ValueError("segment source order must not be negative")
        has_time = self.start is not None or self.end is not None
        if has_time and self.source_timeline_id is None:
            raise ValueError("timed segment requires a source timeline reference")
        if (self.start is None) != (self.end is None):
            raise ValueError("segment time range requires both start and end")
        if self.start is not None and self.end is not None:
            if not isfinite(self.start) or not isfinite(self.end):
                raise ValueError("segment time range must be finite")
            if self.start < 0 or self.end < 0:
                raise ValueError("segment time range must not be negative")
            if self.start > self.end:
                raise ValueError("segment start must not be after end")


@dataclass(frozen=True, slots=True)
class RawTranscript:
    identity: TranscriptId
    domain_result_id: DomainResultId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    provider_result_id: ProviderTranscriptResultId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    segment_ids: tuple[TranscriptSegmentId, ...]
    validation_id: TranscriptValidationId | None = None


@dataclass(frozen=True, slots=True)
class CorrectedTranscriptRevision:
    identity: TranscriptRevisionId
    transcript_id: TranscriptId
    domain_result_id: DomainResultId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    segment_ids: tuple[TranscriptSegmentId, ...]
    parent_raw_transcript_id: TranscriptId | None = None
    parent_revision_id: TranscriptRevisionId | None = None
    correction_candidate_ids: tuple[CorrectionCandidateId, ...] = ()
    decision_reference: ReviewDecisionId | None = None
    validation_id: TranscriptValidationId | None = None
    applicability: TranscriptApplicability = TranscriptApplicability.UNDETERMINED

    def __post_init__(self) -> None:
        parents = (self.parent_raw_transcript_id, self.parent_revision_id)
        if sum(parent is not None for parent in parents) != 1:
            raise ValueError("corrected revision requires exactly one parent")


@dataclass(frozen=True, slots=True)
class CorrectionCandidate:
    identity: CorrectionCandidateId
    domain_result_id: DomainResultId
    transcript_id: TranscriptId
    segment_id: TranscriptSegmentId
    proposed_text: str
    rationale: str
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    target_revision_id: TranscriptRevisionId | None = None
    evidence: tuple[str, ...] = ()
    confidence: float | None = None
    uncertainty: float | None = None
    capability: CapabilityReference | None = None
    plugin_reference: PluginReference | None = None
    provider_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.rationale.strip():
            raise ValueError("correction candidate rationale must not be empty")
        if self.provider_reference is not None and not self.provider_reference.strip():
            raise ValueError("provider reference must not be empty")


@dataclass(frozen=True, slots=True)
class TranscriptValidation:
    identity: TranscriptValidationId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    structural_valid: bool
    timeline_traceable: bool
    provenance_complete: bool
    target_transcript_id: TranscriptId | None = None
    target_revision_id: TranscriptRevisionId | None = None
    ordering_valid: bool | None = None
    time_ranges_valid: bool | None = None
    overlap_detected: bool | None = None
    diagnostic_references: tuple[DiagnosticId, ...] = ()

    def __post_init__(self) -> None:
        targets = (self.target_transcript_id, self.target_revision_id)
        if sum(target is not None for target in targets) != 1:
            raise ValueError("transcript validation requires exactly one target")
