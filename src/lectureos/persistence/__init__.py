"""Approved durable persistence vertical slices."""

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
    UnsupportedSchemaVersionError,
)
from .processing_units import SQLiteProcessingUnitRepository
from .processing_runs import SQLiteProcessingRunRepository
from .sqlite import (
    SQLITE_SCHEMA_VERSION,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)

__all__ = [
    "PersistenceError",
    "PersistenceIdentityCollisionError",
    "SchemaFeatureUnavailableError",
    "SQLITE_SCHEMA_VERSION",
    "SQLiteProcessingUnitRepository",
    "SQLiteProcessingRunRepository",
    "UnsupportedSchemaVersionError",
    "initialize_sqlite_database",
    "migrate_sqlite_database",
    "open_sqlite_database",
]
