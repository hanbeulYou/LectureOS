"""Insert-only SQLite repository for canonical DomainResultReference records."""

from __future__ import annotations

import sqlite3

from lectureos.execution.identities import (
    DomainResultId,
    SourceMediaId,
    SourceTimelineId,
)
from lectureos.execution.models import DomainResultReference

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection


class SQLiteDomainResultReferenceRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        version = validate_sqlite_connection(connection)
        if version < 4:
            raise SchemaFeatureUnavailableError(
                "DomainResultReference persistence requires SQLite schema version 4"
            )
        self._connection = connection

    def get(self, identity: DomainResultId) -> DomainResultReference | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, kind, source_media_id, source_timeline_id,
                       revision_of, applicability
                FROM domain_result_references
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return self._restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read DomainResultReference: {error}"
            ) from error

    def save(self, record: DomainResultReference) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                "DomainResultReference identity already exists"
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _insert_domain_result_reference_record(self._connection, record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "DomainResultReference identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist DomainResultReference: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(
                f"could not persist DomainResultReference: {error}"
            ) from error
        except Exception:
            self._rollback()
            raise

    def _restore(self, row: tuple[object, ...]) -> DomainResultReference:
        identity = DomainResultId(row[0])
        return DomainResultReference(
            identity=identity,
            kind=row[1],
            source_media=SourceMediaId(row[2]) if row[2] is not None else None,
            source_timeline=(
                SourceTimelineId(row[3]) if row[3] is not None else None
            ),
            upstream_results=tuple(
                DomainResultId(value) for value in self._upstream_values(identity)
            ),
            revision_of=DomainResultId(row[4]) if row[4] is not None else None,
            applicability=row[5],
        )

    def _upstream_values(self, identity: DomainResultId) -> tuple[str, ...]:
        rows = self._connection.execute(
            """
            SELECT ordinal, upstream_domain_result_id
            FROM domain_result_upstream_results
            WHERE domain_result_id = ?
            ORDER BY ordinal
            """,
            (identity.value,),
        ).fetchall()
        if tuple(row[0] for row in rows) != tuple(range(len(rows))):
            raise PersistenceError("DomainResultReference upstream ordering is corrupt")
        return tuple(row[1] for row in rows)

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _insert_domain_result_reference_record(
    connection: sqlite3.Connection,
    record: DomainResultReference,
) -> None:
    """Insert one complete canonical result without owning a transaction."""

    connection.execute(
        """
        INSERT INTO domain_result_references(
            identity, kind, source_media_id, source_timeline_id,
            revision_of, applicability
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.kind,
            _optional_value(record.source_media),
            _optional_value(record.source_timeline),
            _optional_value(record.revision_of),
            record.applicability,
        ),
    )
    _insert_upstream_results(connection, record)


def _insert_upstream_results(
    connection: sqlite3.Connection,
    record: DomainResultReference,
) -> None:
    connection.executemany(
        """
        INSERT INTO domain_result_upstream_results(
            domain_result_id, ordinal, upstream_domain_result_id
        ) VALUES (?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, upstream.value)
            for ordinal, upstream in enumerate(record.upstream_results)
        ),
    )


def _optional_value(reference: object | None) -> str | None:
    return reference.value if reference is not None else None
