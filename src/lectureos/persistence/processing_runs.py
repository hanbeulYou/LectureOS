"""Mutable-snapshot SQLite repository for the exact ProcessingRun model."""

from __future__ import annotations

import sqlite3

from lectureos.execution.identities import (
    ConfigurationReference,
    DomainResultId,
    FailureId,
    InputReference,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import ExecutionIntent, ProcessingRun, ProcessingState

from .errors import PersistenceError, SchemaFeatureUnavailableError
from .sqlite import validate_sqlite_connection

_CHILD_TABLES = (
    ("processing_run_inputs", "input_reference"),
    ("processing_run_upstream_results", "domain_result_id"),
    ("processing_run_units", "processing_unit_id"),
    ("processing_run_unit_executions", "unit_execution_id"),
    ("processing_run_results", "domain_result_id"),
    ("processing_run_failures", "failure_id"),
)


class SQLiteProcessingRunRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        version = validate_sqlite_connection(connection)
        if version < 2:
            raise SchemaFeatureUnavailableError(
                "ProcessingRun persistence requires SQLite schema version 2"
            )
        self._connection = connection

    def get(self, identity: ProcessingRunId) -> ProcessingRun | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, intent_purpose, intent_retry_of,
                       intent_reprocessing_of, working_context, configuration,
                       state, reprocessing_of
                FROM processing_runs
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return self._restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(f"could not read ProcessingRun: {error}") from error

    def save(self, record: ProcessingRun) -> None:
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _write_processing_run_snapshot(self._connection, record)
            self._commit()
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(f"could not persist ProcessingRun: {error}") from error
        except Exception:
            self._rollback()
            raise

    def all(self) -> tuple[ProcessingRun, ...]:
        try:
            rows = self._connection.execute(
                """
                SELECT identity, intent_purpose, intent_retry_of,
                       intent_reprocessing_of, working_context, configuration,
                       state, reprocessing_of
                FROM processing_runs
                ORDER BY rowid
                """
            ).fetchall()
            return tuple(self._restore(row) for row in rows)
        except sqlite3.Error as error:
            raise PersistenceError(f"could not list ProcessingRuns: {error}") from error

    def _restore(self, row: tuple[object, ...]) -> ProcessingRun:
        identity = ProcessingRunId(row[0])
        return ProcessingRun(
            identity=identity,
            intent=ExecutionIntent(
                purpose=row[1],
                retry_of=UnitExecutionId(row[2]) if row[2] is not None else None,
                reprocessing_of=(
                    ProcessingRunId(row[3]) if row[3] is not None else None
                ),
            ),
            working_context=WorkingContextReference(row[4]),
            input_references=tuple(
                InputReference(value)
                for value in self._child_values(
                    "processing_run_inputs", "input_reference", identity
                )
            ),
            upstream_results=tuple(
                DomainResultId(value)
                for value in self._child_values(
                    "processing_run_upstream_results", "domain_result_id", identity
                )
            ),
            configuration=(
                ConfigurationReference(row[5]) if row[5] is not None else None
            ),
            unit_references=tuple(
                ProcessingUnitId(value)
                for value in self._child_values(
                    "processing_run_units", "processing_unit_id", identity
                )
            ),
            unit_execution_references=tuple(
                UnitExecutionId(value)
                for value in self._child_values(
                    "processing_run_unit_executions", "unit_execution_id", identity
                )
            ),
            state=ProcessingState(row[6]),
            result_references=tuple(
                DomainResultId(value)
                for value in self._child_values(
                    "processing_run_results", "domain_result_id", identity
                )
            ),
            failure_references=tuple(
                FailureId(value)
                for value in self._child_values(
                    "processing_run_failures", "failure_id", identity
                )
            ),
            reprocessing_of=(
                ProcessingRunId(row[7]) if row[7] is not None else None
            ),
        )

    def _child_values(
        self, table: str, value_column: str, identity: ProcessingRunId
    ) -> tuple[str, ...]:
        rows = self._connection.execute(
            f"""
            SELECT ordinal, {value_column}
            FROM {table}
            WHERE processing_run_id = ?
            ORDER BY ordinal
            """,
            (identity.value,),
        ).fetchall()
        if tuple(row[0] for row in rows) != tuple(range(len(rows))):
            raise PersistenceError(f"ProcessingRun child ordering is corrupt: {table}")
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


def _write_processing_run_snapshot(
    connection: sqlite3.Connection, record: ProcessingRun
) -> None:
    """Write one complete snapshot without owning a transaction."""

    connection.execute(
        """
        INSERT INTO processing_runs(
            identity, intent_purpose, intent_retry_of,
            intent_reprocessing_of, working_context, configuration,
            state, reprocessing_of
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(identity) DO UPDATE SET
            intent_purpose = excluded.intent_purpose,
            intent_retry_of = excluded.intent_retry_of,
            intent_reprocessing_of = excluded.intent_reprocessing_of,
            working_context = excluded.working_context,
            configuration = excluded.configuration,
            state = excluded.state,
            reprocessing_of = excluded.reprocessing_of
        """,
        (
            record.identity.value,
            record.intent.purpose,
            _optional_value(record.intent.retry_of),
            _optional_value(record.intent.reprocessing_of),
            record.working_context.value,
            _optional_value(record.configuration),
            record.state.value,
            _optional_value(record.reprocessing_of),
        ),
    )
    for table, _ in _CHILD_TABLES:
        connection.execute(
            f"DELETE FROM {table} WHERE processing_run_id = ?",
            (record.identity.value,),
        )
    _insert_processing_run_children(
        connection, "processing_run_inputs", "input_reference", record,
        tuple(item.value for item in record.input_references),
    )
    _insert_processing_run_children(
        connection, "processing_run_upstream_results", "domain_result_id", record,
        tuple(item.value for item in record.upstream_results),
    )
    _insert_processing_run_children(
        connection, "processing_run_units", "processing_unit_id", record,
        tuple(item.value for item in record.unit_references),
    )
    _insert_processing_run_children(
        connection, "processing_run_unit_executions", "unit_execution_id", record,
        tuple(item.value for item in record.unit_execution_references),
    )
    _insert_processing_run_children(
        connection, "processing_run_results", "domain_result_id", record,
        tuple(item.value for item in record.result_references),
    )
    _insert_processing_run_children(
        connection, "processing_run_failures", "failure_id", record,
        tuple(item.value for item in record.failure_references),
    )


def _insert_processing_run_children(
    connection: sqlite3.Connection,
    table: str,
    value_column: str,
    record: ProcessingRun,
    values: tuple[str, ...],
) -> None:
    connection.executemany(
        f"""
        INSERT INTO {table}(processing_run_id, ordinal, {value_column})
        VALUES (?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, value)
            for ordinal, value in enumerate(values)
        ),
    )
