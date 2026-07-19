"""Approved durable persistence vertical slices."""

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
    UnsupportedSchemaVersionError,
)
from .domain_results import SQLiteDomainResultReferenceRepository
from .execution_commands import SQLiteExecutionCommandPersistence
from .failures import SQLiteFailureRepository
from .processing_units import SQLiteProcessingUnitRepository
from .processing_runs import SQLiteProcessingRunRepository
from .provider_transcripts import SQLiteProviderTranscriptResultRepository
from .transcript_segments import SQLiteTranscriptSegmentRepository
from .unit_executions import SQLiteUnitExecutionRepository
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
    "SQLiteExecutionCommandPersistence",
    "SQLiteDomainResultReferenceRepository",
    "SQLiteFailureRepository",
    "SQLiteProcessingUnitRepository",
    "SQLiteProcessingRunRepository",
    "SQLiteProviderTranscriptResultRepository",
    "SQLiteTranscriptSegmentRepository",
    "SQLiteUnitExecutionRepository",
    "UnsupportedSchemaVersionError",
    "initialize_sqlite_database",
    "migrate_sqlite_database",
    "open_sqlite_database",
]
