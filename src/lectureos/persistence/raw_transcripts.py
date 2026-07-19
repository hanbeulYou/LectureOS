"""Insert-only SQLite repository for canonical RawTranscript records."""

from __future__ import annotations

import sqlite3

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import RawTranscript

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection


class SQLiteRawTranscriptRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        if validate_sqlite_connection(connection) < 5:
            raise SchemaFeatureUnavailableError(
                "RawTranscript persistence requires SQLite schema version 5"
            )
        self._connection = connection

    def get(self, identity: TranscriptId) -> RawTranscript | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_media_id,
                       source_timeline_id, provider_transcript_result_id,
                       processing_run_id, unit_execution_id, validation_id
                FROM raw_transcripts
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return self._restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(f"could not read RawTranscript: {error}") from error

    def save(self, record: RawTranscript) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                "RawTranscript identity already exists"
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _insert_raw_transcript(self._connection, record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "RawTranscript identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist RawTranscript: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(
                f"could not persist RawTranscript: {error}"
            ) from error
        except Exception:
            self._rollback()
            raise

    def _restore(self, row: tuple[object, ...]) -> RawTranscript:
        identity = TranscriptId(row[0])
        return RawTranscript(
            identity=identity,
            domain_result_id=DomainResultId(row[1]),
            source_media_id=SourceMediaId(row[2]),
            source_timeline_id=SourceTimelineId(row[3]),
            provider_result_id=ProviderTranscriptResultId(row[4]),
            run_id=ProcessingRunId(row[5]),
            unit_execution_id=UnitExecutionId(row[6]),
            segment_ids=tuple(
                TranscriptSegmentId(value) for value in self._segment_values(identity)
            ),
            validation_id=(
                TranscriptValidationId(row[7]) if row[7] is not None else None
            ),
        )

    def _segment_values(self, identity: TranscriptId) -> tuple[str, ...]:
        rows = self._connection.execute(
            """
            SELECT ordinal, transcript_segment_id
            FROM raw_transcript_segments
            WHERE raw_transcript_id = ?
            ORDER BY ordinal
            """,
            (identity.value,),
        ).fetchall()
        if tuple(row[0] for row in rows) != tuple(range(len(rows))):
            raise PersistenceError("RawTranscript segment ordering is corrupt")
        return tuple(row[1] for row in rows)

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _insert_raw_transcript(
    connection: sqlite3.Connection, record: RawTranscript
) -> None:
    """Insert one complete RawTranscript without owning a transaction."""

    connection.execute(
        """
        INSERT INTO raw_transcripts(
            identity, domain_result_id, source_media_id, source_timeline_id,
            provider_transcript_result_id, processing_run_id,
            unit_execution_id, validation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.provider_result_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.validation_id.value if record.validation_id else None,
        ),
    )
    connection.executemany(
        """
        INSERT INTO raw_transcript_segments(
            raw_transcript_id, ordinal, transcript_segment_id
        ) VALUES (?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, segment.value)
            for ordinal, segment in enumerate(record.segment_ids)
        ),
    )
