"""Approved durable persistence vertical slices."""

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    UnsupportedSchemaVersionError,
)
from .processing_units import SQLiteProcessingUnitRepository
from .sqlite import (
    SQLITE_SCHEMA_VERSION,
    initialize_sqlite_database,
    open_sqlite_database,
)

__all__ = [
    "PersistenceError",
    "PersistenceIdentityCollisionError",
    "SQLITE_SCHEMA_VERSION",
    "SQLiteProcessingUnitRepository",
    "UnsupportedSchemaVersionError",
    "initialize_sqlite_database",
    "open_sqlite_database",
]
