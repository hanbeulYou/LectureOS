"""Top-level construction of concrete LectureOS implementation graphs."""

from __future__ import annotations

import sqlite3

from lectureos.application.transcript_correction_generation import (
    CorrectionGenerationPort,
    TranscriptCorrectionGenerationService,
)
from lectureos.application.transcript_applicability_evaluation import (
    TranscriptApplicabilityEvaluationService,
)
from lectureos.application.transcript_current_selection import (
    TranscriptCurrentSelectionService,
)
from lectureos.application.subtitle_transcript_intake import (
    SubtitleTranscriptIntakeService,
)
from lectureos.application.lecture_analysis_input import (
    LectureAnalysisInputService,
)
from lectureos.application.analysis_finding import (
    AnalysisFindingApplicationService,
)
from lectureos.application.lecture_segment import (
    LectureSegmentationApplicationService,
)
from lectureos.application.edit_candidate import (
    EditCandidateApplicationService,
)
from lectureos.application.edit_candidate_generation import (
    EditCandidateGenerationPort,
    EditCandidateGenerationService,
)
from lectureos.application.subtitle_candidate_generation import (
    SubtitleCandidateGenerationService,
)
from lectureos.application.subtitle_reading_representation import (
    SubtitleReadingRepresentationService,
)
from lectureos.application.subtitle_time_representation import (
    SubtitleTimeRepresentationService,
)
from lectureos.application.subtitle_structural_validation import (
    SubtitleStructuralValidationService,
)
from lectureos.application.subtitle_review_preparation import (
    SubtitleReviewPreparationService,
)
from lectureos.application.subtitle_review_decision import (
    SubtitleReviewDecisionService,
)
from lectureos.application.subtitle_decision_application import (
    SubtitleDecisionRevisionService,
)
from lectureos.application.subtitle_approved_assembly import (
    SubtitleApprovedSubtitleAssemblyService,
)
from lectureos.application.subtitle_srt_artifact import (
    SubtitleSrtArtifactGenerationService,
)
from lectureos.application.subtitle_srt_materialization import (
    SubtitleSrtMaterializationService,
)
from lectureos.application.subtitle_final_subtitle import (
    SubtitleFinalSubtitleService,
)
from lectureos.application.transcript_readiness_evaluation import (
    TranscriptReadinessEvaluationService,
)
from lectureos.application.transcript_review_decision import (
    TranscriptReviewDecisionService,
)
from lectureos.application.transcript_review_preparation import (
    TranscriptReviewPreparationService,
)
from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.service import ExecutionService
from lectureos.persistence import (
    SQLiteApplicabilityEvaluationCommandPersistence,
    SQLiteCurrentSelectionCommandPersistence,
    SQLiteReadinessEvaluationCommandPersistence,
    SQLiteSubtitleCandidateCommandPersistence,
    SQLiteSubtitleCandidateRepository,
    SQLiteSubtitleIntakeCommandPersistence,
    SQLiteSubtitleApprovedDocumentCommandPersistence,
    SQLiteSubtitleApprovedDocumentRepository,
    SQLiteSubtitleSrtArtifactCommandPersistence,
    SQLiteSubtitleSrtArtifactRepository,
    SQLiteSubtitleSrtMaterializationCommandPersistence,
    SQLiteSubtitleSrtMaterializationRepository,
    SQLiteEligibleAnalysisInputCommandPersistence,
    SQLiteEligibleAnalysisInputRepository,
    SQLiteAnalysisFindingCommandPersistence,
    SQLiteAnalysisFindingRepository,
    SQLiteLectureSegmentCommandPersistence,
    SQLiteEditCandidateCommandPersistence,
    SQLiteSubtitleReadingCommandPersistence,
    SQLiteSubtitleDecisionRevisionCommandPersistence,
    SQLiteSubtitleDecisionRevisionRepository,
    SQLiteSubtitleFinalSubtitleCommandPersistence,
    SQLiteSubtitleFinalSubtitleRepository,
    SQLiteSubtitleReadingRevisionRepository,
    SQLiteSubtitleReviewDecisionCommandPersistence,
    SQLiteSubtitleReviewDecisionRepository,
    SQLiteSubtitleReviewPreparationCommandPersistence,
    SQLiteSubtitleReviewPreparationRepository,
    SQLiteSubtitleTimeCommandPersistence,
    SQLiteSubtitleTimeRevisionRepository,
    SQLiteSubtitleTranscriptIntakeRepository,
    SQLiteSubtitleValidationCommandPersistence,
    SQLiteSubtitleValidationRepository,
    SQLiteTranscriptReadinessEvaluationRepository,
    SQLiteTranscriptApplicabilityEvaluationRepository,
    SQLiteTranscriptCurrentSelectionRepository,
    SQLiteCorrectionCandidateRepository,
    SQLiteCorrectedTranscriptRevisionRepository,
    SQLiteDomainResultReferenceRepository,
    SQLiteExecutionCommandPersistence,
    SQLiteFailureRepository,
    SQLiteProcessingRunRepository,
    SQLiteProcessingUnitRepository,
    SQLiteProviderTranscriptResultRepository,
    SQLiteRawTranscriptRepository,
    SQLiteReviewCandidateReferenceRepository,
    SQLiteReviewDecisionCommandPersistence,
    SQLiteTranscriptReviewDecisionRepository,
    SQLiteReviewItemRepository,
    SQLiteReviewPreparationCommandPersistence,
    SQLiteTranscriptCommandPersistence,
    SQLiteTranscriptReviewPreparationRepository,
    SQLiteTranscriptSegmentRepository,
    SQLiteUnitExecutionRepository,
)
from lectureos.transcript.service import TranscriptService
from lectureos.transcript.validation import TranscriptValidationService


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
    """Backward-compatible alias for the v4 durable execution composition."""

    return compose_sqlite_execution_service(connection)


