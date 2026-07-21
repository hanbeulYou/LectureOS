"""Provider-independent Application contract for Transcript Applicability.

Derives the applicability of a proposed Transcript Revision deterministically from a canonical
Human Review Decision and records it as an immutable aggregate. It selects no current revision,
produces no Transcript Ready state, and triggers no downstream automation. Application owns
Applicability identity, lifecycle, provenance, persistence and reconstruction. The evaluation
is a pure function of the source decision kind, so reconstruction and replay are deterministic;
no wall-clock is read.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference, ProcessingState
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptRevisionId

from .identities import TranscriptApplicabilityEvaluationId, TranscriptReviewDecisionId
from .transcript_review_decision import (
    REVIEW_DECISION_RESULT_KIND,
    TranscriptReviewDecision,
)

APPLICABILITY_EVALUATION_RESULT_KIND = "transcript_applicability_evaluation"


class ApplicabilityOutcome(str, Enum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    SUPERSEDED_BY_MODIFICATION = "superseded_by_modification"


_OUTCOME_BY_DECISION_KIND = {
    DecisionKind.ACCEPT: ApplicabilityOutcome.APPLICABLE,
    DecisionKind.REJECT: ApplicabilityOutcome.NOT_APPLICABLE,
    DecisionKind.MODIFY: ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION,
}


def outcome_for_decision_kind(kind: DecisionKind) -> ApplicabilityOutcome:
    """The deterministic applicability outcome for a canonical decision kind."""

    try:
        return _OUTCOME_BY_DECISION_KIND[kind]
    except KeyError:
        raise ValueError(f"unsupported review decision kind: {kind}") from None


@dataclass(frozen=True, slots=True)
class TranscriptApplicabilityEvaluation:
    """Immutable applicability derived from one canonical Human Review Decision."""

    identity: TranscriptApplicabilityEvaluationId
    domain_result_id: DomainResultId
    source_decision_id: TranscriptReviewDecisionId
    decision_kind: DecisionKind
    outcome: ApplicabilityOutcome
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_revision_id: TranscriptRevisionId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_evaluation_id: TranscriptApplicabilityEvaluationId | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("applicability evaluation sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("applicability evaluation reason must not be empty")
        if self.outcome is not outcome_for_decision_kind(self.decision_kind):
            raise ValueError(
                "applicability outcome must match the deterministic decision mapping"
            )
        if self.previous_evaluation_id is not None and self.sequence == 0:
            raise ValueError(
                "first applicability evaluation must not reference a previous evaluation"
            )


@dataclass(frozen=True, slots=True)
class ApplicabilityEvaluationIdentityPlan:
    """Application-owned applicability identities for one evaluation."""

    evaluation_id: TranscriptApplicabilityEvaluationId
    evaluation_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedApplicabilityEvaluation:
    """Immutable canonical applicability records; not yet persisted."""

    evaluation: TranscriptApplicabilityEvaluation
    evaluation_result: DomainResultReference


class ReviewDecisionQuery(Protocol):
    def get(self, identity): ...


class AtomicApplicabilityEvaluationPersistence(Protocol):
    def persist_applicability_evaluation(
        self,
        *,
        evaluation: TranscriptApplicabilityEvaluation,
        evaluation_result: DomainResultReference,
    ) -> None: ...


class TranscriptApplicabilityEvaluationError(ValueError):
    """A structurally valid request that cannot become a canonical evaluation."""


class TranscriptApplicabilityEvaluationService:
    """Derives applicability from a canonical Human Review Decision, deterministically."""

    def __init__(
        self,
        decision_query: ReviewDecisionQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicApplicabilityEvaluationPersistence | None = None,
    ) -> None:
        self._decisions = decision_query
        self._executions = execution_query
        self._persistence = persistence

    def record_evaluation(self, **kwargs) -> PreparedApplicabilityEvaluation:
        prepared = self.evaluate_applicability(**kwargs)
        if self._persistence is None:
            raise RuntimeError("applicability evaluation persistence is not configured")
        self._persistence.persist_applicability_evaluation(
            evaluation=prepared.evaluation,
            evaluation_result=prepared.evaluation_result,
        )
        return prepared

    def evaluate_applicability(
        self,
        *,
        source_decision_id: TranscriptReviewDecisionId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: ApplicabilityEvaluationIdentityPlan,
        sequence: int = 0,
        previous_evaluation_id: TranscriptApplicabilityEvaluationId | None = None,
        reason: str | None = None,
    ) -> PreparedApplicabilityEvaluation:
        decision = self._decisions.get(source_decision_id)
        if decision is None:
            raise KeyError("unknown transcript review decision")
        if not isinstance(decision, TranscriptReviewDecision):
            raise TranscriptApplicabilityEvaluationError(
                "applicability must derive from a canonical Human Review Decision"
            )
        self._require_running_execution(run_id, unit_execution_id)
        outcome = outcome_for_decision_kind(decision.kind)
        resolved_reason = reason if reason is not None else _default_reason(outcome)

        evaluation = TranscriptApplicabilityEvaluation(
            identity=identities.evaluation_id,
            domain_result_id=identities.evaluation_result_id,
            source_decision_id=decision.identity,
            decision_kind=decision.kind,
            outcome=outcome,
            review_item_id=decision.review_item_id,
            candidate_reference_id=decision.candidate_reference_id,
            source_revision_id=decision.source_revision_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            previous_evaluation_id=previous_evaluation_id,
        )
        evaluation_result = DomainResultReference(
            identity=identities.evaluation_result_id,
            kind=APPLICABILITY_EVALUATION_RESULT_KIND,
            upstream_results=(decision.domain_result_id,),
        )
        return PreparedApplicabilityEvaluation(
            evaluation=evaluation, evaluation_result=evaluation_result
        )

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise TranscriptApplicabilityEvaluationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise TranscriptApplicabilityEvaluationError(
                "evaluating applicability requires a running unit execution"
            )


def _default_reason(outcome: ApplicabilityOutcome) -> str:
    return {
        ApplicabilityOutcome.APPLICABLE: "accepted decision makes the revision applicable",
        ApplicabilityOutcome.NOT_APPLICABLE: "rejected decision makes the revision not applicable",
        ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION: (
            "modify decision supersedes the revision"
        ),
    }[outcome]


__all__ = [
    "APPLICABILITY_EVALUATION_RESULT_KIND",
    "ApplicabilityEvaluationIdentityPlan",
    "ApplicabilityOutcome",
    "AtomicApplicabilityEvaluationPersistence",
    "PreparedApplicabilityEvaluation",
    "TranscriptApplicabilityEvaluation",
    "TranscriptApplicabilityEvaluationError",
    "TranscriptApplicabilityEvaluationService",
    "outcome_for_decision_kind",
]
