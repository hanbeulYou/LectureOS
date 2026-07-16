"""Transport-independent Review command and query boundaries."""

from typing import Protocol

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
from .models import (
    ApprovedDecision,
    CandidateReconciliation,
    CandidateReference,
    DecisionModification,
    ReviewConflict,
    ReviewContext,
    ReviewDecision,
    ReviewHistoryEntry,
    ReviewItem,
    StaleCandidateRecord,
)


class CandidateQueryBoundary(Protocol):
    def get_candidate_reference(
        self, identity: CandidateReferenceId
    ) -> CandidateReference | None: ...


class ReviewCommandBoundary(Protocol):
    def register_candidate_reference(self, candidate: CandidateReference) -> None: ...

    def create_review_context(self, context: ReviewContext) -> None: ...

    def create_review_item(self, item: ReviewItem) -> None: ...

    def record_accept(
        self,
        *,
        decision_id: ReviewDecisionId,
        history_id: ReviewHistoryEntryId,
        approved_id: ApprovedDecisionId,
        review_item_id: ReviewItemId,
        actor: HumanActorReference,
        rationale: str | None = None,
        approved_intent: str = "accept candidate",
    ) -> tuple[ReviewDecision, ApprovedDecision]: ...

    def record_reject(
        self,
        *,
        decision_id: ReviewDecisionId,
        history_id: ReviewHistoryEntryId,
        review_item_id: ReviewItemId,
        actor: HumanActorReference,
        rationale: str | None = None,
    ) -> ReviewDecision: ...

    def record_modify(
        self,
        *,
        decision_id: ReviewDecisionId,
        modification_id: DecisionModificationId,
        history_id: ReviewHistoryEntryId,
        approved_id: ApprovedDecisionId,
        review_item_id: ReviewItemId,
        actor: HumanActorReference,
        modified_intent: str,
        rationale: str | None = None,
    ) -> tuple[ReviewDecision, DecisionModification, ApprovedDecision]: ...

    def mark_candidate_stale(self, record: StaleCandidateRecord) -> None: ...

    def record_conflict(self, conflict: ReviewConflict) -> None: ...

    def record_reconciliation(
        self, reconciliation: CandidateReconciliation
    ) -> None: ...


class ReviewQueryBoundary(CandidateQueryBoundary, Protocol):
    def get_review_context(self, identity: ReviewContextId) -> ReviewContext | None: ...

    def get_review_item(self, identity: ReviewItemId) -> ReviewItem | None: ...

    def get_decision(self, identity: ReviewDecisionId) -> ReviewDecision | None: ...

    def get_modification(
        self, identity: DecisionModificationId
    ) -> DecisionModification | None: ...

    def get_approved_decision(
        self, identity: ApprovedDecisionId
    ) -> ApprovedDecision | None: ...

    def get_review_history(
        self, review_item_id: ReviewItemId
    ) -> tuple[ReviewHistoryEntry, ...]: ...

    def get_stale_record(
        self, identity: StaleCandidateRecordId
    ) -> StaleCandidateRecord | None: ...

    def get_conflict(self, identity: ReviewConflictId) -> ReviewConflict | None: ...

    def get_reconciliation(
        self, identity: CandidateReconciliationId
    ) -> CandidateReconciliation | None: ...
