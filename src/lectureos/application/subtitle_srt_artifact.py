"""Provider-independent Application contract for SRT Artifact Generation (044 §Export, stage 2).

From exactly one eligible ``SubtitleApprovedDocument`` it produces one canonical, regenerable SRT Artifact
Record whose deterministic payload is the serialized approved subtitle document. The Artifact Record is a
derived, regenerable representation — it never replaces the Approved Subtitle Document, Source Media or
Source Timeline, and it owns no physical file, path, URL, storage location or delivery state.

This module defines the durable record; serialization and the generation service live alongside it. The
stage writes no file and performs no Review/Validation/assembly/AI/provider work.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from lectureos.execution.identities import (
    ArtifactId,
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference

from .identities import SubtitleApprovedDocumentId

SUBTITLE_SRT_ARTIFACT_RESULT_KIND = "subtitle_srt_artifact"

SUBTITLE_ARTIFACT_ENCODING = "utf-8"


class SubtitleArtifactFormat(str, Enum):
    SRT = "srt"


@dataclass(frozen=True, slots=True)
class SubtitleSrtArtifact:
    """Immutable canonical SRT Artifact Record with its deterministic payload."""

    identity: ArtifactId
    domain_result_id: DomainResultId
    source_approved_document_id: SubtitleApprovedDocumentId
    format: SubtitleArtifactFormat
    payload: str
    byte_length: int
    cue_count: int
    encoding: str
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_artifact_id: ArtifactId | None = None

    def __post_init__(self) -> None:
        if self.format is not SubtitleArtifactFormat.SRT:
            raise ValueError("srt artifact format must be SRT")
        if self.encoding != SUBTITLE_ARTIFACT_ENCODING:
            raise ValueError("srt artifact encoding must be utf-8")
        if self.byte_length != len(self.payload.encode(SUBTITLE_ARTIFACT_ENCODING)):
            raise ValueError("srt artifact byte length must match the payload")
        if self.cue_count < 0:
            raise ValueError("srt artifact cue count must not be negative")
        if (self.cue_count == 0) != (self.payload == ""):
            raise ValueError("empty srt artifact must have zero cues and an empty payload")
        if not self.reason.strip():
            raise ValueError("srt artifact reason must not be empty")
        if self.sequence < 0:
            raise ValueError("srt artifact sequence must not be negative")
        if self.previous_artifact_id is not None and self.sequence == 0:
            raise ValueError("first srt artifact must not reference a previous artifact")


@dataclass(frozen=True, slots=True)
class SubtitleSrtArtifactIdentityPlan:
    """Application-owned identities for one SRT artifact generation."""

    artifact_id: ArtifactId
    artifact_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedSubtitleSrtArtifact:
    """Immutable canonical SRT Artifact Record; not yet persisted."""

    artifact: SubtitleSrtArtifact
    artifact_result: DomainResultReference


__all__ = [
    "SUBTITLE_ARTIFACT_ENCODING",
    "SUBTITLE_SRT_ARTIFACT_RESULT_KIND",
    "PreparedSubtitleSrtArtifact",
    "SubtitleArtifactFormat",
    "SubtitleSrtArtifact",
    "SubtitleSrtArtifactIdentityPlan",
]