def compose_sqlite_execution_service(
    connection: sqlite3.Connection,
) -> ExecutionService:
    """Build the complete durable v4 execution command composition."""

    runs = SQLiteProcessingRunRepository(connection)
    units = SQLiteProcessingUnitRepository(connection)
    executions = SQLiteUnitExecutionRepository(connection)
    failures = SQLiteFailureRepository(connection)
    results = SQLiteDomainResultReferenceRepository(connection)
    atomic_commands = SQLiteExecutionCommandPersistence(connection)
    return ExecutionService(
        runs=runs,
        units=units,
        executions=executions,
        failures=failures,
        results=results,
        atomic_start_persistence=atomic_commands,
        atomic_failure_persistence=atomic_commands,
        atomic_retry_persistence=atomic_commands,
        atomic_result_persistence=atomic_commands,
    )


def compose_sqlite_transcript_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> TranscriptService:
    """Build the complete durable v5 canonical Transcript composition."""

    return _compose_sqlite_transcript_service(
        connection,
        execution_query,
        SQLiteTranscriptCommandPersistence(connection),
    )


def compose_sqlite_transcript_correction_generation_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
    generation: CorrectionGenerationPort,
) -> TranscriptCorrectionGenerationService:
    """Build provider-independent durable Transcript correction generation."""

    atomic_commands = SQLiteTranscriptCommandPersistence(connection)
    transcripts = _compose_sqlite_transcript_service(
        connection, execution_query, atomic_commands
    )
    validation = TranscriptValidationService(transcripts, execution_query)
    return TranscriptCorrectionGenerationService(
        transcripts,
        execution_query,
        generation,
        atomic_commands,
        validation,
    )


def compose_sqlite_transcript_review_preparation_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> TranscriptReviewPreparationService:
    """Build durable v6 Transcript Review Preparation on one caller connection."""

    transcripts = compose_sqlite_transcript_service(connection, execution_query)
    persistence = SQLiteReviewPreparationCommandPersistence(connection)
    return TranscriptReviewPreparationService(transcripts, execution_query, persistence)


