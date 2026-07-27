"""Append-only SQLite persistence for Effective-Source Subtitle Review Decisions (GOAL-015).

Serializes one immutable Human Authority record per authority change in a single atomic
transaction — the GOAL-009 idiom: per-subject ``sequence`` + ``previous_decision_id`` supersession,
current authority derived as the highest sequence (no mutable flag, no latest-row heuristic).
Decisions are never updated or deleted; a later judgment appends. Any collision or error rolls
back with no partial state; no review subject, candidate, or legacy decision row is ever touched.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    EffectiveSubtitleReviewDecisionId,
    EffectiveSubtitleReviewSubjectId,
)
from lectureos.review.identities import HumanActorReference

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.effective_subtitle_review_decision import (
        EffectiveSubtitleReviewDecision,
    )

_REQUIRED_VERSION = 41


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Effective Subtitle Review Decision persistence requires SQLite schema version 41"
        )
    return version


class SQLiteEffectiveSubtitleReviewDecisionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: EffectiveSubtitleReviewDecisionId
    ) -> "EffectiveSubtitleReviewDecision | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective Subtitle Review Decision: {error}"
            ) from error

    def get_current(
        self, review_subject_id: EffectiveSubtitleReviewSubjectId
    ) -> "EffectiveSubtitleReviewDecision | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE review_subject_id = ? "
                "ORDER BY sequence DESC LIMIT 1",
                (review_subject_id.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read current Effective Subtitle Review Decision: {error}"
            ) from error

    def history(
        self, review_subject_id: EffectiveSubtitleReviewSubjectId
    ) -> "tuple[EffectiveSubtitleReviewDecision, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE review_subject_id = ? ORDER BY sequence",
                (review_subject_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective Subtitle Review Decision history: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteEffectiveSubtitleReviewDecisionCommandPersistence:
    """Owns one atomic v41 transaction appending a Human Authority record."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_decision(self, *, decision: "EffectiveSubtitleReviewDecision") -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Effective Subtitle Review Decision persistence requires SQLite schema version 41"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(decision.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Effective Subtitle Review Decision identity already exists"
                )
            self._require_valid_supersession(decision)
            self._connection.execute(
                """
                INSERT INTO subtitle_effective_review_decisions(
                    identity, review_subject_id, kind, reviewer, sequence,
                    content_fingerprint, previous_decision_id, rationale
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.identity.value,
                    decision.review_subject_id.value,
                    decision.kind.value,
                    decision.reviewer.value,
                    decision.sequence,
                    decision.content_fingerprint,
                    decision.previous_decision_id.value
                    if decision.previous_decision_id
                    else None,
                    decision.rationale,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Effective Subtitle Review Decision already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Effective Subtitle Review Decision: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _require_valid_supersession(
        self, decision: "EffectiveSubtitleReviewDecision"
    ) -> None:
        if decision.previous_decision_id is None:
            return
        row = self._connection.execute(
            """
            SELECT review_subject_id, sequence
            FROM subtitle_effective_review_decisions
            WHERE identity = ?
            """,
            (decision.previous_decision_id.value,),
        ).fetchone()
        if row is None:
            raise PersistenceError("decision supersedes an unknown previous decision")
        if row[0] != decision.review_subject_id.value:
            raise PersistenceError(
                "decision supersession must stay within one review subject"
            )
        if row[1] != decision.sequence - 1:
            raise PersistenceError(
                "decision supersession must increment the sequence by one"
            )

    def _exists(self, identity: str) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM subtitle_effective_review_decisions WHERE identity = ?",
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


_SELECT_COLUMNS = (
    "SELECT identity, review_subject_id, kind, reviewer, sequence, "
    "content_fingerprint, previous_decision_id, rationale "
    "FROM subtitle_effective_review_decisions"
)


def _restore(row: tuple[object, ...]) -> "EffectiveSubtitleReviewDecision":
    from lectureos.application.effective_subtitle_review_decision import (
        EffectiveSubtitleReviewDecision,
    )
    from lectureos.review.models import DecisionKind

    return EffectiveSubtitleReviewDecision(
        identity=EffectiveSubtitleReviewDecisionId(row[0]),
        review_subject_id=EffectiveSubtitleReviewSubjectId(row[1]),
        kind=DecisionKind(row[2]),
        reviewer=HumanActorReference(row[3]),
        sequence=row[4],
        content_fingerprint=row[5],
        previous_decision_id=(
            EffectiveSubtitleReviewDecisionId(row[6]) if row[6] is not None else None
        ),
        rationale=row[7],
    )


__all__ = [
    "SQLiteEffectiveSubtitleReviewDecisionCommandPersistence",
    "SQLiteEffectiveSubtitleReviewDecisionRepository",
]
