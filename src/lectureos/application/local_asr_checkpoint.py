"""Local ASR execution checkpoint — Application-owned semantics (040 §15 CP-1…CP-21, PATCH-0044).

A checkpoint is **not** a `ProviderTranscriptResult`, a `RawTranscript`, a canonical segment, a
Product Domain record, an Artifact, or Human Authority, and its existence starts no downstream stage
(CP-2, CP-3). It is durable evidence of one in-progress execution, kept so an expensive run can be
continued rather than repeated.

This module owns what CP-4 assigns to Application: the binding key, the compatibility question, the
reuse/resume/fresh ordering vocabulary, and the mode that must be disclosed. It owns no storage: the
concrete store lives under ``infrastructure/`` behind the port declared here, and it never
reconstructs the product meaning of ``provider_result_ref``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Sequence

# The on-disk execution format. Not a product version and not part of any canonical identity; an
# unrecognized value makes a checkpoint incompatible rather than corrupt-in-the-repository (CP-19).
CHECKPOINT_FORMAT_VERSION = 1

CHECKPOINT_IDENTITY_PREFIX = "local-asr-checkpoint"


class ExecutionMode(str, Enum):
    """Which of CP-8's three paths a command took. Disclosed, never a progress API (CP-21)."""

    REUSED = "reused"    # canonical admitted Provider Result already existed (L-8)
    RESUMED = "resumed"  # a compatible checkpoint continued a prior execution
    FRESH = "fresh"      # the engine ran from the beginning


class CheckpointDiscardReason(str, Enum):
    """Why a checkpoint was not used. Never a repository validation finding (CP-19)."""

    ABSENT = "absent"
    UNREADABLE_METADATA = "unreadable_metadata"
    UNKNOWN_FORMAT_VERSION = "unknown_format_version"
    BINDING_MISMATCH = "binding_mismatch"
    MALFORMED_SEGMENT = "malformed_segment"
    NON_INCREASING_SEGMENTS = "non_increasing_segments"
    NO_COMPLETE_SEGMENT = "no_complete_segment"


@dataclass(frozen=True, slots=True)
class CheckpointBinding:
    """CP-5: what a checkpoint may be resumed for.

    ``provider_result_ref`` already binds provider, model, language, provider configuration and
    Source Media (`§15` L-7 as amended by `PATCH-0040` P-4). The three additional fields are the
    CP-6 asymmetry: L-7 excludes device and compute type from the *admission* anchor because they
    serve the same request faster, but a checkpoint resumes **one physical execution**, and splicing
    output produced under different arithmetic — `int8` onto `float32`, or across engine library
    versions — would join segments that were never part of the same run. The checkpoint key is
    therefore strictly narrower than the admission anchor, and this narrowing changes nothing about
    admission identity.
    """

    provider_result_ref: str
    device: str
    compute_type: str
    engine_library: str
    engine_version: str

    def __post_init__(self) -> None:
        for label, value in (
            ("provider result reference", self.provider_result_ref),
            ("device", self.device),
            ("compute type", self.compute_type),
            ("engine library", self.engine_library),
            ("engine version", self.engine_version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"checkpoint binding {label} must not be empty")

    def as_payload(self) -> dict:
        """The binding as stored, so a later run can verify compatibility field by field."""

        return {
            "provider_result_ref": self.provider_result_ref,
            "device": self.device,
            "compute_type": self.compute_type,
            "engine_library": self.engine_library,
            "engine_version": self.engine_version,
        }

    @property
    def checkpoint_id(self) -> str:
        """Filesystem-safe deterministic id.

        The binding is never used as a path itself: a `provider_result_ref` contains ``:`` and ``=``
        and is caller-influenced, so hashing removes every path-injection and traversal surface while
        keeping the id deterministic. The original values stay recoverable from the stored metadata.
        """

        canonical = json.dumps(self.as_payload(), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return digest

    @property
    def identity(self) -> str:
        """A human-readable label for observation. Not a canonical identity (CP-2)."""

        return f"{CHECKPOINT_IDENTITY_PREFIX}:{self.checkpoint_id}"


@dataclass(frozen=True, slots=True)
class CheckpointSegment:
    """One complete engine segment recorded during an execution. Not a canonical segment (CP-2)."""

    ordinal: int
    start: float
    end: float
    text: str

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("checkpoint segment ordinal must not be negative")
        if not isinstance(self.text, str):
            raise ValueError("checkpoint segment text must be a string")

    def as_payload(self) -> dict:
        return {"ordinal": self.ordinal, "start": self.start, "end": self.end, "text": self.text}


@dataclass(frozen=True, slots=True)
class LoadedCheckpoint:
    """The result of inspecting a checkpoint: usable segments, or the reason there are none."""

    segments: tuple[CheckpointSegment, ...] = ()
    discard_reason: CheckpointDiscardReason | None = None

    @property
    def resumable(self) -> bool:
        return bool(self.segments) and self.discard_reason is None

    @property
    def resume_from(self) -> float | None:
        """The absolute source-timeline instant a resumed execution continues from (CP-12)."""

        return self.segments[-1].end if self.resumable else None


class LocalAsrCheckpointStore(Protocol):
    """Infrastructure port (CP-4). Application never learns the storage medium.

    Every method is best-effort by contract (CP-10): losing a checkpoint is never an error
    condition, so an implementation reports absence rather than raising for ordinary I/O trouble.
    """

    def owned(self, binding: CheckpointBinding):
        """Context manager acquiring exclusive ownership of the key, or raising if held (CP-20)."""

    def load(self, binding: CheckpointBinding) -> LoadedCheckpoint: ...

    def begin(self, binding: CheckpointBinding) -> None: ...

    def append(self, binding: CheckpointBinding, segment: CheckpointSegment) -> None: ...

    def delete(self, binding: CheckpointBinding) -> None: ...


class CheckpointOwnershipError(RuntimeError):
    """Another execution already owns this checkpoint key (CP-20). Never queued, never stolen."""


def segments_are_increasing(segments: Sequence[CheckpointSegment]) -> bool:
    """Whether recorded segments form a usable prefix: contiguous ordinals, non-decreasing time."""

    previous_end: float | None = None
    for index, segment in enumerate(segments):
        if segment.ordinal != index:
            return False
        if segment.end < segment.start:
            return False
        if previous_end is not None and segment.start < previous_end:
            return False
        previous_end = segment.end
    return True


__all__ = [
    "CHECKPOINT_FORMAT_VERSION",
    "CHECKPOINT_IDENTITY_PREFIX",
    "CheckpointBinding",
    "CheckpointDiscardReason",
    "CheckpointOwnershipError",
    "CheckpointSegment",
    "ExecutionMode",
    "LoadedCheckpoint",
    "LocalAsrCheckpointStore",
    "segments_are_increasing",
]
