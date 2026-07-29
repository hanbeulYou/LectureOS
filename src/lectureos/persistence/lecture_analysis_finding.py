"""Append-only SQLite persistence for effective-generation Analysis Findings (042 §8.2, GOAL-025).

Serializes one immutable canonical Analysis Finding per exact canonical content in a single
atomic transaction. Rows are never updated or deleted (042 §8.2 D-5/D-7); a different canonical
finding records a NEW row. Collisions map to the released identity-collision error so the
application layer converges idempotently (D-9).

The legacy execution-coupled Finding family (`analysis_findings`, `eligible_analysis_inputs`) is
never read or written here: PATCH-0030 D-11 keeps the two contract generations separate, and the
legacy relation could not hold this generation's rows without fabricating the anchor and execution
provenance that D-6 prohibits.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    LectureAnalysisFindingId,
    LectureAnalysisInputAdmissionId,
)

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.lecture_analysis_finding import LectureAnalysisFinding

_REQUIRED_VERSION = 48


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Lecture Analysis Finding persistence requires SQLite schema version 48"
        )
    return version


class SQLiteLectureAnalysisFindingRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: LectureAnalysisFindingId) -> "LectureAnalysisFinding | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Lecture Analysis Finding: {error}"
            ) from error

    def list_for_admission(
        self, admission_id: LectureAnalysisInputAdmissionId
    ) -> "tuple[LectureAnalysisFinding, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE admission_id = ? ORDER BY identity",
                (admission_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Lecture Analysis Findings: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteLectureAnalysisFindingCommandPersistence:
    """Owns one atomic v48 transaction appending an immutable canonical Analysis Finding."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_finding(self, *, finding: "LectureAnalysisFinding") -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Lecture Analysis Finding persistence requires SQLite schema version 48"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            exists = self._connection.execute(
                "SELECT 1 FROM lecture_analysis_findings WHERE identity = ?",
                (finding.identity.value,),
            ).fetchone()
            if exists is not None:
                raise PersistenceIdentityCollisionError(
                    "Lecture Analysis Finding identity already exists"
                )
            self._connection.execute(
                """
                INSERT INTO lecture_analysis_findings(
                    identity, admission_id, finding_type, evidence, confidence,
                    uncertainty, range_start, range_end, finding_contract_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding.identity.value,
                    finding.admission_id.value,
                    finding.finding_type,
                    finding.evidence,
                    finding.confidence,
                    finding.uncertainty,
                    finding.range_start,
                    finding.range_end,
                    finding.finding_contract_version,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Lecture Analysis Finding already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Lecture Analysis Finding: {error}"
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
    "SELECT identity, admission_id, finding_type, evidence, confidence, "
    "uncertainty, range_start, range_end, finding_contract_version "
    "FROM lecture_analysis_findings"
)


def _restore(row: tuple[object, ...]) -> "LectureAnalysisFinding":
    from lectureos.application.lecture_analysis_finding import LectureAnalysisFinding

    return LectureAnalysisFinding(
        identity=LectureAnalysisFindingId(row[0]),
        admission_id=LectureAnalysisInputAdmissionId(row[1]),
        finding_type=row[2],
        evidence=row[3],
        confidence=row[4],
        uncertainty=row[5],
        range_start=row[6],
        range_end=row[7],
        finding_contract_version=row[8],
    )


__all__ = [
    "SQLiteLectureAnalysisFindingCommandPersistence",
    "SQLiteLectureAnalysisFindingRepository",
]
