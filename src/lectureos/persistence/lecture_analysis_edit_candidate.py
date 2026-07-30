"""Append-only SQLite persistence for effective-generation Edit Candidates (042 §9.3, GOAL-027).

Serializes one immutable canonical Edit Candidate per exact canonical content in a single atomic
transaction. Rows are never updated or deleted (042 §9.3 C-5/C-6); a different canonical candidate
records a NEW row. Collisions map to the released identity-collision error so the application layer
converges idempotently (C-11).

No ordinal column exists: `§9.2` fixes candidate order as transport order carrying no product
meaning, and O-1 declines the ordered-batch idiom `§9.3` C-11 left optional.

The legacy execution-coupled Candidate family (`edit_candidates`) is never read or written here:
PATCH-0032 C-12 keeps the two contract generations separate, and the legacy relation could not hold
this generation's rows without fabricating the legacy Finding anchor, `processing_run_id`,
`unit_execution_id`, and `domain_result_id` that C-7 prohibits.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    LectureAnalysisEditCandidateId,
    LectureAnalysisFindingId,
)

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.lecture_analysis_edit_candidate import (
        LectureAnalysisEditCandidate,
    )

_REQUIRED_VERSION = 50


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Lecture Analysis Edit Candidate persistence requires SQLite schema version 50"
        )
    return version


class SQLiteLectureAnalysisEditCandidateRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: LectureAnalysisEditCandidateId) -> "LectureAnalysisEditCandidate | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Lecture Analysis Edit Candidate: {error}"
            ) from error

    def list_for_finding(
        self, finding_id: LectureAnalysisFindingId
    ) -> "tuple[LectureAnalysisEditCandidate, ...]":
        """Deterministic presentation order by identity.

        This is a listing order, not a canonical ordinal: `§9.2` fixes candidate order as carrying
        no product meaning, and O-1 stores none.
        """

        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE finding_id = ? ORDER BY identity",
                (finding_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Lecture Analysis Edit Candidates: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteLectureAnalysisEditCandidateCommandPersistence:
    """Owns one atomic v50 transaction appending an immutable canonical Edit Candidate."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_candidate(self, *, candidate: "LectureAnalysisEditCandidate") -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Lecture Analysis Edit Candidate persistence requires SQLite schema version 50"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            exists = self._connection.execute(
                "SELECT 1 FROM lecture_analysis_edit_candidates WHERE identity = ?",
                (candidate.identity.value,),
            ).fetchone()
            if exists is not None:
                raise PersistenceIdentityCollisionError(
                    "Lecture Analysis Edit Candidate identity already exists"
                )
            self._connection.execute(
                """
                INSERT INTO lecture_analysis_edit_candidates(
                    identity, finding_id, candidate_type, range_start, range_end,
                    rationale, candidate_contract_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.identity.value,
                    candidate.finding_id.value,
                    candidate.candidate_type,
                    candidate.range_start,
                    candidate.range_end,
                    candidate.rationale,
                    candidate.candidate_contract_version,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Lecture Analysis Edit Candidate already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Lecture Analysis Edit Candidate: {error}"
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
    "SELECT identity, finding_id, candidate_type, range_start, range_end, "
    "rationale, candidate_contract_version "
    "FROM lecture_analysis_edit_candidates"
)


def _restore(row: tuple[object, ...]) -> "LectureAnalysisEditCandidate":
    from lectureos.application.lecture_analysis_edit_candidate import (
        LectureAnalysisEditCandidate,
    )

    return LectureAnalysisEditCandidate(
        identity=LectureAnalysisEditCandidateId(row[0]),
        finding_id=LectureAnalysisFindingId(row[1]),
        candidate_type=row[2],
        range_start=row[3],
        range_end=row[4],
        rationale=row[5],
        candidate_contract_version=row[6],
    )


__all__ = [
    "SQLiteLectureAnalysisEditCandidateCommandPersistence",
    "SQLiteLectureAnalysisEditCandidateRepository",
]
