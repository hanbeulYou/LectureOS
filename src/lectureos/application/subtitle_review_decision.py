"""Provider-independent Application contract for Subtitle Human Review Decision.

Records a Human reviewer's Accept, Reject or Modify judgement against exactly one common ``ReviewItem``
produced by Subtitle Review Preparation, as an immutable durable aggregate. It exercises Human Authority
only — it never applies the decision, produces no Subtitle revision, no Final Subtitle, and no
applicability/selection, and triggers no downstream automation. Application owns Decision identity,
lifecycle, provenance, persistence and reconstruction. The decision timestamp is a caller-supplied
command input so that replay is deterministic; the Application never reads a wall-clock.

Admission boundary: the review target is the supplied ``ReviewItem``. The ``SubtitleReviewPreparation``
is only the immutable container/ordering/provenance boundary for those items; it is validated for
membership and provenance, never operated on as the target, and never mutated. This stage mirrors the
transcript ``TranscriptReviewDecision`` precedent but is subtitle-scoped (candidate reference kind
``subtitle_validation_finding``); it does not reuse the transcript-coupled aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.review.identities import (
    CandidateReferenceId,
    HumanActorReference,
    ReviewItemId,
)
from lectureos.review.models import DecisionKind

from .identities import (
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimeRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)

SUBTITLE_REVIEW_DECISION_RESULT_KIND = "subtitle_review_decision"


@dataclass(frozen=True, slots=True)
class SubtitleReviewDecision:
    """Immutable canonical record of one Human Review judgement on a subtitle Review Item."""

    identity: SubtitleReviewDecisionId
    domain_result_id: DomainResultId
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_preparation_id: SubtitleReviewPreparationId
    source_validation_id: SubtitleValidationId
    source_time_revision_id: SubtitleTimeRevisionId
    source_finding_id: SubtitleValidationFindingId
    rule: str
    reviewer: HumanActorReference
    kind: DecisionKind
    decided_at: datetime
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    previous_decision_id: SubtitleReviewDecisionId | None = None
    rationale: str | None = None
    modified_text: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reviewer, HumanActorReference):
            raise ValueError("review decision reviewer must be a Human actor")
        if not self.rule.strip():
            raise ValueError("subtitle review decision rule must not be empty")
        if self.sequence < 0:
            raise ValueError("review decision sequence must not be negative")
        if self.decided_at.tzinfo is None:
            raise ValueError("review decision timestamp must be timezone-aware")
        if self.kind is DecisionKind.MODIFY:
            if self.modified_text is None or not self.modified_text.strip():
                raise ValueError("Modify decision requires non-empty modified text")
        elif self.modified_text is not None:
            raise ValueError("Accept and Reject decisions must not carry modified text")
        if self.rationale is not None and not self.rationale.strip():
            raise ValueError("review decision rationale must not be blank")
        if self.previous_decision_id is not None and self.sequence == 0:
            raise ValueError("first review decision must not reference a previous decision")


@dataclass(frozen=True, slots=True)
class SubtitleReviewDecisionIdentityPlan:
    """Application-owned decision identity and caller-supplied timestamp."""

    decision_id: SubtitleReviewDecisionId
    decision_result_id: DomainResultId
    decided_at: datetime

    def __post_init__(self) -> None:
        if self.decided_at.tzinfo is None:
            raise ValueError("decision timestamp must be timezone-aware")


__all__ = [
    "SUBTITLE_REVIEW_DECISION_RESULT_KIND",
    "SubtitleReviewDecision",
    "SubtitleReviewDecisionIdentityPlan",
]
