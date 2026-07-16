"""Records produced by applying an already-approved Transcript correction."""

from dataclasses import dataclass
from enum import Enum

from lectureos.execution.identities import ProcessingRunId, UnitExecutionId
from lectureos.review.identities import (
    ApprovedDecisionId,
    CandidateReferenceId,
    DecisionModificationId,
    HumanActorReference,
    ReviewDecisionId,
)
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)

from .identities import TranscriptCorrectionApplicationResultId


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
