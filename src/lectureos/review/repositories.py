"""Review persistence contracts using the shared dependency-free repository."""

from lectureos.execution.repositories import InMemoryRepository, Repository

from .identities import (
    ApprovedDecisionId,
    CandidateReconciliationId,
    CandidateReferenceId,
    DecisionModificationId,
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

CandidateReferenceRepository = Repository[CandidateReferenceId, CandidateReference]
ReviewContextRepository = Repository[ReviewContextId, ReviewContext]
ReviewItemRepository = Repository[ReviewItemId, ReviewItem]
ReviewDecisionRepository = Repository[ReviewDecisionId, ReviewDecision]
DecisionModificationRepository = Repository[DecisionModificationId, DecisionModification]
ApprovedDecisionRepository = Repository[ApprovedDecisionId, ApprovedDecision]
ReviewHistoryRepository = Repository[ReviewHistoryEntryId, ReviewHistoryEntry]
StaleCandidateRepository = Repository[StaleCandidateRecordId, StaleCandidateRecord]
ReviewConflictRepository = Repository[ReviewConflictId, ReviewConflict]
CandidateReconciliationRepository = Repository[
    CandidateReconciliationId, CandidateReconciliation
]

__all__ = [
    "ApprovedDecisionRepository",
    "CandidateReconciliationRepository",
    "CandidateReferenceRepository",
    "DecisionModificationRepository",
    "InMemoryRepository",
    "ReviewConflictRepository",
    "ReviewContextRepository",
    "ReviewDecisionRepository",
    "ReviewHistoryRepository",
    "ReviewItemRepository",
    "StaleCandidateRepository",
]
