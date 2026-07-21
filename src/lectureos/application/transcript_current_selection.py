"""Provider-independent Application contract for Transcript Current Selection.

Derives which proposed Transcript Revision is currently selected deterministically from a
canonical Applicability evaluation and records it as an immutable aggregate. It selects a
revision only in the sense of "currently selected"; it never implies the Transcript is Ready
and triggers no downstream automation. Application owns Current Selection identity, lifecycle,
provenance, persistence and reconstruction. The selection is a pure function of the source
applicability outcome, so reconstruction and replay are deterministic; no wall-clock is read.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import TranscriptRevisionId

from .identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReviewDecisionId,
)
from .transcript_applicability_evaluation import ApplicabilityOutcome

CURRENT_SELECTION_RESULT_KIND = "transcript_current_selection"


class CurrentSelectionOutcome(str, Enum):
    SELECTED = "selected"
    NOT_SELECTED = "not_selected"


_SELECTION_BY_APPLICABILITY = {
    ApplicabilityOutcome.APPLICABLE: CurrentSelectionOutcome.SELECTED,
    ApplicabilityOutcome.NOT_APPLICABLE: CurrentSelectionOutcome.NOT_SELECTED,
    ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION: CurrentSelectionOutcome.NOT_SELECTED,
}


def selection_for_applicability_outcome(
    outcome: ApplicabilityOutcome,
) -> CurrentSelectionOutcome:
    """The deterministic current-selection outcome for an applicability outcome."""

    try:
        return _SELECTION_BY_APPLICABILITY[outcome]
    except KeyError:
        raise ValueError(f"unsupported applicability outcome: {outcome}") from None


@dataclass(frozen=True, slots=True)
class TranscriptCurrentSelection:
    """Immutable current selection derived from one canonical Applicability evaluation."""

    identity: TranscriptCurrentSelectionId
    domain_result_id: DomainResultId
    source_applicability_id: TranscriptApplicabilityEvaluationId
    applicability_outcome: ApplicabilityOutcome
    outcome: CurrentSelectionOutcome
    source_decision_id: TranscriptReviewDecisionId
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_revision_id: TranscriptRevisionId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_selection_id: TranscriptCurrentSelectionId | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("current selection sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("current selection reason must not be empty")
        if self.outcome is not selection_for_applicability_outcome(
            self.applicability_outcome
        ):
            raise ValueError(
                "current selection outcome must match the deterministic applicability mapping"
            )
        if self.previous_selection_id is not None and self.sequence == 0:
            raise ValueError(
                "first current selection must not reference a previous selection"
            )


@dataclass(frozen=True, slots=True)
class CurrentSelectionIdentityPlan:
    """Application-owned current-selection identities for one selection."""

    selection_id: TranscriptCurrentSelectionId
    selection_result_id: DomainResultId


__all__ = [
    "CURRENT_SELECTION_RESULT_KIND",
    "CurrentSelectionIdentityPlan",
    "CurrentSelectionOutcome",
    "TranscriptCurrentSelection",
    "selection_for_applicability_outcome",
]
