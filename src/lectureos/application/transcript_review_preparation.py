"""Provider-independent Application contract for Transcript Review Preparation.

Review Preparation maps a canonical proposed ``CorrectedTranscriptRevision`` and its
``CorrectionCandidate`` set into canonical review targets for later Human Review. It never
records a Review Decision, never changes Transcript state, and never lets a provider own a
Review identity or the Review lifecycle. Application owns Review identity, provenance,
ordering, grouping, metadata, structural integrity and persistence orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.review.identities import (
    CandidateReferenceId,
    ReviewContextId,
    ReviewItemId,
)
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .identities import TranscriptReviewPreparationId

REVIEW_PREPARATION_RESULT_KIND = "transcript_review_preparation"


@dataclass(frozen=True, slots=True)
class ReviewItemGroup:
    """A deterministic grouping of review targets sharing one grouping key."""

    group_key: str
    review_item_ids: tuple[ReviewItemId, ...]

    def __post_init__(self) -> None:
        if not self.group_key.strip():
            raise ValueError("review item group key must not be empty")
        if not self.review_item_ids:
            raise ValueError("review item group must contain at least one item")
        if len(set(self.review_item_ids)) != len(self.review_item_ids):
            raise ValueError("review item group must not repeat an item")


@dataclass(frozen=True, slots=True)
class TranscriptReviewPreparation:
    """Application-owned aggregate presenting a proposed Revision for Human Review."""

    identity: TranscriptReviewPreparationId
    domain_result_id: DomainResultId
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    context_id: ReviewContextId
    candidate_reference_ids: tuple[CandidateReferenceId, ...]
    ordered_item_ids: tuple[ReviewItemId, ...]
    groups: tuple[ReviewItemGroup, ...]
    item_count: int
    structural_valid: bool
    provenance_complete: bool
    ordering_valid: bool

    def __post_init__(self) -> None:
        if self.item_count < 1:
            raise ValueError("review preparation must contain at least one review item")
        if len(self.ordered_item_ids) != self.item_count:
            raise ValueError("ordered review item count must match item count")
        if len(self.candidate_reference_ids) != self.item_count:
            raise ValueError("candidate reference count must match item count")
        if len(set(self.ordered_item_ids)) != len(self.ordered_item_ids):
            raise ValueError("ordered review items must be unique")
        if len(set(self.candidate_reference_ids)) != len(self.candidate_reference_ids):
            raise ValueError("candidate references must be unique")
        if not self.groups:
            raise ValueError("review preparation must contain at least one group")
        grouped = tuple(item for group in self.groups for item in group.review_item_ids)
        if len(grouped) != self.item_count:
            raise ValueError("each review item must belong to exactly one group")
        if set(grouped) != set(self.ordered_item_ids):
            raise ValueError("grouped review items must match ordered review items")


@dataclass(frozen=True, slots=True)
class ReviewPreparationTargetIdentityPlan:
    """Application-owned Review identities for one prepared candidate."""

    candidate_reference_id: CandidateReferenceId
    review_item_id: ReviewItemId


@dataclass(frozen=True, slots=True)
class ReviewPreparationIdentityPlan:
    """Deterministic Application-owned Review identities for one preparation."""

    preparation_id: TranscriptReviewPreparationId
    preparation_result_id: DomainResultId
    context_id: ReviewContextId
    targets: tuple[ReviewPreparationTargetIdentityPlan, ...]

    def __post_init__(self) -> None:
        if not self.targets:
            raise ValueError("review preparation identity plan requires at least one target")
        candidate_ids = tuple(target.candidate_reference_id for target in self.targets)
        item_ids = tuple(target.review_item_id for target in self.targets)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate reference identity plan must be unique")
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("review item identity plan must be unique")


__all__ = [
    "REVIEW_PREPARATION_RESULT_KIND",
    "ReviewItemGroup",
    "ReviewPreparationIdentityPlan",
    "ReviewPreparationTargetIdentityPlan",
    "TranscriptReviewPreparation",
]
