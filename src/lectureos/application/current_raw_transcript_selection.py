"""Current Raw Transcript Selection and downstream readiness (040 §16, PATCH-0023).

Answers, for one `TranscriptSourceIntake` that may hold several admitted `RawTranscript` candidates (040 §14/§15):
**which Raw Transcript is the current authoritative input for downstream transcript work, and is the intake ready
to begin Correction?**

Selection is an explicit **Product and repository authority** decision — never inferred from provider name, model
size, wall-clock time, transcript length, or confidence, and it never ranks or labels a candidate "best". It does
not compare ASR quality, alter Raw Transcript content, or execute Correction. Choosing or switching the current
Raw Transcript never rewrites or deletes any transcript: history is **append-only** (each change is a new record
with an incremented per-intake ``sequence`` superseding the previous one), and the current selection is the
highest-``sequence`` record for the intake. Readiness reflects only repository state: an intake is ``ready`` when
exactly one valid current Raw Transcript is selected, ``not_ready`` with none, and ``error`` if the persisted
current selection is inconsistent. Readiness never depends on source-file existence, ASR/provider availability,
model accuracy, confidence, or human review.

Candidate enumeration is deterministic (ordered by Raw Transcript identity), not ranked. A selected Raw Transcript
must be an admitted candidate of the **same** intake; unknown, unrelated, malformed, or dangling references are
rejected explicitly. Selecting the already-current Raw Transcript is idempotent. No wall-clock/randomness defines
identity.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.transcript.identities import TranscriptId

from .identities import CurrentRawTranscriptSelectionId, TranscriptSourceIntakeId
from .provider_transcript_admission import (
    ProviderTranscriptAdmissionError,
    require_canonical_intake_id,
)

RAW_TRANSCRIPT_SELECTION_IDENTITY_PREFIX = "raw-transcript-selection"
_RAW_TRANSCRIPT_IDENTITY_PREFIX = "raw-transcript:"


class RawTranscriptSelectionError(ValueError):
    """A Raw Transcript selection that cannot be admitted (malformed, unknown, or unrelated reference)."""


class TranscriptIntakeReadiness(str, Enum):
    NOT_READY = "not_ready"
    READY = "ready"
    ERROR = "error"


class SelectionOutcome(str, Enum):
    CREATED = "created"
    REUSED = "reused"
    SWITCHED = "switched"


def require_canonical_raw_transcript_id(value: str) -> TranscriptId:
    """Return a `TranscriptId` if the value is a well-formed admitted Raw Transcript identity, else reject."""

    if not isinstance(value, str) or not value.startswith(_RAW_TRANSCRIPT_IDENTITY_PREFIX):
        raise RawTranscriptSelectionError(
            "raw transcript identity is malformed (expected 'raw-transcript:<digest>')"
        )
    digest = value[len(_RAW_TRANSCRIPT_IDENTITY_PREFIX):]
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise RawTranscriptSelectionError(
            "raw transcript identity is malformed (expected 'raw-transcript:<64 hex digest>')"
        )
    return TranscriptId(value)


def derive_selection_identity(
    intake_id: TranscriptSourceIntakeId, raw_transcript_id: TranscriptId, sequence: int
) -> CurrentRawTranscriptSelectionId:
    """Deterministic selection identity from the intake, chosen Raw Transcript, and per-intake sequence."""

    payload = json.dumps(
        {"intake": intake_id.value, "raw_transcript": raw_transcript_id.value, "sequence": sequence},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return CurrentRawTranscriptSelectionId(
        f"{RAW_TRANSCRIPT_SELECTION_IDENTITY_PREFIX}:{digest}"
    )


@dataclass(frozen=True, slots=True)
class RawTranscriptCandidate:
    """One admitted Raw Transcript candidate of an intake, with its provider evidence metadata (not ranked)."""

    raw_transcript_id: TranscriptId
    provider_reference: str
    provider_model: str | None
    declared_language: str | None
    segment_count: int


@dataclass(frozen=True, slots=True)
class CurrentRawTranscriptSelection:
    """Durable, immutable authority record: which Raw Transcript is current for an intake at a given sequence."""

    identity: CurrentRawTranscriptSelectionId
    transcript_source_intake_id: TranscriptSourceIntakeId
    raw_transcript_id: TranscriptId
    sequence: int
    previous_selection_id: CurrentRawTranscriptSelectionId | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("selection sequence must not be negative")
        if (self.sequence == 0) != (self.previous_selection_id is None):
            raise ValueError(
                "the first selection (sequence 0) has no previous; later selections require one"
            )
        expected = derive_selection_identity(
            self.transcript_source_intake_id, self.raw_transcript_id, self.sequence
        )
        if self.identity != expected:
            raise ValueError(
                "raw transcript selection identity must be derived from its intake, transcript, and sequence"
            )
        if self.reason is not None and not self.reason.strip():
            raise ValueError("selection reason, when present, must not be blank")


@dataclass(frozen=True, slots=True)
class RawTranscriptSelectionResult:
    """The outcome of one selection command: the current record, the outcome, and the superseded record."""

    selection: CurrentRawTranscriptSelection
    outcome: SelectionOutcome
    previous: CurrentRawTranscriptSelection | None = None


@dataclass(frozen=True, slots=True)
class TranscriptIntakeReadinessReport:
    """Whether an intake is ready to begin downstream Correction, derived from current persisted facts."""

    transcript_source_intake_id: TranscriptSourceIntakeId
    readiness: TranscriptIntakeReadiness
    candidate_count: int
    current_selection_id: CurrentRawTranscriptSelectionId | None = None
    current_raw_transcript_id: TranscriptId | None = None


class TranscriptSourceIntakeQuery(Protocol):
    def get(self, identity): ...


class RawTranscriptCandidateQuery(Protocol):
    def candidates(self, intake_id: TranscriptSourceIntakeId) -> tuple[RawTranscriptCandidate, ...]: ...

    def owning_intake(self, raw_transcript_id: TranscriptId) -> TranscriptSourceIntakeId | None: ...


class RawTranscriptSelectionQuery(Protocol):
    def get(self, identity): ...

    def get_current(
        self, intake_id: TranscriptSourceIntakeId
    ) -> CurrentRawTranscriptSelection | None: ...


class AtomicRawTranscriptSelectionPersistence(Protocol):
    def persist_selection(self, *, selection: CurrentRawTranscriptSelection) -> None: ...


class CurrentRawTranscriptSelectionService:
    """Enumerates candidates, selects/switches the current Raw Transcript, and derives intake readiness."""

    def __init__(
        self,
        intake_query: TranscriptSourceIntakeQuery,
        candidate_query: RawTranscriptCandidateQuery,
        selection_query: RawTranscriptSelectionQuery,
        persistence: AtomicRawTranscriptSelectionPersistence | None = None,
    ) -> None:
        self._intakes = intake_query
        self._candidates = candidate_query
        self._selections = selection_query
        self._persistence = persistence

    def _resolve_intake(self, intake_id: str) -> TranscriptSourceIntakeId:
        try:
            identity = require_canonical_intake_id(intake_id)
        except ProviderTranscriptAdmissionError as error:
            raise RawTranscriptSelectionError(str(error)) from error
        if self._intakes.get(identity) is None:
            raise RawTranscriptSelectionError(
                "unknown transcript source intake: admit the Source Media as an intake first"
            )
        return identity

    def candidates(self, intake_id: str) -> tuple[RawTranscriptCandidate, ...]:
        identity = self._resolve_intake(intake_id)
        return self._candidates.candidates(identity)

    def current(self, intake_id: str) -> CurrentRawTranscriptSelection | None:
        identity = self._resolve_intake(intake_id)
        return self._selections.get_current(identity)

    def select(
        self, intake_id: str, raw_transcript_id: str, reason: str | None = None
    ) -> RawTranscriptSelectionResult:
        intake_identity = self._resolve_intake(intake_id)
        transcript_identity = require_canonical_raw_transcript_id(raw_transcript_id)

        owning = self._candidates.owning_intake(transcript_identity)
        if owning is None:
            raise RawTranscriptSelectionError(
                "unknown raw transcript: no admitted Raw Transcript with this identity"
            )
        if owning != intake_identity:
            raise RawTranscriptSelectionError(
                "raw transcript belongs to a different transcript source intake"
            )

        current = self._selections.get_current(intake_identity)
        if current is not None and current.raw_transcript_id == transcript_identity:
            # Idempotent: the requested Raw Transcript is already current.
            return RawTranscriptSelectionResult(
                selection=current, outcome=SelectionOutcome.REUSED, previous=None
            )

        sequence = 0 if current is None else current.sequence + 1
        previous_id = current.identity if current is not None else None
        selection = CurrentRawTranscriptSelection(
            identity=derive_selection_identity(intake_identity, transcript_identity, sequence),
            transcript_source_intake_id=intake_identity,
            raw_transcript_id=transcript_identity,
            sequence=sequence,
            previous_selection_id=previous_id,
            reason=reason,
        )
        if self._persistence is None:
            raise RuntimeError("raw transcript selection persistence is not configured")
        try:
            self._persistence.persist_selection(selection=selection)
        except PersistenceIdentityCollisionError:
            # A near-concurrent selection advanced the sequence; re-resolve and converge.
            resolved = self._selections.get_current(intake_identity)
            if resolved is not None and resolved.raw_transcript_id == transcript_identity:
                return RawTranscriptSelectionResult(
                    selection=resolved, outcome=SelectionOutcome.REUSED, previous=None
                )
            raise
        outcome = SelectionOutcome.CREATED if current is None else SelectionOutcome.SWITCHED
        return RawTranscriptSelectionResult(
            selection=selection, outcome=outcome, previous=current
        )

    def readiness(self, intake_id: str) -> TranscriptIntakeReadinessReport:
        intake_identity = self._resolve_intake(intake_id)
        candidate_count = len(self._candidates.candidates(intake_identity))
        current = self._selections.get_current(intake_identity)
        if current is None:
            return TranscriptIntakeReadinessReport(
                transcript_source_intake_id=intake_identity,
                readiness=TranscriptIntakeReadiness.NOT_READY,
                candidate_count=candidate_count,
            )
        owning = self._candidates.owning_intake(current.raw_transcript_id)
        readiness = (
            TranscriptIntakeReadiness.READY
            if owning == intake_identity
            else TranscriptIntakeReadiness.ERROR
        )
        return TranscriptIntakeReadinessReport(
            transcript_source_intake_id=intake_identity,
            readiness=readiness,
            candidate_count=candidate_count,
            current_selection_id=current.identity,
            current_raw_transcript_id=current.raw_transcript_id,
        )


__all__ = [
    "RAW_TRANSCRIPT_SELECTION_IDENTITY_PREFIX",
    "AtomicRawTranscriptSelectionPersistence",
    "CurrentRawTranscriptSelection",
    "CurrentRawTranscriptSelectionService",
    "RawTranscriptCandidate",
    "RawTranscriptCandidateQuery",
    "RawTranscriptSelectionError",
    "RawTranscriptSelectionQuery",
    "RawTranscriptSelectionResult",
    "SelectionOutcome",
    "TranscriptIntakeReadiness",
    "TranscriptIntakeReadinessReport",
    "TranscriptSourceIntakeQuery",
    "derive_selection_identity",
    "require_canonical_raw_transcript_id",
]
