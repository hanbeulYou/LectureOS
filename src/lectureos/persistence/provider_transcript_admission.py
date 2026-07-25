"""Atomic SQLite persistence for the External ASR Boundary admission (040 §14, PATCH-0021).

Serializes one External ASR Boundary admission in a single transaction: the preserved
`ProviderTranscriptResult` evidence, its canonical `TranscriptSegment`s, exactly one canonical `RawTranscript`
(with its ordered segment membership), the raw transcript's `DomainResultReference`, and the durable
`provider_transcript_admissions` binding row (intake → provider result → raw transcript). It reuses the existing
transaction-free insert helpers so the provider result, segments, raw transcript, and domain result are written
with the same shape as the internal Transcript composition. Any collision or error rolls back with no partial
state; an admitted result is never silently overwritten.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    ProviderTranscriptAdmissionId,
    TranscriptSourceIntakeId,
)
from lectureos.execution.identities import SourceMediaId
from lectureos.execution.models import DomainResultReference
from lectureos.transcript.identities import ProviderTranscriptResultId, TranscriptId
from lectureos.transcript.models import (
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .provider_transcripts import _insert_provider_transcript_result
from .raw_transcripts import _insert_raw_transcript
from .sqlite import validate_sqlite_connection
from .transcript_segments import _insert_transcript_segment

if TYPE_CHECKING:
    from lectureos.application.provider_transcript_admission import (
        ProviderTranscriptAdmission,
    )

_REQUIRED_VERSION = 32


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Provider Transcript Admission persistence requires SQLite schema version 32"
        )
    return version


class SQLiteProviderTranscriptAdmissionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: ProviderTranscriptAdmissionId
    ) -> "ProviderTranscriptAdmission | None":
        try:
            row = self._connection.execute(
                """
                SELECT identity, transcript_source_intake_id, source_media_id,
                       provider_transcript_result_id, raw_transcript_id,
                       provider_reference, provider_model, declared_language,
                       provider_result_ref, segment_count, content_fingerprint
                FROM provider_transcript_admissions
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Provider Transcript Admission: {error}"
            ) from error


class SQLiteProviderTranscriptAdmissionCommandPersistence:
    """Owns one atomic v32 transaction persisting a complete External ASR Boundary admission."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_provider_transcript_admission(
        self,
        *,
        admission: "ProviderTranscriptAdmission",
        provider_result: ProviderTranscriptResult,
        segments: tuple[TranscriptSegment, ...],
        raw_transcript: RawTranscript,
        result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Provider Transcript Admission persistence requires SQLite schema version 32"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            _validate_linkage(admission, provider_result, segments, raw_transcript, result)
            if self._exists("identity", admission.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Provider Transcript Admission identity already exists"
                )
            if (
                self._exists(
                    "provider_transcript_result_id",
                    admission.provider_transcript_result_id.value,
                )
                or self._exists("raw_transcript_id", admission.raw_transcript_id.value)
                or self._raw_transcript_exists(raw_transcript.identity)
                or self._provider_result_exists(provider_result.identity)
            ):
                raise PersistenceIdentityCollisionError(
                    "Provider Transcript Admission canonical records already exist"
                )
            _insert_provider_transcript_result(self._connection, provider_result)
            for segment in segments:
                _insert_transcript_segment(self._connection, segment)
            _insert_raw_transcript(self._connection, raw_transcript)
            _insert_domain_result_reference_record(self._connection, result)
            self._connection.execute(
                """
                INSERT INTO provider_transcript_admissions(
                    identity, transcript_source_intake_id, source_media_id,
                    provider_transcript_result_id, raw_transcript_id,
                    provider_reference, provider_model, declared_language,
                    provider_result_ref, segment_count, content_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    admission.identity.value,
                    admission.transcript_source_intake_id.value,
                    admission.source_media_id.value,
                    admission.provider_transcript_result_id.value,
                    admission.raw_transcript_id.value,
                    admission.provider_reference,
                    admission.provider_model,
                    admission.declared_language,
                    admission.provider_result_ref,
                    admission.segment_count,
                    admission.content_fingerprint,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Provider Transcript Admission already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Provider Transcript Admission: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, column: str, value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM provider_transcript_admissions WHERE {column} = ?",
                (value,),
            ).fetchone()
            is not None
        )

    def _raw_transcript_exists(self, identity: TranscriptId) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM raw_transcripts WHERE identity = ?", (identity.value,)
            ).fetchone()
            is not None
        )

    def _provider_result_exists(self, identity: ProviderTranscriptResultId) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM provider_transcript_results WHERE identity = ?",
                (identity.value,),
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _validate_linkage(
    admission: "ProviderTranscriptAdmission",
    provider_result: ProviderTranscriptResult,
    segments: tuple[TranscriptSegment, ...],
    raw_transcript: RawTranscript,
    result: DomainResultReference,
) -> None:
    if admission.provider_transcript_result_id != provider_result.identity:
        raise PersistenceError("admission provider result identity must match the provider result")
    if admission.raw_transcript_id != raw_transcript.identity:
        raise PersistenceError("admission raw transcript identity must match the raw transcript")
    if admission.source_media_id != raw_transcript.source_media_id:
        raise PersistenceError("admission source media must match the raw transcript")
    if raw_transcript.provider_result_id != provider_result.identity:
        raise PersistenceError("raw transcript must reference the admitted provider result")
    if raw_transcript.source_media_id != provider_result.source_media_id:
        raise PersistenceError("raw transcript source media must match the provider result")
    if raw_transcript.source_timeline_id != provider_result.source_timeline_id:
        raise PersistenceError("raw transcript source timeline must match the provider result")
    if raw_transcript.segment_ids != tuple(segment.identity for segment in segments):
        raise PersistenceError("raw transcript segment references must match supplied segments")
    if admission.segment_count != len(segments):
        raise PersistenceError("admission segment count must match supplied segments")
    if result.identity != raw_transcript.domain_result_id:
        raise PersistenceError("domain result identity must match the raw transcript")
    if result.kind != "raw_transcript":
        raise PersistenceError("domain result kind must be raw_transcript")


def _restore(row: tuple[object, ...]) -> "ProviderTranscriptAdmission":
    from lectureos.application.provider_transcript_admission import (
        ProviderTranscriptAdmission,
    )

    return ProviderTranscriptAdmission(
        identity=ProviderTranscriptAdmissionId(row[0]),
        transcript_source_intake_id=TranscriptSourceIntakeId(row[1]),
        source_media_id=SourceMediaId(row[2]),
        provider_transcript_result_id=ProviderTranscriptResultId(row[3]),
        raw_transcript_id=TranscriptId(row[4]),
        provider_reference=row[5],
        provider_model=row[6],
        declared_language=row[7],
        provider_result_ref=row[8],
        segment_count=row[9],
        content_fingerprint=row[10],
    )


__all__ = [
    "SQLiteProviderTranscriptAdmissionCommandPersistence",
    "SQLiteProviderTranscriptAdmissionRepository",
]
