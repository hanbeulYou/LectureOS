"""Provider-neutral, interface-independent Edit-Pipeline Review Application Foundation (043 §7.1 → §7.4).

The first Review Pipeline milestone (043_REVIEW_PIPELINE.md §7.4, PATCH-0014). From one human judgment about
exactly one existing durable :class:`EditCandidate` (042 §9.1), admitted read-only, it deterministically
records one immutable :class:`EditReviewDecision` and — when the decision is ``accept`` or ``modify`` — exactly
one immutable :class:`ApprovedEditDecision` (Accept snapshots the Candidate's values; Modify carries the
human-approved replacement). Reject records only the durable decision.

It performs no edit, creates no Review Item/Session/History, assigns no status, and defines no state machine or
UI. Raw provider output and interface objects never reach the canonical domain; the interface submits a
normalized decision and this Application boundary owns admission. Application owns Review identity, admission,
provenance, persistence and reconstruction. No wall-clock is read, so reconstruction and replay are
deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Protocol

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference, ProcessingState
from lectureos.review.identities import HumanActorReference

from .edit_candidate import EditCandidate, require_canonical_candidate_type
from .identities import (
    ApprovedEditDecisionId,
    EditCandidateId,
    EditReviewDecisionId,
)

EDIT_REVIEW_DECISION_RESULT_KIND = "edit_review_decision"
APPROVED_EDIT_DECISION_RESULT_KIND = "approved_edit_decision"


class EditReviewDecisionKind(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    MODIFY = "modify"


_APPROVING_KINDS = (EditReviewDecisionKind.ACCEPT, EditReviewDecisionKind.MODIFY)


def require_decision_kind(value: object) -> EditReviewDecisionKind:
    """Return the decision kind for an exact canonical value; reject unknown values (no coercion)."""

    if isinstance(value, EditReviewDecisionKind):
        return value
    if isinstance(value, str):
        for kind in EditReviewDecisionKind:
            if value == kind.value:
                return kind
    raise ValueError(
        "edit review decision kind must be exactly one of accept, reject, modify"
    )


def _validate_time_range(start: float, end: float) -> None:
    for name, value in (("start", start), ("end", end)):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"approved edit decision range {name} must be a real number")
    if not isfinite(start) or not isfinite(end):
        raise ValueError("approved edit decision time range must be finite")
    if start < 0 or end < 0:
        raise ValueError("approved edit decision time range must not be negative")
    if start > end:
        raise ValueError("approved edit decision start must not be after end")


@dataclass(frozen=True, slots=True)
class EditReviewDecision:
    """Immutable, provenance-bearing human Review Decision anchored to one Edit Candidate."""

    identity: EditReviewDecisionId
    domain_result_id: DomainResultId
    source_candidate_id: EditCandidateId
    decision_kind: EditReviewDecisionKind
    actor: HumanActorReference
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("edit review decision sequence must not be negative")
        if not isinstance(self.decision_kind, EditReviewDecisionKind):
            raise ValueError("edit review decision kind must be an EditReviewDecisionKind")
        if not isinstance(self.actor, HumanActorReference):
            raise ValueError("edit review decision requires a human actor reference")


@dataclass(frozen=True, slots=True)
class ApprovedEditDecision:
    """Immutable, self-contained approved edit snapshot; a future 044 Export input."""

    identity: ApprovedEditDecisionId
    domain_result_id: DomainResultId
    source_decision_id: EditReviewDecisionId
    source_candidate_id: EditCandidateId
    decision_kind: EditReviewDecisionKind
    approved_range_start: float
    approved_range_end: float
    approved_candidate_type: str
    approved_rationale: str
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("approved edit decision sequence must not be negative")
        if self.decision_kind not in _APPROVING_KINDS:
            raise ValueError("approved edit decision kind must be accept or modify")
        require_canonical_candidate_type(self.approved_candidate_type)
        if not self.approved_rationale.strip():
            raise ValueError("approved edit decision rationale must not be empty")
        _validate_time_range(self.approved_range_start, self.approved_range_end)


@dataclass(frozen=True, slots=True)
class NormalizedModification:
    """A complete human-approved replacement of the Candidate's review-relevant values (Modify only)."""

    approved_range_start: float
    approved_range_end: float
    approved_candidate_type: str
    approved_rationale: str

    def __post_init__(self) -> None:
        require_canonical_candidate_type(self.approved_candidate_type)
        if not self.approved_rationale.strip():
            raise ValueError("modification rationale must not be empty")
        _validate_time_range(self.approved_range_start, self.approved_range_end)


@dataclass(frozen=True, slots=True)
class EditReviewIdentityPlan:
    """Application-owned identities for one human Review admission."""

    decision_id: EditReviewDecisionId
    decision_result_id: DomainResultId
    approved_id: ApprovedEditDecisionId | None = None
    approved_result_id: DomainResultId | None = None


@dataclass(frozen=True, slots=True)
class PreparedEditReview:
    """Immutable canonical Review records for one admission; not yet persisted."""

    decision: EditReviewDecision
    decision_result: DomainResultReference
    approved: ApprovedEditDecision | None
    approved_result: DomainResultReference | None


class EditCandidateQuery(Protocol):
    def get(self, identity): ...


class AtomicEditReviewPersistence(Protocol):
    def persist_edit_review(self, *, prepared: PreparedEditReview) -> None: ...


class EditReviewError(ValueError):
    """A structurally valid submission that cannot become a canonical Review record."""


