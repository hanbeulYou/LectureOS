"""Provider-independent Application contract for Subtitle Transcript Intake.

The first Subtitle Pipeline stage (041_SUBTITLE_PIPELINE.md §4.1). It evaluates
deterministically, from a canonical Transcript Readiness Evaluation, whether the selected
Corrected Transcript revision is eligible to begin subtitle work, and records it as an immutable
aggregate. Recording intake starts no downstream capability (no candidate generation) and mutates
no upstream record. Application owns intake identity, evaluation, lifecycle, provenance,
persistence and reconstruction. Intake is a pure function of canonical records; no wall-clock is
read, so reconstruction and replay are deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)

from .identities import (
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from .transcript_readiness_evaluation import ReadinessOutcome

SUBTITLE_TRANSCRIPT_INTAKE_RESULT_KIND = "subtitle_transcript_intake"


class SubtitleIntakeOutcome(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"


_INTAKE_BY_READINESS = {
    ReadinessOutcome.READY: SubtitleIntakeOutcome.ELIGIBLE,
    ReadinessOutcome.NOT_READY: SubtitleIntakeOutcome.NOT_ELIGIBLE,
}


def intake_for_readiness_outcome(outcome: ReadinessOutcome) -> SubtitleIntakeOutcome:
    """The deterministic subtitle-intake outcome for a readiness outcome."""

    try:
        return _INTAKE_BY_READINESS[outcome]
    except KeyError:
        raise ValueError(f"unsupported readiness outcome: {outcome}") from None


@dataclass(frozen=True, slots=True)
class SubtitleTranscriptIntake:
    """Immutable subtitle-eligibility record derived from one Readiness Evaluation."""

    identity: SubtitleTranscriptIntakeId
    domain_result_id: DomainResultId
    source_readiness_id: TranscriptReadinessEvaluationId
    readiness_outcome: ReadinessOutcome
    outcome: SubtitleIntakeOutcome
    source_selection_id: TranscriptCurrentSelectionId
    source_applicability_id: TranscriptApplicabilityEvaluationId
    source_decision_id: TranscriptReviewDecisionId
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    validation_id: TranscriptValidationId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_intake_id: SubtitleTranscriptIntakeId | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("subtitle intake sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("subtitle intake reason must not be empty")
        if self.outcome is not intake_for_readiness_outcome(self.readiness_outcome):
            raise ValueError(
                "subtitle intake outcome must match the deterministic readiness mapping"
            )
        if (
            self.outcome is SubtitleIntakeOutcome.ELIGIBLE
            and self.readiness_outcome is not ReadinessOutcome.READY
        ):
            raise ValueError("ELIGIBLE intake requires a READY readiness outcome")
        if self.previous_intake_id is not None and self.sequence == 0:
            raise ValueError(
                "first subtitle intake must not reference a previous intake"
            )


@dataclass(frozen=True, slots=True)
class SubtitleIntakeIdentityPlan:
    """Application-owned intake identities for one evaluation."""

    intake_id: SubtitleTranscriptIntakeId
    intake_result_id: DomainResultId


__all__ = [
    "SUBTITLE_TRANSCRIPT_INTAKE_RESULT_KIND",
    "SubtitleIntakeIdentityPlan",
    "SubtitleIntakeOutcome",
    "SubtitleTranscriptIntake",
    "intake_for_readiness_outcome",
]
