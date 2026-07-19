"""SQLite repository for Transcript-owned provider provenance records."""

from __future__ import annotations

import sqlite3

from lectureos.execution.identities import (
    CapabilityReference,
    DiagnosticId,
    PluginReference,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.transcript.identities import ProviderTranscriptResultId
from lectureos.transcript.models import ProviderTranscriptResult

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection


class SQLiteProviderTranscriptResultRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        if validate_sqlite_connection(connection) < 5:
            raise SchemaFeatureUnavailableError(
                "ProviderTranscriptResult persistence requires SQLite schema version 5"
            )
        self._connection = connection

    def get(
        self, identity: ProviderTranscriptResultId
    ) -> ProviderTranscriptResult | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, source_media_id, source_timeline_id,
                       processing_run_id, unit_execution_id, capability,
                       provider_reference, original_content, plugin_reference,
                       uncertainty, normalized
                FROM provider_transcript_results
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return self._restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read ProviderTranscriptResult: {error}"
            ) from error

    def save(self, record: ProviderTranscriptResult) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                "ProviderTranscriptResult identity already exists"
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _insert_provider_transcript_result(self._connection, record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "ProviderTranscriptResult identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist ProviderTranscriptResult: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(
                f"could not persist ProviderTranscriptResult: {error}"
            ) from error
        except Exception:
            self._rollback()
            raise

    def _restore(self, row: tuple[object, ...]) -> ProviderTranscriptResult:
        identity = ProviderTranscriptResultId(row[0])
        return ProviderTranscriptResult(
            identity=identity,
            source_media_id=SourceMediaId(row[1]),
            source_timeline_id=SourceTimelineId(row[2]),
            run_id=ProcessingRunId(row[3]),
            unit_execution_id=UnitExecutionId(row[4]),
            capability=CapabilityReference(row[5]),
            provider_reference=row[6],
            original_content=row[7],
            plugin_reference=(
                PluginReference(row[8]) if row[8] is not None else None
            ),
            diagnostic_references=tuple(
                DiagnosticId(value) for value in self._diagnostic_values(identity)
            ),
            uncertainty=row[9],
            normalized=_restore_normalized(row[10]),
        )

    def _diagnostic_values(
        self, identity: ProviderTranscriptResultId
    ) -> tuple[str, ...]:
        rows = self._connection.execute(
            """
            SELECT ordinal, diagnostic_id
            FROM provider_transcript_result_diagnostics
            WHERE provider_transcript_result_id = ?
            ORDER BY ordinal
            """,
            (identity.value,),
        ).fetchall()
        if tuple(row[0] for row in rows) != tuple(range(len(rows))):
            raise PersistenceError(
                "ProviderTranscriptResult diagnostic ordering is corrupt"
            )
        return tuple(row[1] for row in rows)

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _insert_provider_transcript_result(
    connection: sqlite3.Connection, record: ProviderTranscriptResult
) -> None:
    """Insert one complete provider provenance record without a transaction."""

    connection.execute(
        """
        INSERT INTO provider_transcript_results(
            identity, source_media_id, source_timeline_id, processing_run_id,
            unit_execution_id, capability, provider_reference, original_content,
            plugin_reference, uncertainty, normalized
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.capability.value,
            record.provider_reference,
            record.original_content,
            record.plugin_reference.value if record.plugin_reference else None,
            record.uncertainty,
            1 if record.normalized else 0,
        ),
    )
    _insert_provider_diagnostics(connection, record)


def _insert_provider_diagnostics(
    connection: sqlite3.Connection, record: ProviderTranscriptResult
) -> None:
    connection.executemany(
        """
        INSERT INTO provider_transcript_result_diagnostics(
            provider_transcript_result_id, ordinal, diagnostic_id
        ) VALUES (?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, diagnostic.value)
            for ordinal, diagnostic in enumerate(record.diagnostic_references)
        ),
    )


def _restore_normalized(value: object) -> bool:
    if value == 0:
        return False
    raise PersistenceError("ProviderTranscriptResult normalized value is unknown")
