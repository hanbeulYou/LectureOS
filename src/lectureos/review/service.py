"""Application service enforcing Human Authority and append-only review history."""

from dataclasses import replace

from lectureos.execution.identities import PluginReference
from lectureos.execution.repositories import InMemoryRepository

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
    DecisionKind,
    DecisionModification,
    ReviewConflict,
    ReviewContext,
    ReviewDecision,
    ReviewHistoryEntry,
    ReviewItem,
    StaleCandidateRecord,
)


class ReviewService:
    """Owns Human Decisions, but never applies them to upstream candidates."""

    def __init__(self) -> None:
        self.candidates: InMemoryRepository[CandidateReferenceId, CandidateReference] = (
            InMemoryRepository()
        )
        self.contexts: InMemoryRepository[ReviewContextId, ReviewContext] = (
            InMemoryRepository()
        )
        self.items: InMemoryRepository[ReviewItemId, ReviewItem] = InMemoryRepository()
        self.decisions: InMemoryRepository[ReviewDecisionId, ReviewDecision] = (
            InMemoryRepository()
        )
        self.modifications: InMemoryRepository[
            DecisionModificationId, DecisionModification
        ] = InMemoryRepository()
        self.approved_decisions: InMemoryRepository[
            ApprovedDecisionId, ApprovedDecision
        ] = InMemoryRepository()
        self.history: InMemoryRepository[
            ReviewHistoryEntryId, ReviewHistoryEntry
        ] = InMemoryRepository()
        self.stale_records: InMemoryRepository[
            StaleCandidateRecordId, StaleCandidateRecord
        ] = InMemoryRepository()
        self.conflicts: InMemoryRepository[ReviewConflictId, ReviewConflict] = (
            InMemoryRepository()
        )
        self.reconciliations: InMemoryRepository[
            CandidateReconciliationId, CandidateReconciliation
        ] = InMemoryRepository()

    def register_candidate_reference(self, candidate: CandidateReference) -> None:
        self._require_new(self.candidates, candidate.identity, "candidate reference")
        self.candidates.save(candidate)

    def create_review_context(self, context: ReviewContext) -> None:
        self._require_new(self.contexts, context.identity, "review context")
        self.contexts.save(context)

    def create_review_item(self, item: ReviewItem) -> None:
        self._require_new(self.items, item.identity, "review item")
        self._require_candidate(item.candidate_id)
        if self.contexts.get(item.context_id) is None:
            raise KeyError("unknown review context")
        if item.decision_references or item.stale_references or item.conflict_references:
            raise ValueError("new review item cannot contain review history references")
        self.items.save(item)

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
    ) -> tuple[ReviewDecision, ApprovedDecision]:
        item = self._prepare_decision(decision_id, history_id, review_item_id, actor)
        self._require_new(self.approved_decisions, approved_id, "approved decision")
        sequence, previous_decision_id, previous_history_id = self._next_history(item)
        decision = ReviewDecision(
            identity=decision_id,
            review_item_id=item.identity,
            candidate_id=item.candidate_id,
            actor=actor,
            kind=DecisionKind.ACCEPT,
            sequence=sequence,
            rationale=rationale,
            previous_decision_id=previous_decision_id,
        )
        approved = ApprovedDecision(
            identity=approved_id,
            source_decision_id=decision.identity,
            source_candidate_id=item.candidate_id,
            actor=actor,
            approved_intent=approved_intent,
        )
        history = self._history_entry(history_id, decision, previous_history_id)
        self._persist_decision(item, decision, history)
        self.approved_decisions.save(approved)
        return decision, approved

    def record_reject(
        self,
        *,
        decision_id: ReviewDecisionId,
        history_id: ReviewHistoryEntryId,
        review_item_id: ReviewItemId,
        actor: HumanActorReference,
        rationale: str | None = None,
    ) -> ReviewDecision:
        item = self._prepare_decision(decision_id, history_id, review_item_id, actor)
        sequence, previous_decision_id, previous_history_id = self._next_history(item)
        decision = ReviewDecision(
            identity=decision_id,
            review_item_id=item.identity,
            candidate_id=item.candidate_id,
            actor=actor,
            kind=DecisionKind.REJECT,
            sequence=sequence,
            rationale=rationale,
            previous_decision_id=previous_decision_id,
        )
        history = self._history_entry(history_id, decision, previous_history_id)
        self._persist_decision(item, decision, history)
        return decision

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
    ) -> tuple[ReviewDecision, DecisionModification, ApprovedDecision]:
        item = self._prepare_decision(decision_id, history_id, review_item_id, actor)
        self._require_new(self.modifications, modification_id, "decision modification")
        self._require_new(self.approved_decisions, approved_id, "approved decision")
        sequence, previous_decision_id, previous_history_id = self._next_history(item)
        decision = ReviewDecision(
            identity=decision_id,
            review_item_id=item.identity,
            candidate_id=item.candidate_id,
            actor=actor,
            kind=DecisionKind.MODIFY,
            sequence=sequence,
            rationale=rationale,
            previous_decision_id=previous_decision_id,
        )
        modification = DecisionModification(
            identity=modification_id,
            decision_id=decision.identity,
            candidate_id=item.candidate_id,
            actor=actor,
            modified_intent=modified_intent,
            rationale=rationale,
        )
        approved = ApprovedDecision(
            identity=approved_id,
            source_decision_id=decision.identity,
            source_candidate_id=item.candidate_id,
            actor=actor,
            approved_intent=modified_intent,
            modification_id=modification.identity,
        )
        history = self._history_entry(history_id, decision, previous_history_id)
        self._persist_decision(item, decision, history)
        self.modifications.save(modification)
        self.approved_decisions.save(approved)
        return decision, modification, approved

    def mark_candidate_stale(self, record: StaleCandidateRecord) -> None:
        self._require_new(self.stale_records, record.identity, "stale candidate record")
        self._require_candidate(record.candidate_id)
        self._require_decisions(record.related_decision_ids)
        affected_items = tuple(
            item for item in self.items.all() if item.candidate_id == record.candidate_id
        )
        self.stale_records.save(record)
        for item in affected_items:
            self.items.save(
                replace(item, stale_references=item.stale_references + (record.identity,))
            )

    def record_conflict(self, conflict: ReviewConflict) -> None:
        self._require_new(self.conflicts, conflict.identity, "review conflict")
        if conflict.review_item_id is not None:
            item = self._require_item(conflict.review_item_id)
        else:
            item = None
        for candidate_id in conflict.candidate_ids:
            self._require_candidate(candidate_id)
        self._require_decisions(conflict.decision_ids)
        self.conflicts.save(conflict)
        if item is not None:
            self.items.save(
                replace(item, conflict_references=item.conflict_references + (conflict.identity,))
            )

    def record_reconciliation(self, reconciliation: CandidateReconciliation) -> None:
        self._require_new(
            self.reconciliations, reconciliation.identity, "candidate reconciliation"
        )
        self._require_candidate(reconciliation.previous_candidate_id)
        self._require_candidate(reconciliation.new_candidate_id)
        self._require_decisions(reconciliation.decision_ids)
        self.reconciliations.save(reconciliation)

    def get_candidate_reference(
        self, identity: CandidateReferenceId
    ) -> CandidateReference | None:
        return self.candidates.get(identity)

    def get_review_context(self, identity: ReviewContextId) -> ReviewContext | None:
        return self.contexts.get(identity)

    def get_review_item(self, identity: ReviewItemId) -> ReviewItem | None:
        return self.items.get(identity)

    def get_decision(self, identity: ReviewDecisionId) -> ReviewDecision | None:
        return self.decisions.get(identity)

    def get_modification(
        self, identity: DecisionModificationId
    ) -> DecisionModification | None:
        return self.modifications.get(identity)

    def get_approved_decision(
        self, identity: ApprovedDecisionId
    ) -> ApprovedDecision | None:
        return self.approved_decisions.get(identity)

    def get_review_history(
        self, review_item_id: ReviewItemId
    ) -> tuple[ReviewHistoryEntry, ...]:
        return tuple(
            sorted(
                (entry for entry in self.history.all() if entry.review_item_id == review_item_id),
                key=lambda entry: entry.sequence,
            )
        )

    def get_stale_record(
        self, identity: StaleCandidateRecordId
    ) -> StaleCandidateRecord | None:
        return self.stale_records.get(identity)

    def get_conflict(self, identity: ReviewConflictId) -> ReviewConflict | None:
        return self.conflicts.get(identity)

    def get_reconciliation(
        self, identity: CandidateReconciliationId
    ) -> CandidateReconciliation | None:
        return self.reconciliations.get(identity)

    def get_stale_records_for_candidate(
        self, candidate_id: CandidateReferenceId
    ) -> tuple[StaleCandidateRecord, ...]:
        return tuple(
            record
            for record in self.stale_records.all()
            if record.candidate_id == candidate_id
        )

    def get_conflicts_for_review_item(
        self, review_item_id: ReviewItemId
    ) -> tuple[ReviewConflict, ...]:
        return tuple(
            conflict
            for conflict in self.conflicts.all()
            if conflict.review_item_id == review_item_id
        )

    def get_reconciliations_for_candidate(
        self, candidate_id: CandidateReferenceId
    ) -> tuple[CandidateReconciliation, ...]:
        return tuple(
            reconciliation
            for reconciliation in self.reconciliations.all()
            if candidate_id in (
                reconciliation.previous_candidate_id,
                reconciliation.new_candidate_id,
            )
        )

    def _prepare_decision(
        self,
        decision_id: ReviewDecisionId,
        history_id: ReviewHistoryEntryId,
        review_item_id: ReviewItemId,
        actor: HumanActorReference,
    ) -> ReviewItem:
        if not isinstance(decision_id, ReviewDecisionId):
            raise TypeError("decision identity must be a ReviewDecisionId")
        if not isinstance(history_id, ReviewHistoryEntryId):
            raise TypeError("history identity must be a ReviewHistoryEntryId")
        self._require_human_actor(actor)
        item = self._require_item(review_item_id)
        self._require_new(self.decisions, decision_id, "review decision")
        self._require_new(self.history, history_id, "review history entry")
        return item

    def _next_history(
        self, item: ReviewItem
    ) -> tuple[int, ReviewDecisionId | None, ReviewHistoryEntryId | None]:
        entries = self.get_review_history(item.identity)
        previous_history_id = entries[-1].identity if entries else None
        previous_decision_id = entries[-1].decision_id if entries else None
        return len(entries), previous_decision_id, previous_history_id

    @staticmethod
    def _history_entry(
        identity: ReviewHistoryEntryId,
        decision: ReviewDecision,
        previous_entry_id: ReviewHistoryEntryId | None,
    ) -> ReviewHistoryEntry:
        return ReviewHistoryEntry(
            identity=identity,
            review_item_id=decision.review_item_id,
            decision_id=decision.identity,
            actor=decision.actor,
            sequence=decision.sequence,
            previous_entry_id=previous_entry_id,
        )

    def _persist_decision(
        self,
        item: ReviewItem,
        decision: ReviewDecision,
        history: ReviewHistoryEntry,
    ) -> None:
        self.decisions.save(decision)
        self.history.save(history)
        self.items.save(
            replace(item, decision_references=item.decision_references + (decision.identity,))
        )

    def _require_candidate(self, identity: CandidateReferenceId) -> CandidateReference:
        candidate = self.candidates.get(identity)
        if candidate is None:
            raise KeyError("unknown candidate reference")
        return candidate

    def _require_item(self, identity: ReviewItemId) -> ReviewItem:
        item = self.items.get(identity)
        if item is None:
            raise KeyError("unknown review item")
        return item

    def _require_decisions(self, identities: tuple[ReviewDecisionId, ...]) -> None:
        for identity in identities:
            if self.decisions.get(identity) is None:
                raise KeyError("unknown review decision")

    @staticmethod
    def _require_human_actor(actor: HumanActorReference) -> None:
        if not isinstance(actor, HumanActorReference):
            source = "plugin" if isinstance(actor, PluginReference) else "non-human"
            raise TypeError(f"{source} reference cannot exercise Human Authority")

    @staticmethod
    def _require_new(repository, identity, label: str) -> None:
        if repository.get(identity) is not None:
            raise ValueError(f"{label} identity already exists")
