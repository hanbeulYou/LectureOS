"""Explicit SQLite lifecycle with approved single-step schema migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .errors import PersistenceError, UnsupportedSchemaVersionError

SQLITE_SCHEMA_VERSION = 3
_SUPPORTED_SCHEMA_VERSIONS = (1, 2, 3)

_V1_TABLE_STATEMENTS = (
    """CREATE TABLE schema_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    version INTEGER NOT NULL
)""",
    """CREATE TABLE processing_units (
    identity TEXT PRIMARY KEY,
    purpose TEXT NOT NULL CHECK (length(trim(purpose)) > 0),
    independently_retryable INTEGER NOT NULL
        CHECK (independently_retryable IN (0, 1))
)""",
    """CREATE TABLE processing_unit_dependencies (
    processing_unit_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    dependency_id TEXT NOT NULL,
    PRIMARY KEY (processing_unit_id, ordinal),
    FOREIGN KEY (processing_unit_id) REFERENCES processing_units(identity)
)""",
    """CREATE TABLE processing_unit_capabilities (
    processing_unit_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    capability TEXT NOT NULL,
    PRIMARY KEY (processing_unit_id, ordinal),
    FOREIGN KEY (processing_unit_id) REFERENCES processing_units(identity)
)""",
    """CREATE TABLE processing_unit_result_kinds (
    processing_unit_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    result_kind TEXT NOT NULL,
    PRIMARY KEY (processing_unit_id, ordinal),
    FOREIGN KEY (processing_unit_id) REFERENCES processing_units(identity)
)""",
)

_V2_ADDITION_STATEMENTS = (
    """CREATE TABLE processing_runs (
    identity TEXT PRIMARY KEY,
    intent_purpose TEXT NOT NULL CHECK (length(trim(intent_purpose)) > 0),
    intent_retry_of TEXT,
    intent_reprocessing_of TEXT,
    working_context TEXT NOT NULL,
    configuration TEXT,
    state TEXT NOT NULL CHECK (
        state IN ('pending', 'running', 'completed', 'failed', 'cancelled')
    ),
    reprocessing_of TEXT,
    CHECK (intent_retry_of IS NULL OR intent_reprocessing_of IS NULL)
)""",
    """CREATE TABLE processing_run_inputs (
    processing_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    input_reference TEXT NOT NULL,
    PRIMARY KEY (processing_run_id, ordinal),
    FOREIGN KEY (processing_run_id) REFERENCES processing_runs(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE processing_run_upstream_results (
    processing_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    domain_result_id TEXT NOT NULL,
    PRIMARY KEY (processing_run_id, ordinal),
    FOREIGN KEY (processing_run_id) REFERENCES processing_runs(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE processing_run_units (
    processing_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    processing_unit_id TEXT NOT NULL,
    PRIMARY KEY (processing_run_id, ordinal),
    FOREIGN KEY (processing_run_id) REFERENCES processing_runs(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE processing_run_unit_executions (
    processing_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    unit_execution_id TEXT NOT NULL,
    PRIMARY KEY (processing_run_id, ordinal),
    FOREIGN KEY (processing_run_id) REFERENCES processing_runs(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE processing_run_results (
    processing_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    domain_result_id TEXT NOT NULL,
    PRIMARY KEY (processing_run_id, ordinal),
    FOREIGN KEY (processing_run_id) REFERENCES processing_runs(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE processing_run_failures (
    processing_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    failure_id TEXT NOT NULL,
    PRIMARY KEY (processing_run_id, ordinal),
    FOREIGN KEY (processing_run_id) REFERENCES processing_runs(identity)
        ON DELETE CASCADE
)""",
)

_V3_ADDITION_STATEMENTS = (
    """CREATE TABLE unit_executions (
    identity TEXT PRIMARY KEY,
    processing_run_id TEXT NOT NULL,
    processing_unit_id TEXT NOT NULL,
    configuration TEXT,
    state TEXT NOT NULL CHECK (
        state IN ('pending', 'running', 'completed', 'failed', 'cancelled')
    ),
    outcome_kind TEXT CHECK (
        outcome_kind IS NULL OR outcome_kind IN (
            'domain_result_generated', 'partial_result', 'no_result',
            'validation_failure', 'recoverable_failure',
            'non_recoverable_condition'
        )
    ),
    outcome_detail TEXT,
    retry_of TEXT,
    cancelled_from TEXT,
    recovery_of TEXT,
    CHECK (outcome_detail IS NULL OR outcome_kind IS NOT NULL)
)""",
    """CREATE TABLE unit_execution_inputs (
    unit_execution_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    input_reference TEXT NOT NULL,
    PRIMARY KEY (unit_execution_id, ordinal),
    FOREIGN KEY (unit_execution_id) REFERENCES unit_executions(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE unit_execution_capabilities (
    unit_execution_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    capability TEXT NOT NULL,
    PRIMARY KEY (unit_execution_id, ordinal),
    FOREIGN KEY (unit_execution_id) REFERENCES unit_executions(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE unit_execution_plugins (
    unit_execution_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    plugin_reference TEXT NOT NULL,
    PRIMARY KEY (unit_execution_id, ordinal),
    FOREIGN KEY (unit_execution_id) REFERENCES unit_executions(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE unit_execution_results (
    unit_execution_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    domain_result_id TEXT NOT NULL,
    PRIMARY KEY (unit_execution_id, ordinal),
    FOREIGN KEY (unit_execution_id) REFERENCES unit_executions(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE unit_execution_failures (
    unit_execution_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    failure_id TEXT NOT NULL,
    PRIMARY KEY (unit_execution_id, ordinal),
    FOREIGN KEY (unit_execution_id) REFERENCES unit_executions(identity)
        ON DELETE CASCADE
)""",
    """CREATE TABLE unit_execution_diagnostics (
    unit_execution_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    diagnostic_id TEXT NOT NULL,
    PRIMARY KEY (unit_execution_id, ordinal),
    FOREIGN KEY (unit_execution_id) REFERENCES unit_executions(identity)
        ON DELETE CASCADE
)""",
)

_V1_EXPECTED_COLUMNS = {
    "schema_metadata": (
        ("singleton", "INTEGER", 0, 1),
        ("version", "INTEGER", 1, 0),
    ),
    "processing_units": (
        ("identity", "TEXT", 0, 1),
        ("purpose", "TEXT", 1, 0),
        ("independently_retryable", "INTEGER", 1, 0),
    ),
    "processing_unit_dependencies": (
        ("processing_unit_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("dependency_id", "TEXT", 1, 0),
    ),
    "processing_unit_capabilities": (
        ("processing_unit_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("capability", "TEXT", 1, 0),
    ),
    "processing_unit_result_kinds": (
        ("processing_unit_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("result_kind", "TEXT", 1, 0),
    ),
}

_V2_EXPECTED_COLUMNS = {
    **_V1_EXPECTED_COLUMNS,
    "processing_runs": (
        ("identity", "TEXT", 0, 1),
        ("intent_purpose", "TEXT", 1, 0),
        ("intent_retry_of", "TEXT", 0, 0),
        ("intent_reprocessing_of", "TEXT", 0, 0),
        ("working_context", "TEXT", 1, 0),
        ("configuration", "TEXT", 0, 0),
        ("state", "TEXT", 1, 0),
        ("reprocessing_of", "TEXT", 0, 0),
    ),
    "processing_run_inputs": (
        ("processing_run_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("input_reference", "TEXT", 1, 0),
    ),
    "processing_run_upstream_results": (
        ("processing_run_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("domain_result_id", "TEXT", 1, 0),
    ),
    "processing_run_units": (
        ("processing_run_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("processing_unit_id", "TEXT", 1, 0),
    ),
    "processing_run_unit_executions": (
        ("processing_run_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("unit_execution_id", "TEXT", 1, 0),
    ),
    "processing_run_results": (
        ("processing_run_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("domain_result_id", "TEXT", 1, 0),
    ),
    "processing_run_failures": (
        ("processing_run_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("failure_id", "TEXT", 1, 0),
    ),
}

_V3_EXPECTED_COLUMNS = {
    **_V2_EXPECTED_COLUMNS,
    "unit_executions": (
        ("identity", "TEXT", 0, 1),
        ("processing_run_id", "TEXT", 1, 0),
        ("processing_unit_id", "TEXT", 1, 0),
        ("configuration", "TEXT", 0, 0),
        ("state", "TEXT", 1, 0),
        ("outcome_kind", "TEXT", 0, 0),
        ("outcome_detail", "TEXT", 0, 0),
        ("retry_of", "TEXT", 0, 0),
        ("cancelled_from", "TEXT", 0, 0),
        ("recovery_of", "TEXT", 0, 0),
    ),
    "unit_execution_inputs": (
        ("unit_execution_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("input_reference", "TEXT", 1, 0),
    ),
    "unit_execution_capabilities": (
        ("unit_execution_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("capability", "TEXT", 1, 0),
    ),
    "unit_execution_plugins": (
        ("unit_execution_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("plugin_reference", "TEXT", 1, 0),
    ),
    "unit_execution_results": (
        ("unit_execution_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("domain_result_id", "TEXT", 1, 0),
    ),
    "unit_execution_failures": (
        ("unit_execution_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("failure_id", "TEXT", 1, 0),
    ),
    "unit_execution_diagnostics": (
        ("unit_execution_id", "TEXT", 1, 1),
        ("ordinal", "INTEGER", 1, 2),
        ("diagnostic_id", "TEXT", 1, 0),
    ),
}


def initialize_sqlite_database(database_path: str | Path) -> sqlite3.Connection:
    """Create the latest schema for a new path; validate existing databases."""

    path = _validate_database_path(database_path)
    is_new = not path.exists()
    if not is_new and not path.is_file():
        raise PersistenceError("SQLite database path must be a file")
    connection = _connect(path)
    try:
        if is_new:
            _initialize_latest_schema(connection)
        _validate_initialized_connection(connection)
    except Exception:
        connection.close()
        raise
    return connection


def open_sqlite_database(database_path: str | Path) -> sqlite3.Connection:
    """Open and validate a supported database without creating or migrating it."""

    path = _validate_database_path(database_path)
    if not path.is_file():
        raise PersistenceError("SQLite database must already be initialized")
    connection = _connect(path)
    try:
        _validate_initialized_connection(connection)
    except Exception:
        connection.close()
        raise
    return connection


def migrate_sqlite_database(
    database_path: str | Path, target_version: int = SQLITE_SCHEMA_VERSION
) -> None:
    """Explicitly perform one approved migration step or validate a no-op target."""

    if target_version not in (2, 3):
        raise PersistenceError(f"unsupported SQLite migration target: {target_version}")
    path = _validate_database_path(database_path)
    if not path.is_file():
        raise PersistenceError("SQLite database must already exist for migration")
    connection = _connect(path)
    try:
        current_version = _validate_initialized_connection(connection)
        if current_version == target_version:
            return
        if current_version == 1 and target_version == 2:
            _migrate_v1_to_v2(connection)
            return
        if current_version == 2 and target_version == 3:
            _migrate_v2_to_v3(connection)
            return
        raise PersistenceError(
            f"unsupported SQLite migration: {current_version} to {target_version}"
        )
    finally:
        connection.close()


def validate_sqlite_connection(connection: sqlite3.Connection) -> int:
    """Validate a caller-owned connection and return its supported schema version."""

    return _validate_initialized_connection(connection)


def _validate_database_path(database_path: str | Path) -> Path:
    if isinstance(database_path, str) and (
        database_path == ":memory:" or database_path.startswith("file:")
    ):
        raise PersistenceError("SQLite memory and URI paths are not supported")
    try:
        path = Path(database_path)
    except TypeError:
        raise PersistenceError("SQLite database path must be path-like") from None
    if not path.is_absolute():
        raise PersistenceError("SQLite database path must be absolute")
    if not path.parent.exists() or not path.parent.is_dir():
        raise PersistenceError("SQLite database parent directory must exist")
    return path


def _connect(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
            connection.close()
            raise PersistenceError("SQLite foreign key enforcement is unavailable")
        return connection
    except PersistenceError:
        raise
    except sqlite3.Error as error:
        raise PersistenceError(f"could not open SQLite database: {error}") from error


def _initialize_latest_schema(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN")
        for statement in (
            *_V1_TABLE_STATEMENTS,
            *_V2_ADDITION_STATEMENTS,
            *_V3_ADDITION_STATEMENTS,
        ):
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_metadata(singleton, version) VALUES (1, ?)",
            (SQLITE_SCHEMA_VERSION,),
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not initialize SQLite schema: {error}") from error


def _migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V2_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 2 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _migrate_v2_to_v3(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in _V3_ADDITION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "UPDATE schema_metadata SET version = 3 WHERE singleton = 1"
        )
        _validate_initialized_connection(connection)
        _commit(connection)
    except PersistenceError:
        _rollback(connection)
        raise
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not migrate SQLite schema: {error}") from error


def _validate_initialized_connection(connection: sqlite3.Connection) -> int:
    try:
        if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
            raise PersistenceError("SQLite foreign key enforcement must be enabled")
        metadata_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_metadata'"
        ).fetchone()
        if metadata_exists is None:
            raise PersistenceError("SQLite database is not initialized")
        versions = connection.execute(
            "SELECT singleton, version FROM schema_metadata"
        ).fetchall()
        if len(versions) != 1 or versions[0][0] != 1:
            raise PersistenceError("SQLite schema version marker is malformed")
        version = versions[0][1]
        if version not in _SUPPORTED_SCHEMA_VERSIONS:
            raise UnsupportedSchemaVersionError(
                f"unsupported SQLite schema version: {version}"
            )
        _validate_schema_shape(connection, version)
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise PersistenceError("SQLite database contains foreign key violations")
        return version
    except (PersistenceError, UnsupportedSchemaVersionError):
        raise
    except sqlite3.Error as error:
        raise PersistenceError(f"could not validate SQLite schema: {error}") from error


def _validate_schema_shape(connection: sqlite3.Connection, version: int) -> None:
    expected_columns = {
        1: _V1_EXPECTED_COLUMNS,
        2: _V2_EXPECTED_COLUMNS,
        3: _V3_EXPECTED_COLUMNS,
    }[version]
    for table, expected in expected_columns.items():
        actual = tuple(
            (row[1], row[2].upper(), row[3], row[5])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        )
        if actual != expected:
            raise PersistenceError(f"SQLite schema table is malformed: {table}")
    _validate_v1_foreign_keys(connection)
    if version == 2:
        _validate_v2_foreign_keys(connection)
    elif version == 3:
        _validate_v2_foreign_keys(connection)
        _validate_v3_foreign_keys(connection)


def _validate_v1_foreign_keys(connection: sqlite3.Connection) -> None:
    for table in (
        "processing_unit_dependencies",
        "processing_unit_capabilities",
        "processing_unit_result_kinds",
    ):
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        if not any(
            row[2] == "processing_units"
            and row[3] == "processing_unit_id"
            and row[4] == "identity"
            for row in foreign_keys
        ):
            raise PersistenceError(f"SQLite schema foreign key is missing: {table}")


def _validate_v2_foreign_keys(connection: sqlite3.Connection) -> None:
    for table in (
        "processing_run_inputs",
        "processing_run_upstream_results",
        "processing_run_units",
        "processing_run_unit_executions",
        "processing_run_results",
        "processing_run_failures",
    ):
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        if not any(
            row[2] == "processing_runs"
            and row[3] == "processing_run_id"
            and row[4] == "identity"
            and row[6].upper() == "CASCADE"
            for row in foreign_keys
        ):
            raise PersistenceError(f"SQLite schema foreign key is missing: {table}")


def _validate_v3_foreign_keys(connection: sqlite3.Connection) -> None:
    for table in (
        "unit_execution_inputs",
        "unit_execution_capabilities",
        "unit_execution_plugins",
        "unit_execution_results",
        "unit_execution_failures",
        "unit_execution_diagnostics",
    ):
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        if not any(
            row[2] == "unit_executions"
            and row[3] == "unit_execution_id"
            and row[4] == "identity"
            and row[6].upper() == "CASCADE"
            for row in foreign_keys
        ):
            raise PersistenceError(f"SQLite schema foreign key is missing: {table}")


def _commit(connection: sqlite3.Connection) -> None:
    connection.execute("COMMIT")


def _rollback(connection: sqlite3.Connection) -> None:
    if connection.in_transaction:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
