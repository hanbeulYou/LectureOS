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

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import TranscriptRevisionId, TranscriptValidationId

from .identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from .transcript_applicability_evaluation import ApplicabilityOutcome
from .transcript_current_selection import CurrentSelectionOutcome

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


__all__ = [
    "READINESS_EVALUATION_RESULT_KIND",
    "ReadinessEvaluationIdentityPlan",
    "ReadinessOutcome",
    "ReadinessReasonCode",
    "TranscriptReadinessEvaluation",
    "evaluate_readiness_outcome",
]
