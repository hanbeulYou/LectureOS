"""Insert-only SQLite repository for the exact ProcessingUnit model."""

from __future__ import annotations

import sqlite3

from lectureos.execution.identities import (
    CapabilityReference,
    ProcessingUnitId,
)
from lectureos.execution.models import ProcessingUnit

from .errors import PersistenceError, PersistenceIdentityCollisionError
from .sqlite import validate_sqlite_connection


class SQLiteProcessingUnitRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        validate_sqlite_connection(connection)
        self._connection = connection

    def get(self, identity: ProcessingUnitId) -> ProcessingUnit | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, purpose, independently_retryable
                FROM processing_units
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return self._restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(f"could not read ProcessingUnit: {error}") from error

    def save(self, record: ProcessingUnit) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                "ProcessingUnit identity already exists"
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                """
                INSERT INTO processing_units(
                    identity, purpose, independently_retryable
                ) VALUES (?, ?, ?)
                """,
                (
                    record.identity.value,
                    record.purpose,
                    1 if record.independently_retryable else 0,
                ),
            )
            self._insert_children(
                "processing_unit_dependencies",
                "dependency_id",
                record.identity.value,
                tuple(item.value for item in record.dependencies),
            )
            self._insert_children(
                "processing_unit_capabilities",
                "capability",
                record.identity.value,
                tuple(item.value for item in record.capabilities),
            )
            self._insert_children(
                "processing_unit_result_kinds",
                "result_kind",
                record.identity.value,
                record.result_kinds,
            )
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "ProcessingUnit identity already exists"
                ) from error
            raise PersistenceError(f"could not persist ProcessingUnit: {error}") from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(f"could not persist ProcessingUnit: {error}") from error

    def all(self) -> tuple[ProcessingUnit, ...]:
        try:
            rows = self._connection.execute(
                """
                SELECT identity, purpose, independently_retryable
                FROM processing_units
                ORDER BY rowid
                """
            ).fetchall()
            return tuple(self._restore(row) for row in rows)
        except sqlite3.Error as error:
            raise PersistenceError(f"could not list ProcessingUnits: {error}") from error

    def _restore(self, row) -> ProcessingUnit:
        identity = ProcessingUnitId(row[0])
        retryable = _restore_boolean(row[2])
        return ProcessingUnit(
            identity=identity,
            purpose=row[1],
            dependencies=tuple(
                ProcessingUnitId(value)
                for value in self._child_values(
                    "processing_unit_dependencies", "dependency_id", identity
                )
            ),
            capabilities=tuple(
                CapabilityReference(value)
                for value in self._child_values(
                    "processing_unit_capabilities", "capability", identity
                )
            ),
            result_kinds=self._child_values(
                "processing_unit_result_kinds", "result_kind", identity
            ),
            independently_retryable=retryable,
        )

    def _insert_children(
        self,
        table: str,
        value_column: str,
        identity: str,
        values: tuple[str, ...],
    ) -> None:
        self._connection.executemany(
            f"""
            INSERT INTO {table}(processing_unit_id, ordinal, {value_column})
            VALUES (?, ?, ?)
            """,
            ((identity, ordinal, value) for ordinal, value in enumerate(values)),
        )

    def _child_values(
        self,
        table: str,
        value_column: str,
        identity: ProcessingUnitId,
    ) -> tuple[str, ...]:
        rows = self._connection.execute(
            f"""
            SELECT ordinal, {value_column}
            FROM {table}
            WHERE processing_unit_id = ?
            ORDER BY ordinal
            """,
            (identity.value,),
        ).fetchall()
        if tuple(row[0] for row in rows) != tuple(range(len(rows))):
            raise PersistenceError(f"ProcessingUnit child ordering is corrupt: {table}")
        return tuple(row[1] for row in rows)

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _restore_boolean(value: object) -> bool:
    if value == 0:
        return False
    if value == 1:
        return True
    raise PersistenceError("ProcessingUnit retryable value is unknown")