class EditReviewApplicationService:
    """Admits one human decision about one Edit Candidate into durable Review records."""

    def __init__(
        self,
        candidate_query: EditCandidateQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicEditReviewPersistence | None = None,
    ) -> None:
        self._candidates = candidate_query
        self._executions = execution_query
        self._persistence = persistence

    def record_decision(self, **kwargs) -> PreparedEditReview:
        prepared = self.evaluate_decision(**kwargs)
        if self._persistence is None:
            raise RuntimeError("edit review persistence is not configured")
        self._persistence.persist_edit_review(prepared=prepared)
        return prepared

    def evaluate_decision(
        self,
        *,
        source_candidate_id: EditCandidateId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        decision_kind,
        actor: HumanActorReference,
        identities: EditReviewIdentityPlan,
        modification: NormalizedModification | None = None,
    ) -> PreparedEditReview:
        # Admit the review target through its canonical Edit Candidate, read only for provenance. The
        # Candidate and its entire upstream lineage are never mutated.
        candidate = self._candidates.get(source_candidate_id)
        if candidate is None:
            raise KeyError("unknown edit candidate")
        if not isinstance(candidate, EditCandidate):
            raise EditReviewError(
                "edit review must anchor to a canonical Edit Candidate"
            )
        self._require_running_execution(run_id, unit_execution_id)
        if not isinstance(actor, HumanActorReference):
            raise EditReviewError("edit review requires a human actor reference")

        kind = require_decision_kind(decision_kind)
        self._validate_plan_and_modification(kind, identities, modification)

        decision = EditReviewDecision(
            identity=identities.decision_id,
            domain_result_id=identities.decision_result_id,
            source_candidate_id=candidate.identity,
            decision_kind=kind,
            actor=actor,
            source_media_id=candidate.source_media_id,
            source_timeline_id=candidate.source_timeline_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=0,
        )
        decision_result = DomainResultReference(
            identity=identities.decision_result_id,
            kind=EDIT_REVIEW_DECISION_RESULT_KIND,
            source_media=candidate.source_media_id,
            source_timeline=candidate.source_timeline_id,
            upstream_results=(candidate.domain_result_id,),
        )

        approved = None
        approved_result = None
        if kind in _APPROVING_KINDS:
            snapshot = self._approved_snapshot(kind, candidate, modification)
            approved = ApprovedEditDecision(
                identity=identities.approved_id,
                domain_result_id=identities.approved_result_id,
                source_decision_id=decision.identity,
                source_candidate_id=candidate.identity,
                decision_kind=kind,
                approved_range_start=snapshot[0],
                approved_range_end=snapshot[1],
                approved_candidate_type=snapshot[2],
                approved_rationale=snapshot[3],
                source_media_id=candidate.source_media_id,
                source_timeline_id=candidate.source_timeline_id,
                run_id=run_id,
                unit_execution_id=unit_execution_id,
                sequence=0,
            )
            approved_result = DomainResultReference(
                identity=identities.approved_result_id,
                kind=APPROVED_EDIT_DECISION_RESULT_KIND,
                source_media=candidate.source_media_id,
                source_timeline=candidate.source_timeline_id,
                upstream_results=(decision.domain_result_id,),
            )
        return PreparedEditReview(
            decision=decision,
            decision_result=decision_result,
            approved=approved,
            approved_result=approved_result,
        )

    @staticmethod
    def _validate_plan_and_modification(
        kind: EditReviewDecisionKind,
        identities: EditReviewIdentityPlan,
        modification: NormalizedModification | None,
    ) -> None:
        approving = kind in _APPROVING_KINDS
        has_approved_plan = (
            identities.approved_id is not None
            and identities.approved_result_id is not None
        )
        if approving and not has_approved_plan:
            raise EditReviewError(
                "accept and modify require an approved edit decision identity plan"
            )
        if not approving and (
            identities.approved_id is not None
            or identities.approved_result_id is not None
        ):
            raise EditReviewError(
                "reject must not supply an approved edit decision identity plan"
            )
        if kind is EditReviewDecisionKind.MODIFY and modification is None:
            raise EditReviewError("modify requires a complete approved replacement")
        if kind is not EditReviewDecisionKind.MODIFY and modification is not None:
            raise EditReviewError(
                "only modify may supply an approved modification"
            )

    @staticmethod
    def _approved_snapshot(
        kind: EditReviewDecisionKind,
        candidate: EditCandidate,
        modification: NormalizedModification | None,
    ) -> tuple[float, float, str, str]:
        if kind is EditReviewDecisionKind.ACCEPT:
            return (
                candidate.range_start,
                candidate.range_end,
                candidate.candidate_type,
                candidate.rationale,
            )
        assert modification is not None  # guaranteed by _validate_plan_and_modification
        return (
            modification.approved_range_start,
            modification.approved_range_end,
            modification.approved_candidate_type,
            modification.approved_rationale,
        )

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise EditReviewError("unit execution must belong to processing run")
        if execution.state is not ProcessingState.RUNNING:
            raise EditReviewError(
                "recording an edit review decision requires a running unit execution"
            )


__all__ = [
    "APPROVED_EDIT_DECISION_RESULT_KIND",
    "EDIT_REVIEW_DECISION_RESULT_KIND",
    "ApprovedEditDecision",
    "AtomicEditReviewPersistence",
    "EditReviewApplicationService",
    "EditReviewDecision",
    "EditReviewDecisionKind",
    "EditReviewError",
    "EditReviewIdentityPlan",
    "NormalizedModification",
    "PreparedEditReview",
    "require_decision_kind",
]
