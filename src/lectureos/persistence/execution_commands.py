"""SQLite-only atomic persistence for already-computed execution snapshots."""

from __future__ import annotations

import sqlite3

from lectureos.execution.models import ProcessingRun, UnitExecution

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .processing_runs import _write_processing_run_snapshot
from .sqlite import validate_sqlite_connection
from .unit_executions import _insert_unit_execution_snapshot


class SQLiteExecutionCommandPersistence:
    """Persist command outputs without deciding execution lifecycle transitions."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        version = validate_sqlite_connection(connection)
        if version < 3:
            raise SchemaFeatureUnavailableError(
                "atomic UnitExecution start persistence requires SQLite schema version 3"
            )
        self._connection = connection

    def persist_started_execution(
        self,
        *,
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None:
        self._validate_linkage(execution, run)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._execution_exists(execution):
                raise PersistenceIdentityCollisionError(
                    "UnitExecution identity already exists"
                )
            _insert_unit_execution_snapshot(self._connection, execution)
            _write_processing_run_snapshot(self._connection, run)
            self._commit()
        except PersistenceIdentityCollisionError:
            self._rollback_if_owned(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback_if_owned(transaction_started)
            if self._execution_exists_safely(execution):
                raise PersistenceIdentityCollisionError(
                    "UnitExecution identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist atomic UnitExecution start: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback_if_owned(transaction_started)
            raise PersistenceError(
                f"could not persist atomic UnitExecution start: {error}"
            ) from error
        except Exception:
            self._rollback_if_owned(transaction_started)
            raise

    @staticmethod
    def _validate_linkage(execution: UnitExecution, run: ProcessingRun) -> None:
        if execution.run_id != run.identity:
            raise ValueError("UnitExecution run must match ProcessingRun identity")
        if execution.identity not in run.unit_execution_references:
            raise ValueError("ProcessingRun must reference the UnitExecution")

    def _execution_exists(self, execution: UnitExecution) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM unit_executions WHERE identity = ?",
            (execution.identity.value,),
        ).fetchone() is not None

    def _execution_exists_safely(self, execution: UnitExecution) -> bool:
        try:
            return self._execution_exists(execution)
        except sqlite3.Error:
            return False

    def _commit(self) -> None:
        self._connection.execute("COMMIT")

    def _rollback_if_owned(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
