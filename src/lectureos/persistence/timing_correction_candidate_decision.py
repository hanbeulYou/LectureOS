"""Atomic SQLite persistence for Timing Correction Candidate Human Decisions (040 §18, PATCH-0047 TC-10).

Append-only serialization of one Accept/Reject authority record into the additive
`timing_correction_candidate_decisions` relation. The relation is a sibling purely because
`correction_candidate_decisions` foreign-keys to `correction_candidates(identity)` and therefore
cannot reference a timing candidate; it carries the same columns, the same append-only supersession,
and the same three derived states. INSERT only — no UPDATE, no DELETE, and no released relation is
read, written, or reinterpreted.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    TimingCorrectionCandidateDecisionId,
    TimingCorrectionCandidateId,
)
from lectureos.review.identities import HumanActorReference
from lectureos.review.models import DecisionKind

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.timing_correction_candidate_decision import (
        TimingCorrectionCandidateDecision,
    )

_REQUIRED_VERSION = 54
_UNAVAILABLE = (
    "Timing Correction Decision persistence requires SQLite schema version 54"
)

_SELECT_COLUMNS = (
    "SELECT identity, timing_correction_candidate_id, kind, reviewer, sequence, "
    "previous_decision_id, rationale, content_fingerprint "
    "FROM timing_correction_candidate_decisions"
)


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(_UNAVAILABLE)
    return version


class SQLiteTimingCorrectionDecisionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: TimingCorrectionCandidateDecisionId
    ) -> "TimingCorrectionCandidateDecision | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Timing Correction Decision: {error}"
            ) from error
        return None if row is None else _restore(row)

    def get_current(
        self, candidate_id: TimingCorrectionCandidateId
    ) -> "TimingCorrectionCandidateDecision | None":
        """The highest-sequence record — the current authority, always derived, never stored."""

        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE timing_correction_candidate_id = ? "
                "ORDER BY sequence DESC LIMIT 1",
                (candidate_id.value,),
            ).fetchone()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Timing Correction Decision: {error}"
            ) from error
        return None if row is None else _restore(row)

    def history(
        self, candidate_id: TimingCorrectionCandidateId
    ) -> "tuple[TimingCorrectionCandidateDecision, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE timing_correction_candidate_id = ? ORDER BY sequence",
                (candidate_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Timing Correction Decisions: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteTimingCorrectionDecisionCommandPersistence:
    """Owns one atomic v54 transaction appending a Timing Correction Human Decision."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_timing_decision(
        self, *, decision: "TimingCorrectionCandidateDecision"
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(_UNAVAILABLE)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(decision.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Timing Correction Decision already exists"
                )
            self._connection.execute(
                """
                INSERT INTO timing_correction_candidate_decisions(
                    identity, timing_correction_candidate_id, kind, reviewer, sequence,
                    previous_decision_id, rationale, content_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.identity.value,
                    decision.timing_correction_candidate_id.value,
                    decision.kind.value,
                    decision.reviewer.value,
                    decision.sequence,
                    None
                    if decision.previous_decision_id is None
                    else decision.previous_decision_id.value,
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
                f"Timing Correction Decision already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Timing Correction Decision: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, identity: str) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM timing_correction_candidate_decisions WHERE identity = ?",
                (identity,),
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _restore(row: tuple[object, ...]) -> "TimingCorrectionCandidateDecision":
    from lectureos.application.timing_correction_candidate_decision import (
        TimingCorrectionCandidateDecision,
    )

    return TimingCorrectionCandidateDecision(
        identity=TimingCorrectionCandidateDecisionId(row[0]),
        timing_correction_candidate_id=TimingCorrectionCandidateId(row[1]),
        kind=DecisionKind(row[2]),
        reviewer=HumanActorReference(row[3]),
        sequence=row[4],
        previous_decision_id=(
            None if row[5] is None else TimingCorrectionCandidateDecisionId(row[5])
        ),
        rationale=row[6],
        content_fingerprint=row[7],
    )


__all__ = [
    "SQLiteTimingCorrectionDecisionCommandPersistence",
    "SQLiteTimingCorrectionDecisionRepository",
]
