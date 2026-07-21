"""Approved durable persistence vertical slices."""

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
    UnsupportedSchemaVersionError,
)
from .applicability_evaluation import (
    SQLiteApplicabilityEvaluationCommandPersistence,
    SQLiteTranscriptApplicabilityEvaluationRepository,
)
from .correction_candidates import SQLiteCorrectionCandidateRepository
from .current_selection import (
    SQLiteCurrentSelectionCommandPersistence,
    SQLiteTranscriptCurrentSelectionRepository,
)
from .corrected_transcript_revisions import (
    SQLiteCorrectedTranscriptRevisionRepository,
)
from .domain_results import SQLiteDomainResultReferenceRepository
from .execution_commands import SQLiteExecutionCommandPersistence
from .failures import SQLiteFailureRepository
from .processing_units import SQLiteProcessingUnitRepository
from .processing_runs import SQLiteProcessingRunRepository
from .provider_transcripts import SQLiteProviderTranscriptResultRepository
from .raw_transcripts import SQLiteRawTranscriptRepository
from .review_decision import (
    SQLiteReviewDecisionCommandPersistence,
    SQLiteTranscriptReviewDecisionRepository,
)
from .review_preparation import (
    SQLiteReviewCandidateReferenceRepository,
    SQLiteReviewContextRepository,
    SQLiteReviewItemRepository,
    SQLiteReviewPreparationCommandPersistence,
    SQLiteTranscriptReviewPreparationRepository,
)
from .transcript_commands import SQLiteTranscriptCommandPersistence
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
    "SQLiteApplicabilityEvaluationCommandPersistence",
    "SQLiteTranscriptApplicabilityEvaluationRepository",
    "SQLiteCurrentSelectionCommandPersistence",
    "SQLiteTranscriptCurrentSelectionRepository",
    "SQLiteCorrectionCandidateRepository",
    "SQLiteCorrectedTranscriptRevisionRepository",
    "SQLiteExecutionCommandPersistence",
    "SQLiteDomainResultReferenceRepository",
    "SQLiteFailureRepository",
    "SQLiteProcessingUnitRepository",
    "SQLiteProcessingRunRepository",
    "SQLiteProviderTranscriptResultRepository",
    "SQLiteRawTranscriptRepository",
    "SQLiteReviewDecisionCommandPersistence",
    "SQLiteTranscriptReviewDecisionRepository",
    "SQLiteReviewCandidateReferenceRepository",
    "SQLiteReviewContextRepository",
    "SQLiteReviewItemRepository",
    "SQLiteReviewPreparationCommandPersistence",
    "SQLiteTranscriptReviewPreparationRepository",
    "SQLiteTranscriptCommandPersistence",
    "SQLiteTranscriptSegmentRepository",
    "SQLiteUnitExecutionRepository",
    "UnsupportedSchemaVersionError",
    "initialize_sqlite_database",
    "migrate_sqlite_database",
    "open_sqlite_database",
]
