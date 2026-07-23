"""Provider-neutral, interface-independent Edit-Pipeline Export Application Foundation (044 §19).

The first Edit-Pipeline Export milestone (044_EXPORT_PIPELINE.md §19, PATCH-0015). From exactly one durable
:class:`ApprovedEditDecision` (043 §7.4), admitted read-only, it deterministically records one immutable
:class:`ApprovedEditExportRepresentation`: a durable, canonical, format-neutral structured representation of
the approved edit intent, suitable as a future 044 Export input.

The `ApprovedEditDecision` remains the sole authority for the human-approved edit intent; this representation
is authoritative only for its exported form. It faithfully copies the approved snapshot (range, Candidate
Type/label, rationale, approving kind) from the approved decision and the human actor from its review
decision; it never mutates upstream, reinterprets a Candidate Type as an edit operation, produces any
executable/NLE/serialized/Artifact/file output, or carries a status. Reject decisions produce no approved
decision and therefore no representation. Application owns identity, admission, provenance, persistence and
reconstruction. No wall-clock is read, so reconstruction and replay are deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from .edit_review import (
    ApprovedEditDecision,
    EditReviewDecision,
    EditReviewDecisionKind,
)
from .identities import (
    ApprovedEditDecisionId,
    ApprovedEditExportRepresentationId,
    EditCandidateId,
    EditReviewDecisionId,
)

APPROVED_EDIT_EXPORT_REPRESENTATION_RESULT_KIND = "approved_edit_export_representation"

_APPROVING_KINDS = (EditReviewDecisionKind.ACCEPT, EditReviewDecisionKind.MODIFY)


def _validate_time_range(start: float, end: float) -> None:
    for name, value in (("start", start), ("end", end)):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"export representation range {name} must be a real number")
    if not isfinite(start) or not isfinite(end):
        raise ValueError("export representation time range must be finite")
    if start < 0 or end < 0:
        raise ValueError("export representation time range must not be negative")
    if start > end:
        raise ValueError("export representation start must not be after end")


@dataclass(frozen=True, slots=True)
class ApprovedEditExportRepresentation:
    """Immutable, canonical, format-neutral export representation of one approved edit decision."""

    identity: ApprovedEditExportRepresentationId
    domain_result_id: DomainResultId
    source_approved_decision_id: ApprovedEditDecisionId
    source_review_decision_id: EditReviewDecisionId
    source_candidate_id: EditCandidateId
    decision_kind: EditReviewDecisionKind
    approved_range_start: float
    approved_range_end: float
    approved_candidate_type: str
    approved_rationale: str
    actor: HumanActorReference
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("export representation sequence must not be negative")
        if self.decision_kind not in _APPROVING_KINDS:
            raise ValueError("export representation kind must be accept or modify")
        require_canonical_candidate_type(self.approved_candidate_type)
        if not self.approved_rationale.strip():
            raise ValueError("export representation rationale must not be empty")
        if not isinstance(self.actor, HumanActorReference):
            raise ValueError("export representation requires a human actor reference")
        _validate_time_range(self.approved_range_start, self.approved_range_end)


@dataclass(frozen=True, slots=True)
class ApprovedEditExportIdentityPlan:
    """Application-owned identities for one export admission."""

    representation_id: ApprovedEditExportRepresentationId
    representation_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedApprovedEditExport:
    """Immutable canonical export records for one admission; not yet persisted."""

    representation: ApprovedEditExportRepresentation
    representation_result: DomainResultReference


class ApprovedEditDecisionQuery(Protocol):
    def get(self, identity): ...


class EditReviewDecisionQuery(Protocol):
    def get(self, identity): ...


class EditCandidateQuery(Protocol):
    def get(self, identity): ...


class AtomicApprovedEditExportPersistence(Protocol):
    def persist_export_representation(
        self, *, prepared: PreparedApprovedEditExport
    ) -> None: ...


class EditExportError(ValueError):
    """A structurally valid request that cannot become a canonical export representation."""


class ApprovedEditExportService:
    """Records the durable export representation of one canonical Approved Edit Decision."""

    def __init__(
        self,
        approved_query: ApprovedEditDecisionQuery,
        review_query: EditReviewDecisionQuery,
        candidate_query: EditCandidateQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicApprovedEditExportPersistence | None = None,
    ) -> None:
        self._approved = approved_query
        self._reviews = review_query
        self._candidates = candidate_query
        self._executions = execution_query
        self._persistence = persistence

    def record_representation(self, **kwargs) -> PreparedApprovedEditExport:
        prepared = self.evaluate_representation(**kwargs)
        if self._persistence is None:
            raise RuntimeError("edit export persistence is not configured")
        self._persistence.persist_export_representation(prepared=prepared)
        return prepared

    def evaluate_representation(
        self,
        *,
        source_approved_decision_id: ApprovedEditDecisionId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: ApprovedEditExportIdentityPlan,
    ) -> PreparedApprovedEditExport:
        # Admit exactly one canonical Approved Edit Decision, read only. The approved decision and its whole
        # lineage are never mutated; the approved decision remains authoritative for the approved intent.
        approved = self._approved.get(source_approved_decision_id)
        if approved is None:
            raise KeyError("unknown approved edit decision")
        if not isinstance(approved, ApprovedEditDecision):
            raise EditExportError(
                "edit export must anchor to a canonical Approved Edit Decision"
            )
        self._require_running_execution(run_id, unit_execution_id)
        review, candidate = self._require_consistent_lineage(approved)

        representation = ApprovedEditExportRepresentation(
            identity=identities.representation_id,
            domain_result_id=identities.representation_result_id,
            source_approved_decision_id=approved.identity,
            source_review_decision_id=review.identity,
            source_candidate_id=candidate.identity,
            # Exported snapshot is copied faithfully from the Approved Edit Decision (and its actor from the
            # review decision) — never re-derived from the original Candidate proposal.
            decision_kind=approved.decision_kind,
            approved_range_start=approved.approved_range_start,
            approved_range_end=approved.approved_range_end,
            approved_candidate_type=approved.approved_candidate_type,
            approved_rationale=approved.approved_rationale,
            actor=review.actor,
            source_media_id=approved.source_media_id,
            source_timeline_id=approved.source_timeline_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=0,
        )
        representation_result = DomainResultReference(
            identity=identities.representation_result_id,
            kind=APPROVED_EDIT_EXPORT_REPRESENTATION_RESULT_KIND,
            source_media=approved.source_media_id,
            source_timeline=approved.source_timeline_id,
            upstream_results=(approved.domain_result_id,),
        )
        return PreparedApprovedEditExport(
            representation=representation, representation_result=representation_result
        )

    def _require_consistent_lineage(
        self, approved: ApprovedEditDecision
    ) -> tuple[EditReviewDecision, EditCandidate]:
        review = self._reviews.get(approved.source_decision_id)
        if review is None:
            raise KeyError("unknown edit review decision")
        if not isinstance(review, EditReviewDecision):
            raise EditExportError("approved edit decision must trace to a canonical review decision")
        candidate = self._candidates.get(approved.source_candidate_id)
        if candidate is None:
            raise KeyError("unknown edit candidate")
        if not isinstance(candidate, EditCandidate):
            raise EditExportError("approved edit decision must trace to a canonical edit candidate")
        if approved.decision_kind not in _APPROVING_KINDS:
            raise EditExportError("approved edit decision kind must be accept or modify")
        if review.source_candidate_id != candidate.identity:
            raise EditExportError("review decision must reference the same edit candidate")
        if review.decision_kind != approved.decision_kind:
            raise EditExportError("approved decision kind must match its review decision")
        if (
            approved.source_media_id != candidate.source_media_id
            or approved.source_timeline_id != candidate.source_timeline_id
            or review.source_media_id != candidate.source_media_id
            or review.source_timeline_id != candidate.source_timeline_id
        ):
            raise EditExportError("approved edit decision lineage media/timeline is inconsistent")
        return review, candidate

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise EditExportError("unit execution must belong to processing run")
        if execution.state is not ProcessingState.RUNNING:
            raise EditExportError(
                "recording an edit export representation requires a running unit execution"
            )


__all__ = [
    "APPROVED_EDIT_EXPORT_REPRESENTATION_RESULT_KIND",
    "ApprovedEditExportIdentityPlan",
    "ApprovedEditExportRepresentation",
    "ApprovedEditExportService",
    "AtomicApprovedEditExportPersistence",
    "EditExportError",
    "PreparedApprovedEditExport",
]
