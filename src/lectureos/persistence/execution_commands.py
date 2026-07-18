"""SQLite-only atomic persistence for already-computed execution snapshots."""

from __future__ import annotations

import sqlite3

from lectureos.execution.models import Failure, ProcessingRun, UnitExecution

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .failures import _insert_failure_record
from .processing_runs import _write_processing_run_snapshot
from .sqlite import validate_sqlite_connection
from .unit_executions import (
    _insert_unit_execution_snapshot,
    _write_unit_execution_snapshot,
)


class SQLiteExecutionCommandPersistence:
    """Persist command outputs without deciding execution lifecycle transitions."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        version = validate_sqlite_connection(connection)
        if version < 3:
            raise SchemaFeatureUnavailableError(
                "atomic UnitExecution start persistence requires SQLite schema version 3"
            )
        self._connection = connection
        self._schema_version = version

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

    def persist_recorded_failure(
        self,
        *,
        failure: Failure,
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None:
        if self._schema_version < 4:
            raise SchemaFeatureUnavailableError(
                "atomic Failure persistence requires SQLite schema version 4"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            self._validate_failure_linkage(failure, execution, run)
            if self._failure_exists(failure):
                raise PersistenceIdentityCollisionError(
                    "Failure identity already exists"
                )
            _insert_failure_record(self._connection, failure)
            _write_unit_execution_snapshot(self._connection, execution)
            _write_processing_run_snapshot(self._connection, run)
            self._commit()
        except PersistenceError:
            self._rollback_if_owned(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback_if_owned(transaction_started)
            if self._failure_exists_safely(failure):
                raise PersistenceIdentityCollisionError(
                    "Failure identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist atomic Failure record: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback_if_owned(transaction_started)
            raise PersistenceError(
                f"could not persist atomic Failure record: {error}"
            ) from error
        except Exception:
            self._rollback_if_owned(transaction_started)
            raise

    def persist_retried_execution(
        self,
        *,
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None:
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            self._validate_retry_linkage(execution, run)
            if self._execution_exists(execution):
                raise PersistenceIdentityCollisionError(
                    "UnitExecution identity already exists"
                )
            _insert_unit_execution_snapshot(self._connection, execution)
            _write_processing_run_snapshot(self._connection, run)
            self._commit()
        except PersistenceError:
            self._rollback_if_owned(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback_if_owned(transaction_started)
            if self._execution_exists_safely(execution):
                raise PersistenceIdentityCollisionError(
                    "UnitExecution identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist atomic UnitExecution retry: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback_if_owned(transaction_started)
            raise PersistenceError(
                f"could not persist atomic UnitExecution retry: {error}"
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

    @staticmethod
    def _validate_failure_linkage(
        failure: Failure,
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None:
        if failure.unit_execution_id != execution.identity:
            raise PersistenceError("Failure must reference the UnitExecution")
        if failure.run_id is not None and failure.run_id != run.identity:
            raise PersistenceError("Failure run must match ProcessingRun identity")
        if execution.run_id != run.identity:
            raise PersistenceError("UnitExecution run must match ProcessingRun identity")
        if failure.identity not in execution.failure_references:
            raise PersistenceError("UnitExecution must reference the Failure")
        if failure.identity not in run.failure_references:
            raise PersistenceError("ProcessingRun must reference the Failure")

    @staticmethod
    def _validate_retry_linkage(
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None:
        if execution.run_id != run.identity:
            raise PersistenceError("Retry UnitExecution run must match ProcessingRun")
        if execution.retry_of is None:
            raise PersistenceError("Retry UnitExecution must reference its source")
        if run.unit_execution_references.count(execution.identity) != 1:
            raise PersistenceError(
                "ProcessingRun must reference the Retry UnitExecution exactly once"
            )

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

    def _failure_exists(self, failure: Failure) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM failures WHERE identity = ?",
            (failure.identity.value,),
        ).fetchone() is not None

    def _failure_exists_safely(self, failure: Failure) -> bool:
        try:
            return self._failure_exists(failure)
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
