"""Provider-independent Application contract for Transcript Ready State.

Evaluates deterministically whether the currently selected Transcript Revision is ready for
downstream use, from canonical upstream records only, and records it as an immutable aggregate.
Recording READY starts no downstream capability; recording NOT_READY mutates no upstream record.
Application owns readiness identity, evaluation, lifecycle, provenance, persistence and
reconstruction. Readiness is a pure function of canonical records plus a deterministic
recomputation of the Revision's structural Validation, so reconstruction and replay are
deterministic; no wall-clock is read.
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
from lectureos.transcript.boundaries import (
    TranscriptQueryBoundary,
    TranscriptStructuralValidationBoundary,
)
from lectureos.transcript.identities import TranscriptRevisionId, TranscriptValidationId

from .identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from .transcript_applicability_evaluation import (
    ApplicabilityOutcome,
    TranscriptApplicabilityEvaluation,
)
from .transcript_current_selection import (
    CurrentSelectionOutcome,
    TranscriptCurrentSelection,
)

READINESS_EVALUATION_RESULT_KIND = "transcript_readiness_evaluation"


class ReadinessOutcome(str, Enum):
    READY = "ready"
    NOT_READY = "not_ready"


class ReadinessReasonCode(str, Enum):
    ALL_CONDITIONS_MET = "all_conditions_met"
    NOT_SELECTED = "not_selected"
    NOT_APPLICABLE = "not_applicable"
    SUPERSEDED_BY_MODIFICATION = "superseded_by_modification"
    STRUCTURAL_VALIDATION_FAILED = "structural_validation_failed"


def evaluate_readiness_outcome(
    *,
    selection_outcome: CurrentSelectionOutcome,
    applicability_outcome: ApplicabilityOutcome,
    structural_valid: bool,
) -> tuple[ReadinessOutcome, ReadinessReasonCode]:
    """Deterministically map canonical outcomes to a readiness outcome and reason code."""

    if selection_outcome is CurrentSelectionOutcome.NOT_SELECTED:
        if applicability_outcome is ApplicabilityOutcome.NOT_APPLICABLE:
            return ReadinessOutcome.NOT_READY, ReadinessReasonCode.NOT_APPLICABLE
        if applicability_outcome is ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION:
            return (
                ReadinessOutcome.NOT_READY,
                ReadinessReasonCode.SUPERSEDED_BY_MODIFICATION,
            )
        return ReadinessOutcome.NOT_READY, ReadinessReasonCode.NOT_SELECTED
    # selection SELECTED implies applicability APPLICABLE by the selection mapping.
    if not structural_valid:
        return (
            ReadinessOutcome.NOT_READY,
            ReadinessReasonCode.STRUCTURAL_VALIDATION_FAILED,
        )
    return ReadinessOutcome.READY, ReadinessReasonCode.ALL_CONDITIONS_MET


@dataclass(frozen=True, slots=True)
class TranscriptReadinessEvaluation:
    """Immutable readiness derived from one canonical Current Selection lineage."""

    identity: TranscriptReadinessEvaluationId
    domain_result_id: DomainResultId
    source_selection_id: TranscriptCurrentSelectionId
    selection_outcome: CurrentSelectionOutcome
    source_applicability_id: TranscriptApplicabilityEvaluationId
    applicability_outcome: ApplicabilityOutcome
    source_decision_id: TranscriptReviewDecisionId
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_revision_id: TranscriptRevisionId
    validation_id: TranscriptValidationId
    structural_valid: bool
    outcome: ReadinessOutcome
    reason_code: ReadinessReasonCode
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_readiness_id: TranscriptReadinessEvaluationId | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("readiness evaluation sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("readiness evaluation reason must not be empty")
        expected_outcome, expected_reason = evaluate_readiness_outcome(
            selection_outcome=self.selection_outcome,
            applicability_outcome=self.applicability_outcome,
            structural_valid=self.structural_valid,
        )
        if self.outcome is not expected_outcome or self.reason_code is not expected_reason:
            raise ValueError(
                "readiness outcome and reason code must match the deterministic evaluation"
            )
        if self.outcome is ReadinessOutcome.READY:
            if self.reason_code is not ReadinessReasonCode.ALL_CONDITIONS_MET:
                raise ValueError("READY readiness must record ALL_CONDITIONS_MET")
            if self.selection_outcome is not CurrentSelectionOutcome.SELECTED:
                raise ValueError("READY requires a SELECTED current selection")
            if self.applicability_outcome is not ApplicabilityOutcome.APPLICABLE:
                raise ValueError("READY requires an APPLICABLE applicability outcome")
            if not self.structural_valid:
                raise ValueError("READY requires successful structural Validation")
        elif self.reason_code is ReadinessReasonCode.ALL_CONDITIONS_MET:
            raise ValueError("NOT_READY readiness must not record ALL_CONDITIONS_MET")
        if self.previous_readiness_id is not None and self.sequence == 0:
            raise ValueError(
                "first readiness evaluation must not reference a previous evaluation"
            )


@dataclass(frozen=True, slots=True)
class ReadinessEvaluationIdentityPlan:
    """Application-owned readiness identities for one evaluation."""

    readiness_id: TranscriptReadinessEvaluationId
    readiness_result_id: DomainResultId
    validation_id: TranscriptValidationId


@dataclass(frozen=True, slots=True)
class PreparedTranscriptReadiness:
    """Immutable canonical readiness records; not yet persisted."""

    readiness: TranscriptReadinessEvaluation
    readiness_result: DomainResultReference


class CurrentSelectionQuery(Protocol):
    def get(self, identity): ...


class ApplicabilityEvaluationQuery(Protocol):
    def get(self, identity): ...


class ReviewDecisionQuery(Protocol):
    def get(self, identity): ...


class AtomicReadinessEvaluationPersistence(Protocol):
    def persist_readiness_evaluation(
        self,
        *,
        readiness: TranscriptReadinessEvaluation,
        readiness_result: DomainResultReference,
    ) -> None: ...


class TranscriptReadinessEvaluationError(ValueError):
    """A structurally valid request that cannot become a canonical readiness record."""


class TranscriptReadinessEvaluationService:
    """Evaluates Transcript readiness from canonical records, deterministically."""

    def __init__(
        self,
        selection_query: CurrentSelectionQuery,
        applicability_query: ApplicabilityEvaluationQuery,
        decision_query: ReviewDecisionQuery,
        transcript_query: TranscriptQueryBoundary,
        structural_validation: TranscriptStructuralValidationBoundary,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicReadinessEvaluationPersistence | None = None,
    ) -> None:
        self._selections = selection_query
        self._applicabilities = applicability_query
        self._decisions = decision_query
        self._transcripts = transcript_query
        self._validation = structural_validation
        self._executions = execution_query
        self._persistence = persistence

    def record_readiness(self, **kwargs) -> PreparedTranscriptReadiness:
        prepared = self.evaluate_readiness(**kwargs)
        if self._persistence is None:
            raise RuntimeError("readiness evaluation persistence is not configured")
        self._persistence.persist_readiness_evaluation(
            readiness=prepared.readiness,
            readiness_result=prepared.readiness_result,
        )
        return prepared

    def evaluate_readiness(
        self,
        *,
        source_selection_id: TranscriptCurrentSelectionId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: ReadinessEvaluationIdentityPlan,
        sequence: int = 0,
        previous_readiness_id: TranscriptReadinessEvaluationId | None = None,
        reason: str | None = None,
    ) -> PreparedTranscriptReadiness:
        selection = self._selections.get(source_selection_id)
        if selection is None:
            raise KeyError("unknown transcript current selection")
        if not isinstance(selection, TranscriptCurrentSelection):
            raise TranscriptReadinessEvaluationError(
                "readiness must derive from a canonical Current Selection"
            )
        self._require_running_execution(run_id, unit_execution_id)

        applicability = self._applicabilities.get(selection.source_applicability_id)
        if applicability is None:
            raise KeyError("unknown transcript applicability evaluation")
        if not isinstance(applicability, TranscriptApplicabilityEvaluation):
            raise TranscriptReadinessEvaluationError(
                "readiness applicability lineage is not canonical"
            )
        self._require_consistent_applicability(selection, applicability)

        decision = self._decisions.get(selection.source_decision_id)
        if decision is None:
            raise KeyError("unknown transcript review decision")
        self._require_consistent_decision(selection, decision)

        revision = self._transcripts.get_corrected_revision(selection.source_revision_id)
        if revision is None:
            raise KeyError("unknown corrected transcript revision")

        validation = self._validation.validate_corrected_revision(
            validation_id=identities.validation_id,
            revision_id=selection.source_revision_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
        )
        if validation.target_revision_id != selection.source_revision_id:
            raise TranscriptReadinessEvaluationError(
                "structural Validation does not target the selected revision"
            )

        outcome, reason_code = evaluate_readiness_outcome(
            selection_outcome=selection.outcome,
            applicability_outcome=selection.applicability_outcome,
            structural_valid=validation.structural_valid,
        )
        resolved_reason = reason if reason is not None else _default_reason(reason_code)

        readiness = TranscriptReadinessEvaluation(
            identity=identities.readiness_id,
            domain_result_id=identities.readiness_result_id,
            source_selection_id=selection.identity,
            selection_outcome=selection.outcome,
            source_applicability_id=applicability.identity,
            applicability_outcome=selection.applicability_outcome,
            source_decision_id=selection.source_decision_id,
            review_item_id=selection.review_item_id,
            candidate_reference_id=selection.candidate_reference_id,
            source_revision_id=selection.source_revision_id,
            validation_id=validation.identity,
            structural_valid=validation.structural_valid,
            outcome=outcome,
            reason_code=reason_code,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            previous_readiness_id=previous_readiness_id,
        )
        readiness_result = DomainResultReference(
            identity=identities.readiness_result_id,
            kind=READINESS_EVALUATION_RESULT_KIND,
            upstream_results=(selection.domain_result_id,),
        )
        return PreparedTranscriptReadiness(
            readiness=readiness, readiness_result=readiness_result
        )

    @staticmethod
    def _require_consistent_applicability(selection, applicability) -> None:
        if applicability.outcome is not selection.applicability_outcome:
            raise TranscriptReadinessEvaluationError(
                "current selection applicability outcome is inconsistent with its source"
            )
        if applicability.source_revision_id != selection.source_revision_id:
            raise TranscriptReadinessEvaluationError(
                "applicability revision lineage does not match current selection"
            )
        if applicability.review_item_id != selection.review_item_id:
            raise TranscriptReadinessEvaluationError(
                "applicability review item lineage does not match current selection"
            )
        if applicability.candidate_reference_id != selection.candidate_reference_id:
            raise TranscriptReadinessEvaluationError(
                "applicability candidate lineage does not match current selection"
            )
        if applicability.source_decision_id != selection.source_decision_id:
            raise TranscriptReadinessEvaluationError(
                "applicability decision lineage does not match current selection"
            )

    @staticmethod
    def _require_consistent_decision(selection, decision) -> None:
        if decision.review_item_id != selection.review_item_id:
            raise TranscriptReadinessEvaluationError(
                "review decision review item lineage does not match current selection"
            )
        if decision.candidate_reference_id != selection.candidate_reference_id:
            raise TranscriptReadinessEvaluationError(
                "review decision candidate lineage does not match current selection"
            )
        if decision.source_revision_id != selection.source_revision_id:
            raise TranscriptReadinessEvaluationError(
                "review decision revision lineage does not match current selection"
            )

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise TranscriptReadinessEvaluationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise TranscriptReadinessEvaluationError(
                "evaluating readiness requires a running unit execution"
            )


def _default_reason(reason_code: ReadinessReasonCode) -> str:
    return {
        ReadinessReasonCode.ALL_CONDITIONS_MET: (
            "selected applicable revision passed structural validation"
        ),
        ReadinessReasonCode.NOT_SELECTED: "revision is not the current selection",
        ReadinessReasonCode.NOT_APPLICABLE: "revision applicability is not applicable",
        ReadinessReasonCode.SUPERSEDED_BY_MODIFICATION: (
            "revision was superseded by a modification"
        ),
        ReadinessReasonCode.STRUCTURAL_VALIDATION_FAILED: (
            "selected revision failed structural validation"
        ),
    }[reason_code]


__all__ = [
    "READINESS_EVALUATION_RESULT_KIND",
    "AtomicReadinessEvaluationPersistence",
    "PreparedTranscriptReadiness",
    "ReadinessEvaluationIdentityPlan",
    "ReadinessOutcome",
    "ReadinessReasonCode",
    "TranscriptReadinessEvaluation",
    "TranscriptReadinessEvaluationError",
    "TranscriptReadinessEvaluationService",
    "evaluate_readiness_outcome",
]
