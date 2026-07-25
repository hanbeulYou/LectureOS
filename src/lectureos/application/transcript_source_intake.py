"""Source Intake Application Foundation — Source Media transcription intake eligibility (040 §13).

The first application slice of 040 §4.1 Source Intake (PATCH-0020). It answers only one question: **can an
already-imported canonical Source Media record (045 §1) be admitted as an input to the Transcript Pipeline?**
It accepts a canonical `SourceMediaId` (never a filesystem path), resolves the persisted `source_media` record
read-only, and — when the reference resolves — records a durable, content-derived `TranscriptSourceIntake`
confirming eligibility.

Eligibility is a repository/application-contract decision evaluated from **persisted facts only**: a Source
Media is eligible iff its id resolves to a persisted `source_media` record. This slice performs **no** decoding,
probing, hashing, file access, or transcription, and it makes **no** claim about codecs, audio streams,
playability, duration, language, or transcription success. It does **not** check whether the original file still
physically exists (a moved/deleted reference-in-place original is a later-execution concern, not an eligibility
failure), and it produces no transcript content or execution result. The intake identity is derived
deterministically from the Source Media (`transcript-source-intake:<source_media_id>`), so admission is
idempotent and there is exactly one canonical intake per Source Media. The Source Media record is never mutated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from lectureos.execution.identities import SourceMediaId
from lectureos.persistence.errors import PersistenceIdentityCollisionError

from .identities import TranscriptSourceIntakeId

TRANSCRIPT_SOURCE_INTAKE_IDENTITY_PREFIX = "transcript-source-intake"

# A canonical Source Media identity is content-addressed as "<algorithm>:<hexdigest>" (e.g. sha256:<64 hex>).
_CANONICAL_SOURCE_MEDIA_ID = re.compile(r"^[a-z0-9]+:[0-9a-f]{64}$")


def require_canonical_source_media_id(value: str) -> SourceMediaId:
    """Return a `SourceMediaId` if the value is a well-formed content-addressed media identity, else reject."""

    if not isinstance(value, str) or not _CANONICAL_SOURCE_MEDIA_ID.fullmatch(value):
        raise TranscriptSourceIntakeError(
            "source media identity is malformed (expected '<algorithm>:<64 hex digest>')"
        )
    return SourceMediaId(value)


def derive_intake_identity(source_media_id: SourceMediaId) -> TranscriptSourceIntakeId:
    """Derive the content-addressed transcript intake identity from a Source Media identity."""

    return TranscriptSourceIntakeId(
        f"{TRANSCRIPT_SOURCE_INTAKE_IDENTITY_PREFIX}:{source_media_id.value}"
    )


@dataclass(frozen=True, slots=True)
class TranscriptSourceIntake:
    """Durable, immutable confirmation that a persisted Source Media is an admitted transcription input."""

    identity: TranscriptSourceIntakeId
    source_media_id: SourceMediaId

    def __post_init__(self) -> None:
        expected = derive_intake_identity(self.source_media_id)
        if self.identity != expected:
            raise ValueError(
                "transcript source intake identity must be derived from its Source Media identity"
            )


@dataclass(frozen=True, slots=True)
class TranscriptSourceIntakeResult:
    """The outcome of one admission: the intake record and whether it was newly created or reused."""

    intake: TranscriptSourceIntake
    created: bool


class SourceMediaQuery(Protocol):
    def get(self, identity): ...


class TranscriptSourceIntakeQuery(Protocol):
    def get(self, identity): ...


class AtomicTranscriptSourceIntakePersistence(Protocol):
    def persist_transcript_source_intake(
        self, *, intake: TranscriptSourceIntake
    ) -> None: ...


class TranscriptSourceIntakeError(ValueError):
    """A Source Media reference that cannot be admitted as a transcription input."""


class TranscriptSourceIntakeService:
    """Admits an existing persisted Source Media as an eligible transcription input, idempotently."""

    def __init__(
        self,
        source_media_query: SourceMediaQuery,
        intake_query: TranscriptSourceIntakeQuery,
        persistence: AtomicTranscriptSourceIntakePersistence | None = None,
    ) -> None:
        self._source_media = source_media_query
        self._intakes = intake_query
        self._persistence = persistence

    def admit(self, source_media_id: str) -> TranscriptSourceIntakeResult:
        # Reject a malformed identity before touching the repository.
        media_id = require_canonical_source_media_id(source_media_id)

        # Eligibility: the Source Media must resolve to a persisted record (persisted facts only; no filesystem).
        record = self._source_media.get(media_id)
        if record is None:
            raise TranscriptSourceIntakeError(
                "unknown source media: no imported Source Media record for this identity"
            )

        intake_identity = derive_intake_identity(media_id)
        existing = self._intakes.get(intake_identity)
        if existing is not None:
            # Idempotent: the same Source Media resolves the existing canonical intake.
            return TranscriptSourceIntakeResult(intake=existing, created=False)

        intake = TranscriptSourceIntake(identity=intake_identity, source_media_id=media_id)
        if self._persistence is None:
            raise RuntimeError("transcript source intake persistence is not configured")
        try:
            self._persistence.persist_transcript_source_intake(intake=intake)
        except PersistenceIdentityCollisionError:
            # A near-concurrent admission registered this Source Media first; converge on the existing intake.
            resolved = self._intakes.get(intake_identity)
            if resolved is None:
                raise
            return TranscriptSourceIntakeResult(intake=resolved, created=False)
        return TranscriptSourceIntakeResult(intake=intake, created=True)


__all__ = [
    "TRANSCRIPT_SOURCE_INTAKE_IDENTITY_PREFIX",
    "AtomicTranscriptSourceIntakePersistence",
    "SourceMediaQuery",
    "TranscriptSourceIntake",
    "TranscriptSourceIntakeError",
    "TranscriptSourceIntakeQuery",
    "TranscriptSourceIntakeResult",
    "TranscriptSourceIntakeService",
    "derive_intake_identity",
    "require_canonical_source_media_id",
]
