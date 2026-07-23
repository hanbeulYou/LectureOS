"""Insert-only SQLite persistence for durable canonical Lecture Segments (042 §7.1).

Serializes the immutable Lecture Segments admitted from one normalized segmentation result together with
their DomainResultReferences in a single atomic transaction. The records are a deterministic derivation from
a canonical Eligible Analysis Input; persisting them records only the Segments and starts no downstream
capability.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    EligibleAnalysisInputId,
    LectureSegmentId,
)
from lectureos.application.lecture_segment import (
    LECTURE_SEGMENT_RESULT_KIND,
    LectureSegment,
    PreparedLectureSegment,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 25


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Lecture Segment persistence requires SQLite schema version 25"
        )
    return version


class SQLiteLectureSegmentRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: LectureSegmentId) -> LectureSegment | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_input_id, source_media_id,
                       source_timeline_id, processing_run_id, unit_execution_id,
                       sequence, range_start, range_end
                FROM lecture_segments
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_segment(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Lecture Segment: {error}"
            ) from error


class SQLiteLectureSegmentCommandPersistence:
    """Owns one atomic v25 transaction persisting Lecture Segments and their Result references."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_lecture_segments(
        self, *, prepared: tuple[PreparedLectureSegment, ...]
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Lecture Segment persistence requires SQLite schema version 25"
            )
        if not prepared:
            raise PersistenceError("lecture segment persistence requires at least one segment")
        for record in prepared:
            _validate_segment_linkage(record)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            for record in prepared:
                if self._exists("lecture_segments", record.segment.identity.value):
                    raise PersistenceIdentityCollisionError(
                        "Lecture Segment identity already exists"
                    )
                if self._exists(
                    "domain_result_references", record.segment_result.identity.value
                ):
                    raise PersistenceIdentityCollisionError(
                        "lecture segment Domain Result identity already exists"
                    )
                _insert_segment(self._connection, record.segment)
                _insert_domain_result_reference_record(
                    self._connection, record.segment_result
                )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Lecture Segment: {error}"
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


def _validate_segment_linkage(record: PreparedLectureSegment) -> None:
    segment = record.segment
    result = record.segment_result
    if segment.domain_result_id != result.identity:
        raise PersistenceError("lecture segment Domain Result identity mismatch")
    if result.kind != LECTURE_SEGMENT_RESULT_KIND:
        raise PersistenceError("lecture segment Domain Result kind is invalid")
    if len(result.upstream_results) != 1:
        raise PersistenceError("lecture segment Domain Result upstream is invalid")


def _restore_segment(row: tuple[object, ...]) -> LectureSegment:
    return LectureSegment(
        identity=LectureSegmentId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_input_id=EligibleAnalysisInputId(row[2]),
        source_media_id=SourceMediaId(row[3]),
        source_timeline_id=SourceTimelineId(row[4]),
        run_id=ProcessingRunId(row[5]),
        unit_execution_id=UnitExecutionId(row[6]),
        sequence=row[7],
        range_start=row[8],
        range_end=row[9],
    )


def _insert_segment(connection: sqlite3.Connection, record: LectureSegment) -> None:
    connection.execute(
        """
        INSERT INTO lecture_segments(
            identity, domain_result_id, source_input_id, source_media_id,
            source_timeline_id, processing_run_id, unit_execution_id, sequence,
            range_start, range_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_input_id.value,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.range_start,
            record.range_end,
        ),
    )


__all__ = [
    "SQLiteLectureSegmentCommandPersistence",
    "SQLiteLectureSegmentRepository",
]
