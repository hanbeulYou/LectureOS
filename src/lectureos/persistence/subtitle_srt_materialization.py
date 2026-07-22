"""Insert-only SQLite persistence for SRT Physical Materialization records (044 §17).

The materialization act is two immutable, insert-only records. The **Materialization** (intent) is
co-persisted with its DomainResultReference in one atomic transaction (the record-first PENDING commit);
the **Materialization Outcome** (terminal MATERIALIZED | FAILED) is persisted in a separate atomic
transaction after the file write. Materialization State is derived: no outcome row ⇒ PENDING. No existing
record is modified, and no filesystem access happens here.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import SubtitleSrtMaterializationId
from lectureos.application.subtitle_srt_materialization import (
    SUBTITLE_SRT_MATERIALIZATION_RESULT_KIND,
    SubtitleMaterializationState,
    SubtitleMaterializationStorageKind,
    SubtitleSrtMaterialization,
    SubtitleSrtMaterializationOutcome,
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

_REQUIRED_VERSION = 22


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Subtitle SRT Materialization persistence requires SQLite schema version 22"
        )
    return version


class SQLiteSubtitleSrtMaterializationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: SubtitleSrtMaterializationId
    ) -> SubtitleSrtMaterialization | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_artifact_id, storage_kind,
                       relative_location, source_media_id, source_timeline_id,
                       processing_run_id, unit_execution_id, sequence, reason,
                       previous_materialization_id
                FROM subtitle_srt_materializations
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_materialization(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle SRT Materialization: {error}"
            ) from error

    def get_outcome(
        self, identity: SubtitleSrtMaterializationId
    ) -> SubtitleSrtMaterializationOutcome | None:
        try:
            row = self._connection.execute(
                """
                SELECT subtitle_srt_materialization_id, state, byte_length, failure_reason
                FROM subtitle_srt_materialization_outcomes
                WHERE subtitle_srt_materialization_id = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_outcome(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle SRT Materialization Outcome: {error}"
            ) from error


class SQLiteSubtitleSrtMaterializationCommandPersistence:
    """Owns the two atomic v22 transactions: intent (with Result), then terminal outcome."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_materialization_intent(
        self,
        *,
        materialization: SubtitleSrtMaterialization,
        materialization_result: DomainResultReference,
    ) -> None:
        self._require_version()
        _validate_intent_linkage(materialization, materialization_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(
                "subtitle_srt_materializations", materialization.identity.value
            ):
                raise PersistenceIdentityCollisionError(
                    "Subtitle SRT Materialization identity already exists"
                )
            if self._exists(
                "domain_result_references", materialization_result.identity.value
            ):
                raise PersistenceIdentityCollisionError(
                    "subtitle srt materialization Domain Result identity already exists"
                )
            _insert_materialization(self._connection, materialization)
            _insert_domain_result_reference_record(
                self._connection, materialization_result
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Subtitle SRT Materialization: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def persist_materialization_outcome(
        self, *, outcome: SubtitleSrtMaterializationOutcome
    ) -> None:
        self._require_version()
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if not self._exists(
                "subtitle_srt_materializations", outcome.materialization_id.value
            ):
                raise PersistenceError(
                    "outcome must reference an existing materialization"
                )
            if self._exists(
                "subtitle_srt_materialization_outcomes",
                outcome.materialization_id.value,
                column="subtitle_srt_materialization_id",
            ):
                raise PersistenceIdentityCollisionError(
                    "Subtitle SRT Materialization Outcome already exists"
                )
            _insert_outcome(self._connection, outcome)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Subtitle SRT Materialization Outcome: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _require_version(self) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Subtitle SRT Materialization persistence requires SQLite schema version 22"
            )

    def _exists(self, table: str, identity_value: str, *, column: str = "identity") -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM {table} WHERE {column} = ?",
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


def _validate_intent_linkage(
    materialization: SubtitleSrtMaterialization,
    materialization_result: DomainResultReference,
) -> None:
    if materialization.domain_result_id != materialization_result.identity:
        raise PersistenceError("subtitle srt materialization Domain Result identity mismatch")
    if materialization_result.kind != SUBTITLE_SRT_MATERIALIZATION_RESULT_KIND:
        raise PersistenceError("subtitle srt materialization Domain Result kind is invalid")
    if len(materialization_result.upstream_results) != 1:
        raise PersistenceError("subtitle srt materialization Domain Result upstream is invalid")


def _restore_materialization(row: tuple[object, ...]) -> SubtitleSrtMaterialization:
    return SubtitleSrtMaterialization(
        identity=SubtitleSrtMaterializationId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_artifact_id=ArtifactId(row[2]),
        storage_kind=SubtitleMaterializationStorageKind(row[3]),
        relative_location=row[4],
        source_media_id=SourceMediaId(row[5]),
        source_timeline_id=SourceTimelineId(row[6]),
        run_id=ProcessingRunId(row[7]),
        unit_execution_id=UnitExecutionId(row[8]),
        sequence=row[9],
        reason=row[10],
        previous_materialization_id=(
            SubtitleSrtMaterializationId(row[11]) if row[11] is not None else None
        ),
    )


def _restore_outcome(row: tuple[object, ...]) -> SubtitleSrtMaterializationOutcome:
    return SubtitleSrtMaterializationOutcome(
        materialization_id=SubtitleSrtMaterializationId(row[0]),
        state=SubtitleMaterializationState(row[1]),
        byte_length=row[2],
        failure_reason=row[3],
    )


def _insert_materialization(
    connection: sqlite3.Connection, record: SubtitleSrtMaterialization
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_srt_materializations(
            identity, domain_result_id, source_artifact_id, storage_kind, relative_location,
            source_media_id, source_timeline_id, processing_run_id, unit_execution_id,
            sequence, reason, previous_materialization_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_artifact_id.value,
            record.storage_kind.value,
            record.relative_location,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.reason,
            record.previous_materialization_id.value
            if record.previous_materialization_id
            else None,
        ),
    )


def _insert_outcome(
    connection: sqlite3.Connection, record: SubtitleSrtMaterializationOutcome
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_srt_materialization_outcomes(
            subtitle_srt_materialization_id, state, byte_length, failure_reason
        ) VALUES (?, ?, ?, ?)
        """,
        (
            record.materialization_id.value,
            record.state.value,
            record.byte_length,
            record.failure_reason,
        ),
    )


__all__ = [
    "SQLiteSubtitleSrtMaterializationCommandPersistence",
    "SQLiteSubtitleSrtMaterializationRepository",
]
