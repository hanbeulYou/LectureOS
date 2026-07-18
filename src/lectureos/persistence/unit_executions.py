"""Mutable-snapshot SQLite repository for the exact UnitExecution model."""

from __future__ import annotations

import sqlite3

from lectureos.execution.identities import (
    CapabilityReference,
    ConfigurationReference,
    DiagnosticId,
    DomainResultId,
    FailureId,
    InputReference,
    PluginReference,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
)
from lectureos.execution.models import (
    ExecutionOutcome,
    OutcomeKind,
    ProcessingState,
    UnitExecution,
)

from .errors import PersistenceError, SchemaFeatureUnavailableError
from .sqlite import validate_sqlite_connection

_CHILD_TABLES = (
    ("unit_execution_inputs", "input_reference"),
    ("unit_execution_capabilities", "capability"),
    ("unit_execution_plugins", "plugin_reference"),
    ("unit_execution_results", "domain_result_id"),
    ("unit_execution_failures", "failure_id"),
    ("unit_execution_diagnostics", "diagnostic_id"),
)


class SQLiteUnitExecutionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        version = validate_sqlite_connection(connection)
        if version < 3:
            raise SchemaFeatureUnavailableError(
                "UnitExecution persistence requires SQLite schema version 3"
            )
        self._connection = connection

    def get(self, identity: UnitExecutionId) -> UnitExecution | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, processing_run_id, processing_unit_id,
                       configuration, state, outcome_kind, outcome_detail,
                       retry_of, cancelled_from, recovery_of
                FROM unit_executions
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return self._restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(f"could not read UnitExecution: {error}") from error

    def save(self, record: UnitExecution) -> None:
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _write_unit_execution_snapshot(self._connection, record)
            self._commit()
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(f"could not persist UnitExecution: {error}") from error
        except Exception:
            self._rollback()
            raise

    def all(self) -> tuple[UnitExecution, ...]:
        try:
            rows = self._connection.execute(
                """
                SELECT identity, processing_run_id, processing_unit_id,
                       configuration, state, outcome_kind, outcome_detail,
                       retry_of, cancelled_from, recovery_of
                FROM unit_executions
                ORDER BY rowid
                """
            ).fetchall()
            return tuple(self._restore(row) for row in rows)
        except sqlite3.Error as error:
            raise PersistenceError(f"could not list UnitExecutions: {error}") from error

    def _restore(self, row: tuple[object, ...]) -> UnitExecution:
        identity = UnitExecutionId(row[0])
        outcome = (
            ExecutionOutcome(kind=OutcomeKind(row[5]), detail=row[6])
            if row[5] is not None
            else None
        )
        return UnitExecution(
            identity=identity,
            run_id=ProcessingRunId(row[1]),
            unit_id=ProcessingUnitId(row[2]),
            input_references=tuple(
                InputReference(value)
                for value in self._child_values(
                    "unit_execution_inputs", "input_reference", identity
                )
            ),
            configuration=(
                ConfigurationReference(row[3]) if row[3] is not None else None
            ),
            capabilities=tuple(
                CapabilityReference(value)
                for value in self._child_values(
                    "unit_execution_capabilities", "capability", identity
                )
            ),
            plugins=tuple(
                PluginReference(value)
                for value in self._child_values(
                    "unit_execution_plugins", "plugin_reference", identity
                )
            ),
            state=ProcessingState(row[4]),
            outcome=outcome,
            result_references=tuple(
                DomainResultId(value)
                for value in self._child_values(
                    "unit_execution_results", "domain_result_id", identity
                )
            ),
            failure_references=tuple(
                FailureId(value)
                for value in self._child_values(
                    "unit_execution_failures", "failure_id", identity
                )
            ),
            diagnostic_references=tuple(
                DiagnosticId(value)
                for value in self._child_values(
                    "unit_execution_diagnostics", "diagnostic_id", identity
                )
            ),
            retry_of=UnitExecutionId(row[7]) if row[7] is not None else None,
            cancelled_from=(
                UnitExecutionId(row[8]) if row[8] is not None else None
            ),
            recovery_of=UnitExecutionId(row[9]) if row[9] is not None else None,
        )

    def _child_values(
        self, table: str, value_column: str, identity: UnitExecutionId
    ) -> tuple[str, ...]:
        rows = self._connection.execute(
            f"""
            SELECT ordinal, {value_column}
            FROM {table}
            WHERE unit_execution_id = ?
            ORDER BY ordinal
            """,
            (identity.value,),
        ).fetchall()
        if tuple(row[0] for row in rows) != tuple(range(len(rows))):
            raise PersistenceError(f"UnitExecution child ordering is corrupt: {table}")
        return tuple(row[1] for row in rows)

    def _commit(self) -> None:
        self._connection.execute("COMMIT")

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _optional_value(reference: object | None) -> str | None:
    return reference.value if reference is not None else None


