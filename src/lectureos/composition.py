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
from lectureos.application.edit_review import (
    EditReviewApplicationService,
)
from lectureos.application.edit_export import (
    ApprovedEditExportService,
)
from lectureos.application.edit_export_assembly import (
    EditExportAssemblyService,
)
from lectureos.application.edit_export_artifact import (
    EditExportArtifactService,
)
from lectureos.application.edit_export_materialization import (
    EditExportMaterializationService,
)
from lectureos.application.media_import import MediaImportService
from lectureos.application.transcript_source_intake import (
    TranscriptSourceIntakeService,
)
from lectureos.application.provider_transcript_admission import (
    ProviderTranscriptAdmissionService,
)
from lectureos.application.local_asr_transcription import (
    LocalAsrEngineRunner,
    LocalAsrTranscriptionService,
)
from lectureos.application.current_raw_transcript_selection import (
    CurrentRawTranscriptSelectionService,
)
from lectureos.application.correction_candidate_admission import (
    CorrectionCandidateAdmissionService,
)
from lectureos.application.correction_candidate_decision import (
    CorrectionCandidateDecisionService,
)
from lectureos.application.corrected_revision_generation import (
    CorrectedRevisionGenerationService,
)
from lectureos.application.effective_subtitle_generation import (
    EffectiveSubtitleGenerationService,
)
from lectureos.application.effective_subtitle_final_selection import (
    EffectiveSubtitleFinalSelectionService,
)
from lectureos.application.effective_srt_delivery import (
    EffectiveSrtDeliveryService,
)
from lectureos.application.effective_srt_publication import (
    EffectiveSrtPublicationService,
)
from lectureos.application.effective_srt_materialization import (
    EffectiveSrtMaterializationService,
)
from lectureos.application.effective_subtitle_srt_artifact import (
    EffectiveSubtitleSrtArtifactService,
)
from lectureos.application.effective_subtitle_review_decision import (
    EffectiveSubtitleReviewDecisionService,
)
from lectureos.application.effective_subtitle_review_preparation import (
    EffectiveSubtitleReviewPreparationService,
)
from lectureos.application.effective_transcript_consumption import (
    EffectiveTranscriptConsumptionService,
    EffectiveTranscriptInputService,
)
from lectureos.application.corrected_revision_selection import (
    CorrectedRevisionSelectionService,
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
    SQLiteEditCandidateRepository,
    SQLiteEditReviewCommandPersistence,
    SQLiteApprovedEditDecisionRepository,
    SQLiteEditReviewDecisionRepository,
    SQLiteApprovedEditExportCommandPersistence,
    SQLiteApprovedEditExportRepresentationRepository,
    SQLiteEditExportAssemblyCommandPersistence,
    SQLiteEditExportAssemblyRepository,
    SQLiteSourceMediaCommandPersistence,
    SQLiteSourceMediaRepository,
    SQLiteTranscriptSourceIntakeCommandPersistence,
    SQLiteTranscriptSourceIntakeRepository,
    SQLiteProviderTranscriptAdmissionCommandPersistence,
    SQLiteProviderTranscriptAdmissionRepository,
    SQLiteRawTranscriptSelectionCommandPersistence,
    SQLiteRawTranscriptSelectionRepository,
    SQLiteCorrectionCandidateAdmissionCommandPersistence,
    SQLiteCorrectionCandidateAdmissionRepository,
    SQLiteCorrectionCandidateDecisionCommandPersistence,
    SQLiteCorrectionCandidateDecisionRepository,
    SQLiteCorrectedRevisionGenerationCommandPersistence,
    SQLiteCorrectedRevisionGenerationRepository,
    SQLiteCorrectedRevisionSelectionCommandPersistence,
    SQLiteCorrectedRevisionSelectionRepository,
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
    SQLiteEffectiveSubtitleCandidateCommandPersistence,
    SQLiteEffectiveSubtitleCandidateRepository,
    SQLiteEffectiveSubtitleFinalSelectionCommandPersistence,
    SQLiteEffectiveSubtitleFinalSelectionRepository,
    SQLiteEffectiveSrtDeliveryCommandPersistence,
    SQLiteEffectiveSrtDeliveryRepository,
    SQLiteEffectiveSrtPublicationCommandPersistence,
    SQLiteEffectiveSrtPublicationRepository,
    SQLiteEffectiveSrtMaterializationCommandPersistence,
    SQLiteEffectiveSrtMaterializationRepository,
    SQLiteEffectiveSubtitleSrtArtifactCommandPersistence,
    SQLiteEffectiveSubtitleSrtArtifactRepository,
    SQLiteEffectiveSubtitleReviewDecisionCommandPersistence,
    SQLiteEffectiveSubtitleReviewDecisionRepository,
    SQLiteEffectiveSubtitleReviewSubjectCommandPersistence,
    SQLiteEffectiveSubtitleReviewSubjectRepository,
    SQLiteEffectiveTranscriptConsumptionCommandPersistence,
    SQLiteEffectiveTranscriptConsumptionRepository,
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


def compose_sqlite_edit_review_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> EditReviewApplicationService:
    """Build the durable v27 Edit-Pipeline Review Application Foundation on one caller connection."""

    candidates = SQLiteEditCandidateRepository(connection)
    persistence = SQLiteEditReviewCommandPersistence(connection)
    return EditReviewApplicationService(candidates, execution_query, persistence)


def compose_sqlite_edit_export_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> ApprovedEditExportService:
    """Build the durable v28 Edit-Pipeline Export Application Foundation on one caller connection."""

    approved = SQLiteApprovedEditDecisionRepository(connection)
    reviews = SQLiteEditReviewDecisionRepository(connection)
    candidates = SQLiteEditCandidateRepository(connection)
    persistence = SQLiteApprovedEditExportCommandPersistence(connection)
    return ApprovedEditExportService(
        approved, reviews, candidates, execution_query, persistence
    )


def compose_sqlite_edit_export_assembly_service(
    connection: sqlite3.Connection,
    execution_query: ExecutionQueryBoundary,
) -> EditExportAssemblyService:
    """Build the durable v29 Edit-Pipeline Export Assembly Application Foundation on one caller connection."""

    representations = SQLiteApprovedEditExportRepresentationRepository(connection)
    persistence = SQLiteEditExportAssemblyCommandPersistence(connection)
    return EditExportAssemblyService(representations, execution_query, persistence)


def compose_sqlite_edit_export_artifact_service(
    connection: sqlite3.Connection,
) -> EditExportArtifactService:
    """Build the format-neutral v29 Edit-Pipeline Export Artifact Foundation on one caller connection.

    The Artifact is a derived, non-authoritative external representation; it reads one Edit Export Assembly and
    its member representations read-only and is not persisted, so no persistence port is composed.
    """

    assemblies = SQLiteEditExportAssemblyRepository(connection)
    representations = SQLiteApprovedEditExportRepresentationRepository(connection)
    return EditExportArtifactService(assemblies, representations)


def compose_edit_export_materialization_service() -> EditExportMaterializationService:
    """Build the first runnable Edit Export local materialization service (044 §22).

    The serializer and local file writer are pure/filesystem side-effect components with no database
    dependency; nothing here is persisted, so no connection or persistence port is composed.
    """

    from lectureos.infrastructure.local_edit_export_file_writer import (
        LocalEditExportFileWriter,
    )

    return EditExportMaterializationService(LocalEditExportFileWriter())


def compose_sqlite_media_import_service(
    connection: sqlite3.Connection,
) -> MediaImportService:
    """Build the v30 Media Import Application Foundation on one caller connection (045 §1).

    The local filesystem inspector reads and streaming-hashes the source read-only; the repository resolves
    existing content-addressed records; the command persistence writes atomically.
    """

    from lectureos.infrastructure.local_source_media_inspector import (
        LocalSourceMediaInspector,
    )

    repository = SQLiteSourceMediaRepository(connection)
    persistence = SQLiteSourceMediaCommandPersistence(connection)
    return MediaImportService(LocalSourceMediaInspector(), repository, persistence)


def compose_sqlite_transcript_source_intake_service(
    connection: sqlite3.Connection,
) -> TranscriptSourceIntakeService:
    """Build the v31 Source Intake Application Foundation on one caller connection (040 §13).

    Resolves an existing persisted Source Media record read-only and records a deterministic, content-derived
    transcript intake confirming eligibility. It reads no filesystem and performs no decoding or transcription.
    """

    source_media = SQLiteSourceMediaRepository(connection)
    intakes = SQLiteTranscriptSourceIntakeRepository(connection)
    persistence = SQLiteTranscriptSourceIntakeCommandPersistence(connection)
    return TranscriptSourceIntakeService(source_media, intakes, persistence)


def compose_sqlite_provider_transcript_admission_service(
    connection: sqlite3.Connection,
) -> ProviderTranscriptAdmissionService:
    """Build the v32 External ASR Boundary admission on one caller connection (040 §14).

    Resolves an existing transcript source intake and its Source Media read-only, then admits an externally
    produced provider ASR result — preserving the provider evidence and producing exactly one canonical Raw
    Transcript in a single atomic transaction. It executes no ASR engine and reads no media file.
    """

    intakes = SQLiteTranscriptSourceIntakeRepository(connection)
    source_media = SQLiteSourceMediaRepository(connection)
    admissions = SQLiteProviderTranscriptAdmissionRepository(connection)
    persistence = SQLiteProviderTranscriptAdmissionCommandPersistence(connection)
    return ProviderTranscriptAdmissionService(
        intakes, source_media, admissions, persistence
    )


def compose_sqlite_local_asr_transcription_service(
    connection: sqlite3.Connection,
    engine_runner: LocalAsrEngineRunner | None = None,
) -> LocalAsrTranscriptionService:
    """Build the local ASR execution adapter on one caller connection (040 §15).

    Resolves an admitted intake and its Source Media read-only, verifies the reference-in-place source file is
    available and unchanged, runs one concrete local ASR engine (faster-whisper by default; inject a fake runner
    for tests/demo), and hands the provider-neutral result to the existing admission service — the sole write
    boundary. Injecting ``engine_runner`` keeps the core importable and tests offline.
    """

    from lectureos.infrastructure.local_source_media_verifier import (
        LocalSourceMediaVerifier,
    )

    intakes = SQLiteTranscriptSourceIntakeRepository(connection)
    source_media = SQLiteSourceMediaRepository(connection)
    admissions = SQLiteProviderTranscriptAdmissionRepository(connection)
    admission_service = compose_sqlite_provider_transcript_admission_service(connection)
    verifier = LocalSourceMediaVerifier()
    if engine_runner is None:
        from lectureos.infrastructure.faster_whisper_engine import (
            FasterWhisperEngineRunner,
        )

        engine_runner = FasterWhisperEngineRunner()
    return LocalAsrTranscriptionService(
        intakes,
        source_media,
        admissions,
        admission_service,
        verifier,
        engine_runner,
    )


def compose_sqlite_current_raw_transcript_selection_service(
    connection: sqlite3.Connection,
) -> CurrentRawTranscriptSelectionService:
    """Build Current Raw Transcript Selection + readiness on one caller connection (040 §16).

    Enumerates an intake's admitted Raw Transcript candidates (from provider_transcript_admissions), resolves and
    switches the current selection (append-only, one current per intake), and derives readiness — read-only over
    all upstream records; it mutates no transcript, provider result, Source Media, or intake row.
    """

    intakes = SQLiteTranscriptSourceIntakeRepository(connection)
    read_model = SQLiteRawTranscriptSelectionRepository(connection)
    persistence = SQLiteRawTranscriptSelectionCommandPersistence(connection)
    return CurrentRawTranscriptSelectionService(
        intakes, read_model, read_model, persistence
    )


def compose_sqlite_correction_candidate_admission_service(
    connection: sqlite3.Connection,
) -> CorrectionCandidateAdmissionService:
    """Build Correction Candidate Admission on one caller connection (040 §17).

    Admits a proposed correction against the intake's current Raw Transcript segment — reusing the canonical
    CorrectionCandidate — without applying it. It resolves readiness (current selection), the target segment, and
    lineage read-only, and writes only the candidate + its provenance + the admission binding row; it never
    mutates Raw Transcript text, the current selection, or produces a corrected revision or decision.
    """

    intakes = SQLiteTranscriptSourceIntakeRepository(connection)
    selections = SQLiteRawTranscriptSelectionRepository(connection)
    segments = SQLiteTranscriptSegmentRepository(connection)
    raw_transcripts = SQLiteRawTranscriptRepository(connection)
    admissions = SQLiteCorrectionCandidateAdmissionRepository(connection)
    persistence = SQLiteCorrectionCandidateAdmissionCommandPersistence(connection)
    return CorrectionCandidateAdmissionService(
        intakes, selections, segments, raw_transcripts, admissions, persistence
    )


def compose_sqlite_correction_candidate_decision_service(
    connection: sqlite3.Connection,
) -> CorrectionCandidateDecisionService:
    """Build Correction Candidate Human Decision on one caller connection (040 §18).

    Records append-only Human Accept/Reject authority on admitted Correction Candidates and derives the current
    authority (Undecided/Accepted/Rejected) — read-only over the candidate. It never mutates the candidate, the
    Raw Transcript, the current selection, or any segment, and creates no corrected revision.
    """

    decisions = SQLiteCorrectionCandidateDecisionRepository(connection)
    persistence = SQLiteCorrectionCandidateDecisionCommandPersistence(connection)
    return CorrectionCandidateDecisionService(decisions, decisions, persistence)


def compose_sqlite_corrected_revision_generation_service(
    connection: sqlite3.Connection,
) -> CorrectedRevisionGenerationService:
    """Build Corrected Revision Generation on one caller connection (040 §19).

    Explicitly applies one currently Accepted correction candidate to its source Raw Transcript and persists one
    immutable canonical CorrectedTranscriptRevision plus the generation binding — read-only over the candidate,
    decision history, raw transcript, segments, and current selection. The revision is never selected as current.
    """

    admissions = SQLiteCorrectionCandidateAdmissionRepository(connection)
    decisions = SQLiteCorrectionCandidateDecisionRepository(connection)
    selections = SQLiteRawTranscriptSelectionRepository(connection)
    raw_transcripts = SQLiteRawTranscriptRepository(connection)
    segments = SQLiteTranscriptSegmentRepository(connection)
    generations = SQLiteCorrectedRevisionGenerationRepository(connection)
    persistence = SQLiteCorrectedRevisionGenerationCommandPersistence(connection)
    return CorrectedRevisionGenerationService(
        admissions, decisions, selections, raw_transcripts, segments, generations, persistence
    )


def compose_sqlite_corrected_revision_selection_service(
    connection: sqlite3.Connection,
) -> CorrectedRevisionSelectionService:
    """Build Current Corrected Revision Selection + effective resolution on one caller connection (040 §20).

    Explicit append-only selection of the current corrected revision (or explicit Raw fallback) for an intake,
    with write-time eligibility, query-time applicability, and the deterministic effective-transcript resolver —
    read-only over revisions, candidates, decisions, raw transcripts, and the raw selection; it mutates none of
    them and never auto-promotes a revision.
    """

    intakes = SQLiteTranscriptSourceIntakeRepository(connection)
    generations = SQLiteCorrectedRevisionGenerationRepository(connection)
    admissions = SQLiteCorrectionCandidateAdmissionRepository(connection)
    decisions = SQLiteCorrectionCandidateDecisionRepository(connection)
    raw_selections = SQLiteRawTranscriptSelectionRepository(connection)
    selections = SQLiteCorrectedRevisionSelectionRepository(connection)
    persistence = SQLiteCorrectedRevisionSelectionCommandPersistence(connection)
    return CorrectedRevisionSelectionService(
        intakes, generations, admissions, decisions, raw_selections, selections, persistence
    )


def compose_sqlite_effective_transcript_consumption_service(
    connection: sqlite3.Connection,
) -> EffectiveTranscriptConsumptionService:
    """Build the Effective Transcript Consumption Boundary on one caller connection (040 §21).

    Acquisition resolves solely through the §20 resolver, loads the snapshot by immutable source
    identity, and records the deterministic consumption binding for the bounded manifest consumer —
    read-only over every upstream record; only `effective_transcript_consumptions` is written.
    """

    selection_service = compose_sqlite_corrected_revision_selection_service(connection)
    input_service = EffectiveTranscriptInputService(
        selection_service,
        SQLiteRawTranscriptRepository(connection),
        SQLiteCorrectedTranscriptRevisionRepository(connection),
        SQLiteTranscriptSegmentRepository(connection),
    )
    consumptions = SQLiteEffectiveTranscriptConsumptionRepository(connection)
    persistence = SQLiteEffectiveTranscriptConsumptionCommandPersistence(connection)
    return EffectiveTranscriptConsumptionService(
        input_service, selection_service, consumptions, persistence
    )


def compose_sqlite_lecture_analysis_input_eligibility_service(
    connection: sqlite3.Connection,
) -> "LectureAnalysisInputEligibilityService":
    """Build the derived Lecture Analysis Input Eligibility query (042 §5.1 / GOAL-022).

    Read-only over every record: authority resolves once through the sole released 040 §20
    resolver, the corrected snapshot loads by immutable identity, and the released §19 content
    fingerprint is reused verbatim. Nothing is persisted — eligibility is advisory and a later
    explicit admission command must revalidate current authority.
    """

    from lectureos.application.lecture_analysis_input_eligibility import (
        LectureAnalysisInputEligibilityService,
    )
    from lectureos.persistence.current_raw_transcript_selection import (
        SQLiteRawTranscriptSelectionRepository,
    )

    return LectureAnalysisInputEligibilityService(
        SQLiteTranscriptSourceIntakeRepository(connection),
        SQLiteRawTranscriptSelectionRepository(connection),
        compose_sqlite_corrected_revision_selection_service(connection),
        SQLiteCorrectedTranscriptRevisionRepository(connection),
        SQLiteTranscriptSegmentRepository(connection),
    )


def compose_sqlite_lecture_analysis_input_admission_service(
    connection: sqlite3.Connection,
) -> "LectureAnalysisInputAdmissionService":
    """Build explicit Lecture Analysis Input Admission on one caller connection (GOAL-023).

    Every admission revalidates the derived GOAL-022 eligibility at command time, then appends
    one immutable analysis input record binding the exact authority snapshot — read-only over
    every upstream record; only `lecture_analysis_input_admissions` is written. No analysis,
    execution, or AI exists in this contract, and the legacy `eligible_analysis_inputs` path
    is never touched.
    """

    from lectureos.application.lecture_analysis_input_admission import (
        LectureAnalysisInputAdmissionService,
    )
    from lectureos.persistence.lecture_analysis_input_admission import (
        SQLiteLectureAnalysisInputAdmissionCommandPersistence,
        SQLiteLectureAnalysisInputAdmissionRepository,
    )

    return LectureAnalysisInputAdmissionService(
        compose_sqlite_lecture_analysis_input_eligibility_service(connection),
        SQLiteLectureAnalysisInputAdmissionRepository(connection),
        SQLiteLectureAnalysisInputAdmissionCommandPersistence(connection),
    )


def compose_sqlite_lecture_analysis_finding_service(
    connection: sqlite3.Connection,
) -> "LectureAnalysisFindingService":
    """Build effective-generation Analysis Finding admission on one caller connection (042 §8.2).

    Every command re-derives the anchoring admission's authority standing through the released
    GOAL-023 service — no authority resolver is reimplemented here — and admits only at `current`.
    One immutable canonical finding is appended; only `lecture_analysis_findings` is written and
    every upstream record is read-only. No analysis, provider, AI, ProcessingRun, or UnitExecution
    exists in this contract, and the legacy execution-coupled `analysis_findings` /
    `eligible_analysis_inputs` paths are never touched (PATCH-0030 D-6, D-11).
    """

    from lectureos.application.lecture_analysis_finding import (
        LectureAnalysisFindingService,
    )
    from lectureos.persistence.lecture_analysis_finding import (
        SQLiteLectureAnalysisFindingCommandPersistence,
        SQLiteLectureAnalysisFindingRepository,
    )

    return LectureAnalysisFindingService(
        compose_sqlite_lecture_analysis_input_admission_service(connection),
        SQLiteLectureAnalysisFindingRepository(connection),
        SQLiteLectureAnalysisFindingCommandPersistence(connection),
    )


def compose_sqlite_lecture_analysis_edit_candidate_service(
    connection: sqlite3.Connection,
) -> "LectureAnalysisEditCandidateService":
    """Build effective-generation Edit Candidate admission on one caller connection (042 §9.3).

    Every command resolves the anchoring §8.2 Analysis Finding and re-derives the standing of the
    admission it hangs from through the released GOAL-025/GOAL-023 path — no authority resolver is
    reimplemented — admitting only at `current`. One immutable canonical candidate is appended;
    only `lecture_analysis_edit_candidates` is written and every upstream record is read-only. No
    Lecture Segment is required or referenced, and no provider, AI, ProcessingRun, UnitExecution,
    or DomainResult exists in this contract (PATCH-0032 C-3, C-7). The legacy execution-coupled
    `edit_candidates` path is never touched (C-12).
    """

    from lectureos.application.lecture_analysis_edit_candidate import (
        LectureAnalysisEditCandidateService,
    )
    from lectureos.persistence.lecture_analysis_edit_candidate import (
        SQLiteLectureAnalysisEditCandidateCommandPersistence,
        SQLiteLectureAnalysisEditCandidateRepository,
    )

    return LectureAnalysisEditCandidateService(
        compose_sqlite_lecture_analysis_finding_service(connection),
        SQLiteLectureAnalysisEditCandidateRepository(connection),
        SQLiteLectureAnalysisEditCandidateCommandPersistence(connection),
    )


def compose_sqlite_lecture_review_service(
    connection: sqlite3.Connection,
) -> "LectureReviewApplicationService":
    """Build effective-generation Review admission on one caller connection (043 §7.5).

    Every command resolves the anchoring §9.3 Edit Candidate and re-derives the standing of the
    admission at the root of its chain through the released GOAL-027/GOAL-025/GOAL-023 path — no
    authority resolver is reimplemented — admitting only at `current`. One immutable
    `ReviewDecision`, plus exactly one `ApprovedEditDecision` for accept and modify, is appended in
    a single atomic transaction together with the admission's authority-history position
    (043 §7.6 / PATCH-0034); only `lecture_review_decisions`, `lecture_approved_edit_decisions`, and
    `lecture_review_authority_positions` are written and every upstream record is read-only. The
    current judgment of one (candidate, actor) scope is derived from the highest position and never
    stored, and nothing is arbitrated across actors. No
    provider, AI, ProcessingRun, UnitExecution, RUNNING state, or DomainResult exists in this
    contract (PATCH-0033 R-6), and the legacy execution-coupled `edit_review_decisions` /
    `approved_edit_decisions` path is never touched (R-12).
    """

    from lectureos.application.lecture_review_decision import (
        LectureReviewApplicationService,
    )
    from lectureos.persistence.lecture_review_decision import (
        SQLiteLectureReviewCommandPersistence,
        SQLiteLectureReviewRepository,
    )

    return LectureReviewApplicationService(
        compose_sqlite_lecture_analysis_edit_candidate_service(connection),
        SQLiteLectureReviewRepository(connection),
        SQLiteLectureReviewCommandPersistence(connection),
    )


def compose_sqlite_lecture_edit_export_assembly_service(
    connection: sqlite3.Connection,
) -> "LectureEditExportAssemblyService":
    """Build effective-generation Edit Export Assembly admission on one connection (044 §23).

    Concrete construction only. The scope repository resolves which §9.3 Edit Candidates belong to
    one Source Timeline through the released anchor chain; the released Review service supplies the
    derived current operative judgment (043 §7.6 AH-8/AH-9) and the chain standing (§7.5 R-3), so no
    authority or standing resolver is reimplemented here. Membership is the timeline's complete
    export-eligible set (EA-3/EA-4), derived and never stored as a selection (EA-7); only
    `lecture_edit_export_assemblies` and `lecture_edit_export_assembly_members` are written and every
    upstream record is read-only. No provider, AI, ProcessingRun, UnitExecution, RUNNING state, or
    DomainResult exists in this contract (EA-8), no Artifact or serializer is built (§23 Sections Not
    Re-scoped), and the legacy `edit_export_*` family is never touched (EA-10).
    """

    from lectureos.application.lecture_edit_export_assembly import (
        LectureEditExportAssemblyService,
    )
    from lectureos.persistence.lecture_edit_export_assembly import (
        SQLiteEditExportAssemblyCommandPersistence,
        SQLiteEditExportAssemblyRepository,
        SQLiteEditExportScopeRepository,
    )

    return LectureEditExportAssemblyService(
        review_service=compose_sqlite_lecture_review_service(connection),
        scope_query=SQLiteEditExportScopeRepository(connection),
        assembly_query=SQLiteEditExportAssemblyRepository(connection),
        persistence=SQLiteEditExportAssemblyCommandPersistence(connection),
    )


def compose_sqlite_lecture_analysis_segmentation_service(
    connection: sqlite3.Connection,
) -> "LectureAnalysisSegmentationService":
    """Build effective-generation Lecture Segmentation on one caller connection (042 §7.2).

    Every command re-derives the anchoring admission's authority standing through the released
    GOAL-023 service — no authority resolver is reimplemented here — and admits only at `current`.
    One ordered batch of immutable canonical segments is appended atomically; only
    `lecture_analysis_segments` is written and every upstream record is read-only. No Analysis
    Finding is required or created (the two are siblings, 042 §7.2 S-3), and no provider, AI,
    ProcessingRun, UnitExecution, or DomainResult exists in this contract. The legacy
    execution-coupled `lecture_segments` / `eligible_analysis_inputs` paths are never touched
    (PATCH-0031 S-7, S-12).
    """

    from lectureos.application.lecture_analysis_segment import (
        LectureAnalysisSegmentationService,
    )
    from lectureos.persistence.lecture_analysis_segment import (
        SQLiteLectureAnalysisSegmentCommandPersistence,
        SQLiteLectureAnalysisSegmentRepository,
    )

    return LectureAnalysisSegmentationService(
        compose_sqlite_lecture_analysis_input_admission_service(connection),
        SQLiteLectureAnalysisSegmentRepository(connection),
        SQLiteLectureAnalysisSegmentCommandPersistence(connection),
    )


def compose_sqlite_effective_subtitle_generation_service(
    connection: sqlite3.Connection,
) -> EffectiveSubtitleGenerationService:
    """Build the effective-transcript subtitle generation path on one caller connection (041 §15).

    Source acquisition flows solely through the GOAL-012 consumption boundary (the binding exists
    before generation); the deterministic passthrough generator persists one immutable candidate
    graph — read-only over every upstream record; only the `subtitle_effective_*` tables are
    written. Legacy subtitle tables are never touched.
    """

    consumption = compose_sqlite_effective_transcript_consumption_service(connection)
    candidates = SQLiteEffectiveSubtitleCandidateRepository(connection)
    persistence = SQLiteEffectiveSubtitleCandidateCommandPersistence(connection)
    return EffectiveSubtitleGenerationService(consumption, candidates, persistence)


def compose_sqlite_effective_subtitle_review_preparation_service(
    connection: sqlite3.Connection,
) -> EffectiveSubtitleReviewPreparationService:
    """Build effective-source subtitle review preparation on one caller connection (GOAL-014).

    Preparation binds one exact immutable candidate graph as an immutable review subject —
    read-only over candidates, cues, bindings, and every authority record; only
    `subtitle_effective_review_subjects` is written. No Human Decision, reviewer, or legacy
    review record is created.
    """

    generation = compose_sqlite_effective_subtitle_generation_service(connection)
    subjects = SQLiteEffectiveSubtitleReviewSubjectRepository(connection)
    persistence = SQLiteEffectiveSubtitleReviewSubjectCommandPersistence(connection)
    return EffectiveSubtitleReviewPreparationService(generation, subjects, persistence)


def compose_sqlite_effective_subtitle_review_decision_service(
    connection: sqlite3.Connection,
) -> EffectiveSubtitleReviewDecisionService:
    """Build Human Decisions over effective-source review subjects on one caller connection (GOAL-015).

    The GOAL-009 authority idiom over GOAL-014 review subjects: explicit append-only decisions with
    derived current authority and derived applicability — read-only over subjects, candidates, and
    every upstream record; only `subtitle_effective_review_decisions` is written.
    """

    preparation = compose_sqlite_effective_subtitle_review_preparation_service(connection)
    generation = compose_sqlite_effective_subtitle_generation_service(connection)
    decisions = SQLiteEffectiveSubtitleReviewDecisionRepository(connection)
    persistence = SQLiteEffectiveSubtitleReviewDecisionCommandPersistence(connection)
    return EffectiveSubtitleReviewDecisionService(
        preparation, generation, decisions, persistence
    )


def compose_sqlite_effective_subtitle_final_selection_service(
    connection: sqlite3.Connection,
) -> EffectiveSubtitleFinalSelectionService:
    """Build Final Subtitle Selection Authority on one caller connection (GOAL-016).

    The GOAL-011 selection idiom over GOAL-014/015 authority lineage: derived eligibility
    (current applicable Accept required), explicit append-only selections with derived current
    and derived applicability — read-only over every upstream record; only
    `subtitle_effective_final_selections` is written. No export or legacy record is created.
    """

    preparation = compose_sqlite_effective_subtitle_review_preparation_service(connection)
    decisions = compose_sqlite_effective_subtitle_review_decision_service(connection)
    selections = SQLiteEffectiveSubtitleFinalSelectionRepository(connection)
    persistence = SQLiteEffectiveSubtitleFinalSelectionCommandPersistence(connection)
    return EffectiveSubtitleFinalSelectionService(
        preparation, decisions, selections, persistence
    )


def compose_sqlite_effective_subtitle_srt_artifact_service(
    connection: sqlite3.Connection,
) -> EffectiveSubtitleSrtArtifactService:
    """Build logical SRT artifact generation on one caller connection (GOAL-017).

    Derived export eligibility (current applicable Final Selection required), the released
    canonical SRT serializer, and immutable logical artifacts — read-only over every upstream
    record; only `subtitle_effective_srt_artifacts` is written. No file, path, materialization,
    or legacy export record is created.
    """

    selections = compose_sqlite_effective_subtitle_final_selection_service(connection)
    generation = compose_sqlite_effective_subtitle_generation_service(connection)
    artifacts = SQLiteEffectiveSubtitleSrtArtifactRepository(connection)
    persistence = SQLiteEffectiveSubtitleSrtArtifactCommandPersistence(connection)
    return EffectiveSubtitleSrtArtifactService(
        selections, generation, artifacts, persistence
    )


def compose_sqlite_effective_srt_materialization_service(
    connection: sqlite3.Connection,
    storage_root: str,
) -> EffectiveSrtMaterializationService:
    """Build physical SRT materialization on one caller connection + one approved Storage Root
    (GOAL-018). Record-first: the immutable intent is durable before any write, the immutable
    terminal outcome after; only the `subtitle_effective_srt_materialization*` tables and files
    beneath the approved root are touched. Artifact identity never depends on any path.
    """

    from lectureos.infrastructure.local_effective_srt_file_writer import (
        LocalEffectiveSrtFileWriter,
    )

    artifacts = compose_sqlite_effective_subtitle_srt_artifact_service(connection)
    materializations = SQLiteEffectiveSrtMaterializationRepository(connection)
    persistence = SQLiteEffectiveSrtMaterializationCommandPersistence(connection)
    writer = LocalEffectiveSrtFileWriter(storage_root)
    return EffectiveSrtMaterializationService(
        artifacts, materializations, persistence, writer
    )


def compose_sqlite_effective_srt_delivery_service(
    connection: sqlite3.Connection,
    storage_root: str,
    delivery_root: str,
) -> EffectiveSrtDeliveryService:
    """Build explicit delivery on one caller connection, one approved Storage Root (source), and
    one approved Delivery Root (destination) (GOAL-019). Record-first: the immutable intent is
    durable before any destination write, the immutable terminal outcome after; only the
    `subtitle_effective_srt_delivery_*` tables and files beneath the approved Delivery Root are
    touched. Delivery never publishes, never creates a URL, and never mutates Artifact or
    Materialization records.
    """

    from lectureos.infrastructure.local_effective_srt_delivery_writer import (
        LocalEffectiveSrtDeliveryWriter,
    )

    artifacts = compose_sqlite_effective_subtitle_srt_artifact_service(connection)
    materializations = SQLiteEffectiveSrtMaterializationRepository(connection)
    deliveries = SQLiteEffectiveSrtDeliveryRepository(connection)
    persistence = SQLiteEffectiveSrtDeliveryCommandPersistence(connection)
    source_reader = LocalEffectiveSrtDeliveryWriter(storage_root)
    destination_writer = LocalEffectiveSrtDeliveryWriter(delivery_root)
    return EffectiveSrtDeliveryService(
        artifacts,
        materializations,
        deliveries,
        persistence,
        source_reader,
        destination_writer,
    )


def compose_sqlite_effective_srt_publication_service(
    connection: sqlite3.Connection,
    delivery_root: str | None = None,
) -> EffectiveSrtPublicationService:
    """Build publication authority on one caller connection (GOAL-020). Publication is an
    explicit append-only Human Authority record over one exact DELIVERED delivery — it writes
    no file, creates no URL, performs no network operation, and never mutates artifact,
    materialization, or delivery records. The optional approved Delivery Root enables purely
    observational destination-agreement and availability derivation; without it, availability
    honestly reports ``not_observed``. No root is ever persisted.
    """

    destination_reader = None
    if delivery_root is not None:
        from lectureos.infrastructure.local_effective_srt_delivery_writer import (
            LocalEffectiveSrtDeliveryWriter,
        )

        destination_reader = LocalEffectiveSrtDeliveryWriter(delivery_root)
    artifacts = compose_sqlite_effective_subtitle_srt_artifact_service(connection)
    materializations = SQLiteEffectiveSrtMaterializationRepository(connection)
    deliveries = SQLiteEffectiveSrtDeliveryRepository(connection)
    publications = SQLiteEffectiveSrtPublicationRepository(connection)
    persistence = SQLiteEffectiveSrtPublicationCommandPersistence(connection)
    return EffectiveSrtPublicationService(
        deliveries,
        materializations,
        artifacts,
        publications,
        persistence,
        destination_reader,
    )


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
