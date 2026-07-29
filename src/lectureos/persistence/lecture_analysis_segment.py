"""Append-only SQLite persistence for effective-generation Lecture Segments (042 §7.2, GOAL-026).

Serializes one ordered batch of immutable canonical Lecture Segments in a single atomic
transaction: either every pending segment of the command is recorded or none is (042 §7.2 S-9).
Rows are never updated or deleted; a different canonical segment records a NEW row. Collisions map
to the released identity-collision error so the application layer converges idempotently (S-11).

**No uniqueness constraint over (admission, sequence) exists, deliberately.** `§7.1` forbids
canonical-set/uniqueness constraints and does not force one canonical segmentation, so one
Admission may carry several independent batches whose positions legitimately overlap; only the
canonical identity is unique.

The legacy execution-coupled family (`lecture_segments`, `eligible_analysis_inputs`) is never read
or written here: PATCH-0031 S-12 keeps the two contract generations separate, and the legacy
relation could not hold this generation's rows without fabricating the anchor and execution
provenance that S-7 prohibits.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Sequence

from lectureos.application.identities import (
    LectureAnalysisInputAdmissionId,
    LectureAnalysisSegmentId,
)

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.lecture_analysis_segment import LectureAnalysisSegment

_REQUIRED_VERSION = 49


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Lecture Analysis Segment persistence requires SQLite schema version 49"
        )
    return version


class SQLiteLectureAnalysisSegmentRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: LectureAnalysisSegmentId) -> "LectureAnalysisSegment | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Lecture Analysis Segment: {error}"
            ) from error

    def list_for_admission(
        self, admission_id: LectureAnalysisInputAdmissionId
    ) -> "tuple[LectureAnalysisSegment, ...]":
        """Deterministic order: sequence first, then identity.

        The identity tie-break is required, not cosmetic: several independent batches may share a
        sequence value under one Admission (no uniqueness constraint exists), so sequence alone
        would not be a total order.
        """

        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE admission_id = ? ORDER BY sequence, identity",
                (admission_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Lecture Analysis Segments: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteLectureAnalysisSegmentCommandPersistence:
    """Owns one atomic v49 transaction appending an ordered batch of canonical Lecture Segments."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_segments(self, *, segments: "Sequence[LectureAnalysisSegment]") -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Lecture Analysis Segment persistence requires SQLite schema version 49"
            )
        if not segments:
            raise PersistenceError(
                "a lecture segmentation admission requires at least one segment"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            for segment in segments:
                exists = self._connection.execute(
                    "SELECT 1 FROM lecture_analysis_segments WHERE identity = ?",
                    (segment.identity.value,),
                ).fetchone()
                if exists is not None:
                    raise PersistenceIdentityCollisionError(
                        "Lecture Analysis Segment identity already exists"
                    )
            self._connection.executemany(
                """
                INSERT INTO lecture_analysis_segments(
                    identity, admission_id, sequence, range_start, range_end,
                    segment_contract_version
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        segment.identity.value,
                        segment.admission_id.value,
                        segment.sequence,
                        segment.range_start,
                        segment.range_end,
                        segment.segment_contract_version,
                    )
                    for segment in segments
                ],
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Lecture Analysis Segment already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Lecture Analysis Segments: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


_SELECT_COLUMNS = (
    "SELECT identity, admission_id, sequence, range_start, range_end, "
    "segment_contract_version "
    "FROM lecture_analysis_segments"
)


def _restore(row: tuple[object, ...]) -> "LectureAnalysisSegment":
    from lectureos.application.lecture_analysis_segment import LectureAnalysisSegment

    return LectureAnalysisSegment(
        identity=LectureAnalysisSegmentId(row[0]),
        admission_id=LectureAnalysisInputAdmissionId(row[1]),
        sequence=row[2],
        range_start=row[3],
        range_end=row[4],
        segment_contract_version=row[5],
    )


__all__ = [
    "SQLiteLectureAnalysisSegmentCommandPersistence",
    "SQLiteLectureAnalysisSegmentRepository",
]