def _insert_unit_execution_snapshot(
    connection: sqlite3.Connection, record: UnitExecution
) -> None:
    """Insert one complete snapshot without owning a transaction."""

    _write_unit_execution_snapshot(connection, record, replace_existing=False)


def _write_unit_execution_snapshot(
    connection: sqlite3.Connection,
    record: UnitExecution,
    *,
    replace_existing: bool = True,
) -> None:
    """Write one complete snapshot without owning a transaction."""

    outcome_kind = record.outcome.kind.value if record.outcome is not None else None
    outcome_detail = record.outcome.detail if record.outcome is not None else None
    conflict_clause = (
        """
            ON CONFLICT(identity) DO UPDATE SET
                processing_run_id = excluded.processing_run_id,
                processing_unit_id = excluded.processing_unit_id,
                configuration = excluded.configuration,
                state = excluded.state,
                outcome_kind = excluded.outcome_kind,
                outcome_detail = excluded.outcome_detail,
                retry_of = excluded.retry_of,
                cancelled_from = excluded.cancelled_from,
                recovery_of = excluded.recovery_of
        """
        if replace_existing
        else ""
    )
    connection.execute(
        f"""
        INSERT INTO unit_executions(
            identity, processing_run_id, processing_unit_id,
            configuration, state, outcome_kind, outcome_detail,
            retry_of, cancelled_from, recovery_of
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        {conflict_clause}
        """,
        (
            record.identity.value,
            record.run_id.value,
            record.unit_id.value,
            _optional_value(record.configuration),
            record.state.value,
            outcome_kind,
            outcome_detail,
            _optional_value(record.retry_of),
            _optional_value(record.cancelled_from),
            _optional_value(record.recovery_of),
        ),
    )
    if replace_existing:
        for table, _ in _CHILD_TABLES:
            connection.execute(
                f"DELETE FROM {table} WHERE unit_execution_id = ?",
                (record.identity.value,),
            )
    _insert_unit_execution_children(
        connection, "unit_execution_inputs", "input_reference", record,
        tuple(item.value for item in record.input_references),
    )
    _insert_unit_execution_children(
        connection, "unit_execution_capabilities", "capability", record,
        tuple(item.value for item in record.capabilities),
    )
    _insert_unit_execution_children(
        connection, "unit_execution_plugins", "plugin_reference", record,
        tuple(item.value for item in record.plugins),
    )
    _insert_unit_execution_children(
        connection, "unit_execution_results", "domain_result_id", record,
        tuple(item.value for item in record.result_references),
    )
    _insert_unit_execution_children(
        connection, "unit_execution_failures", "failure_id", record,
        tuple(item.value for item in record.failure_references),
    )
    _insert_unit_execution_children(
        connection, "unit_execution_diagnostics", "diagnostic_id", record,
        tuple(item.value for item in record.diagnostic_references),
    )


def _insert_unit_execution_children(
    connection: sqlite3.Connection,
    table: str,
    value_column: str,
    record: UnitExecution,
    values: tuple[str, ...],
) -> None:
    connection.executemany(
        f"""
        INSERT INTO {table}(unit_execution_id, ordinal, {value_column})
        VALUES (?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, value)
            for ordinal, value in enumerate(values)
        ),
    )
