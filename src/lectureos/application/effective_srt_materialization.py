"""Physical SRT Materialization for Effective Subtitle Artifacts (GOAL-018).

The materialization boundary of the effective-transcript subtitle contract generation: an explicit
request realizes one exact logical `EffectiveSubtitleSrtArtifact` payload as a physical file under
an approved Storage Root, following the released record-first discipline (044 §17 / PATCH-0007)
truthfully: the immutable **intent** (PENDING) is durable before any file write; the immutable
terminal **outcome** (MATERIALIZED | FAILED) is recorded after; state is always derived. Write
failures — collisions, containment escapes, I/O errors — are honest FAILED outcomes, never hidden
and never retried silently.

**Artifact ≠ Materialization ≠ delivery.** The artifact's identity and payload never depend on any
path; the relative location is operational provenance of one write event. The physical bytes are
always the artifact's exact stored canonical payload (UTF-8, LF, no BOM) — materialization never
regenerates, rewrites, or fingerprints anew. Replay: when the latest materialization for one
(artifact, location) is MATERIALIZED and the file still holds the exact payload, the request
reuses that record without rewriting. An existing file with different bytes refuses by default
(the hardened writer's no-overwrite discipline); only an explicit ``overwrite=True`` request
replaces it — as a NEW append-only write event, never a mutation of history. A later deleted
physical file never mutates any record: filesystem state and logical history remain separate.
No wall-clock, randomness, ProcessingRun, or UnitExecution participates in identity or authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .identities import (
    EffectiveSrtMaterializationId,
    EffectiveSubtitleSrtArtifactId,
)
from .effective_subtitle_srt_artifact import (
    EffectiveSubtitleSrtArtifact,
    require_canonical_srt_artifact_id,
)
from .subtitle_srt_materialization import (
    MaterializationCollisionError,
    MaterializationContainmentError,
    MaterializationWriteError,
)

EFFECTIVE_SRT_MATERIALIZATION_IDENTITY_PREFIX = "subtitle-effective-srt-materialization"

MATERIALIZATION_STORAGE_KIND = "local_file"


class EffectiveSrtMaterializationError(ValueError):
    """A materialization request that cannot proceed (malformed, unknown, or unsupported input)."""


class MaterializationState(str, Enum):
    PENDING = "pending"           # intent recorded, no terminal outcome (derived)
    MATERIALIZED = "materialized"
    FAILED = "failed"


class MaterializationOutcomeKind(str, Enum):
    CREATED = "created"     # a new write event was recorded
    REUSED = "reused"       # the latest materialization already realizes this exact payload


def _is_safe_relative_location(location: str) -> bool:
    if not location.strip():
        return False
    if location.startswith("/"):
        return False
    return ".." not in location.split("/")


def default_relative_location(artifact_id: EffectiveSubtitleSrtArtifactId) -> str:
    """Deterministic default location policy — operational provenance, never identity."""

    return f"{artifact_id.value}.srt"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def derive_materialization_identity(
    artifact_id: EffectiveSubtitleSrtArtifactId,
    relative_location: str,
    sequence: int,
) -> EffectiveSrtMaterializationId:
    """Deterministic identity of one write event: (artifact, location, per-pair sequence).

    Never a path alone, never the artifact id alone, never a timestamp — one immutable record per
    explicit write attempt against one target.
    """

    digest = hashlib.sha256(
        _canonical_json(
            {
                "artifact": artifact_id.value,
                "relative_location": relative_location,
                "sequence": sequence,
            }
        ).encode("utf-8")
    ).hexdigest()
    return EffectiveSrtMaterializationId(
        f"{EFFECTIVE_SRT_MATERIALIZATION_IDENTITY_PREFIX}:{digest}"
    )


@dataclass(frozen=True, slots=True)
class EffectiveSrtMaterialization:
    """Immutable materialization intent: the committed act of realizing one artifact (PENDING record)."""

    identity: EffectiveSrtMaterializationId
    artifact_id: EffectiveSubtitleSrtArtifactId
    storage_kind: str
    relative_location: str
    payload_fingerprint: str
    sequence: int
    previous_materialization_id: EffectiveSrtMaterializationId | None = None

    def __post_init__(self) -> None:
        if self.storage_kind != MATERIALIZATION_STORAGE_KIND:
            raise ValueError("unsupported materialization storage kind")
        if not _is_safe_relative_location(self.relative_location):
            raise ValueError(
                "materialization relative location must be a non-empty, contained relative path"
            )
        if len(self.payload_fingerprint) != 64:
            raise ValueError(
                "materialization payload fingerprint must be a 64-hex SHA-256 digest"
            )
        if self.sequence < 0:
            raise ValueError("materialization sequence must not be negative")
        if (self.sequence == 0) != (self.previous_materialization_id is None):
            raise ValueError(
                "the first materialization (sequence 0) has no previous; later ones require one"
            )
        if self.previous_materialization_id == self.identity:
            raise ValueError("a materialization cannot supersede itself")
        if self.identity != derive_materialization_identity(
            self.artifact_id, self.relative_location, self.sequence
        ):
            raise ValueError(
                "materialization identity must derive from its artifact, location, and sequence"
            )


@dataclass(frozen=True, slots=True)
class EffectiveSrtMaterializationOutcome:
    """Immutable terminal outcome of one materialization act (MATERIALIZED or FAILED)."""

    materialization_id: EffectiveSrtMaterializationId
    state: MaterializationState
    byte_length: int | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.state is MaterializationState.MATERIALIZED:
            if self.byte_length is None or self.byte_length < 0:
                raise ValueError("materialized outcome requires a non-negative byte length")
            if self.failure_reason is not None:
                raise ValueError("materialized outcome must not carry a failure reason")
        elif self.state is MaterializationState.FAILED:
            if self.failure_reason is None or not self.failure_reason.strip():
                raise ValueError("failed outcome requires a non-empty failure reason")
            if self.byte_length is not None:
                raise ValueError("failed outcome must not carry a byte length")
        else:
            raise ValueError("materialization outcome state must be terminal")


@dataclass(frozen=True, slots=True)
class MaterializationRecord:
    """One act with its derived state: intent + optional terminal outcome."""

    materialization: EffectiveSrtMaterialization
    outcome: EffectiveSrtMaterializationOutcome | None
    kind: MaterializationOutcomeKind

    @property
    def state(self) -> MaterializationState:
        if self.outcome is None:
            return MaterializationState.PENDING
        return self.outcome.state


class EffectiveMaterializedFileWriter(Protocol):
    """The released writer port: contained, atomic, no-overwrite-of-different-bytes.

    ``replace`` additionally realizes bytes over an existing regular file — used ONLY for an
    explicit overwrite request; every other safety property is preserved.
    """

    def write(self, *, relative_location: str, content: bytes) -> int: ...

    def replace(self, *, relative_location: str, content: bytes) -> int: ...

    def read(self, *, relative_location: str) -> bytes | None: ...


class SrtArtifactLookup(Protocol):
    def get(self, artifact_id: str): ...


class MaterializationQuery(Protocol):
    def get(self, identity): ...

    def get_outcome(self, identity): ...

    def get_latest(self, artifact_id, relative_location): ...

    def list_for_artifact(self, artifact_id) -> tuple: ...


class AtomicMaterializationPersistence(Protocol):
    def persist_materialization_intent(
        self, *, materialization: EffectiveSrtMaterialization
    ) -> None: ...

    def persist_materialization_outcome(
        self, *, outcome: EffectiveSrtMaterializationOutcome
    ) -> None: ...


class EffectiveSrtMaterializationService:
    """The single canonical physical-materialization path of the effective generation (GOAL-018)."""

    def __init__(
        self,
        artifact_lookup: SrtArtifactLookup,
        materialization_query: MaterializationQuery,
        persistence: AtomicMaterializationPersistence,
        writer: EffectiveMaterializedFileWriter,
    ) -> None:
        self._artifacts = artifact_lookup
        self._materializations = materialization_query
        self._persistence = persistence
        self._writer = writer

    # -- explicit materialization command -------------------------------------------------------------

    def materialize(
        self,
        *,
        artifact_id: str,
        relative_location: str | None = None,
        overwrite: bool = False,
    ) -> MaterializationRecord:
        artifact = self._require_artifact(artifact_id)
        location = (
            relative_location
            if relative_location is not None
            else default_relative_location(artifact.identity)
        )
        if not _is_safe_relative_location(location):
            raise EffectiveSrtMaterializationError(
                "materialization relative location must be a non-empty, contained relative path"
            )
        content = artifact.srt_content.encode("utf-8")

        latest = self._materializations.get_latest(artifact.identity, location)
        if latest is not None:
            latest_outcome = self._materializations.get_outcome(latest.identity)
            if latest_outcome is None:
                # A dangling PENDING intent (e.g. crash between record and write) is completed
                # rather than duplicated — the released reconciliation rule.
                return MaterializationRecord(
                    latest,
                    self._finalize(latest, content, overwrite=overwrite),
                    MaterializationOutcomeKind.CREATED,
                )
            if (
                latest_outcome.state is MaterializationState.MATERIALIZED
                and latest.payload_fingerprint == artifact.content_fingerprint
                and self._writer.read(relative_location=location) == content
            ):
                # The file already holds the exact payload — reuse, never rewrite.
                return MaterializationRecord(
                    latest, latest_outcome, MaterializationOutcomeKind.REUSED
                )

        sequence = 0 if latest is None else latest.sequence + 1
        materialization = EffectiveSrtMaterialization(
            identity=derive_materialization_identity(artifact.identity, location, sequence),
            artifact_id=artifact.identity,
            storage_kind=MATERIALIZATION_STORAGE_KIND,
            relative_location=location,
            payload_fingerprint=artifact.content_fingerprint,
            sequence=sequence,
            previous_materialization_id=latest.identity if latest is not None else None,
        )
        # Record-first: the PENDING act is durable before any file write.
        self._persistence.persist_materialization_intent(materialization=materialization)
        return MaterializationRecord(
            materialization,
            self._finalize(materialization, content, overwrite=overwrite),
            MaterializationOutcomeKind.CREATED,
        )

    def _finalize(
        self,
        materialization: EffectiveSrtMaterialization,
        content: bytes,
        *,
        overwrite: bool,
    ) -> EffectiveSrtMaterializationOutcome:
        try:
            if overwrite:
                byte_length = self._writer.replace(
                    relative_location=materialization.relative_location, content=content
                )
            else:
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
        materialization_id: EffectiveSrtMaterializationId,
        byte_length: int | None,
        failure_reason: str | None,
    ) -> EffectiveSrtMaterializationOutcome:
        if failure_reason is None:
            outcome = EffectiveSrtMaterializationOutcome(
                materialization_id=materialization_id,
                state=MaterializationState.MATERIALIZED,
                byte_length=byte_length,
            )
        else:
            outcome = EffectiveSrtMaterializationOutcome(
                materialization_id=materialization_id,
                state=MaterializationState.FAILED,
                failure_reason=failure_reason,
            )
        self._persistence.persist_materialization_outcome(outcome=outcome)
        return outcome

    def _require_artifact(self, artifact_id: str) -> EffectiveSubtitleSrtArtifact:
        try:
            identity = require_canonical_srt_artifact_id(artifact_id)
        except ValueError as error:
            raise EffectiveSrtMaterializationError(str(error)) from error
        artifact = self._artifacts.get(identity.value)
        if artifact is None:
            raise EffectiveSrtMaterializationError(
                "unknown effective subtitle SRT artifact: materialization requires one "
                "exact existing logical artifact"
            )
        return artifact

    # -- queries (derived; never mutate history) ------------------------------------------------------

    def get(self, materialization_id: str) -> EffectiveSrtMaterialization | None:
        return self._materializations.get(
            require_canonical_materialization_id(materialization_id)
        )

    def state(self, materialization: EffectiveSrtMaterialization) -> MaterializationState:
        outcome = self._materializations.get_outcome(materialization.identity)
        if outcome is None:
            return MaterializationState.PENDING
        return outcome.state

    def outcome(
        self, materialization: EffectiveSrtMaterialization
    ) -> EffectiveSrtMaterializationOutcome | None:
        return self._materializations.get_outcome(materialization.identity)

    def file_matches(self, materialization: EffectiveSrtMaterialization) -> bool | None:
        """Does the physical file currently hold the exact payload? None when the file is absent.

        Purely observational: a deleted or diverged file never mutates any record and is never
        repository corruption — filesystem state and logical history are separate.
        """

        artifact = self._artifacts.get(materialization.artifact_id.value)
        if artifact is None:
            raise EffectiveSrtMaterializationError(
                "materialization references an unknown artifact (repository integrity failure)"
            )
        current = self._writer.read(
            relative_location=materialization.relative_location
        )
        if current is None:
            return None
        return current == artifact.srt_content.encode("utf-8")

    def list_for_artifact(
        self, artifact_id: str
    ) -> tuple[EffectiveSrtMaterialization, ...]:
        try:
            identity = require_canonical_srt_artifact_id(artifact_id)
        except ValueError as error:
            raise EffectiveSrtMaterializationError(str(error)) from error
        return self._materializations.list_for_artifact(identity)


def require_canonical_materialization_id(value: str) -> EffectiveSrtMaterializationId:
    prefix = EFFECTIVE_SRT_MATERIALIZATION_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise EffectiveSrtMaterializationError(
            "effective SRT materialization identity is malformed "
            "(expected 'subtitle-effective-srt-materialization:<64 hex digest>')"
        )
    return EffectiveSrtMaterializationId(value)


__all__ = [
    "EFFECTIVE_SRT_MATERIALIZATION_IDENTITY_PREFIX",
    "MATERIALIZATION_STORAGE_KIND",
    "AtomicMaterializationPersistence",
    "EffectiveMaterializedFileWriter",
    "EffectiveSrtMaterialization",
    "EffectiveSrtMaterializationError",
    "EffectiveSrtMaterializationOutcome",
    "EffectiveSrtMaterializationService",
    "MaterializationOutcomeKind",
    "MaterializationRecord",
    "MaterializationState",
    "default_relative_location",
    "derive_materialization_identity",
    "require_canonical_materialization_id",
]
