"""Provider-independent Application contract for SRT Physical Materialization (044 §17, PATCH-0007).

From exactly one canonical ``SubtitleSrtArtifact`` and one Materialization Request, this stage durably
realizes the artifact's inline SRT payload as a physical file under an approved Storage Root and records
the act's canonical lifecycle ``PENDING → MATERIALIZED | FAILED``.

The act is modelled as two immutable, insert-only records: a **Materialization** (the committed intent,
persisted before any file write) and a **Materialization Outcome** (the terminal result, persisted after
the write). Materialization State is *derived*: a Materialization with no Outcome is ``PENDING``; with an
Outcome it is that Outcome's terminal state. This module defines those records; the file-writer port and
the record-first service live alongside it.

Artifact identity is permanently independent of any physical file. The Storage Location is operational
provenance, never identity. This module owns no filesystem access, no cloud/object storage, and no
Delivery behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.execution.identities import (
    ArtifactId,
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference

from .identities import SubtitleSrtMaterializationId

SUBTITLE_SRT_MATERIALIZATION_RESULT_KIND = "subtitle_srt_materialization"


class SubtitleMaterializationState(str, Enum):
    PENDING = "pending"
    MATERIALIZED = "materialized"
    FAILED = "failed"


class SubtitleMaterializationStorageKind(str, Enum):
    LOCAL_FILE = "local_file"


def _is_safe_relative_location(location: str) -> bool:
    if not location.strip():
        return False
    if location.startswith("/"):
        return False
    return ".." not in location.split("/")


@dataclass(frozen=True, slots=True)
class SubtitleSrtMaterialization:
    """Immutable materialization intent: the committed act of realizing one artifact (the PENDING record)."""

    identity: SubtitleSrtMaterializationId
    domain_result_id: DomainResultId
    source_artifact_id: ArtifactId
    storage_kind: SubtitleMaterializationStorageKind
    relative_location: str
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_materialization_id: SubtitleSrtMaterializationId | None = None

    def __post_init__(self) -> None:
        if not _is_safe_relative_location(self.relative_location):
            raise ValueError(
                "materialization relative location must be a non-empty, contained relative path"
            )
        if not self.reason.strip():
            raise ValueError("materialization reason must not be empty")
        if self.sequence < 0:
            raise ValueError("materialization sequence must not be negative")
        if self.previous_materialization_id is not None and self.sequence == 0:
            raise ValueError(
                "first materialization must not reference a previous materialization"
            )


@dataclass(frozen=True, slots=True)
class SubtitleSrtMaterializationOutcome:
    """Immutable terminal outcome of one materialization act (MATERIALIZED or FAILED)."""

    materialization_id: SubtitleSrtMaterializationId
    state: SubtitleMaterializationState
    byte_length: int | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.state is SubtitleMaterializationState.MATERIALIZED:
            if self.byte_length is None or self.byte_length < 0:
                raise ValueError("materialized outcome requires a non-negative byte length")
            if self.failure_reason is not None:
                raise ValueError("materialized outcome must not carry a failure reason")
        elif self.state is SubtitleMaterializationState.FAILED:
            if self.failure_reason is None or not self.failure_reason.strip():
                raise ValueError("failed outcome requires a non-empty failure reason")
            if self.byte_length is not None:
                raise ValueError("failed outcome must not carry a byte length")
        else:
            raise ValueError("materialization outcome state must be terminal")


@dataclass(frozen=True, slots=True)
class SubtitleSrtMaterializationIdentityPlan:
    """Application-owned identities for one materialization act."""

    materialization_id: SubtitleSrtMaterializationId
    materialization_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedSubtitleSrtMaterialization:
    """Immutable materialization intent and its DomainResultReference; not yet persisted."""

    materialization: SubtitleSrtMaterialization
    materialization_result: DomainResultReference


def srt_materialization_relative_location(
    identity: SubtitleSrtMaterializationId,
) -> str:
    """Application-owned deterministic relative location policy (operational provenance, not identity)."""

    return f"{identity.value}.srt"


class MaterializationContainmentError(Exception):
    """A realization would escape the approved Storage Root."""


class MaterializationCollisionError(Exception):
    """The target location holds different bytes or a foreign object; it must not be overwritten."""


class MaterializationWriteError(Exception):
    """The physical file could not be written."""


class MaterializedFileWriter(Protocol):
    """Infrastructure boundary that realizes bytes beneath an approved Storage Root.

    ``write`` returns the realized byte length. Identical existing bytes are an idempotent success; a
    different-bytes or foreign target raises ``MaterializationCollisionError``; a root escape raises
    ``MaterializationContainmentError``; an I/O failure raises ``MaterializationWriteError``. ``read``
    returns the current bytes at a location (for reconciliation) or ``None`` if absent.
    """

    def write(self, *, relative_location: str, content: bytes) -> int: ...

    def read(self, *, relative_location: str) -> bytes | None: ...


__all__ = [
    "SUBTITLE_SRT_MATERIALIZATION_RESULT_KIND",
    "MaterializationCollisionError",
    "MaterializationContainmentError",
    "MaterializationWriteError",
    "MaterializedFileWriter",
    "PreparedSubtitleSrtMaterialization",
    "SubtitleMaterializationState",
    "SubtitleMaterializationStorageKind",
    "SubtitleSrtMaterialization",
    "SubtitleSrtMaterializationIdentityPlan",
    "SubtitleSrtMaterializationOutcome",
    "srt_materialization_relative_location",
]
