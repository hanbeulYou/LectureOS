"""Single-process executable demonstration of the implemented LectureOS slice."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lectureos.application.identities import (
    SubtitleDecisionApplicationResultId,
    TranscriptCorrectionApplicationResultId,
)
from lectureos.application.subtitle_decision import SubtitleDecisionApplicationService
from lectureos.application.subtitle_review import SubtitleReviewIntegrationService
from lectureos.application.transcript_correction import (
    TranscriptCorrectionApplicationService,
)
from lectureos.execution.identities import (
    ArtifactId,
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    ProcessingUnitId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import ExecutionIntent, ProcessingUnit
from lectureos.execution.service import ExecutionService
from lectureos.export.identities import (
    ExportRequestId,
    MaterializationRequestId,
    MaterializationResultId,
    SystemRequesterReference,
)
from lectureos.export.materialization import LocalArtifactMaterializationService
from lectureos.export.models import (
    ExportArtifact,
    ExportRequesterKind,
    ExportRequesterReference,
    ExportTargetMode,
    LocalOverwritePolicy,
    MaterializedFileResult,
)
from lectureos.export.service import MinimalSrtExportService
from lectureos.review.identities import (
    ApprovedDecisionId,
    CandidateReferenceId,
    HumanActorReference,
    ReviewContextId,
    ReviewDecisionId,
    ReviewHistoryEntryId,
    ReviewItemId,
)
from lectureos.review.models import CandidateReference, ReviewContext, ReviewItem
from lectureos.review.service import ReviewService
from lectureos.subtitle.applicability import (
    SubtitleApplicabilityService,
    SubtitleSelectionReason,
)
from lectureos.subtitle.final_selection import (
    FinalSubtitleSelection,
    FinalSubtitleSelectionReason,
    FinalSubtitleSelectionService,
)
from lectureos.subtitle.identities import (
    FinalSubtitleSelectionId,
    SubtitleCandidateId,
    SubtitleCueId,
    SubtitleId,
    SubtitleRevisionApplicabilityId,
    SubtitleRevisionId,
    SubtitleValidationId,
)
from lectureos.subtitle.models import SubtitleCandidate, SubtitleCue, SubtitleRevision
from lectureos.subtitle.service import SubtitleService
from lectureos.subtitle.validation import SubtitleValidationService
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import (
    CorrectedTranscriptRevision,
    CorrectionCandidate,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)
from lectureos.transcript.service import TranscriptService
from lectureos.transcript.validation import TranscriptValidationService


@dataclass(frozen=True, slots=True)
class DemoRunResult:
    raw_transcript: RawTranscript
    transcript_candidate: CorrectionCandidate
    transcript_revision: CorrectedTranscriptRevision
    subtitle_candidate: SubtitleCandidate
    subtitle_revision: SubtitleRevision
    final_selection: FinalSubtitleSelection
    export_artifact: ExportArtifact
    materialization: MaterializedFileResult


@dataclass(frozen=True, slots=True)
class DemoTranscriptSegment:
    text: str
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class DemoTranscriptInput:
    provider_reference: str
    original_content: str
    segments: tuple[DemoTranscriptSegment, ...]
    correction_text: str


def run_end_to_end_demo(
    target_directory: str | Path,
    *,
    filename: str = "lectureos-demo.srt",
) -> DemoRunResult:
    """Run the smallest complete approved pipeline in one Python process."""

    return run_demo_from_transcript(
        target_directory,
        transcript_input=DemoTranscriptInput(
            provider_reference="demo-provider-fixture",
            original_content="안녕 세계",
            segments=(
                DemoTranscriptSegment(text="안녕", start=0.0, end=1.0),
                DemoTranscriptSegment(text="세계", start=1.0, end=2.0),
            ),
            correction_text="안녕하세요",
        ),
        filename=filename,
    )


def run_demo_from_transcript(
    target_directory: str | Path,
    *,
    transcript_input: DemoTranscriptInput,
    filename: str,
) -> DemoRunResult:
    """Run the existing demo orchestration from normalized transcript input."""

    if not transcript_input.segments:
        raise ValueError("demo transcript requires at least one timed segment")

    execution = ExecutionService()
    unit = ProcessingUnit(
        identity=ProcessingUnitId("demo.pipeline"),
        purpose="run the in-process LectureOS demonstration",
        capabilities=(CapabilityReference("demo.orchestration"),),
        result_kinds=(
            "raw_transcript",
            "transcript_correction_candidate",
            "corrected_transcript_revision",
            "subtitle_candidate",
            "subtitle_revision",
        ),
    )
    execution.register_unit(unit)
    run_id = ProcessingRunId("demo-run")
    execution_id = UnitExecutionId("demo-execution")
    working_context = WorkingContextReference("demo-working-context")
    execution.start_run(
        run_id=run_id,
        intent=ExecutionIntent("produce one materialized SRT demo"),
        working_context=working_context,
        unit_ids=(unit.identity,),
    )
    execution.start_unit_execution(
        execution_id=execution_id,
        run_id=run_id,
        unit_id=unit.identity,
    )

    transcript = TranscriptService(execution)
    review = ReviewService()
    media_id = SourceMediaId("demo-source-media")
    timeline_id = SourceTimelineId("demo-source-timeline")
    provider = ProviderTranscriptResult(
        identity=ProviderTranscriptResultId("demo-provider-result"),
        source_media_id=media_id,
        source_timeline_id=timeline_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        capability=CapabilityReference("speech.transcription"),
        provider_reference=transcript_input.provider_reference,
        original_content=transcript_input.original_content,
    )
    transcript.register_provider_result(provider)
    transcript_id = TranscriptId("demo-transcript")
    source_segments = tuple(
        TranscriptSegment(
            identity=TranscriptSegmentId(f"demo-segment-{index + 1}"),
            transcript_id=transcript_id,
            source_timeline_id=timeline_id,
            text=segment.text,
            source_order=index,
            start=segment.start,
            end=segment.end,
        )
        for index, segment in enumerate(transcript_input.segments)
    )
    raw = RawTranscript(
        identity=transcript_id,
        domain_result_id=DomainResultId("demo-raw-result"),
        source_media_id=media_id,
        source_timeline_id=timeline_id,
        provider_result_id=provider.identity,
        run_id=run_id,
        unit_execution_id=execution_id,
        segment_ids=tuple(segment.identity for segment in source_segments),
    )
    transcript.create_raw_transcript(raw, source_segments)

    correction = CorrectionCandidate(
        identity=CorrectionCandidateId("demo-correction-candidate"),
        domain_result_id=DomainResultId("demo-correction-result"),
        transcript_id=raw.identity,
        segment_id=source_segments[0].identity,
        proposed_text=transcript_input.correction_text,
        rationale="demo review of normalized provider transcript",
        run_id=run_id,
        unit_execution_id=execution_id,
    )
    transcript.create_correction_candidate(correction)
    transcript_reference = CandidateReference(
        identity=CandidateReferenceId(correction.identity.value),
        kind="transcript_correction_candidate",
        source_domain="transcript",
        domain_result_id=correction.domain_result_id,
        source_media_id=media_id,
        source_timeline_id=timeline_id,
        run_id=run_id,
        unit_execution_id=execution_id,
    )
    review.register_candidate_reference(transcript_reference)
    review.create_review_context(
        ReviewContext(
            identity=ReviewContextId("demo-transcript-review-context"),
            source_media_id=media_id,
            source_timeline_id=timeline_id,
            domain_result_references=(correction.domain_result_id,),
        )
    )
    transcript_item = ReviewItem(
        identity=ReviewItemId("demo-transcript-review-item"),
        candidate_id=transcript_reference.identity,
        context_id=ReviewContextId("demo-transcript-review-context"),
        run_id=run_id,
        unit_execution_id=execution_id,
    )
    review.create_review_item(transcript_item)
    actor = HumanActorReference("demo-human")
    _, transcript_approval = review.record_accept(
        decision_id=ReviewDecisionId("demo-transcript-decision"),
        history_id=ReviewHistoryEntryId("demo-transcript-history"),
        approved_id=ApprovedDecisionId("demo-transcript-approval"),
        review_item_id=transcript_item.identity,
        actor=actor,
    )
    transcript_application = TranscriptCorrectionApplicationService(
        review, transcript, transcript
    )
    transcript_application_result = (
        transcript_application.apply_approved_transcript_correction(
            approved_decision_id=transcript_approval.identity,
            application_result_id=TranscriptCorrectionApplicationResultId(
                "demo-transcript-application"
            ),
            revision_id=TranscriptRevisionId("demo-transcript-revision"),
            revision_domain_result_id=DomainResultId(
                "demo-transcript-revision-result"
            ),
            replacement_segment_id=TranscriptSegmentId("demo-replacement-segment"),
            run_id=run_id,
            unit_execution_id=execution_id,
        )
    )
    transcript_revision = transcript.get_corrected_revision(
        transcript_application_result.created_revision_id
    )
    if transcript_revision is None:
        raise RuntimeError("Transcript application did not create a revision")
    transcript_validation = TranscriptValidationService(transcript, execution)
    validated_transcript = transcript_validation.validate_corrected_revision(
        validation_id=TranscriptValidationId("demo-transcript-validation"),
        revision_id=transcript_revision.identity,
        run_id=run_id,
        unit_execution_id=execution_id,
    )
    if not validated_transcript.structural_valid:
        raise RuntimeError("demo Transcript revision is structurally invalid")

    subtitle = SubtitleService(transcript, execution)
    subtitle_id = SubtitleId("demo-subtitle")
    cues = tuple(
        SubtitleCue(
            identity=SubtitleCueId(f"demo-cue-{index + 1}"),
            subtitle_id=subtitle_id,
            source_timeline_id=timeline_id,
            start=segment.start,
            end=segment.end,
            text=segment.text,
            display_order=index,
            source_segment_ids=(segment.identity,),
            source_transcript_id=raw.identity,
            source_revision_id=transcript_revision.identity,
        )
        for index, segment_id in enumerate(transcript_revision.segment_ids)
        if (segment := transcript.get_segment(segment_id)) is not None
    )
    if len(cues) != len(transcript_revision.segment_ids):
        raise RuntimeError("demo Transcript revision contains a missing segment")
    subtitle_candidate = SubtitleCandidate(
        identity=SubtitleCandidateId("demo-subtitle-candidate"),
        subtitle_id=subtitle_id,
        domain_result_id=DomainResultId("demo-subtitle-candidate-result"),
        source_transcript_id=raw.identity,
        source_revision_id=transcript_revision.identity,
        source_media_id=media_id,
        source_timeline_id=timeline_id,
        cue_ids=tuple(cue.identity for cue in cues),
        run_id=run_id,
        unit_execution_id=execution_id,
    )
    subtitle.create_candidate(subtitle_candidate, cues)

    subtitle_review = SubtitleReviewIntegrationService(
        subtitle, review, review, execution
    )
    subtitle_item = subtitle_review.create_subtitle_review_item(
        candidate_id=subtitle_candidate.identity,
        review_item_id=ReviewItemId("demo-subtitle-review-item"),
        review_context_id=ReviewContextId("demo-subtitle-review-context"),
    )
    _, subtitle_approval = review.record_accept(
        decision_id=ReviewDecisionId("demo-subtitle-decision"),
        history_id=ReviewHistoryEntryId("demo-subtitle-history"),
        approved_id=ApprovedDecisionId("demo-subtitle-approval"),
        review_item_id=subtitle_item.identity,
        actor=actor,
    )
    subtitle_application = SubtitleDecisionApplicationService(
        review, subtitle, subtitle, execution
    )
    subtitle_application_result = (
        subtitle_application.apply_approved_subtitle_decision(
            approved_decision_id=subtitle_approval.identity,
            application_result_id=SubtitleDecisionApplicationResultId(
                "demo-subtitle-application"
            ),
            revision_id=SubtitleRevisionId("demo-subtitle-revision"),
            revision_domain_result_id=DomainResultId(
                "demo-subtitle-revision-result"
            ),
            run_id=run_id,
            unit_execution_id=execution_id,
        )
    )
    subtitle_revision = subtitle.get_revision(
        subtitle_application_result.created_revision_id
    )
    if subtitle_revision is None:
        raise RuntimeError("Subtitle application did not create a revision")

    applicability = SubtitleApplicabilityService(
        subtitle, execution, review, subtitle_application
    )
    applicability.select_current_revision(
        identity=SubtitleRevisionApplicabilityId("demo-current-subtitle"),
        working_context=working_context,
        revision_id=subtitle_revision.identity,
        actor=actor,
        reason=SubtitleSelectionReason.MANUAL_SELECTION,
    )
    subtitle_validation = SubtitleValidationService(subtitle, transcript, execution)
    validated_subtitle = subtitle_validation.validate_revision_in_context(
        validation_id=SubtitleValidationId("demo-subtitle-validation"),
        revision_id=subtitle_revision.identity,
        working_context=working_context,
        run_id=run_id,
        unit_execution_id=execution_id,
    )
    if not validated_subtitle.structural_valid:
        raise RuntimeError("demo Subtitle revision is structurally invalid")

    final_service = FinalSubtitleSelectionService(
        subtitle, subtitle_validation, applicability, execution
    )
    final_selection = final_service.select_final_subtitle(
        identity=FinalSubtitleSelectionId("demo-final-selection"),
        working_context=working_context,
        revision_id=subtitle_revision.identity,
        actor=actor,
        validation_id=validated_subtitle.identity,
        reason=FinalSubtitleSelectionReason.MANUAL_SELECTION,
    )
    requester = ExportRequesterReference(
        kind=ExportRequesterKind.SYSTEM,
        system_reference=SystemRequesterReference("demo-runner"),
    )
    export_service = MinimalSrtExportService(
        final_service, subtitle, subtitle_validation, applicability
    )
    artifact = export_service.export_final_subtitle_to_srt(
        request_id=ExportRequestId("demo-export-request"),
        artifact_id=ArtifactId("demo-export-artifact"),
        working_context=working_context,
        final_selection_id=final_selection.identity,
        target_mode=ExportTargetMode.ACTIVE_FINAL,
        requester=requester,
    )
    materialization_service = LocalArtifactMaterializationService(export_service)
    materialized = materialization_service.materialize_export_artifact_to_local_file(
        request_id=MaterializationRequestId("demo-materialization-request"),
        result_id=MaterializationResultId("demo-materialization-result"),
        artifact_id=artifact.identity,
        requester=requester,
        target_directory=target_directory,
        requested_filename=filename,
        overwrite_policy=LocalOverwritePolicy.FAIL_IF_EXISTS,
    )
    file_bytes = Path(materialized.final_path).read_bytes()
    if file_bytes.startswith(b"\xef\xbb\xbf"):
        raise RuntimeError("demo SRT unexpectedly contains a UTF-8 BOM")
    if b"\r\n" in file_bytes or file_bytes.decode("utf-8") != artifact.content:
        raise RuntimeError("materialized SRT differs from its Export Artifact")

    return DemoRunResult(
        raw_transcript=raw,
        transcript_candidate=correction,
        transcript_revision=transcript_revision,
        subtitle_candidate=subtitle_candidate,
        subtitle_revision=subtitle_revision,
        final_selection=final_selection,
        export_artifact=artifact,
        materialization=materialized,
    )
