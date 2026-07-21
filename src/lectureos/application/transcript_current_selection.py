"""Provider-independent Application contract for Transcript Current Selection.

Derives which proposed Transcript Revision is currently selected deterministically from a
canonical Applicability evaluation and records it as an immutable aggregate. It selects a
revision only in the sense of "currently selected"; it never implies the Transcript is Ready
and triggers no downstream automation. Application owns Current Selection identity, lifecycle,
provenance, persistence and reconstruction. The selection is a pure function of the source
applicability outcome, so reconstruction and replay are deterministic; no wall-clock is read.
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
from lectureos.transcript.identities import TranscriptRevisionId

from .identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReviewDecisionId,
)
from .transcript_applicability_evaluation import (
    ApplicabilityOutcome,
    TranscriptApplicabilityEvaluation,
)

CURRENT_SELECTION_RESULT_KIND = "transcript_current_selection"


class CurrentSelectionOutcome(str, Enum):
    SELECTED = "selected"
    NOT_SELECTED = "not_selected"


_SELECTION_BY_APPLICABILITY = {
    ApplicabilityOutcome.APPLICABLE: CurrentSelectionOutcome.SELECTED,
    ApplicabilityOutcome.NOT_APPLICABLE: CurrentSelectionOutcome.NOT_SELECTED,
    ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION: CurrentSelectionOutcome.NOT_SELECTED,
}


def selection_for_applicability_outcome(
    outcome: ApplicabilityOutcome,
) -> CurrentSelectionOutcome:
    """The deterministic current-selection outcome for an applicability outcome."""

    try:
        return _SELECTION_BY_APPLICABILITY[outcome]
    except KeyError:
        raise ValueError(f"unsupported applicability outcome: {outcome}") from None


@dataclass(frozen=True, slots=True)
class TranscriptCurrentSelection:
    """Immutable current selection derived from one canonical Applicability evaluation."""

    identity: TranscriptCurrentSelectionId
    domain_result_id: DomainResultId
    source_applicability_id: TranscriptApplicabilityEvaluationId
    applicability_outcome: ApplicabilityOutcome
    outcome: CurrentSelectionOutcome
    source_decision_id: TranscriptReviewDecisionId
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_revision_id: TranscriptRevisionId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_selection_id: TranscriptCurrentSelectionId | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("current selection sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("current selection reason must not be empty")
        if self.outcome is not selection_for_applicability_outcome(
            self.applicability_outcome
        ):
            raise ValueError(
                "current selection outcome must match the deterministic applicability mapping"
            )
        if self.previous_selection_id is not None and self.sequence == 0:
            raise ValueError(
                "first current selection must not reference a previous selection"
            )


@dataclass(frozen=True, slots=True)
class CurrentSelectionIdentityPlan:
    """Application-owned current-selection identities for one selection."""

    selection_id: TranscriptCurrentSelectionId
    selection_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedCurrentSelection:
    """Immutable canonical current-selection records; not yet persisted."""

    selection: TranscriptCurrentSelection
    selection_result: DomainResultReference


class ApplicabilityEvaluationQuery(Protocol):
    def get(self, identity): ...


class AtomicCurrentSelectionPersistence(Protocol):
    def persist_current_selection(
        self,
        *,
        selection: TranscriptCurrentSelection,
        selection_result: DomainResultReference,
    ) -> None: ...


class TranscriptCurrentSelectionError(ValueError):
    """A structurally valid request that cannot become a canonical current selection."""


class TranscriptCurrentSelectionService:
    """Derives the current selection from a canonical Applicability evaluation."""

    def __init__(
        self,
        applicability_query: ApplicabilityEvaluationQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicCurrentSelectionPersistence | None = None,
    ) -> None:
        self._applicability = applicability_query
        self._executions = execution_query
        self._persistence = persistence

    def record_selection(self, **kwargs) -> PreparedCurrentSelection:
        prepared = self.evaluate_selection(**kwargs)
        if self._persistence is None:
            raise RuntimeError("current selection persistence is not configured")
        self._persistence.persist_current_selection(
            selection=prepared.selection,
            selection_result=prepared.selection_result,
        )
        return prepared

    def evaluate_selection(
        self,
        *,
        source_applicability_id: TranscriptApplicabilityEvaluationId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: CurrentSelectionIdentityPlan,
        sequence: int = 0,
        previous_selection_id: TranscriptCurrentSelectionId | None = None,
        reason: str | None = None,
    ) -> PreparedCurrentSelection:
        evaluation = self._applicability.get(source_applicability_id)
        if evaluation is None:
            raise KeyError("unknown transcript applicability evaluation")
        if not isinstance(evaluation, TranscriptApplicabilityEvaluation):
            raise TranscriptCurrentSelectionError(
                "current selection must derive from a canonical Applicability evaluation"
            )
        self._require_running_execution(run_id, unit_execution_id)
        outcome = selection_for_applicability_outcome(evaluation.outcome)
        resolved_reason = reason if reason is not None else _default_reason(outcome)

        selection = TranscriptCurrentSelection(
            identity=identities.selection_id,
            domain_result_id=identities.selection_result_id,
            source_applicability_id=evaluation.identity,
            applicability_outcome=evaluation.outcome,
            outcome=outcome,
            source_decision_id=evaluation.source_decision_id,
            review_item_id=evaluation.review_item_id,
            candidate_reference_id=evaluation.candidate_reference_id,
            source_revision_id=evaluation.source_revision_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            previous_selection_id=previous_selection_id,
        )
        selection_result = DomainResultReference(
            identity=identities.selection_result_id,
            kind=CURRENT_SELECTION_RESULT_KIND,
            upstream_results=(evaluation.domain_result_id,),
        )
        return PreparedCurrentSelection(
            selection=selection, selection_result=selection_result
        )

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise TranscriptCurrentSelectionError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise TranscriptCurrentSelectionError(
                "selecting the current revision requires a running unit execution"
            )


def _default_reason(outcome: CurrentSelectionOutcome) -> str:
    return {
        CurrentSelectionOutcome.SELECTED: (
            "applicable revision is currently selected"
        ),
        CurrentSelectionOutcome.NOT_SELECTED: (
            "non-applicable revision is not currently selected"
        ),
    }[outcome]


__all__ = [
    "CURRENT_SELECTION_RESULT_KIND",
    "AtomicCurrentSelectionPersistence",
    "CurrentSelectionIdentityPlan",
    "CurrentSelectionOutcome",
    "PreparedCurrentSelection",
    "TranscriptCurrentSelection",
    "TranscriptCurrentSelectionError",
    "TranscriptCurrentSelectionService",
    "selection_for_applicability_outcome",
]
