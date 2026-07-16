"""Immutable Subtitle candidates, revisions, cues, and validation records."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite

from lectureos.execution.identities import (
    CapabilityReference,
    ConfigurationReference,
    DiagnosticId,
    DomainResultId,
    PluginReference,
    ProcessingRunId,
    ReviewDecisionId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)

from .identities import (
    SubtitleCandidateId,
    SubtitleCueId,
    SubtitleId,
    SubtitleRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)


class SubtitleApplicability(str, Enum):
    UNDETERMINED = "undetermined"


@dataclass(frozen=True, slots=True)
class SubtitleCue:
    identity: SubtitleCueId
    subtitle_id: SubtitleId
    source_timeline_id: SourceTimelineId
    start: float
    end: float
    text: str
    display_order: int
    source_segment_ids: tuple[TranscriptSegmentId, ...]
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId | None = None
    speaker_label: str | None = None
    line_count: int | None = None
    reading_rate: float | None = None
    replaces_cue_id: SubtitleCueId | None = None

    def __post_init__(self) -> None:
        if self.source_timeline_id is None:
            raise ValueError("subtitle cue requires a Source Timeline")
        if not isfinite(self.start) or not isfinite(self.end):
            raise ValueError("subtitle cue time range must be finite")
        if self.start < 0 or self.end < 0:
            raise ValueError("subtitle cue time range must not be negative")
        if self.start > self.end:
            raise ValueError("subtitle cue start must not be after end")
        if self.display_order < 0:
            raise ValueError("subtitle cue display order must not be negative")
        if not self.source_segment_ids:
            raise ValueError("subtitle cue requires a source Transcript Segment")
        if not self.text.strip():
            raise ValueError("subtitle cue text must not be empty")


@dataclass(frozen=True, slots=True)
class SubtitleCandidate:
    identity: SubtitleCandidateId
    subtitle_id: SubtitleId
    domain_result_id: DomainResultId
    source_transcript_id: TranscriptId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    cue_ids: tuple[SubtitleCueId, ...]
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    source_revision_id: TranscriptRevisionId | None = None
    configuration: ConfigurationReference | None = None
    capability: CapabilityReference | None = None
    plugin_reference: PluginReference | None = None
    validation_id: SubtitleValidationId | None = None
    applicability: SubtitleApplicability = SubtitleApplicability.UNDETERMINED


@dataclass(frozen=True, slots=True)
class SubtitleRevision:
    identity: SubtitleRevisionId
    subtitle_id: SubtitleId
    domain_result_id: DomainResultId
    cue_ids: tuple[SubtitleCueId, ...]
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    parent_candidate_id: SubtitleCandidateId | None = None
    parent_revision_id: SubtitleRevisionId | None = None
    modification_provenance: str = "unspecified"
    decision_reference: ReviewDecisionId | None = None
    validation_id: SubtitleValidationId | None = None
    applicability: SubtitleApplicability = SubtitleApplicability.UNDETERMINED

    def __post_init__(self) -> None:
        if sum(
            parent is not None
            for parent in (self.parent_candidate_id, self.parent_revision_id)
        ) != 1:
            raise ValueError("subtitle revision requires exactly one parent")
        if not self.modification_provenance.strip():
            raise ValueError("subtitle revision provenance must not be empty")


@dataclass(frozen=True, slots=True)
class SubtitleValidation:
    identity: SubtitleValidationId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    structural_valid: bool
    timeline_consistent: bool
    ordering_consistent: bool
    provenance_complete: bool
    target_candidate_id: SubtitleCandidateId | None = None
    target_revision_id: SubtitleRevisionId | None = None
    finding_ids: tuple[SubtitleValidationFindingId, ...] = ()
    has_warnings: bool = False
    diagnostic_references: tuple[DiagnosticId, ...] = ()
    working_context: WorkingContextReference | None = None
    target_cue_ids: tuple[SubtitleCueId, ...] = ()
    recorded_at: datetime | None = None
    sequence: int | None = None
    previous_validation_id: SubtitleValidationId | None = None

    def __post_init__(self) -> None:
        if sum(
            target is not None
            for target in (self.target_candidate_id, self.target_revision_id)
        ) != 1:
            raise ValueError("subtitle validation requires exactly one target")
        if self.sequence is not None and self.sequence < 0:
            raise ValueError("subtitle validation sequence must not be negative")


@dataclass(frozen=True, slots=True)
class SubtitleValidationFinding:
    identity: SubtitleValidationFindingId
    validation_id: SubtitleValidationId
    rule: str
    description: str
    blocking: bool
    cue_id: SubtitleCueId | None = None
    revision_id: SubtitleRevisionId | None = None

    def __post_init__(self) -> None:
        if not self.rule.strip() or not self.description.strip():
            raise ValueError("subtitle validation finding must be explainable")
