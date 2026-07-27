"""Append-only SQLite persistence for Effective Subtitle Final Selections (GOAL-016).

Serializes one immutable selection-authority record per authority change in a single atomic
transaction — the GOAL-011 idiom: per-intake ``sequence`` + ``previous_selection_id`` supersession,
current selection derived as the highest sequence (no mutable flag, no latest-row heuristic).
Selections are never updated or deleted; a later selection appends. Any collision or error rolls
back with no partial state; no candidate, review subject, decision, or legacy selection row is
ever touched.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    EffectiveSubtitleCandidateId,
    EffectiveSubtitleFinalSelectionId,
    EffectiveSubtitleReviewDecisionId,
    EffectiveSubtitleReviewSubjectId,
    TranscriptSourceIntakeId,
)
from lectureos.review.identities import HumanActorReference

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.effective_subtitle_final_selection import (
        EffectiveSubtitleFinalSelection,
    )

_REQUIRED_VERSION = 42


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Effective Subtitle Final Selection persistence requires SQLite schema version 42"
        )
    return version


class SQLiteEffectiveSubtitleFinalSelectionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: EffectiveSubtitleFinalSelectionId
    ) -> "EffectiveSubtitleFinalSelection | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective Subtitle Final Selection: {error}"
            ) from error

    def get_current(
        self, intake_id: TranscriptSourceIntakeId
    ) -> "EffectiveSubtitleFinalSelection | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE transcript_source_intake_id = ? "
                "ORDER BY sequence DESC LIMIT 1",
                (intake_id.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read current Effective Subtitle Final Selection: {error}"
            ) from error

    def history(
        self, intake_id: TranscriptSourceIntakeId
    ) -> "tuple[EffectiveSubtitleFinalSelection, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE transcript_source_intake_id = ? ORDER BY sequence",
                (intake_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective Subtitle Final Selection history: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteEffectiveSubtitleFinalSelectionCommandPersistence:
    """Owns one atomic v42 transaction appending a selection-authority record."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_selection(self, *, selection: "EffectiveSubtitleFinalSelection") -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Effective Subtitle Final Selection persistence requires SQLite schema version 42"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(selection.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Effective Subtitle Final Selection identity already exists"
                )
            self._require_valid_supersession(selection)
            self._connection.execute(
                """
                INSERT INTO subtitle_effective_final_selections(
                    identity, transcript_source_intake_id, candidate_id, review_subject_id,
                    supporting_decision_id, selector, sequence, content_fingerprint,
                    previous_selection_id, rationale
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    selection.identity.value,
                    selection.transcript_source_intake_id.value,
                    selection.candidate_id.value,
                    selection.review_subject_id.value,
                    selection.supporting_decision_id.value,
                    selection.selector.value,
                    selection.sequence,
                    selection.content_fingerprint,
                    selection.previous_selection_id.value
                    if selection.previous_selection_id
                    else None,
                    selection.rationale,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Effective Subtitle Final Selection already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Effective Subtitle Final Selection: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _require_valid_supersession(
        self, selection: "EffectiveSubtitleFinalSelection"
    ) -> None:
        if selection.previous_selection_id is None:
            return
        row = self._connection.execute(
            """
            SELECT transcript_source_intake_id, sequence
            FROM subtitle_effective_final_selections
            WHERE identity = ?
            """,
            (selection.previous_selection_id.value,),
        ).fetchone()
        if row is None:
            raise PersistenceError("selection supersedes an unknown previous selection")
        if row[0] != selection.transcript_source_intake_id.value:
            raise PersistenceError(
                "selection supersession must stay within one intake scope"
            )
        if row[1] != selection.sequence - 1:
            raise PersistenceError(
                "selection supersession must increment the sequence by one"
            )

    def _exists(self, identity: str) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM subtitle_effective_final_selections WHERE identity = ?",
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
    "SELECT identity, transcript_source_intake_id, candidate_id, review_subject_id, "
    "supporting_decision_id, selector, sequence, content_fingerprint, "
    "previous_selection_id, rationale "
    "FROM subtitle_effective_final_selections"
)


def _restore(row: tuple[object, ...]) -> "EffectiveSubtitleFinalSelection":
    from lectureos.application.effective_subtitle_final_selection import (
        EffectiveSubtitleFinalSelection,
    )

    return EffectiveSubtitleFinalSelection(
        identity=EffectiveSubtitleFinalSelectionId(row[0]),
        transcript_source_intake_id=TranscriptSourceIntakeId(row[1]),
        candidate_id=EffectiveSubtitleCandidateId(row[2]),
        review_subject_id=EffectiveSubtitleReviewSubjectId(row[3]),
        supporting_decision_id=EffectiveSubtitleReviewDecisionId(row[4]),
        selector=HumanActorReference(row[5]),
        sequence=row[6],
        content_fingerprint=row[7],
        previous_selection_id=(
            EffectiveSubtitleFinalSelectionId(row[8]) if row[8] is not None else None
        ),
        rationale=row[9],
    )


__all__ = [
    "SQLiteEffectiveSubtitleFinalSelectionCommandPersistence",
    "SQLiteEffectiveSubtitleFinalSelectionRepository",
]
