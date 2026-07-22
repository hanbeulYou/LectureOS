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

from .identities import SubtitleSrtMaterializationId
from .subtitle_srt_artifact import SubtitleSrtArtifact

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


@dataclass(frozen=True, slots=True)
class SubtitleSrtMaterializationRecord:
    """The materialization intent together with its terminal outcome."""

    materialization: SubtitleSrtMaterialization
    outcome: SubtitleSrtMaterializationOutcome


class SubtitleSrtArtifactQuery(Protocol):
    def get(self, identity): ...


class SubtitleSrtMaterializationQuery(Protocol):
    def get(self, identity): ...

    def get_outcome(self, identity): ...


class AtomicSubtitleSrtMaterializationPersistence(Protocol):
    def persist_materialization_intent(
        self,
        *,
        materialization: SubtitleSrtMaterialization,
        materialization_result: DomainResultReference,
    ) -> None: ...

    def persist_materialization_outcome(
        self, *, outcome: SubtitleSrtMaterializationOutcome
    ) -> None: ...


class SubtitleSrtMaterializationError(ValueError):
    """A structurally valid request that cannot begin a canonical materialization act."""


class SubtitleSrtMaterializationService:
    """Realizes one SRT artifact as a physical file record-first, mutating nothing upstream."""

    def __init__(
        self,
        artifact_query: SubtitleSrtArtifactQuery,
        materialization_query: SubtitleSrtMaterializationQuery,
        execution_query: ExecutionQueryBoundary,
        file_writer: MaterializedFileWriter,
        persistence: AtomicSubtitleSrtMaterializationPersistence,
    ) -> None:
        self._artifacts = artifact_query
        self._materializations = materialization_query
        self._executions = execution_query
        self._writer = file_writer
        self._persistence = persistence

    def record_materialization(
        self,
        *,
        source_artifact_id: ArtifactId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: SubtitleSrtMaterializationIdentityPlan,
        sequence: int = 0,
        previous_materialization_id: SubtitleSrtMaterializationId | None = None,
        reason: str | None = None,
    ) -> SubtitleSrtMaterializationRecord:
        # Duplicate Materialization Identity is idempotent; a dangling PENDING is completed (§17.9/§17.12).
        existing = self._materializations.get(identities.materialization_id)
        if existing is not None:
            outcome = self._materializations.get_outcome(existing.identity)
            if outcome is not None:
                return SubtitleSrtMaterializationRecord(existing, outcome)
            artifact = self._require_artifact(existing.source_artifact_id)
            return SubtitleSrtMaterializationRecord(
                existing, self._finalize(existing, artifact)
            )

        artifact = self._require_artifact(source_artifact_id)
        self._require_running_execution(run_id, unit_execution_id)
        materialization = SubtitleSrtMaterialization(
            identity=identities.materialization_id,
            domain_result_id=identities.materialization_result_id,
            source_artifact_id=artifact.identity,
            storage_kind=SubtitleMaterializationStorageKind.LOCAL_FILE,
            relative_location=srt_materialization_relative_location(
                identities.materialization_id
            ),
            source_media_id=artifact.source_media_id,
            source_timeline_id=artifact.source_timeline_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=reason if reason is not None else _default_reason(),
            previous_materialization_id=previous_materialization_id,
        )
        materialization_result = DomainResultReference(
            identity=identities.materialization_result_id,
            kind=SUBTITLE_SRT_MATERIALIZATION_RESULT_KIND,
            source_media=artifact.source_media_id,
            source_timeline=artifact.source_timeline_id,
            upstream_results=(artifact.domain_result_id,),
        )
        # Record-first: the PENDING act is durable before any file write.
        self._persistence.persist_materialization_intent(
            materialization=materialization,
            materialization_result=materialization_result,
        )
        return SubtitleSrtMaterializationRecord(
            materialization, self._finalize(materialization, artifact)
        )

    def reconcile_materialization(
        self, *, materialization_id: SubtitleSrtMaterializationId
    ) -> SubtitleSrtMaterializationRecord:
        materialization = self._materializations.get(materialization_id)
        if materialization is None:
            raise KeyError("unknown subtitle srt materialization")
        outcome = self._materializations.get_outcome(materialization_id)
        if outcome is not None:
            return SubtitleSrtMaterializationRecord(materialization, outcome)  # already terminal
        artifact = self._artifacts.get(materialization.source_artifact_id)
        if not isinstance(artifact, SubtitleSrtArtifact):
            outcome = self._persist_outcome(
                materialization.identity,
                None,
                "source artifact unavailable for reconciliation",
            )
            return SubtitleSrtMaterializationRecord(materialization, outcome)
        return SubtitleSrtMaterializationRecord(
            materialization, self._finalize(materialization, artifact)
        )

    def _finalize(
        self, materialization: SubtitleSrtMaterialization, artifact: SubtitleSrtArtifact
    ) -> SubtitleSrtMaterializationOutcome:
        content = artifact.payload.encode("utf-8")
        try:
            byte_length = self._writer.write(
                relative_location=materialization.relative_location, content=content
            )
        except (
            MaterializationCollisionError,
            MaterializationContainmentError,
            MaterializationWriteError,
        ) as error:
            return self._persist_outcome(
                materialization.identity, None, f"{type(error).__name__}: {error}"
            )
        return self._persist_outcome(materialization.identity, byte_length, None)

    def _persist_outcome(
        self,
        materialization_id: SubtitleSrtMaterializationId,
        byte_length: int | None,
        failure_reason: str | None,
    ) -> SubtitleSrtMaterializationOutcome:
        if failure_reason is None:
            outcome = SubtitleSrtMaterializationOutcome(
                materialization_id=materialization_id,
                state=SubtitleMaterializationState.MATERIALIZED,
                byte_length=byte_length,
            )
        else:
            outcome = SubtitleSrtMaterializationOutcome(
                materialization_id=materialization_id,
                state=SubtitleMaterializationState.FAILED,
                failure_reason=failure_reason,
            )
        self._persistence.persist_materialization_outcome(outcome=outcome)
        return outcome

    def _require_artifact(self, artifact_id: ArtifactId) -> SubtitleSrtArtifact:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            raise KeyError("unknown subtitle srt artifact")
        if not isinstance(artifact, SubtitleSrtArtifact):
            raise SubtitleSrtMaterializationError(
                "materialization must derive from a canonical SRT Artifact"
            )
        return artifact

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise SubtitleSrtMaterializationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise SubtitleSrtMaterializationError(
                "materializing an srt artifact requires a running unit execution"
            )


def _default_reason() -> str:
    return "materialized the srt artifact to a physical file"


__all__ = [
    "SUBTITLE_SRT_MATERIALIZATION_RESULT_KIND",
    "AtomicSubtitleSrtMaterializationPersistence",
    "MaterializationCollisionError",
    "MaterializationContainmentError",
    "MaterializationWriteError",
    "MaterializedFileWriter",
    "PreparedSubtitleSrtMaterialization",
    "SubtitleMaterializationState",
    "SubtitleMaterializationStorageKind",
    "SubtitleSrtArtifactQuery",
    "SubtitleSrtMaterialization",
    "SubtitleSrtMaterializationError",
    "SubtitleSrtMaterializationIdentityPlan",
    "SubtitleSrtMaterializationOutcome",
    "SubtitleSrtMaterializationQuery",
    "SubtitleSrtMaterializationRecord",
    "SubtitleSrtMaterializationService",
    "srt_materialization_relative_location",
]
