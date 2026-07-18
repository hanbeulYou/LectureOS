"""Insert-only SQLite repository for canonical Failure records."""

from __future__ import annotations

import sqlite3

from lectureos.execution.identities import (
    DiagnosticId,
    DomainResultId,
    FailureId,
    InputReference,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import Failure, FailureCategory

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection


class SQLiteFailureRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        version = validate_sqlite_connection(connection)
        if version < 4:
            raise SchemaFeatureUnavailableError(
                "Failure persistence requires SQLite schema version 4"
            )
        self._connection = connection

    def get(self, identity: FailureId) -> Failure | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, category, processing_run_id, unit_execution_id,
                       retryable, reprocessing_required, human_action_required
                FROM failures
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return self._restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(f"could not read Failure: {error}") from error

    def save(self, record: Failure) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError("Failure identity already exists")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _insert_failure_record(self._connection, record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "Failure identity already exists"
                ) from error
            raise PersistenceError(f"could not persist Failure: {error}") from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(f"could not persist Failure: {error}") from error
        except Exception:
            self._rollback()
            raise

    def _restore(self, row: tuple[object, ...]) -> Failure:
        identity = FailureId(row[0])
        return Failure(
            identity=identity,
            category=FailureCategory(row[1]),
            run_id=ProcessingRunId(row[2]) if row[2] is not None else None,
            unit_execution_id=(
                UnitExecutionId(row[3]) if row[3] is not None else None
            ),
            affected_inputs=tuple(
                InputReference(value)
                for value in self._child_values(
                    "failure_affected_inputs", "input_reference", identity
                )
            ),
            affected_results=tuple(
                DomainResultId(value)
                for value in self._child_values(
                    "failure_affected_results", "domain_result_id", identity
                )
            ),
            retryable=_restore_boolean(row[4], "retryable"),
            reprocessing_required=_restore_boolean(
                row[5], "reprocessing_required"
            ),
            human_action_required=_restore_boolean(
                row[6], "human_action_required"
            ),
            diagnostics=tuple(
                DiagnosticId(value)
                for value in self._child_values(
                    "failure_diagnostics", "diagnostic_id", identity
                )
            ),
        )

    def _child_values(
        self, table: str, value_column: str, identity: FailureId
    ) -> tuple[str, ...]:
        rows = self._connection.execute(
            f"""
            SELECT ordinal, {value_column}
            FROM {table}
            WHERE failure_id = ?
            ORDER BY ordinal
            """,
            (identity.value,),
        ).fetchall()
        if tuple(row[0] for row in rows) != tuple(range(len(rows))):
            raise PersistenceError(f"Failure child ordering is corrupt: {table}")
        return tuple(row[1] for row in rows)

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _insert_failure_record(
    connection: sqlite3.Connection, record: Failure
) -> None:
    """Insert one complete canonical Failure without owning a transaction."""

    connection.execute(
        """
        INSERT INTO failures(
            identity, category, processing_run_id, unit_execution_id,
            retryable, reprocessing_required, human_action_required
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.category.value,
            _optional_value(record.run_id),
            _optional_value(record.unit_execution_id),
            1 if record.retryable else 0,
            1 if record.reprocessing_required else 0,
            1 if record.human_action_required else 0,
        ),
    )
    _insert_children(
        connection,
        "failure_affected_inputs",
        "input_reference",
        record,
        tuple(item.value for item in record.affected_inputs),
    )
    _insert_children(
        connection,
        "failure_affected_results",
        "domain_result_id",
        record,
        tuple(item.value for item in record.affected_results),
    )
    _insert_children(
        connection,
        "failure_diagnostics",
        "diagnostic_id",
        record,
        tuple(item.value for item in record.diagnostics),
    )


def _insert_children(
    connection: sqlite3.Connection,
    table: str,
    value_column: str,
    record: Failure,
    values: tuple[str, ...],
) -> None:
    connection.executemany(
        f"""
        INSERT INTO {table}(failure_id, ordinal, {value_column})
        VALUES (?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, value)
            for ordinal, value in enumerate(values)
        ),
    )


def _optional_value(reference: object | None) -> str | None:
    return reference.value if reference is not None else None


def _restore_boolean(value: object, field: str) -> bool:
    if value == 0:
        return False
    if value == 1:
        return True
    raise PersistenceError(f"Failure {field} value is unknown")
