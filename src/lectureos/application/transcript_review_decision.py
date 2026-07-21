"""Provider-independent Application contract for Transcript Human Review Decision.

Records a Human reviewer's Accept, Reject or Modify judgement on a prepared Review Item as an
immutable durable aggregate. It exercises Human Authority only — it never applies the decision,
never changes Transcript selection or applicability, and never triggers any downstream
automation. Application owns Decision identity, lifecycle, provenance, persistence and
reconstruction. The decision timestamp is a caller-supplied command input so that replay is
deterministic; the Application never reads a wall-clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference, ProcessingState
from lectureos.review.identities import CandidateReferenceId, HumanActorReference, ReviewItemId
from lectureos.review.models import CandidateReference, DecisionKind, ReviewItem
from lectureos.transcript.identities import TranscriptRevisionId

from .identities import TranscriptReviewDecisionId
from .transcript_review_preparation import CORRECTION_CANDIDATE_KIND

REVIEW_DECISION_RESULT_KIND = "transcript_review_decision"


@dataclass(frozen=True, slots=True)
class TranscriptReviewDecision:
    """Immutable canonical record of one Human Review judgement."""

    identity: TranscriptReviewDecisionId
    domain_result_id: DomainResultId
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_revision_id: TranscriptRevisionId
    reviewer: HumanActorReference
    kind: DecisionKind
    decided_at: datetime
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    previous_decision_id: TranscriptReviewDecisionId | None = None
    rationale: str | None = None
    modified_text: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reviewer, HumanActorReference):
            raise ValueError("review decision reviewer must be a Human actor")
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
class ReviewDecisionIdentityPlan:
    """Application-owned decision identity and caller-supplied timestamp."""

    decision_id: TranscriptReviewDecisionId
    decision_result_id: DomainResultId
    decided_at: datetime

    def __post_init__(self) -> None:
        if self.decided_at.tzinfo is None:
            raise ValueError("decision timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class PreparedReviewDecision:
    """Immutable canonical decision records; not yet persisted."""

    decision: TranscriptReviewDecision
    decision_result: DomainResultReference


class ReviewItemQuery(Protocol):
    def get(self, identity: ReviewItemId) -> ReviewItem | None: ...


class CandidateReferenceQuery(Protocol):
    def get(self, identity: CandidateReferenceId) -> CandidateReference | None: ...


class ReviewPreparationQuery(Protocol):
    def get(self, identity): ...


class AtomicReviewDecisionPersistence(Protocol):
    def persist_review_decision(
        self,
        *,
        decision: TranscriptReviewDecision,
        decision_result: DomainResultReference,
    ) -> None: ...


class TranscriptReviewDecisionError(ValueError):
    """A structurally valid request that cannot become a canonical Human Decision."""


class TranscriptReviewDecisionService:
    """Records Human Accept/Reject/Modify judgements without applying them anywhere."""

    def __init__(
        self,
        preparation_query: ReviewPreparationQuery,
        review_item_query: ReviewItemQuery,
        candidate_reference_query: CandidateReferenceQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicReviewDecisionPersistence | None = None,
    ) -> None:
        self._preparations = preparation_query
        self._review_items = review_item_query
        self._candidate_references = candidate_reference_query
        self._executions = execution_query
        self._persistence = persistence

    def record_decision(self, **kwargs) -> PreparedReviewDecision:
        prepared = self.prepare_decision(**kwargs)
        if self._persistence is None:
            raise RuntimeError("review decision persistence is not configured")
        self._persistence.persist_review_decision(
            decision=prepared.decision,
            decision_result=prepared.decision_result,
        )
        return prepared

    def prepare_decision(
        self,
        *,
        preparation_id,
        review_item_id: ReviewItemId,
        reviewer: HumanActorReference,
        kind: DecisionKind,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: ReviewDecisionIdentityPlan,
        sequence: int = 0,
        previous_decision_id: TranscriptReviewDecisionId | None = None,
        rationale: str | None = None,
        modified_text: str | None = None,
    ) -> PreparedReviewDecision:
        if not isinstance(reviewer, HumanActorReference):
            raise TranscriptReviewDecisionError(
                "only a Human actor can record a Review Decision"
            )
        preparation = self._preparations.get(preparation_id)
        if preparation is None:
            raise KeyError("unknown transcript review preparation")
        self._require_running_execution(run_id, unit_execution_id)
        item = self._review_items.get(review_item_id)
        if item is None:
            raise KeyError("unknown review item")
        if item.identity not in preparation.ordered_item_ids:
            raise TranscriptReviewDecisionError(
                "review item does not belong to the review preparation"
            )
        candidate_reference_id = item.candidate_id
        if candidate_reference_id not in preparation.candidate_reference_ids:
            raise TranscriptReviewDecisionError(
                "review item candidate is not part of the review preparation"
            )
        candidate_reference = self._candidate_references.get(candidate_reference_id)
        if candidate_reference is None:
            raise KeyError("unknown candidate reference")
        if candidate_reference.kind != CORRECTION_CANDIDATE_KIND:
            raise TranscriptReviewDecisionError(
                "only Transcript Correction Candidates can be reviewed here"
            )
        source_revision_id = preparation.source_revision_id
        expected_revision_reference = f"transcript_revision:{source_revision_id.value}"
        if candidate_reference.revision_reference != expected_revision_reference:
            raise TranscriptReviewDecisionError(
                "candidate reference revision provenance does not match preparation"
            )
        if kind is DecisionKind.MODIFY:
            if modified_text is None or not modified_text.strip():
                raise TranscriptReviewDecisionError(
                    "Modify decision requires non-empty modified text"
                )
        elif modified_text is not None:
            raise TranscriptReviewDecisionError(
                "Accept and Reject decisions must not carry modified text"
            )

        decision = TranscriptReviewDecision(
            identity=identities.decision_id,
            domain_result_id=identities.decision_result_id,
            review_item_id=item.identity,
            candidate_reference_id=candidate_reference_id,
            source_revision_id=source_revision_id,
            reviewer=reviewer,
            kind=kind,
            decided_at=identities.decided_at,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            previous_decision_id=previous_decision_id,
            rationale=rationale,
            modified_text=modified_text,
        )
        decision_result = DomainResultReference(
            identity=identities.decision_result_id,
            kind=REVIEW_DECISION_RESULT_KIND,
            source_media=preparation.source_media_id,
            source_timeline=preparation.source_timeline_id,
            upstream_results=(preparation.domain_result_id,),
        )
        return PreparedReviewDecision(decision=decision, decision_result=decision_result)

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise TranscriptReviewDecisionError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise TranscriptReviewDecisionError(
                "recording a review decision requires a running unit execution"
            )


__all__ = [
    "REVIEW_DECISION_RESULT_KIND",
    "AtomicReviewDecisionPersistence",
    "PreparedReviewDecision",
    "ReviewDecisionIdentityPlan",
    "TranscriptReviewDecision",
    "TranscriptReviewDecisionError",
    "TranscriptReviewDecisionService",
]
