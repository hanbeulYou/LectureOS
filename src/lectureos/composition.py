"""Top-level construction of concrete LectureOS implementation graphs."""

from __future__ import annotations

import sqlite3

from lectureos.execution.service import ExecutionService
from lectureos.persistence import (
    SQLiteExecutionCommandPersistence,
    SQLiteFailureRepository,
    SQLiteProcessingRunRepository,
    SQLiteProcessingUnitRepository,
    SQLiteUnitExecutionRepository,
)


def compose_sqlite_atomic_start_execution_service(
    connection: sqlite3.Connection,
) -> ExecutionService:
    """Build the Start-capable SQLite execution slice on one caller connection."""

    runs = SQLiteProcessingRunRepository(connection)
    units = SQLiteProcessingUnitRepository(connection)
    executions = SQLiteUnitExecutionRepository(connection)
    atomic_start = SQLiteExecutionCommandPersistence(connection)
    return ExecutionService(
        runs=runs,
        units=units,
        executions=executions,
        atomic_start_persistence=atomic_start,
    )


def compose_sqlite_atomic_failure_execution_service(
    connection: sqlite3.Connection,
) -> ExecutionService:
    """Build the Start and terminal-Failure SQLite slice on one connection."""

    runs = SQLiteProcessingRunRepository(connection)
    units = SQLiteProcessingUnitRepository(connection)
    executions = SQLiteUnitExecutionRepository(connection)
    failures = SQLiteFailureRepository(connection)
    atomic_commands = SQLiteExecutionCommandPersistence(connection)
    return ExecutionService(
        runs=runs,
        units=units,
        executions=executions,
        failures=failures,
        atomic_start_persistence=atomic_commands,
        atomic_failure_persistence=atomic_commands,
    )