def compose_sqlite_transcript_review_decision_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> TranscriptReviewDecisionService:
    """Build durable v7 Transcript Human Review Decision on one caller connection."""

    preparations = SQLiteTranscriptReviewPreparationRepository(connection)
    review_items = SQLiteReviewItemRepository(connection)
    candidate_references = SQLiteReviewCandidateReferenceRepository(connection)
    persistence = SQLiteReviewDecisionCommandPersistence(connection)
    return TranscriptReviewDecisionService(
        preparations,
        review_items,
        candidate_references,
        execution_query,
        persistence,
    )


def compose_sqlite_transcript_applicability_evaluation_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> TranscriptApplicabilityEvaluationService:
    """Build durable v8 Transcript Applicability evaluation on one caller connection."""

    decisions = SQLiteTranscriptReviewDecisionRepository(connection)
    persistence = SQLiteApplicabilityEvaluationCommandPersistence(connection)
    return TranscriptApplicabilityEvaluationService(
        decisions, execution_query, persistence
    )


def compose_sqlite_transcript_current_selection_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> TranscriptCurrentSelectionService:
    """Build durable v9 Transcript Current Selection on one caller connection."""

    evaluations = SQLiteTranscriptApplicabilityEvaluationRepository(connection)
    persistence = SQLiteCurrentSelectionCommandPersistence(connection)
    return TranscriptCurrentSelectionService(
        evaluations, execution_query, persistence
    )


def compose_sqlite_transcript_readiness_evaluation_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> TranscriptReadinessEvaluationService:
    """Build durable v10 Transcript Ready State evaluation on one caller connection."""

    selections = SQLiteTranscriptCurrentSelectionRepository(connection)
    applicabilities = SQLiteTranscriptApplicabilityEvaluationRepository(connection)
    decisions = SQLiteTranscriptReviewDecisionRepository(connection)
    transcripts = compose_sqlite_transcript_service(connection, execution_query)
    validation = TranscriptValidationService(transcripts, execution_query)
    persistence = SQLiteReadinessEvaluationCommandPersistence(connection)
    return TranscriptReadinessEvaluationService(
        selections,
        applicabilities,
        decisions,
        transcripts,
        validation,
        execution_query,
        persistence,
    )


def compose_sqlite_subtitle_transcript_intake_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> SubtitleTranscriptIntakeService:
    """Build durable v11 Subtitle Transcript Intake on one caller connection."""

    readiness = SQLiteTranscriptReadinessEvaluationRepository(connection)
    transcripts = compose_sqlite_transcript_service(connection, execution_query)
    persistence = SQLiteSubtitleIntakeCommandPersistence(connection)
    return SubtitleTranscriptIntakeService(
        readiness, transcripts, execution_query, persistence
    )


def compose_sqlite_lecture_analysis_input_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> LectureAnalysisInputService:
    """Build durable v23 Lecture Analysis Input Eligibility (Intake) on one caller connection."""

    readiness = SQLiteTranscriptReadinessEvaluationRepository(connection)
    transcripts = compose_sqlite_transcript_service(connection, execution_query)
    persistence = SQLiteEligibleAnalysisInputCommandPersistence(connection)
    return LectureAnalysisInputService(
        readiness, transcripts, execution_query, persistence
    )


def compose_sqlite_analysis_finding_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> AnalysisFindingApplicationService:
    """Build the durable v24 Analysis Finding Application Foundation on one caller connection."""

    inputs = SQLiteEligibleAnalysisInputRepository(connection)
    persistence = SQLiteAnalysisFindingCommandPersistence(connection)
    return AnalysisFindingApplicationService(inputs, execution_query, persistence)


def compose_sqlite_lecture_segmentation_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> LectureSegmentationApplicationService:
    """Build the durable v25 Lecture Segmentation Application Foundation on one caller connection."""

    inputs = SQLiteEligibleAnalysisInputRepository(connection)
    persistence = SQLiteLectureSegmentCommandPersistence(connection)
    return LectureSegmentationApplicationService(inputs, execution_query, persistence)


