"""Insert-only SQLite persistence for canonical SRT Artifact Records (044 §Export, stage 2).

Serializes one immutable SRT Artifact Record — with its deterministic payload stored inline so it remains
durably recoverable after restart — together with its DomainResultReference in a single atomic transaction.
The artifact is the only newly created canonical record; no existing artifact is modified, and no physical
file, path, URL, storage location or delivery state is involved.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import SubtitleApprovedDocumentId
from lectureos.application.subtitle_srt_artifact import (
    SUBTITLE_SRT_ARTIFACT_RESULT_KIND,
    SubtitleArtifactFormat,
    SubtitleSrtArtifact,
)
from lectureos.execution.identities import (
    ArtifactId,
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 21


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Subtitle SRT Artifact persistence requires SQLite schema version 21"
        )
    return version


class SQLiteSubtitleSrtArtifactRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: ArtifactId) -> SubtitleSrtArtifact | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_approved_document_id, format,
                       payload, byte_length, cue_count, encoding, source_media_id,
                       source_timeline_id, processing_run_id, unit_execution_id, sequence,
                       reason, previous_artifact_id
                FROM subtitle_srt_artifacts
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_artifact(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle SRT Artifact: {error}"
            ) from error


class SQLiteSubtitleSrtArtifactCommandPersistence:
    """Owns one atomic v21 transaction persisting an SRT artifact and its Result reference."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_subtitle_srt_artifact(
        self,
        *,
        artifact: SubtitleSrtArtifact,
        artifact_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Subtitle SRT Artifact persistence requires SQLite schema version 21"
            )
        _validate_artifact_linkage(artifact, artifact_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("subtitle_srt_artifacts", artifact.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Subtitle SRT Artifact identity already exists"
                )
            if self._exists("domain_result_references", artifact_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "subtitle srt artifact Domain Result identity already exists"
                )
            _insert_artifact(self._connection, artifact)
            _insert_domain_result_reference_record(self._connection, artifact_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Subtitle SRT Artifact: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, table: str, identity_value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM {table} WHERE identity = ?",
                (identity_value,),
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _validate_artifact_linkage(
    artifact: SubtitleSrtArtifact,
    artifact_result: DomainResultReference,
) -> None:
    if artifact.domain_result_id != artifact_result.identity:
        raise PersistenceError("subtitle srt artifact Domain Result identity mismatch")
    if artifact_result.kind != SUBTITLE_SRT_ARTIFACT_RESULT_KIND:
        raise PersistenceError("subtitle srt artifact Domain Result kind is invalid")
    if len(artifact_result.upstream_results) != 1:
        raise PersistenceError("subtitle srt artifact Domain Result upstream is invalid")


def _restore_artifact(row: tuple[object, ...]) -> SubtitleSrtArtifact:
    return SubtitleSrtArtifact(
        identity=ArtifactId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_approved_document_id=SubtitleApprovedDocumentId(row[2]),
        format=SubtitleArtifactFormat(row[3]),
        payload=row[4],
        byte_length=row[5],
        cue_count=row[6],
        encoding=row[7],
        source_media_id=SourceMediaId(row[8]),
        source_timeline_id=SourceTimelineId(row[9]),
        run_id=ProcessingRunId(row[10]),
        unit_execution_id=UnitExecutionId(row[11]),
        sequence=row[12],
        reason=row[13],
        previous_artifact_id=(ArtifactId(row[14]) if row[14] is not None else None),
    )


def _insert_artifact(
    connection: sqlite3.Connection, record: SubtitleSrtArtifact
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_srt_artifacts(
            identity, domain_result_id, source_approved_document_id, format, payload,
            byte_length, cue_count, encoding, source_media_id, source_timeline_id,
            processing_run_id, unit_execution_id, sequence, reason, previous_artifact_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_approved_document_id.value,
            record.format.value,
            record.payload,
            record.byte_length,
            record.cue_count,
            record.encoding,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.reason,
            record.previous_artifact_id.value if record.previous_artifact_id else None,
        ),
    )


__all__ = [
    "SQLiteSubtitleSrtArtifactCommandPersistence",
    "SQLiteSubtitleSrtArtifactRepository",
]
