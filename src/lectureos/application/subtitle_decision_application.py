"""Provider-independent Application contract for Subtitle Decision Application (041 §4.7).

From exactly one canonical ``SubtitleReviewDecision``, it deterministically applies the recorded Human
Accept/Reject/Modify and produces the next Subtitle revision — a new immutable ``SubtitleDecisionRevision``
reflecting the applied outcome (and, for Modify, the user's modified text) — together with its provenance.

Application is a pure deterministic transformation. The consumed decision remains immutable, and no
existing canonical artifact is modified: the ``SubtitleReviewDecision``, its ``ReviewItem``, its
``SubtitleReviewPreparation`` and the ``SubtitleValidation`` are never mutated. The only newly created
canonical artifact is the ``SubtitleDecisionRevision`` and its ``DomainResultReference``. This stage
never records a decision, never selects a Final Subtitle, and derives no current-selection / readiness /
applicability; it is entirely deterministic and provider-free (no wall-clock is read).
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
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .identities import (
    SubtitleCandidateId,
    SubtitleDecisionRevisionId,
    SubtitleReadingRevisionId,
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)

SUBTITLE_DECISION_REVISION_RESULT_KIND = "subtitle_decision_revision"


class SubtitleAppliedOutcome(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"


_OUTCOME_BY_KIND = {
    DecisionKind.ACCEPT: SubtitleAppliedOutcome.ACCEPTED,
    DecisionKind.REJECT: SubtitleAppliedOutcome.REJECTED,
    DecisionKind.MODIFY: SubtitleAppliedOutcome.MODIFIED,
}


def applied_outcome_for_kind(kind: DecisionKind) -> SubtitleAppliedOutcome:
    """The deterministic applied outcome for a recorded Human decision kind."""

    try:
        return _OUTCOME_BY_KIND[kind]
    except KeyError:
        raise ValueError(f"unsupported decision kind: {kind}") from None


@dataclass(frozen=True, slots=True)
class SubtitleDecisionRevision:
    """Immutable next Subtitle revision produced by applying one Human Review Decision."""

    identity: SubtitleDecisionRevisionId
    domain_result_id: DomainResultId
    source_review_decision_id: SubtitleReviewDecisionId
    decision_kind: DecisionKind
    outcome: SubtitleAppliedOutcome
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_preparation_id: SubtitleReviewPreparationId
    source_validation_id: SubtitleValidationId
    source_time_revision_id: SubtitleTimeRevisionId
    source_reading_revision_id: SubtitleReadingRevisionId
    source_candidate_id: SubtitleCandidateId
    source_finding_id: SubtitleValidationFindingId
    rule: str
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    target_timed_unit_id: SubtitleTimedUnitId | None = None
    applied_text: str | None = None
    previous_revision_id: SubtitleDecisionRevisionId | None = None

    def __post_init__(self) -> None:
        if self.outcome is not applied_outcome_for_kind(self.decision_kind):
            raise ValueError(
                "decision revision outcome must match the deterministic decision mapping"
            )
        if not self.rule.strip():
            raise ValueError("decision revision rule must not be empty")
        if not self.reason.strip():
            raise ValueError("decision revision reason must not be empty")
        if self.sequence < 0:
            raise ValueError("decision revision sequence must not be negative")
        if self.outcome is SubtitleAppliedOutcome.MODIFIED:
            if self.applied_text is None or not self.applied_text.strip():
                raise ValueError("Modified decision revision requires non-empty applied text")
        elif self.applied_text is not None:
            raise ValueError(
                "Accepted and Rejected decision revisions must not carry applied text"
            )
        if self.previous_revision_id is not None and self.sequence == 0:
            raise ValueError(
                "first decision revision must not reference a previous revision"
            )


@dataclass(frozen=True, slots=True)
class SubtitleDecisionRevisionIdentityPlan:
    """Application-owned identities for one decision application."""

    revision_id: SubtitleDecisionRevisionId
    revision_result_id: DomainResultId


__all__ = [
    "SUBTITLE_DECISION_REVISION_RESULT_KIND",
    "SubtitleAppliedOutcome",
    "SubtitleDecisionRevision",
    "SubtitleDecisionRevisionIdentityPlan",
    "applied_outcome_for_kind",
]
