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
from .readiness_evaluation import (
    SQLiteReadinessEvaluationCommandPersistence,
    SQLiteTranscriptReadinessEvaluationRepository,
)
from .subtitle_candidate import (
    SQLiteSubtitleCandidateCommandPersistence,
    SQLiteSubtitleCandidateRepository,
)
from .subtitle_reading import (
    SQLiteSubtitleReadingCommandPersistence,
    SQLiteSubtitleReadingRevisionRepository,
)
from .subtitle_time import (
    SQLiteSubtitleTimeCommandPersistence,
    SQLiteSubtitleTimeRevisionRepository,
)
from .subtitle_decision_application import (
    SQLiteSubtitleDecisionRevisionCommandPersistence,
    SQLiteSubtitleDecisionRevisionRepository,
)
from .subtitle_approved_assembly import (
    SQLiteSubtitleApprovedDocumentCommandPersistence,
    SQLiteSubtitleApprovedDocumentRepository,
)
from .subtitle_srt_artifact import (
    SQLiteSubtitleSrtArtifactCommandPersistence,
    SQLiteSubtitleSrtArtifactRepository,
)
from .subtitle_srt_materialization import (
    SQLiteSubtitleSrtMaterializationCommandPersistence,
    SQLiteSubtitleSrtMaterializationRepository,
)
from .lecture_analysis_input import (
    SQLiteEligibleAnalysisInputCommandPersistence,
    SQLiteEligibleAnalysisInputRepository,
)
from .analysis_finding import (
    SQLiteAnalysisFindingCommandPersistence,
    SQLiteAnalysisFindingRepository,
)
from .lecture_segment import (
    SQLiteLectureSegmentCommandPersistence,
    SQLiteLectureSegmentRepository,
)
from .edit_candidate import (
    SQLiteEditCandidateCommandPersistence,
    SQLiteEditCandidateRepository,
)
from .subtitle_final_subtitle import (
    SQLiteSubtitleFinalSubtitleCommandPersistence,
    SQLiteSubtitleFinalSubtitleRepository,
)
from .subtitle_review_decision import (
    SQLiteSubtitleReviewDecisionCommandPersistence,
    SQLiteSubtitleReviewDecisionRepository,
)
from .subtitle_review_preparation import (
    SQLiteSubtitleReviewPreparationCommandPersistence,
    SQLiteSubtitleReviewPreparationRepository,
)
from .subtitle_validation import (
    SQLiteSubtitleValidationCommandPersistence,
    SQLiteSubtitleValidationRepository,
)
from .subtitle_intake import (
    SQLiteSubtitleIntakeCommandPersistence,
    SQLiteSubtitleTranscriptIntakeRepository,
)
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
    "SQLiteReadinessEvaluationCommandPersistence",
    "SQLiteTranscriptReadinessEvaluationRepository",
    "SQLiteSubtitleCandidateCommandPersistence",
    "SQLiteSubtitleCandidateRepository",
    "SQLiteSubtitleReadingCommandPersistence",
    "SQLiteSubtitleReadingRevisionRepository",
    "SQLiteSubtitleTimeCommandPersistence",
    "SQLiteSubtitleTimeRevisionRepository",
    "SQLiteSubtitleDecisionRevisionCommandPersistence",
    "SQLiteSubtitleDecisionRevisionRepository",
    "SQLiteSubtitleApprovedDocumentCommandPersistence",
    "SQLiteSubtitleApprovedDocumentRepository",
    "SQLiteSubtitleSrtArtifactCommandPersistence",
    "SQLiteSubtitleSrtArtifactRepository",
    "SQLiteSubtitleSrtMaterializationCommandPersistence",
    "SQLiteSubtitleSrtMaterializationRepository",
    "SQLiteEligibleAnalysisInputCommandPersistence",
    "SQLiteEligibleAnalysisInputRepository",
    "SQLiteAnalysisFindingCommandPersistence",
    "SQLiteAnalysisFindingRepository",
    "SQLiteLectureSegmentCommandPersistence",
    "SQLiteLectureSegmentRepository",
    "SQLiteEditCandidateCommandPersistence",
    "SQLiteEditCandidateRepository",
    "SQLiteSubtitleFinalSubtitleCommandPersistence",
    "SQLiteSubtitleFinalSubtitleRepository",
    "SQLiteSubtitleReviewDecisionCommandPersistence",
    "SQLiteSubtitleReviewDecisionRepository",
    "SQLiteSubtitleReviewPreparationCommandPersistence",
    "SQLiteSubtitleReviewPreparationRepository",
    "SQLiteSubtitleValidationCommandPersistence",
    "SQLiteSubtitleValidationRepository",
    "SQLiteSubtitleIntakeCommandPersistence",
    "SQLiteSubtitleTranscriptIntakeRepository",
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
