"""Append-only SQLite persistence for Current Raw Transcript Selection (040 §16, PATCH-0023).

Serializes one immutable current-selection record per authority change in a single atomic transaction. History is
append-only: each change is a new row with an incremented per-intake ``sequence`` whose ``previous_selection_id``
supersedes the prior current record; the current selection is the highest-``sequence`` row for the intake (no
wall-clock ordering). Candidates are read from the v32 ``provider_transcript_admissions`` table (each admitted
Raw Transcript of the intake). Any collision or error rolls back with no partial state; no Raw Transcript,
Provider Result, Source Media, or intake row is ever mutated.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    CurrentRawTranscriptSelectionId,
    TranscriptSourceIntakeId,
)
from lectureos.transcript.identities import TranscriptId

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.current_raw_transcript_selection import (
        CurrentRawTranscriptSelection,
        RawTranscriptCandidate,
    )

_REQUIRED_VERSION = 33


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Current Raw Transcript Selection persistence requires SQLite schema version 33"
        )
    return version


class SQLiteRawTranscriptSelectionRepository:
    """Read model: admitted Raw Transcript candidates of an intake, and its current selection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def candidates(
        self, intake_id: TranscriptSourceIntakeId
    ) -> "tuple[RawTranscriptCandidate, ...]":
        from lectureos.application.current_raw_transcript_selection import (
            RawTranscriptCandidate,
        )

        try:
            rows = self._connection.execute(
                """
                SELECT raw_transcript_id, provider_reference, provider_model,
                       declared_language, segment_count
                FROM provider_transcript_admissions
                WHERE transcript_source_intake_id = ?
                ORDER BY raw_transcript_id
                """,
                (intake_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read raw transcript candidates: {error}"
            ) from error
        return tuple(
            RawTranscriptCandidate(
                raw_transcript_id=TranscriptId(row[0]),
                provider_reference=row[1],
                provider_model=row[2],
                declared_language=row[3],
                segment_count=row[4],
            )
            for row in rows
        )

    def owning_intake(
        self, raw_transcript_id: TranscriptId
    ) -> TranscriptSourceIntakeId | None:
        try:
            row = self._connection.execute(
                """
                SELECT transcript_source_intake_id
                FROM provider_transcript_admissions
                WHERE raw_transcript_id = ?
                """,
                (raw_transcript_id.value,),
            ).fetchone()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not resolve raw transcript owner: {error}"
            ) from error
        return None if row is None else TranscriptSourceIntakeId(row[0])

    def get(
        self, identity: CurrentRawTranscriptSelectionId
    ) -> "CurrentRawTranscriptSelection | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read raw transcript selection: {error}"
            ) from error

    def get_current(
        self, intake_id: TranscriptSourceIntakeId
    ) -> "CurrentRawTranscriptSelection | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE transcript_source_intake_id = ? "
                "ORDER BY sequence DESC LIMIT 1",
                (intake_id.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read current raw transcript selection: {error}"
            ) from error


class SQLiteRawTranscriptSelectionCommandPersistence:
    """Owns one atomic v33 transaction appending a current raw transcript selection record."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_selection(self, *, selection: "CurrentRawTranscriptSelection") -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Current Raw Transcript Selection persistence requires SQLite schema version 33"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("identity", selection.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Current Raw Transcript Selection identity already exists"
                )
            self._require_valid_supersession(selection)
            self._connection.execute(
                """
                INSERT INTO current_raw_transcript_selections(
                    identity, transcript_source_intake_id, raw_transcript_id,
                    sequence, previous_selection_id, reason
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    selection.identity.value,
                    selection.transcript_source_intake_id.value,
                    selection.raw_transcript_id.value,
                    selection.sequence,
                    selection.previous_selection_id.value
                    if selection.previous_selection_id
                    else None,
                    selection.reason,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            # UNIQUE(intake, sequence) or identity collision — a near-concurrent selection won the race.
            raise PersistenceIdentityCollisionError(
                f"Current Raw Transcript Selection already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Current Raw Transcript Selection: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _require_valid_supersession(
        self, selection: "CurrentRawTranscriptSelection"
    ) -> None:
        if selection.previous_selection_id is None:
            return
        row = self._connection.execute(
            """
            SELECT transcript_source_intake_id, sequence
            FROM current_raw_transcript_selections
            WHERE identity = ?
            """,
            (selection.previous_selection_id.value,),
        ).fetchone()
        if row is None:
            raise PersistenceError(
                "raw transcript selection supersedes an unknown previous selection"
            )
        if row[0] != selection.transcript_source_intake_id.value:
            raise PersistenceError(
                "raw transcript selection supersession must stay within one intake"
            )
        if row[1] != selection.sequence - 1:
            raise PersistenceError(
                "raw transcript selection supersession must increment the sequence by one"
            )

    def _exists(self, column: str, value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM current_raw_transcript_selections WHERE {column} = ?",
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
    "SELECT identity, transcript_source_intake_id, raw_transcript_id, sequence, "
    "previous_selection_id, reason FROM current_raw_transcript_selections"
)


def _restore(row: tuple[object, ...]) -> "CurrentRawTranscriptSelection":
    from lectureos.application.current_raw_transcript_selection import (
        CurrentRawTranscriptSelection,
    )

    return CurrentRawTranscriptSelection(
        identity=CurrentRawTranscriptSelectionId(row[0]),
        transcript_source_intake_id=TranscriptSourceIntakeId(row[1]),
        raw_transcript_id=TranscriptId(row[2]),
        sequence=row[3],
        previous_selection_id=(
            CurrentRawTranscriptSelectionId(row[4]) if row[4] is not None else None
        ),
        reason=row[5],
    )


__all__ = [
    "SQLiteRawTranscriptSelectionCommandPersistence",
    "SQLiteRawTranscriptSelectionRepository",
]
