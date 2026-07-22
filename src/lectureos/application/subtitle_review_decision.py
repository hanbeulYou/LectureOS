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
from typing import Protocol

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference, ProcessingState
from lectureos.review.identities import (
    CandidateReferenceId,
    HumanActorReference,
    ReviewItemId,
)
from lectureos.review.models import CandidateReference, DecisionKind, ReviewItem

from .identities import (
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimeRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from .subtitle_review_preparation import SUBTITLE_VALIDATION_FINDING_KIND

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


@dataclass(frozen=True, slots=True)
class PreparedSubtitleReviewDecision:
    """Immutable canonical decision records; not yet persisted."""

    decision: SubtitleReviewDecision
    decision_result: DomainResultReference


class SubtitleReviewPreparationQuery(Protocol):
    def get(self, identity): ...


class ReviewItemQuery(Protocol):
    def get(self, identity: ReviewItemId) -> ReviewItem | None: ...


class CandidateReferenceQuery(Protocol):
    def get(self, identity: CandidateReferenceId) -> CandidateReference | None: ...


class AtomicSubtitleReviewDecisionPersistence(Protocol):
    def persist_subtitle_review_decision(
        self,
        *,
        decision: SubtitleReviewDecision,
        decision_result: DomainResultReference,
    ) -> None: ...


class SubtitleReviewDecisionError(ValueError):
    """A structurally valid request that cannot become a canonical Human Decision."""


class SubtitleReviewDecisionService:
    """Records a Human Accept/Reject/Modify against one subtitle Review Item, applying nothing."""

    def __init__(
        self,
        preparation_query: SubtitleReviewPreparationQuery,
        review_item_query: ReviewItemQuery,
        candidate_reference_query: CandidateReferenceQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicSubtitleReviewDecisionPersistence | None = None,
    ) -> None:
        self._preparations = preparation_query
        self._review_items = review_item_query
        self._candidate_references = candidate_reference_query
        self._executions = execution_query
        self._persistence = persistence

    def record_decision(self, **kwargs) -> PreparedSubtitleReviewDecision:
        prepared = self.prepare_decision(**kwargs)
        if self._persistence is None:
            raise RuntimeError("subtitle review decision persistence is not configured")
        self._persistence.persist_subtitle_review_decision(
            decision=prepared.decision,
            decision_result=prepared.decision_result,
        )
        return prepared

    def prepare_decision(
        self,
        *,
        preparation_id: SubtitleReviewPreparationId,
        review_item_id: ReviewItemId,
        reviewer: HumanActorReference,
        kind: DecisionKind,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: SubtitleReviewDecisionIdentityPlan,
        sequence: int = 0,
        previous_decision_id: SubtitleReviewDecisionId | None = None,
        rationale: str | None = None,
        modified_text: str | None = None,
    ) -> PreparedSubtitleReviewDecision:
        if not isinstance(reviewer, HumanActorReference):
            raise SubtitleReviewDecisionError(
                "only a Human actor can record a Review Decision"
            )
        # The SubtitleReviewPreparation is the container/provenance boundary, not the target.
        preparation = self._preparations.get(preparation_id)
        if preparation is None:
            raise KeyError("unknown subtitle review preparation")
        self._require_running_execution(run_id, unit_execution_id)

        # Human Authority is exercised against exactly one supplied Review Item.
        item = self._review_items.get(review_item_id)
        if item is None:
            raise KeyError("unknown review item")
        link = next(
            (
                candidate
                for candidate in preparation.item_links
                if candidate.review_item_id == item.identity
            ),
            None,
        )
        if link is None:
            raise SubtitleReviewDecisionError(
                "review item does not belong to the review preparation"
            )
        candidate_reference_id = item.candidate_id
        if candidate_reference_id != link.candidate_reference_id:
            raise SubtitleReviewDecisionError(
                "review item candidate reference does not match the preparation"
            )
        candidate_reference = self._candidate_references.get(candidate_reference_id)
        if candidate_reference is None:
            raise KeyError("unknown candidate reference")
        if candidate_reference.kind != SUBTITLE_VALIDATION_FINDING_KIND:
            raise SubtitleReviewDecisionError(
                "only Subtitle Validation Findings can be reviewed here"
            )
        expected_reference = (
            f"subtitle_time_revision:{preparation.source_time_revision_id.value}"
        )
        if candidate_reference.revision_reference != expected_reference:
            raise SubtitleReviewDecisionError(
                "candidate reference provenance does not match the preparation"
            )
        if kind is DecisionKind.MODIFY:
            if modified_text is None or not modified_text.strip():
                raise SubtitleReviewDecisionError(
                    "Modify decision requires non-empty modified text"
                )
        elif modified_text is not None:
            raise SubtitleReviewDecisionError(
                "Accept and Reject decisions must not carry modified text"
            )

        decision = SubtitleReviewDecision(
            identity=identities.decision_id,
            domain_result_id=identities.decision_result_id,
            review_item_id=item.identity,
            candidate_reference_id=candidate_reference_id,
            source_preparation_id=preparation.identity,
            source_validation_id=preparation.source_validation_id,
            source_time_revision_id=preparation.source_time_revision_id,
            source_finding_id=link.source_finding_id,
            rule=link.rule,
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
            kind=SUBTITLE_REVIEW_DECISION_RESULT_KIND,
            source_media=preparation.source_media_id,
            source_timeline=preparation.source_timeline_id,
            upstream_results=(preparation.domain_result_id,),
        )
        return PreparedSubtitleReviewDecision(
            decision=decision, decision_result=decision_result
        )

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise SubtitleReviewDecisionError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise SubtitleReviewDecisionError(
                "recording a review decision requires a running unit execution"
            )


__all__ = [
    "SUBTITLE_REVIEW_DECISION_RESULT_KIND",
    "AtomicSubtitleReviewDecisionPersistence",
    "CandidateReferenceQuery",
    "PreparedSubtitleReviewDecision",
    "ReviewItemQuery",
    "SubtitleReviewDecision",
    "SubtitleReviewDecisionError",
    "SubtitleReviewDecisionIdentityPlan",
    "SubtitleReviewDecisionService",
    "SubtitleReviewPreparationQuery",
]
