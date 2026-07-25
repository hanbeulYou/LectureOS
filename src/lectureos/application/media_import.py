"""Media Import Application Foundation — local Source Media registration (045 §1).

The first Media Import milestone (045_MEDIA_IMPORT_PIPELINE.md §1, PATCH-0019). From one caller-selected local
file, inspected read-only, it registers a canonical, durable :class:`SourceMediaRecord`: the first owner of
``SourceMediaId``. Media identity is **content-addressed** — derived from a streaming SHA-256 fingerprint of the
file bytes (``sha256:<hexdigest>``) — so it is independent of path, filename, and extension; identical content
always yields the same identity. The original file is referenced in place; the record stores the content
fingerprint, byte length, and the resolved observed source path as immutable import provenance.

Import is idempotent: re-importing identical content resolves and returns the existing record (never a duplicate
Media record); the same content under a different path converges on the same identity; changed content at the
same path is a different identity and a new record. LectureOS is not authoritative for the file's continued
physical availability. The record asserts no decodability, playability, duration, or transcription and never
mutates the source bytes. Failures (ineligible source, hashing failure, persistence failure) leave no partial
persisted state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from lectureos.execution.identities import SourceMediaId
from lectureos.persistence.errors import PersistenceIdentityCollisionError

SHA256_ALGORITHM = "sha256"
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def derive_media_identity(algorithm: str, digest: str) -> SourceMediaId:
    """Derive the content-addressed Source Media identity from a fingerprint (``<algorithm>:<digest>``)."""

    return SourceMediaId(f"{algorithm}:{digest}")


def _validate_fingerprint(algorithm: str, digest: str, byte_length: int, path: str) -> None:
    if algorithm != SHA256_ALGORITHM:
        raise ValueError("source media fingerprint algorithm must be sha256")
    if not isinstance(digest, str) or not _SHA256_HEX.fullmatch(digest):
        raise ValueError("source media fingerprint digest must be 64 lowercase hex characters")
    if not isinstance(byte_length, int) or isinstance(byte_length, bool) or byte_length <= 0:
        raise ValueError("source media byte length must be a positive integer")
    if not path.strip():
        raise ValueError("source media observed source path must not be empty")


@dataclass(frozen=True, slots=True)
class SourceMediaFingerprint:
    """The stable filesystem facts observed for one local source file (not yet a persisted record)."""

    algorithm: str
    digest: str
    byte_length: int
    observed_source_path: str

    def __post_init__(self) -> None:
        _validate_fingerprint(
            self.algorithm, self.digest, self.byte_length, self.observed_source_path
        )


@dataclass(frozen=True, slots=True)
class SourceMediaRecord:
    """Canonical, immutable, insert-only Source Media record — the first owner of a content identity."""

    identity: SourceMediaId
    fingerprint_algorithm: str
    fingerprint_digest: str
    byte_length: int
    observed_source_path: str

    def __post_init__(self) -> None:
        _validate_fingerprint(
            self.fingerprint_algorithm,
            self.fingerprint_digest,
            self.byte_length,
            self.observed_source_path,
        )
        # Identity is content-derived; enforce the derivation so a record can never disagree with its content.
        expected = derive_media_identity(self.fingerprint_algorithm, self.fingerprint_digest)
        if self.identity != expected:
            raise ValueError("source media identity must be derived from its content fingerprint")


@dataclass(frozen=True, slots=True)
class MediaImportResult:
    """The outcome of one import: the canonical record and whether it was newly created or reused."""

    record: SourceMediaRecord
    created: bool


class SourceMediaInspector(Protocol):
    def inspect(self, source_path: str) -> SourceMediaFingerprint: ...


class SourceMediaQuery(Protocol):
    def get(self, identity): ...


class AtomicSourceMediaPersistence(Protocol):
    def persist_source_media(self, *, record: SourceMediaRecord) -> None: ...


class MediaImportError(ValueError):
    """A source that cannot be imported as canonical Source Media (ineligible or unreadable)."""


class MediaImportService:
    """Registers one local file as a canonical Source Media record, idempotently by content."""

    def __init__(
        self,
        inspector: SourceMediaInspector,
        repository: SourceMediaQuery,
        persistence: AtomicSourceMediaPersistence | None = None,
    ) -> None:
        self._inspector = inspector
        self._repository = repository
        self._persistence = persistence

    def import_media(self, source_path: str) -> MediaImportResult:
        # Inspect the local source read-only; ineligible/unreadable sources raise MediaImportError.
        fingerprint = self._inspector.inspect(source_path)
        identity = derive_media_identity(fingerprint.algorithm, fingerprint.digest)

        existing = self._repository.get(identity)
        if existing is not None:
            # Idempotent: identical content (any path/filename) resolves the existing canonical record.
            return MediaImportResult(record=existing, created=False)

        record = SourceMediaRecord(
            identity=identity,
            fingerprint_algorithm=fingerprint.algorithm,
            fingerprint_digest=fingerprint.digest,
            byte_length=fingerprint.byte_length,
            observed_source_path=fingerprint.observed_source_path,
        )
        if self._persistence is None:
            raise RuntimeError("media import persistence is not configured")
        try:
            self._persistence.persist_source_media(record=record)
        except PersistenceIdentityCollisionError:
            # A near-concurrent import registered the same content first; converge on the existing record.
            resolved = self._repository.get(identity)
            if resolved is None:
                raise
            return MediaImportResult(record=resolved, created=False)
        return MediaImportResult(record=record, created=True)


__all__ = [
    "SHA256_ALGORITHM",
    "AtomicSourceMediaPersistence",
    "MediaImportError",
    "MediaImportResult",
    "MediaImportService",
    "SourceMediaFingerprint",
    "SourceMediaInspector",
    "SourceMediaQuery",
    "SourceMediaRecord",
    "derive_media_identity",
]