def compose_sqlite_edit_candidate_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> EditCandidateApplicationService:
    """Build the durable v26 Edit Candidate Application Foundation on one caller connection."""

    findings = SQLiteAnalysisFindingRepository(connection)
    persistence = SQLiteEditCandidateCommandPersistence(connection)
    return EditCandidateApplicationService(findings, execution_query, persistence)


DEFAULT_EDIT_CANDIDATE_CONTEXT_WINDOW_SECONDS = 15.0


def compose_sqlite_edit_candidate_generation_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
    generation: EditCandidateGenerationPort,
    *,
    context_window_seconds: float = DEFAULT_EDIT_CANDIDATE_CONTEXT_WINDOW_SECONDS,
) -> EditCandidateGenerationService:
    """Build the v26 provider-neutral Edit Candidate generation orchestration (042 §9.2).

    The concrete or fake provider Port is injected by the caller; this orchestration reuses the completed
    Edit Candidate Application Foundation for admission and adds no persistence.
    """

    findings = SQLiteAnalysisFindingRepository(connection)
    inputs = SQLiteEligibleAnalysisInputRepository(connection)
    transcripts = compose_sqlite_transcript_service(connection, execution_query)
    admission = compose_sqlite_edit_candidate_service(connection, execution_query)
    return EditCandidateGenerationService(
        findings,
        inputs,
        transcripts,
        execution_query,
        generation,
        admission,
        context_window_seconds=context_window_seconds,
    )


def compose_sqlite_subtitle_candidate_generation_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> SubtitleCandidateGenerationService:
    """Build durable v12 Subtitle Candidate Generation on one caller connection."""

    intakes = SQLiteSubtitleTranscriptIntakeRepository(connection)
    transcripts = compose_sqlite_transcript_service(connection, execution_query)
    persistence = SQLiteSubtitleCandidateCommandPersistence(connection)
    return SubtitleCandidateGenerationService(
        intakes, transcripts, execution_query, persistence
    )


def compose_sqlite_subtitle_reading_representation_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> SubtitleReadingRepresentationService:
    """Build durable v13 Subtitle Reading Representation on one caller connection."""

    candidates = SQLiteSubtitleCandidateRepository(connection)
    persistence = SQLiteSubtitleReadingCommandPersistence(connection)
    return SubtitleReadingRepresentationService(
        candidates, execution_query, persistence
    )


def compose_sqlite_subtitle_time_representation_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> SubtitleTimeRepresentationService:
    """Build durable v14 Subtitle Time Representation on one caller connection."""

    readings = SQLiteSubtitleReadingRevisionRepository(connection)
    cues = SQLiteSubtitleCandidateRepository(connection)
    persistence = SQLiteSubtitleTimeCommandPersistence(connection)
    return SubtitleTimeRepresentationService(
        readings, cues, execution_query, persistence
    )


def compose_sqlite_subtitle_structural_validation_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> SubtitleStructuralValidationService:
    """Build durable v15 Subtitle Structural Validation on one caller connection."""

    times = SQLiteSubtitleTimeRevisionRepository(connection)
    readings = SQLiteSubtitleReadingRevisionRepository(connection)
    persistence = SQLiteSubtitleValidationCommandPersistence(connection)
    return SubtitleStructuralValidationService(
        times, readings, execution_query, persistence
    )


def compose_sqlite_subtitle_review_preparation_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> SubtitleReviewPreparationService:
    """Build durable v16 Subtitle Review Preparation on one caller connection."""

    validations = SQLiteSubtitleValidationRepository(connection)
    persistence = SQLiteSubtitleReviewPreparationCommandPersistence(connection)
    return SubtitleReviewPreparationService(
        validations, execution_query, persistence
    )


def compose_sqlite_subtitle_review_decision_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> SubtitleReviewDecisionService:
    """Build durable v17 Subtitle Human Review Decision on one caller connection."""

    preparations = SQLiteSubtitleReviewPreparationRepository(connection)
    review_items = SQLiteReviewItemRepository(connection)
    candidate_references = SQLiteReviewCandidateReferenceRepository(connection)
    persistence = SQLiteSubtitleReviewDecisionCommandPersistence(connection)
    return SubtitleReviewDecisionService(
        preparations,
        review_items,
        candidate_references,
        execution_query,
        persistence,
    )


