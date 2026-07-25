"""Insert-only SQLite persistence for the Source Intake Application Foundation (040 §13).

Serializes one immutable, content-derived transcript source intake record in a single atomic transaction. The
record confirms that a persisted `source_media` row is admitted as a transcription input; it is insert-only, one
canonical intake per Source Media (identity PK + UNIQUE(source_media_id)), with a foreign key to the owning
`source_media` record. Any collision or error rolls back with no partial state.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import TranscriptSourceIntakeId
from lectureos.execution.identities import SourceMediaId

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.transcript_source_intake import TranscriptSourceIntake

_REQUIRED_VERSION = 31


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Transcript Source Intake persistence requires SQLite schema version 31"
        )
    return version


class SQLiteTranscriptSourceIntakeRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: TranscriptSourceIntakeId) -> "TranscriptSourceIntake | None":
        try:
            row = self._connection.execute(
                "SELECT identity, source_media_id FROM transcript_source_intakes WHERE identity = ?",
                (identity.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Transcript Source Intake: {error}"
            ) from error

    def get_by_source_media(
        self, source_media_id: SourceMediaId
    ) -> "TranscriptSourceIntake | None":
        try:
            row = self._connection.execute(
                "SELECT identity, source_media_id FROM transcript_source_intakes "
                "WHERE source_media_id = ?",
                (source_media_id.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Transcript Source Intake: {error}"
            ) from error


class SQLiteTranscriptSourceIntakeCommandPersistence:
    """Owns one atomic v31 transaction persisting a transcript source intake record."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_transcript_source_intake(
        self, *, intake: "TranscriptSourceIntake"
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Transcript Source Intake persistence requires SQLite schema version 31"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("identity", intake.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Transcript Source Intake identity already exists"
                )
            self._connection.execute(
                "INSERT INTO transcript_source_intakes(identity, source_media_id) VALUES (?, ?)",
                (intake.identity.value, intake.source_media_id.value),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            # Identity/UNIQUE collision (a near-concurrent admission of the same Source Media).
            raise PersistenceIdentityCollisionError(
                f"Transcript Source Intake already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Transcript Source Intake: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, column: str, value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM transcript_source_intakes WHERE {column} = ?", (value,)
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _restore(row: tuple[object, ...]) -> "TranscriptSourceIntake":
    from lectureos.application.transcript_source_intake import TranscriptSourceIntake

    return TranscriptSourceIntake(
        identity=TranscriptSourceIntakeId(row[0]),
        source_media_id=SourceMediaId(row[1]),
    )


__all__ = [
    "SQLiteTranscriptSourceIntakeCommandPersistence",
    "SQLiteTranscriptSourceIntakeRepository",
]
