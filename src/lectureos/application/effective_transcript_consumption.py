"""Effective Transcript Consumption Boundary (040 §21, PATCH-0028).

The shared application boundary through which downstream transcript-derived operations acquire
**one immutable transcript source**. Resolution — *which transcript is effective now* — is owned
solely by the 040 §20 resolver (`CorrectedRevisionSelectionService.resolve_effective_transcript`);
this module never re-derives selection, acceptance, parent, or fallback logic. It adds the three
things resolution does not answer: consumability validation for a *new* consumption, loading of
the exact immutable snapshot **by resolved source identity** (never back through current
authority, so no mixed-source snapshot is possible), and the stable deterministic **consumption
binding** pinning a consumer to the exact source it consumed.

Five distinctions are preserved: current authority ≠ consumed source ≠ historical binding lineage
≠ binding currentness ≠ repository integrity. A binding is never mutated, deleted, or
reinterpreted when authority later changes; whether its source is still effective is **derived**
by comparison with the current resolver result (`ConsumptionCurrentness`), never stored as a
mutable flag. A selected-but-inapplicable corrected revision blocks new consumption explicitly —
there is no silent Raw fallback. The only consumer in this slice is the neutral deterministic
consumption manifest; its persisted output is the binding itself carrying a harmless deterministic
summary (segment count + the §19 content fingerprint, reused verbatim). No wall-clock, randomness,
ProcessingRun, DomainResult, Artifact, or physical file participates.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId
from lectureos.transcript.models import TranscriptSegment

from .corrected_revision_generation import content_fingerprint_for
from .corrected_revision_selection import (
    CorrectedRevisionSelectionError,
    CorrectedRevisionSelectionService,
    EffectiveKind,
    EffectiveTranscript,
    SelectionState,
)
from .identities import (
    CorrectedRevisionSelectionId,
    CurrentRawTranscriptSelectionId,
    EffectiveTranscriptConsumptionId,
    TranscriptSourceIntakeId,
)
from .provider_transcript_admission import (
    ProviderTranscriptAdmissionError,
    require_canonical_intake_id,
)

CONSUMPTION_IDENTITY_PREFIX = "transcript-consumption"

# The single bounded first consumer of this slice (040 §21 S3-12). Further consumer kinds are
# separately gated milestones — the service refuses unknown kinds instead of speculating.
MANIFEST_CONSUMER_KIND = "transcript_consumption_manifest"
# 041 §15 / PATCH-0029: subtitle candidate generation is the approved second consumer.
SUBTITLE_GENERATION_CONSUMER_KIND = "subtitle_candidate_generation"
SUPPORTED_CONSUMER_KINDS = frozenset(
    {MANIFEST_CONSUMER_KIND, SUBTITLE_GENERATION_CONSUMER_KIND}
)


class EffectiveTranscriptConsumptionError(ValueError):
    """A consumption request that cannot proceed (malformed, unknown, or unsupported input)."""


class InapplicableSelectedRevisionError(EffectiveTranscriptConsumptionError):
    """The selected corrected revision is currently inapplicable — new consumption is refused explicitly."""


class ConsumptionConflictError(EffectiveTranscriptConsumptionError):
    """An existing binding for the same deterministic identity records different content."""


class ConsumedSourceKind(str, Enum):
    RAW_TRANSCRIPT = "raw_transcript"
    CORRECTED_TRANSCRIPT_REVISION = "corrected_transcript_revision"


class ConsumptionOutcome(str, Enum):
    CREATED = "created"   # a new binding was persisted for this (consumer, source)
    REUSED = "reused"     # an identical binding already existed; no new row


class ConsumptionCurrentness(str, Enum):
    """Derived comparison of a historical binding against the current resolver result — never stored."""

    CURRENT = "current"
    STALE_DUE_TO_RAW_SELECTION_CHANGE = "stale_due_to_raw_selection_change"
    STALE_DUE_TO_CORRECTED_SELECTION_CHANGE = "stale_due_to_corrected_selection_change"
    STALE_DUE_TO_SELECTED_REVISION_INAPPLICABILITY = (
        "stale_due_to_selected_revision_inapplicability"
    )
    UNRESOLVABLE = "unresolvable"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def derive_consumption_identity(
    consumer_kind: str,
    intake_id: TranscriptSourceIntakeId,
    source_kind: ConsumedSourceKind,
    source_transcript_identity: str,
) -> EffectiveTranscriptConsumptionId:
    """Deterministic binding identity — consumer, context, and the exact immutable source only.

    Authority provenance and content fingerprint are recorded facts, not identity (040 §21 S3-8):
    re-consuming the same source under changed-but-equivalent authority converges on one binding.
    """

    digest = hashlib.sha256(
        _canonical_json(
            {
                "consumer_kind": consumer_kind,
                "intake": intake_id.value,
                "source_kind": source_kind.value,
                "source": source_transcript_identity,
            }
        ).encode("utf-8")
    ).hexdigest()
    return EffectiveTranscriptConsumptionId(f"{CONSUMPTION_IDENTITY_PREFIX}:{digest}")


@dataclass(frozen=True, slots=True)
class EffectiveTranscriptInput:
    """One immutable transcript source, acquired through the sole §20 resolver, ready to consume.

    Normalizes Raw and Corrected sources without erasing kind, provenance, or lineage: the ordered
    ``segments`` are the canonical ``TranscriptSegment`` records of the exact source (corrected
    replacement lineage via ``replaces_segment_id``, provider/human provenance, timing, speaker —
    all passed through faithfully; nothing fabricated, retimed, or renormalized).
    """

    transcript_source_intake_id: TranscriptSourceIntakeId
    selection_state: SelectionState
    source_kind: ConsumedSourceKind
    parent_raw_transcript_id: TranscriptId
    corrected_revision_id: TranscriptRevisionId | None
    raw_selection_id: CurrentRawTranscriptSelectionId
    corrected_selection_id: CorrectedRevisionSelectionId | None
    segments: tuple[TranscriptSegment, ...]
    content_fingerprint: str

    def __post_init__(self) -> None:
        _require_kind_state_consistency(
            source_kind=self.source_kind,
            selection_state=self.selection_state,
            corrected_revision_id=self.corrected_revision_id,
            corrected_selection_id=self.corrected_selection_id,
        )
        if self.content_fingerprint != content_fingerprint_for(self.segments):
            raise ValueError(
                "input content fingerprint must match its ordered segment snapshot"
            )

    @property
    def source_transcript_identity(self) -> str:
        """The exact immutable source consumed — never the intake or a selection pointer."""

        if self.source_kind is ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION:
            return self.corrected_revision_id.value
        return self.parent_raw_transcript_id.value


@dataclass(frozen=True, slots=True)
class EffectiveTranscriptConsumption:
    """Immutable persisted binding: one consumer consumed one exact source under one observed authority."""

    identity: EffectiveTranscriptConsumptionId
    consumer_kind: str
    transcript_source_intake_id: TranscriptSourceIntakeId
    resolution_state: SelectionState
    source_kind: ConsumedSourceKind
    parent_raw_transcript_id: TranscriptId
    corrected_revision_id: TranscriptRevisionId | None
    raw_selection_id: CurrentRawTranscriptSelectionId
    corrected_selection_id: CorrectedRevisionSelectionId | None
    content_fingerprint: str
    segment_count: int

    def __post_init__(self) -> None:
        if not self.consumer_kind.strip():
            raise ValueError("consumption consumer kind must not be empty")
        if self.segment_count < 0:
            raise ValueError("consumption segment count must not be negative")
        if len(self.content_fingerprint) != 64:
            raise ValueError(
                "consumption content fingerprint must be a 64-hex SHA-256 digest"
            )
        _require_kind_state_consistency(
            source_kind=self.source_kind,
            selection_state=self.resolution_state,
            corrected_revision_id=self.corrected_revision_id,
            corrected_selection_id=self.corrected_selection_id,
        )
        expected = derive_consumption_identity(
            self.consumer_kind,
            self.transcript_source_intake_id,
            self.source_kind,
            self.source_transcript_identity,
        )
        if self.identity != expected:
            raise ValueError(
                "consumption identity must be derived from consumer kind, intake, and exact source"
            )

    @property
    def source_transcript_identity(self) -> str:
        if self.source_kind is ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION:
            return self.corrected_revision_id.value
        return self.parent_raw_transcript_id.value


def _require_kind_state_consistency(
    *,
    source_kind: ConsumedSourceKind,
    selection_state: SelectionState,
    corrected_revision_id: TranscriptRevisionId | None,
    corrected_selection_id: CorrectedRevisionSelectionId | None,
) -> None:
    if source_kind is ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION:
        if corrected_revision_id is None:
            raise ValueError("a corrected consumption requires the exact revision identity")
        if selection_state is not SelectionState.CORRECTED_SELECTED:
            raise ValueError(
                "a corrected consumption requires a corrected_revision_selected resolution state"
            )
        if corrected_selection_id is None:
            raise ValueError(
                "a corrected consumption requires the observed corrected selection authority"
            )
        return
    if corrected_revision_id is not None:
        raise ValueError("a raw consumption must not carry a corrected revision identity")
    if selection_state is SelectionState.NO_HISTORY:
        if corrected_selection_id is not None:
            raise ValueError(
                "a no-history raw consumption observed no corrected selection authority"
            )
    elif selection_state is SelectionState.RAW_FALLBACK:
        if corrected_selection_id is None:
            raise ValueError(
                "an explicit raw fallback consumption requires the observed fallback authority"
            )
    else:
        raise ValueError(
            "a raw consumption requires a no-history or raw-fallback resolution state"
        )


@dataclass(frozen=True, slots=True)
class ConsumptionResult:
    """One consumption command outcome: the binding, the acquired input, and replay provenance."""

    consumption: EffectiveTranscriptConsumption
    input: EffectiveTranscriptInput
    outcome: ConsumptionOutcome
    currently_effective: bool


class RawTranscriptSnapshotQuery(Protocol):
    def get(self, identity): ...


class CorrectedRevisionSnapshotQuery(Protocol):
    def get(self, identity): ...


class TranscriptSegmentSnapshotQuery(Protocol):
    def get(self, identity): ...


class ConsumptionQuery(Protocol):
    def get(self, identity): ...

    def list_for_intake(self, intake_id) -> tuple: ...


class AtomicConsumptionPersistence(Protocol):
    def persist_consumption(self, *, consumption: EffectiveTranscriptConsumption) -> None: ...


class EffectiveTranscriptInputService:
    """Acquires one immutable transcript snapshot through the sole §20 resolver (no duplicate logic)."""

    def __init__(
        self,
        selection_service: CorrectedRevisionSelectionService,
        raw_transcript_query: RawTranscriptSnapshotQuery,
        revision_query: CorrectedRevisionSnapshotQuery,
        segment_query: TranscriptSegmentSnapshotQuery,
    ) -> None:
        self._resolver = selection_service
        self._raw_transcripts = raw_transcript_query
        self._revisions = revision_query
        self._segments = segment_query

    def acquire(self, intake_id: str) -> EffectiveTranscriptInput:
        resolution = self._resolver.resolve_effective_transcript(intake_id)
        if resolution.effective_kind is EffectiveKind.INAPPLICABLE_SELECTION:
            raise InapplicableSelectedRevisionError(
                "selected corrected revision is currently inapplicable "
                f"({resolution.inapplicability_reason}); consumption is refused and no silent "
                "raw fallback is performed"
            )
        if resolution.effective_kind is EffectiveKind.CORRECTED_REVISION:
            return self._acquire_corrected(resolution)
        return self._acquire_raw(resolution)

    # -- snapshot loading by immutable resolved source identity (never through current authority) ----

    def _acquire_raw(self, resolution: EffectiveTranscript) -> EffectiveTranscriptInput:
        raw = self._raw_transcripts.get(resolution.raw_transcript_id)
        if raw is None:
            raise EffectiveTranscriptConsumptionError(
                "resolved raw transcript does not exist (repository integrity failure)"
            )
        segments = self._load_segments(raw.segment_ids)
        return EffectiveTranscriptInput(
            transcript_source_intake_id=resolution.transcript_source_intake_id,
            selection_state=resolution.selection_state,
            source_kind=ConsumedSourceKind.RAW_TRANSCRIPT,
            parent_raw_transcript_id=raw.identity,
            corrected_revision_id=None,
            raw_selection_id=resolution.raw_selection_id,
            corrected_selection_id=resolution.corrected_selection_id,
            segments=segments,
            content_fingerprint=content_fingerprint_for(segments),
        )

    def _acquire_corrected(self, resolution: EffectiveTranscript) -> EffectiveTranscriptInput:
        revision = self._revisions.get(resolution.corrected_revision_id)
        if revision is None:
            raise EffectiveTranscriptConsumptionError(
                "resolved corrected revision does not exist (repository integrity failure)"
            )
        if revision.parent_raw_transcript_id != resolution.raw_transcript_id:
            # The revision's immutable lineage must agree with the authority state the resolver
            # observed; a disagreement means authority changed between reads — fail truthfully
            # rather than persist a mixed-state acquisition (040 §21 S3-5).
            raise EffectiveTranscriptConsumptionError(
                "corrected revision parent does not match the resolved raw transcript; "
                "authority changed during acquisition — retry"
            )
        segments = self._load_segments(revision.segment_ids)
        return EffectiveTranscriptInput(
            transcript_source_intake_id=resolution.transcript_source_intake_id,
            selection_state=resolution.selection_state,
            source_kind=ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION,
            parent_raw_transcript_id=revision.parent_raw_transcript_id,
            corrected_revision_id=revision.identity,
            raw_selection_id=resolution.raw_selection_id,
            corrected_selection_id=resolution.corrected_selection_id,
            segments=segments,
            content_fingerprint=content_fingerprint_for(segments),
        )

    def _load_segments(self, segment_ids) -> tuple[TranscriptSegment, ...]:
        segments = []
        for segment_id in segment_ids:
            segment = self._segments.get(segment_id)
            if segment is None:
                raise EffectiveTranscriptConsumptionError(
                    "transcript source snapshot is incomplete: a segment record is missing "
                    "(repository integrity failure)"
                )
            segments.append(segment)
        return tuple(segments)


class EffectiveTranscriptConsumptionService:
    """Records the stable consumption binding for the bounded manifest consumer (040 §21)."""

    def __init__(
        self,
        input_service: EffectiveTranscriptInputService,
        selection_service: CorrectedRevisionSelectionService,
        consumption_query: ConsumptionQuery,
        persistence: AtomicConsumptionPersistence | None = None,
    ) -> None:
        self._inputs = input_service
        self._resolver = selection_service
        self._consumptions = consumption_query
        self._persistence = persistence

    # -- acquisition and binding ---------------------------------------------------------------------

    def acquire_input(self, intake_id: str) -> EffectiveTranscriptInput:
        return self._inputs.acquire(intake_id)

    def consume(
        self, *, intake_id: str, consumer_kind: str = MANIFEST_CONSUMER_KIND
    ) -> ConsumptionResult:
        if consumer_kind not in SUPPORTED_CONSUMER_KINDS:
            raise EffectiveTranscriptConsumptionError(
                "unsupported consumer kind for this slice: "
                f"{consumer_kind!r} (supported: {sorted(SUPPORTED_CONSUMER_KINDS)})"
            )
        acquired = self._inputs.acquire(intake_id)
        identity = derive_consumption_identity(
            consumer_kind,
            acquired.transcript_source_intake_id,
            acquired.source_kind,
            acquired.source_transcript_identity,
        )
        existing = self._consumptions.get(identity)
        if existing is not None:
            return self._reuse(existing, acquired)

        consumption = EffectiveTranscriptConsumption(
            identity=identity,
            consumer_kind=consumer_kind,
            transcript_source_intake_id=acquired.transcript_source_intake_id,
            resolution_state=acquired.selection_state,
            source_kind=acquired.source_kind,
            parent_raw_transcript_id=acquired.parent_raw_transcript_id,
            corrected_revision_id=acquired.corrected_revision_id,
            raw_selection_id=acquired.raw_selection_id,
            corrected_selection_id=acquired.corrected_selection_id,
            content_fingerprint=acquired.content_fingerprint,
            segment_count=len(acquired.segments),
        )
        if self._persistence is None:
            raise RuntimeError("effective transcript consumption persistence is not configured")
        try:
            self._persistence.persist_consumption(consumption=consumption)
        except PersistenceIdentityCollisionError:
            # A near-concurrent identical consumption won the insert; converge on its binding.
            resolved = self._consumptions.get(identity)
            if resolved is not None:
                return self._reuse(resolved, acquired)
            raise
        return ConsumptionResult(
            consumption=consumption,
            input=acquired,
            outcome=ConsumptionOutcome.CREATED,
            currently_effective=True,
        )

    @staticmethod
    def _reuse(
        existing: EffectiveTranscriptConsumption, acquired: EffectiveTranscriptInput
    ) -> ConsumptionResult:
        # The source entity is immutable, so its content fingerprint can never legitimately
        # change; a disagreement is an explicit conflict, never an overwrite.
        if existing.content_fingerprint != acquired.content_fingerprint:
            raise ConsumptionConflictError(
                "existing consumption binding for this source records a different content "
                "fingerprint (repository integrity failure)"
            )
        return ConsumptionResult(
            consumption=existing,
            input=acquired,
            outcome=ConsumptionOutcome.REUSED,
            currently_effective=True,
        )

    # -- queries (derived; never mutate history) ------------------------------------------------------

    def get_binding(self, identity) -> EffectiveTranscriptConsumption | None:
        """Load one persisted binding by identity (read-only)."""

        return self._consumptions.get(identity)

    def bindings(self, intake_id: str) -> tuple[EffectiveTranscriptConsumption, ...]:
        try:
            intake_identity = require_canonical_intake_id(intake_id)
        except ProviderTranscriptAdmissionError as error:
            raise EffectiveTranscriptConsumptionError(str(error)) from error
        return self._consumptions.list_for_intake(intake_identity)

    def currentness(self, consumption: EffectiveTranscriptConsumption) -> ConsumptionCurrentness:
        """Is this historical binding's source still the current effective transcript? Derived only."""

        try:
            resolution = self._resolver.resolve_effective_transcript(
                consumption.transcript_source_intake_id.value
            )
        except CorrectedRevisionSelectionError:
            return ConsumptionCurrentness.UNRESOLVABLE

        if resolution.effective_kind is EffectiveKind.INAPPLICABLE_SELECTION:
            bound_to_selected = (
                consumption.source_kind is ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION
                and consumption.corrected_revision_id == resolution.corrected_revision_id
            )
            if not bound_to_selected:
                if (
                    consumption.source_kind is ConsumedSourceKind.RAW_TRANSCRIPT
                    and consumption.parent_raw_transcript_id != resolution.raw_transcript_id
                ):
                    return ConsumptionCurrentness.STALE_DUE_TO_RAW_SELECTION_CHANGE
                return ConsumptionCurrentness.STALE_DUE_TO_CORRECTED_SELECTION_CHANGE
            if resolution.inapplicability_reason == "parent_raw_transcript_not_current":
                return ConsumptionCurrentness.STALE_DUE_TO_RAW_SELECTION_CHANGE
            return ConsumptionCurrentness.STALE_DUE_TO_SELECTED_REVISION_INAPPLICABILITY

        if resolution.effective_kind is EffectiveKind.CORRECTED_REVISION:
            if (
                consumption.source_kind is ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION
                and consumption.corrected_revision_id == resolution.corrected_revision_id
            ):
                return ConsumptionCurrentness.CURRENT
            return ConsumptionCurrentness.STALE_DUE_TO_CORRECTED_SELECTION_CHANGE

        # Effective source is the Raw Transcript (no history or explicit fallback).
        if consumption.source_kind is ConsumedSourceKind.RAW_TRANSCRIPT:
            if consumption.parent_raw_transcript_id == resolution.raw_transcript_id:
                return ConsumptionCurrentness.CURRENT
            return ConsumptionCurrentness.STALE_DUE_TO_RAW_SELECTION_CHANGE
        return ConsumptionCurrentness.STALE_DUE_TO_CORRECTED_SELECTION_CHANGE


__all__ = [
    "CONSUMPTION_IDENTITY_PREFIX",
    "MANIFEST_CONSUMER_KIND",
    "SUBTITLE_GENERATION_CONSUMER_KIND",
    "SUPPORTED_CONSUMER_KINDS",
    "AtomicConsumptionPersistence",
    "ConsumedSourceKind",
    "ConsumptionConflictError",
    "ConsumptionCurrentness",
    "ConsumptionOutcome",
    "ConsumptionQuery",
    "ConsumptionResult",
    "EffectiveTranscriptConsumption",
    "EffectiveTranscriptConsumptionError",
    "EffectiveTranscriptConsumptionService",
    "EffectiveTranscriptInput",
    "EffectiveTranscriptInputService",
    "InapplicableSelectedRevisionError",
    "derive_consumption_identity",
]
