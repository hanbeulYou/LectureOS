"""Typed identities and references owned by the Review domain."""

from dataclasses import dataclass

from lectureos.execution.identities import OpaqueIdentity, ReviewDecisionId


@dataclass(frozen=True, slots=True)
class CandidateReferenceId(OpaqueIdentity):
    """Reference to an upstream Candidate identity; Review does not own it."""


@dataclass(frozen=True, slots=True)
class ReviewItemId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class ReviewContextId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class DecisionModificationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class ApprovedDecisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class ReviewHistoryEntryId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class ReviewConflictId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class CandidateReconciliationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class StaleCandidateRecordId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class HumanActorReference(OpaqueIdentity):
    """Human authority reference, independent of authentication implementation."""


__all__ = [
    "ApprovedDecisionId",
    "CandidateReconciliationId",
    "CandidateReferenceId",
    "DecisionModificationId",
    "HumanActorReference",
    "ReviewConflictId",
    "ReviewContextId",
    "ReviewDecisionId",
    "ReviewHistoryEntryId",
    "ReviewItemId",
    "StaleCandidateRecordId",
]
