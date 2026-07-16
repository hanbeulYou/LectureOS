"""Records produced by applying an already-approved Transcript correction."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.review.identities import (
    ApprovedDecisionId,
    CandidateReferenceId,
    DecisionModificationId,
    HumanActorReference,
    ReviewDecisionId,
    ReviewItemId,
)
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)
from lectureos.subtitle.identities import (
    SubtitleCandidateId,
    SubtitleCueId,
    SubtitleRevisionId,
)

from .identities import (
    SubtitleDecisionApplicationResultId,
    SubtitleTextReplacementId,
    TranscriptCorrectionApplicationResultId,
)


class TranscriptCorrectionApplicationStatus(str, Enum):
    APPLIED = "applied"


@dataclass(frozen=True, slots=True)
class TranscriptCorrectionApplicationResult:
    identity: TranscriptCorrectionApplicationResultId
    approved_decision_id: ApprovedDecisionId
    source_decision_id: ReviewDecisionId
    candidate_id: CandidateReferenceId
    modification_id: DecisionModificationId | None
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId | None
    created_revision_id: TranscriptRevisionId
    created_segment_ids: tuple[TranscriptSegmentId, ...]
    actor: HumanActorReference
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    status: TranscriptCorrectionApplicationStatus = (
        TranscriptCorrectionApplicationStatus.APPLIED
    )


@dataclass(frozen=True, slots=True)
class SubtitleTextReplacement:
    identity: SubtitleTextReplacementId
    modification_id: DecisionModificationId
    target_cue_id: SubtitleCueId
    replacement_text: str

    def __post_init__(self) -> None:
        if not self.replacement_text.strip():
            raise ValueError("Subtitle replacement text must not be empty")


@dataclass(frozen=True, slots=True)
class SubtitleDecisionApplicationResult:
    identity: SubtitleDecisionApplicationResultId
    approved_decision_id: ApprovedDecisionId
    source_decision_id: ReviewDecisionId
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    subtitle_candidate_id: SubtitleCandidateId
    modification_id: DecisionModificationId | None
    text_replacement: SubtitleTextReplacement | None
    original_cue_id: SubtitleCueId | None
    replacement_cue_id: SubtitleCueId | None
    created_revision_id: SubtitleRevisionId
    revision_domain_result_id: DomainResultId
    actor: HumanActorReference
    working_context: WorkingContextReference
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    applied_at: datetime
    outcome: str = "applied"

    def __post_init__(self) -> None:
        cue_pair = (self.original_cue_id, self.replacement_cue_id)
        if (self.text_replacement is not None) != all(
            item is not None for item in cue_pair
        ):
            raise ValueError(
                "Subtitle modification result requires replacement specification and Cue pair"
            )
        if self.text_replacement is None and self.modification_id is not None:
            raise ValueError("Accept application result must not reference a modification")
        if (
            self.text_replacement is not None
            and self.modification_id != self.text_replacement.modification_id
        ):
            raise ValueError(
                "Subtitle application result modification references must match"
            )
