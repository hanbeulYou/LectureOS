"""Insert-only SQLite persistence for the Media Import Application Foundation (045 §1).

Serializes one immutable, content-addressed Source Media record in a single atomic transaction. Records are
insert-only; the content fingerprint's canonical uniqueness is enforced (one Media record per content). Any
collision or error rolls back with no partial state.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.execution.identities import SourceMediaId

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.media_import import SourceMediaRecord

_REQUIRED_VERSION = 30


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Media Import persistence requires SQLite schema version 30"
        )
    return version


class SQLiteSourceMediaRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: SourceMediaId) -> SourceMediaRecord | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, fingerprint_algorithm, fingerprint_digest,
                       byte_length, observed_source_path
                FROM source_media
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(f"could not read Source Media: {error}") from error

    def get_by_fingerprint(self, algorithm: str, digest: str) -> SourceMediaRecord | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, fingerprint_algorithm, fingerprint_digest,
                       byte_length, observed_source_path
                FROM source_media
                WHERE fingerprint_algorithm = ? AND fingerprint_digest = ?
                """,
                (algorithm, digest),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(f"could not read Source Media: {error}") from error


class SQLiteSourceMediaCommandPersistence:
    """Owns one atomic v30 transaction persisting a Source Media record."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_source_media(self, *, record: SourceMediaRecord) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Media Import persistence requires SQLite schema version 30"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("identity", record.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Source Media identity already exists"
                )
            _insert_source_media(self._connection, record)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            # A concurrent insert of the same content (identity or fingerprint uniqueness) races here.
            raise PersistenceIdentityCollisionError(
                f"Source Media already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Source Media: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, column: str, value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM source_media WHERE {column} = ?", (value,)
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _restore(row: tuple[object, ...]) -> "SourceMediaRecord":
    from lectureos.application.media_import import SourceMediaRecord

    return SourceMediaRecord(
        identity=SourceMediaId(row[0]),
        fingerprint_algorithm=row[1],
        fingerprint_digest=row[2],
        byte_length=row[3],
        observed_source_path=row[4],
    )


def _insert_source_media(
    connection: sqlite3.Connection, record: SourceMediaRecord
) -> None:
    connection.execute(
        """
        INSERT INTO source_media(
            identity, fingerprint_algorithm, fingerprint_digest,
            byte_length, observed_source_path
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.fingerprint_algorithm,
            record.fingerprint_digest,
            record.byte_length,
            record.observed_source_path,
        ),
    )


__all__ = [
    "SQLiteSourceMediaCommandPersistence",
    "SQLiteSourceMediaRepository",
]
