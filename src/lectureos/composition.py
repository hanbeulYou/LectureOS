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
