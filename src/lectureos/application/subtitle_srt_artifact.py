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
from typing import Protocol

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import (
    ArtifactId,
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference, ProcessingState

from .identities import SubtitleApprovedDocumentId
from .srt_payload import serialize_srt_cues
from .subtitle_approved_assembly import (
    SubtitleApprovedDocument,
    SubtitleExportEligibility,
)

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


class SubtitleApprovedDocumentQuery(Protocol):
    def get(self, identity): ...

    def get_unit(self, identity): ...


class AtomicSubtitleSrtArtifactPersistence(Protocol):
    def persist_subtitle_srt_artifact(
        self,
        *,
        artifact: SubtitleSrtArtifact,
        artifact_result: DomainResultReference,
    ) -> None: ...


class SubtitleArtifactGenerationError(ValueError):
    """A structurally valid request that cannot become a canonical SRT Artifact."""


class SubtitleSrtArtifactGenerationService:
    """Serializes one eligible Approved Subtitle Document into a canonical SRT artifact, mutating nothing."""

    def __init__(
        self,
        document_query: SubtitleApprovedDocumentQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicSubtitleSrtArtifactPersistence | None = None,
    ) -> None:
        self._documents = document_query
        self._executions = execution_query
        self._persistence = persistence

    def record_generation(self, **kwargs) -> PreparedSubtitleSrtArtifact:
        prepared = self.generate_artifact(**kwargs)
        if self._persistence is None:
            raise RuntimeError("srt artifact persistence is not configured")
        self._persistence.persist_subtitle_srt_artifact(
            artifact=prepared.artifact,
            artifact_result=prepared.artifact_result,
        )
        return prepared

    def generate_artifact(
        self,
        *,
        source_approved_document_id: SubtitleApprovedDocumentId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: SubtitleSrtArtifactIdentityPlan,
        sequence: int = 0,
        previous_artifact_id: ArtifactId | None = None,
        reason: str | None = None,
    ) -> PreparedSubtitleSrtArtifact:
        # Admit exactly one canonical Approved Subtitle Document. Its approved meaning, ordering, timing,
        # omission and modified text are consumed as-is; nothing upstream is re-read or mutated.
        document = self._documents.get(source_approved_document_id)
        if document is None:
            raise KeyError("unknown subtitle approved document")
        if not isinstance(document, SubtitleApprovedDocument):
            raise SubtitleArtifactGenerationError(
                "srt artifact must derive from a canonical Approved Subtitle Document"
            )
        self._require_running_execution(run_id, unit_execution_id)

        if document.eligibility is not SubtitleExportEligibility.ELIGIBLE:
            raise SubtitleArtifactGenerationError(
                "srt artifact generation requires an eligible approved subtitle document"
            )

        cues = []
        for unit_id in document.approved_unit_ids:
            unit = self._documents.get_unit(unit_id)
            if unit is None:
                raise SubtitleArtifactGenerationError(
                    "approved unit provenance is unresolved"
                )
            cues.append((unit.start, unit.end, "\n".join(unit.lines)))

        try:
            payload = serialize_srt_cues(cues)
        except ValueError as error:
            raise SubtitleArtifactGenerationError(
                f"approved subtitle document cannot be serialized to SRT: {error}"
            ) from error

        resolved_reason = reason if reason is not None else _default_reason()
        artifact = SubtitleSrtArtifact(
            identity=identities.artifact_id,
            domain_result_id=identities.artifact_result_id,
            source_approved_document_id=document.identity,
            format=SubtitleArtifactFormat.SRT,
            payload=payload,
            byte_length=len(payload.encode(SUBTITLE_ARTIFACT_ENCODING)),
            cue_count=len(cues),
            encoding=SUBTITLE_ARTIFACT_ENCODING,
            source_media_id=document.source_media_id,
            source_timeline_id=document.source_timeline_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            previous_artifact_id=previous_artifact_id,
        )
        artifact_result = DomainResultReference(
            identity=identities.artifact_result_id,
            kind=SUBTITLE_SRT_ARTIFACT_RESULT_KIND,
            source_media=document.source_media_id,
            source_timeline=document.source_timeline_id,
            upstream_results=(document.domain_result_id,),
        )
        return PreparedSubtitleSrtArtifact(
            artifact=artifact, artifact_result=artifact_result
        )

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise SubtitleArtifactGenerationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise SubtitleArtifactGenerationError(
                "generating an srt artifact requires a running unit execution"
            )


def _default_reason() -> str:
    return "generated the srt artifact from the approved subtitle document"


__all__ = [
    "SUBTITLE_ARTIFACT_ENCODING",
    "SUBTITLE_SRT_ARTIFACT_RESULT_KIND",
    "AtomicSubtitleSrtArtifactPersistence",
    "PreparedSubtitleSrtArtifact",
    "SubtitleApprovedDocumentQuery",
    "SubtitleArtifactFormat",
    "SubtitleArtifactGenerationError",
    "SubtitleSrtArtifact",
    "SubtitleSrtArtifactGenerationService",
    "SubtitleSrtArtifactIdentityPlan",
]
