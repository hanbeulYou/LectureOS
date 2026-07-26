"""Append-only SQLite persistence for Correction Candidate Human Decisions (040 §18, PATCH-0025).

Serializes one immutable Human Authority record per authority change in a single atomic transaction. History is
append-only: each change is a new row with an incremented per-candidate ``sequence`` whose ``previous_decision_id``
supersedes the prior current record; the current authority is the highest-``sequence`` row for the candidate (no
wall-clock ordering). Decisions target admitted `CorrectionCandidate` rows (040 §17). Any collision or error rolls
back with no partial state; a decision row is never updated or deleted (INSERT-only), and no candidate, raw
transcript, segment, or selection row is ever touched.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import CorrectionCandidateDecisionId
from lectureos.review.identities import HumanActorReference
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import CorrectionCandidateId

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.correction_candidate_decision import (
        CorrectionCandidateDecision,
    )

_REQUIRED_VERSION = 35


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Correction Candidate Decision persistence requires SQLite schema version 35"
        )
    return version


class SQLiteCorrectionCandidateDecisionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def is_admitted_candidate(self, candidate_id: CorrectionCandidateId) -> bool:
        try:
            return (
                self._connection.execute(
                    "SELECT 1 FROM correction_candidate_admissions "
                    "WHERE correction_candidate_id = ?",
                    (candidate_id.value,),
                ).fetchone()
                is not None
            )
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not resolve correction candidate: {error}"
            ) from error

    def get(
        self, identity: CorrectionCandidateDecisionId
    ) -> "CorrectionCandidateDecision | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read correction candidate decision: {error}"
            ) from error

    def get_current(
        self, candidate_id: CorrectionCandidateId
    ) -> "CorrectionCandidateDecision | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE correction_candidate_id = ? "
                "ORDER BY sequence DESC LIMIT 1",
                (candidate_id.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read current correction candidate decision: {error}"
            ) from error

    def history(
        self, candidate_id: CorrectionCandidateId
    ) -> "tuple[CorrectionCandidateDecision, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE correction_candidate_id = ? ORDER BY sequence",
                (candidate_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read correction candidate decision history: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteCorrectionCandidateDecisionCommandPersistence:
    """Owns one atomic v35 transaction appending a Human Authority decision record."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_decision(self, *, decision: "CorrectionCandidateDecision") -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Correction Candidate Decision persistence requires SQLite schema version 35"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("identity", decision.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Correction Candidate Decision identity already exists"
                )
            self._require_valid_supersession(decision)
            self._connection.execute(
                """
                INSERT INTO correction_candidate_decisions(
                    identity, correction_candidate_id, kind, reviewer, sequence,
                    previous_decision_id, rationale, content_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.identity.value,
                    decision.correction_candidate_id.value,
                    decision.kind.value,
                    decision.reviewer.value,
                    decision.sequence,
                    decision.previous_decision_id.value
                    if decision.previous_decision_id
                    else None,
                    decision.rationale,
                    decision.content_fingerprint,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Correction Candidate Decision already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Correction Candidate Decision: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _require_valid_supersession(
        self, decision: "CorrectionCandidateDecision"
    ) -> None:
        if decision.previous_decision_id is None:
            return
        row = self._connection.execute(
            """
            SELECT correction_candidate_id, sequence
            FROM correction_candidate_decisions
            WHERE identity = ?
            """,
            (decision.previous_decision_id.value,),
        ).fetchone()
        if row is None:
            raise PersistenceError("decision supersedes an unknown previous decision")
        if row[0] != decision.correction_candidate_id.value:
            raise PersistenceError("decision supersession must stay within one candidate")
        if row[1] != decision.sequence - 1:
            raise PersistenceError("decision supersession must increment the sequence by one")

    def _exists(self, column: str, value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM correction_candidate_decisions WHERE {column} = ?",
                (value,),
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


_SELECT_COLUMNS = (
    "SELECT identity, correction_candidate_id, kind, reviewer, sequence, "
    "previous_decision_id, rationale, content_fingerprint "
    "FROM correction_candidate_decisions"
)


def _restore(row: tuple[object, ...]) -> "CorrectionCandidateDecision":
    from lectureos.application.correction_candidate_decision import (
        CorrectionCandidateDecision,
    )

    return CorrectionCandidateDecision(
        identity=CorrectionCandidateDecisionId(row[0]),
        correction_candidate_id=CorrectionCandidateId(row[1]),
        kind=DecisionKind(row[2]),
        reviewer=HumanActorReference(row[3]),
        sequence=row[4],
        previous_decision_id=(
            CorrectionCandidateDecisionId(row[5]) if row[5] is not None else None
        ),
        rationale=row[6],
        content_fingerprint=row[7],
    )


__all__ = [
    "SQLiteCorrectionCandidateDecisionCommandPersistence",
    "SQLiteCorrectionCandidateDecisionRepository",
]
