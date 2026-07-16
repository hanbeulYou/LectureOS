"""Immutable records for Human Review, history, and reconciliation."""

from dataclasses import dataclass
from enum import Enum

from lectureos.execution.identities import (
    DiagnosticId,
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)

from .identities import (
    ApprovedDecisionId,
    CandidateReconciliationId,
    CandidateReferenceId,
    DecisionModificationId,
    HumanActorReference,
    ReviewConflictId,
    ReviewContextId,
    ReviewDecisionId,
    ReviewHistoryEntryId,
    ReviewItemId,
    StaleCandidateRecordId,
)


class DecisionKind(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    MODIFY = "modify"


@dataclass(frozen=True, slots=True)
class CandidateReference:
    identity: CandidateReferenceId
    kind: str
    source_domain: str
    domain_result_id: DomainResultId | None = None
    source_media_id: SourceMediaId | None = None
    source_timeline_id: SourceTimelineId | None = None
    run_id: ProcessingRunId | None = None
    unit_execution_id: UnitExecutionId | None = None
    revision_reference: str | None = None
    applicability: str = "undetermined"

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.source_domain.strip():
            raise ValueError("candidate kind and source domain must not be empty")
        if (self.run_id is None) != (self.unit_execution_id is None):
            raise ValueError("candidate execution provenance requires run and unit execution")


@dataclass(frozen=True, slots=True)
class ReviewContext:
    identity: ReviewContextId
    source_media_id: SourceMediaId | None = None
    source_timeline_id: SourceTimelineId | None = None
    domain_result_references: tuple[DomainResultId, ...] = ()
    evidence_references: tuple[str, ...] = ()
    validation_references: tuple[str, ...] = ()
    diagnostic_references: tuple[DiagnosticId, ...] = ()
    previous_history_references: tuple[ReviewHistoryEntryId, ...] = ()
    blocking_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewItem:
    identity: ReviewItemId
    candidate_id: CandidateReferenceId
    context_id: ReviewContextId
    applicability_at_creation: str = "undetermined"
    run_id: ProcessingRunId | None = None
    unit_execution_id: UnitExecutionId | None = None
    decision_references: tuple[ReviewDecisionId, ...] = ()
    stale_references: tuple[StaleCandidateRecordId, ...] = ()
    conflict_references: tuple[ReviewConflictId, ...] = ()

    def __post_init__(self) -> None:
        if (self.run_id is None) != (self.unit_execution_id is None):
            raise ValueError("review item provenance requires run and unit execution")


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    identity: ReviewDecisionId
    review_item_id: ReviewItemId
    candidate_id: CandidateReferenceId
    actor: HumanActorReference
    kind: DecisionKind
    sequence: int
    rationale: str | None = None
    previous_decision_id: ReviewDecisionId | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("decision sequence must not be negative")


@dataclass(frozen=True, slots=True)
class DecisionModification:
    identity: DecisionModificationId
    decision_id: ReviewDecisionId
    candidate_id: CandidateReferenceId
    actor: HumanActorReference
    modified_intent: str
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not self.modified_intent.strip():
            raise ValueError("modified intent must not be empty")


@dataclass(frozen=True, slots=True)
class ApprovedDecision:
    identity: ApprovedDecisionId
    source_decision_id: ReviewDecisionId
    source_candidate_id: CandidateReferenceId
    actor: HumanActorReference
    approved_intent: str
    modification_id: DecisionModificationId | None = None
    applicability: str = "undetermined"

    def __post_init__(self) -> None:
        if not self.approved_intent.strip():
            raise ValueError("approved intent must not be empty")


@dataclass(frozen=True, slots=True)
class ReviewHistoryEntry:
    identity: ReviewHistoryEntryId
    review_item_id: ReviewItemId
    decision_id: ReviewDecisionId
    actor: HumanActorReference
    sequence: int
    previous_entry_id: ReviewHistoryEntryId | None = None


@dataclass(frozen=True, slots=True)
class StaleCandidateRecord:
    identity: StaleCandidateRecordId
    candidate_id: CandidateReferenceId
    reason: str
    related_decision_ids: tuple[ReviewDecisionId, ...] = ()
    changed_upstream_references: tuple[DomainResultId, ...] = ()
    reconciliation_required: bool = True

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("stale reason must not be empty")


@dataclass(frozen=True, slots=True)
class ReviewConflict:
    identity: ReviewConflictId
    description: str
    review_item_id: ReviewItemId | None = None
    candidate_ids: tuple[CandidateReferenceId, ...] = ()
    decision_ids: tuple[ReviewDecisionId, ...] = ()
    human_action_required: bool = True
    resolution_status: str = "unresolved"

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("conflict description must not be empty")
        if self.review_item_id is None and not self.candidate_ids:
            raise ValueError("conflict requires a review item or candidate reference")


@dataclass(frozen=True, slots=True)
class CandidateReconciliation:
    identity: CandidateReconciliationId
    previous_candidate_id: CandidateReferenceId
    new_candidate_id: CandidateReferenceId
    relationship: str
    decision_ids: tuple[ReviewDecisionId, ...] = ()
    human_confirmation_required: bool = True

    def __post_init__(self) -> None:
        if self.previous_candidate_id == self.new_candidate_id:
            raise ValueError("reconciliation requires distinct candidates")
        if not self.relationship.strip():
            raise ValueError("reconciliation relationship must not be empty")
