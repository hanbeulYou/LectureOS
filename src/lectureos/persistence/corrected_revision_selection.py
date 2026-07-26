"""Append-only SQLite persistence for Current Corrected Revision Selection (040 §20, PATCH-0027).

Serializes one immutable selection-authority record per authority change in a single atomic transaction. History
is append-only: each change is a new row with an incremented per-intake ``sequence`` whose
``previous_selection_id`` supersedes the prior current record; the current selection is the highest-``sequence``
row (no wall-clock ordering, no mutable current pointer, no ``is_current`` flag). Two kinds exist —
``corrected_revision`` (revision required) and ``raw_fallback`` (revision must be absent), CHECK-enforced so Raw
fallback is never a fake revision. Any collision or error rolls back with no partial state; no revision,
candidate, decision, raw transcript, or raw-selection row is ever touched, and selection rows are never updated
or deleted.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    CorrectedRevisionSelectionId,
    TranscriptSourceIntakeId,
)
from lectureos.review.identities import HumanActorReference
from lectureos.transcript.identities import TranscriptRevisionId

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.corrected_revision_selection import (
        CorrectedRevisionSelection,
    )

_REQUIRED_VERSION = 37


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Corrected Revision Selection persistence requires SQLite schema version 37"
        )
    return version


class SQLiteCorrectedRevisionSelectionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: CorrectedRevisionSelectionId
    ) -> "CorrectedRevisionSelection | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Corrected Revision Selection: {error}"
            ) from error

    def get_current(
        self, intake_id: TranscriptSourceIntakeId
    ) -> "CorrectedRevisionSelection | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE transcript_source_intake_id = ? "
                "ORDER BY sequence DESC LIMIT 1",
                (intake_id.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read current Corrected Revision Selection: {error}"
            ) from error

    def history(
        self, intake_id: TranscriptSourceIntakeId
    ) -> "tuple[CorrectedRevisionSelection, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE transcript_source_intake_id = ? ORDER BY sequence",
                (intake_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Corrected Revision Selection history: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteCorrectedRevisionSelectionCommandPersistence:
    """Owns one atomic v37 transaction appending a selection-authority record."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_selection(self, *, selection: "CorrectedRevisionSelection") -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Corrected Revision Selection persistence requires SQLite schema version 37"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("identity", selection.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Corrected Revision Selection identity already exists"
                )
            self._require_valid_supersession(selection)
            self._connection.execute(
                """
                INSERT INTO corrected_revision_selections(
                    identity, transcript_source_intake_id, kind, corrected_revision_id,
                    reviewer, sequence, previous_selection_id, rationale
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    selection.identity.value,
                    selection.transcript_source_intake_id.value,
                    selection.kind.value,
                    selection.corrected_revision_id.value
                    if selection.corrected_revision_id
                    else None,
                    selection.reviewer.value,
                    selection.sequence,
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
                f"Corrected Revision Selection already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Corrected Revision Selection: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _require_valid_supersession(self, selection: "CorrectedRevisionSelection") -> None:
        if selection.previous_selection_id is None:
            return
        row = self._connection.execute(
            """
            SELECT transcript_source_intake_id, sequence
            FROM corrected_revision_selections
            WHERE identity = ?
            """,
            (selection.previous_selection_id.value,),
        ).fetchone()
        if row is None:
            raise PersistenceError("selection supersedes an unknown previous selection")
        if row[0] != selection.transcript_source_intake_id.value:
            raise PersistenceError("selection supersession must stay within one intake context")
        if row[1] != selection.sequence - 1:
            raise PersistenceError("selection supersession must increment the sequence by one")

    def _exists(self, column: str, value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM corrected_revision_selections WHERE {column} = ?",
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
    "SELECT identity, transcript_source_intake_id, kind, corrected_revision_id, "
    "reviewer, sequence, previous_selection_id, rationale "
    "FROM corrected_revision_selections"
)


def _restore(row: tuple[object, ...]) -> "CorrectedRevisionSelection":
    from lectureos.application.corrected_revision_selection import (
        CorrectedRevisionSelection,
        SelectionKind,
    )

    return CorrectedRevisionSelection(
        identity=CorrectedRevisionSelectionId(row[0]),
        transcript_source_intake_id=TranscriptSourceIntakeId(row[1]),
        kind=SelectionKind(row[2]),
        corrected_revision_id=(
            TranscriptRevisionId(row[3]) if row[3] is not None else None
        ),
        reviewer=HumanActorReference(row[4]),
        sequence=row[5],
        previous_selection_id=(
            CorrectedRevisionSelectionId(row[6]) if row[6] is not None else None
        ),
        rationale=row[7],
    )


__all__ = [
    "SQLiteCorrectedRevisionSelectionCommandPersistence",
    "SQLiteCorrectedRevisionSelectionRepository",
]
