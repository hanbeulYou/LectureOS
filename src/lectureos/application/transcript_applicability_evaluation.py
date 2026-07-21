"""Provider-independent Application contract for Transcript Applicability.

Derives the applicability of a proposed Transcript Revision deterministically from a canonical
Human Review Decision and records it as an immutable aggregate. It selects no current revision,
produces no Transcript Ready state, and triggers no downstream automation. Application owns
Applicability identity, lifecycle, provenance, persistence and reconstruction. The evaluation
is a pure function of the source decision kind, so reconstruction and replay are deterministic;
no wall-clock is read.
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
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptRevisionId

from .identities import TranscriptApplicabilityEvaluationId, TranscriptReviewDecisionId

APPLICABILITY_EVALUATION_RESULT_KIND = "transcript_applicability_evaluation"


class ApplicabilityOutcome(str, Enum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    SUPERSEDED_BY_MODIFICATION = "superseded_by_modification"


_OUTCOME_BY_DECISION_KIND = {
    DecisionKind.ACCEPT: ApplicabilityOutcome.APPLICABLE,
    DecisionKind.REJECT: ApplicabilityOutcome.NOT_APPLICABLE,
    DecisionKind.MODIFY: ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION,
}


def outcome_for_decision_kind(kind: DecisionKind) -> ApplicabilityOutcome:
    """The deterministic applicability outcome for a canonical decision kind."""

    try:
        return _OUTCOME_BY_DECISION_KIND[kind]
    except KeyError:
        raise ValueError(f"unsupported review decision kind: {kind}") from None


@dataclass(frozen=True, slots=True)
class TranscriptApplicabilityEvaluation:
    """Immutable applicability derived from one canonical Human Review Decision."""

    identity: TranscriptApplicabilityEvaluationId
    domain_result_id: DomainResultId
    source_decision_id: TranscriptReviewDecisionId
    decision_kind: DecisionKind
    outcome: ApplicabilityOutcome
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_revision_id: TranscriptRevisionId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_evaluation_id: TranscriptApplicabilityEvaluationId | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("applicability evaluation sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("applicability evaluation reason must not be empty")
        if self.outcome is not outcome_for_decision_kind(self.decision_kind):
            raise ValueError(
                "applicability outcome must match the deterministic decision mapping"
            )
        if self.previous_evaluation_id is not None and self.sequence == 0:
            raise ValueError(
                "first applicability evaluation must not reference a previous evaluation"
            )


@dataclass(frozen=True, slots=True)
class ApplicabilityEvaluationIdentityPlan:
    """Application-owned applicability identities for one evaluation."""

    evaluation_id: TranscriptApplicabilityEvaluationId
    evaluation_result_id: DomainResultId


__all__ = [
    "APPLICABILITY_EVALUATION_RESULT_KIND",
    "ApplicabilityEvaluationIdentityPlan",
    "ApplicabilityOutcome",
    "TranscriptApplicabilityEvaluation",
    "outcome_for_decision_kind",
]
