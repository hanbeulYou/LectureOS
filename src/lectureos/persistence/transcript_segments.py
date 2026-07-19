"""Insert-only SQLite repository for canonical TranscriptSegment records."""

from __future__ import annotations

import sqlite3

from lectureos.execution.identities import SourceTimelineId
from lectureos.transcript.identities import TranscriptId, TranscriptSegmentId
from lectureos.transcript.models import TranscriptSegment

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection


class SQLiteTranscriptSegmentRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        if validate_sqlite_connection(connection) < 5:
            raise SchemaFeatureUnavailableError(
                "TranscriptSegment persistence requires SQLite schema version 5"
            )
        self._connection = connection

    def get(self, identity: TranscriptSegmentId) -> TranscriptSegment | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, transcript_id, source_timeline_id, text,
                       source_order, start, end, speaker_label, confidence,
                       uncertainty, replaces_segment_id
                FROM transcript_segments
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_transcript_segment(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read TranscriptSegment: {error}"
            ) from error

    def save(self, record: TranscriptSegment) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                "TranscriptSegment identity already exists"
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _insert_transcript_segment(self._connection, record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "TranscriptSegment identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist TranscriptSegment: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(
                f"could not persist TranscriptSegment: {error}"
            ) from error
        except Exception:
            self._rollback()
            raise

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _insert_transcript_segment(
    connection: sqlite3.Connection, record: TranscriptSegment
) -> None:
    """Insert one Segment without owning a transaction."""

    connection.execute(
        """
        INSERT INTO transcript_segments(
            identity, transcript_id, source_timeline_id, text, source_order,
            start, end, speaker_label, confidence, uncertainty,
            replaces_segment_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.transcript_id.value,
            record.source_timeline_id.value if record.source_timeline_id else None,
            record.text,
            record.source_order,
            record.start,
            record.end,
            record.speaker_label,
            record.confidence,
            record.uncertainty,
            record.replaces_segment_id.value if record.replaces_segment_id else None,
        ),
    )


def _restore_transcript_segment(row: tuple[object, ...]) -> TranscriptSegment:
    return TranscriptSegment(
        identity=TranscriptSegmentId(row[0]),
        transcript_id=TranscriptId(row[1]),
        source_timeline_id=(
            SourceTimelineId(row[2]) if row[2] is not None else None
        ),
        text=row[3],
        source_order=row[4],
        start=row[5],
        end=row[6],
        speaker_label=row[7],
        confidence=row[8],
        uncertainty=row[9],
        replaces_segment_id=(
            TranscriptSegmentId(row[10]) if row[10] is not None else None
        ),
    )
