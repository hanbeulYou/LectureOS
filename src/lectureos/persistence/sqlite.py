"""Explicit SQLite lifecycle for the first durable repository slice."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .errors import PersistenceError, UnsupportedSchemaVersionError

SQLITE_SCHEMA_VERSION = 1

_SCHEMA_STATEMENTS = (
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
    "INSERT INTO schema_metadata(singleton, version) VALUES (1, 1)",
)

_EXPECTED_COLUMNS = {
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


def initialize_sqlite_database(database_path: str | Path) -> sqlite3.Connection:
    """Create version 1 only for a new path; otherwise validate without migration."""

    path = _validate_database_path(database_path)
    is_new = not path.exists()
    if not is_new and not path.is_file():
        raise PersistenceError("SQLite database path must be a file")
    connection = _connect(path)
    try:
        if is_new:
            _initialize_schema(connection)
        _validate_initialized_connection(connection)
    except Exception:
        connection.close()
        raise
    return connection


def open_sqlite_database(database_path: str | Path) -> sqlite3.Connection:
    """Open and validate an explicitly initialized database without creating it."""

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


def validate_sqlite_connection(connection: sqlite3.Connection) -> None:
    """Validate a caller-owned connection before a durable repository uses it."""

    _validate_initialized_connection(connection)


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


def _initialize_schema(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN")
        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.execute("COMMIT")
    except sqlite3.Error as error:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise PersistenceError(f"could not initialize SQLite schema: {error}") from error


def _validate_initialized_connection(connection: sqlite3.Connection) -> None:
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
        if version != SQLITE_SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError(
                f"unsupported SQLite schema version: {version}"
            )
        _validate_schema_shape(connection)
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise PersistenceError("SQLite database contains foreign key violations")
    except (PersistenceError, UnsupportedSchemaVersionError):
        raise
    except sqlite3.Error as error:
        raise PersistenceError(f"could not validate SQLite schema: {error}") from error


def _validate_schema_shape(connection: sqlite3.Connection) -> None:
    for table, expected in _EXPECTED_COLUMNS.items():
        actual = tuple(
            (row[1], row[2].upper(), row[3], row[5])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        )
        if actual != expected:
            raise PersistenceError(f"SQLite schema table is malformed: {table}")
    for table in _EXPECTED_COLUMNS:
        if table in ("schema_metadata", "processing_units"):
            continue
        foreign_keys = connection.execute(
            f"PRAGMA foreign_key_list({table})"
        ).fetchall()
        if not any(
            row[2] == "processing_units"
            and row[3] == "processing_unit_id"
            and row[4] == "identity"
            for row in foreign_keys
        ):
            raise PersistenceError(f"SQLite schema foreign key is missing: {table}")