def compose_sqlite_subtitle_decision_application_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> SubtitleDecisionRevisionService:
    """Build durable v18 Subtitle Decision Application on one caller connection."""

    decisions = SQLiteSubtitleReviewDecisionRepository(connection)
    validations = SQLiteSubtitleValidationRepository(connection)
    persistence = SQLiteSubtitleDecisionRevisionCommandPersistence(connection)
    return SubtitleDecisionRevisionService(
        decisions, validations, execution_query, persistence
    )


def compose_sqlite_subtitle_final_subtitle_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> SubtitleFinalSubtitleService:
    """Build durable v19 Subtitle Final Subtitle selection on one caller connection."""

    revisions = SQLiteSubtitleDecisionRevisionRepository(connection)
    persistence = SQLiteSubtitleFinalSubtitleCommandPersistence(connection)
    return SubtitleFinalSubtitleService(revisions, execution_query, persistence)


def compose_sqlite_subtitle_approved_assembly_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> SubtitleApprovedSubtitleAssemblyService:
    """Build durable v20 Approved Subtitle Assembly on one caller connection."""

    time_revisions = SQLiteSubtitleTimeRevisionRepository(connection)
    reading_revisions = SQLiteSubtitleReadingRevisionRepository(connection)
    finals = SQLiteSubtitleFinalSubtitleRepository(connection)
    decision_revisions = SQLiteSubtitleDecisionRevisionRepository(connection)
    persistence = SQLiteSubtitleApprovedDocumentCommandPersistence(connection)
    return SubtitleApprovedSubtitleAssemblyService(
        time_revisions,
        reading_revisions,
        finals,
        decision_revisions,
        execution_query,
        persistence,
    )


def compose_sqlite_subtitle_srt_artifact_generation_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> SubtitleSrtArtifactGenerationService:
    """Build durable v21 SRT Artifact Generation on one caller connection."""

    documents = SQLiteSubtitleApprovedDocumentRepository(connection)
    persistence = SQLiteSubtitleSrtArtifactCommandPersistence(connection)
    return SubtitleSrtArtifactGenerationService(documents, execution_query, persistence)


def compose_sqlite_subtitle_srt_materialization_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
    storage_root,
) -> SubtitleSrtMaterializationService:
    """Build durable v22 SRT Physical Materialization on one caller connection and approved root."""

    from lectureos.infrastructure.local_srt_file_writer import LocalSrtFileWriter

    artifacts = SQLiteSubtitleSrtArtifactRepository(connection)
    materializations = SQLiteSubtitleSrtMaterializationRepository(connection)
    persistence = SQLiteSubtitleSrtMaterializationCommandPersistence(connection)
    writer = LocalSrtFileWriter(storage_root)
    return SubtitleSrtMaterializationService(
        artifacts, materializations, execution_query, writer, persistence
    )


def _compose_sqlite_transcript_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
    atomic_commands: SQLiteTranscriptCommandPersistence,
) -> TranscriptService:

    provider_results = SQLiteProviderTranscriptResultRepository(connection)
    raw_transcripts = SQLiteRawTranscriptRepository(connection)
    segments = SQLiteTranscriptSegmentRepository(connection)
    candidates = SQLiteCorrectionCandidateRepository(connection)
    revisions = SQLiteCorrectedTranscriptRevisionRepository(connection)
    domain_results = SQLiteDomainResultReferenceRepository(connection)
    return TranscriptService(
        execution_query,
        provider_results=provider_results,
        raw_transcripts=raw_transcripts,
        segments=segments,
        candidates=candidates,
        revisions=revisions,
        domain_results=domain_results,
        atomic_raw_persistence=atomic_commands,
        atomic_candidate_persistence=atomic_commands,
        atomic_revision_persistence=atomic_commands,
    )
