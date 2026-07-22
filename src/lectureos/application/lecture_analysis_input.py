"""Provider-independent Application contract for Lecture Analysis Input Eligibility (042 §5.1).

The first Lecture Intelligence Pipeline stage (042_LECTURE_INTELLIGENCE_PIPELINE.md §5.1, PATCH-0009).
From the validated Corrected Transcript selected by the Transcript Pipeline — admitted read-only through
its canonical Transcript Readiness Evaluation — it deterministically records one immutable **Eligible
Analysis Input**: the validated, durable analysis basis for later Lecture Intelligence stages.

Its sole responsibility is establishing a validated, durable analysis input. It performs **no analysis**
and creates **no** Analysis Finding, Lecture Segment, Segment Label, Edit Candidate, or Review Item, and
performs **no AI reasoning**; it starts no downstream capability and mutates no upstream record.
Application owns intake identity, evaluation, provenance, persistence and reconstruction. No wall-clock is
read, so reconstruction and replay are deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.boundaries import TranscriptQueryBoundary
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)

from .identities import (
    EligibleAnalysisInputId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from .transcript_readiness_evaluation import (
    ReadinessOutcome,
    TranscriptReadinessEvaluation,
)

ELIGIBLE_ANALYSIS_INPUT_RESULT_KIND = "eligible_analysis_input"


class LectureAnalysisEligibility(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"


_ELIGIBILITY_BY_READINESS = {
    ReadinessOutcome.READY: LectureAnalysisEligibility.ELIGIBLE,
    ReadinessOutcome.NOT_READY: LectureAnalysisEligibility.NOT_ELIGIBLE,
}


def eligibility_for_readiness_outcome(
    outcome: ReadinessOutcome,
) -> LectureAnalysisEligibility:
    """The deterministic analysis-input eligibility for a transcript readiness outcome."""

    try:
        return _ELIGIBILITY_BY_READINESS[outcome]
    except KeyError:
        raise ValueError(f"unsupported readiness outcome: {outcome}") from None


@dataclass(frozen=True, slots=True)
class EligibleAnalysisInput:
    """Immutable, provenance-bearing analysis-input record derived from one Readiness Evaluation."""

    identity: EligibleAnalysisInputId
    domain_result_id: DomainResultId
    source_readiness_id: TranscriptReadinessEvaluationId
    readiness_outcome: ReadinessOutcome
    eligibility: LectureAnalysisEligibility
    source_selection_id: TranscriptCurrentSelectionId
    source_applicability_id: TranscriptApplicabilityEvaluationId
    source_decision_id: TranscriptReviewDecisionId
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    validation_id: TranscriptValidationId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_input_id: EligibleAnalysisInputId | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("eligible analysis input sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("eligible analysis input reason must not be empty")
        if self.eligibility is not eligibility_for_readiness_outcome(self.readiness_outcome):
            raise ValueError(
                "eligible analysis input eligibility must match the deterministic readiness mapping"
            )
        if (
            self.eligibility is LectureAnalysisEligibility.ELIGIBLE
            and self.readiness_outcome is not ReadinessOutcome.READY
        ):
            raise ValueError("ELIGIBLE analysis input requires a READY readiness outcome")
        if self.previous_input_id is not None and self.sequence == 0:
            raise ValueError(
                "first eligible analysis input must not reference a previous input"
            )


@dataclass(frozen=True, slots=True)
class LectureAnalysisInputIdentityPlan:
    """Application-owned analysis-input identities for one evaluation."""

    input_id: EligibleAnalysisInputId
    input_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedEligibleAnalysisInput:
    """Immutable canonical analysis-input records; not yet persisted."""

    eligible_input: EligibleAnalysisInput
    input_result: DomainResultReference


class ReadinessEvaluationQuery(Protocol):
    def get(self, identity): ...


class AtomicEligibleAnalysisInputPersistence(Protocol):
    def persist_eligible_analysis_input(
        self,
        *,
        eligible_input: EligibleAnalysisInput,
        input_result: DomainResultReference,
    ) -> None: ...


class LectureAnalysisInputError(ValueError):
    """A structurally valid request that cannot become a canonical analysis-input record."""


class LectureAnalysisInputService:
    """Derives analysis-input eligibility from a canonical Transcript Readiness Evaluation."""

    def __init__(
        self,
        readiness_query: ReadinessEvaluationQuery,
        transcript_query: TranscriptQueryBoundary,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicEligibleAnalysisInputPersistence | None = None,
    ) -> None:
        self._readiness = readiness_query
        self._transcripts = transcript_query
        self._executions = execution_query
        self._persistence = persistence

    def record_input(self, **kwargs) -> PreparedEligibleAnalysisInput:
        prepared = self.evaluate_input(**kwargs)
        if self._persistence is None:
            raise RuntimeError("lecture analysis input persistence is not configured")
        self._persistence.persist_eligible_analysis_input(
            eligible_input=prepared.eligible_input,
            input_result=prepared.input_result,
        )
        return prepared

    def evaluate_input(
        self,
        *,
        source_readiness_id: TranscriptReadinessEvaluationId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: LectureAnalysisInputIdentityPlan,
        sequence: int = 0,
        previous_input_id: EligibleAnalysisInputId | None = None,
        reason: str | None = None,
    ) -> PreparedEligibleAnalysisInput:
        # Admit the validated selected Corrected Transcript through its canonical Readiness Evaluation.
        # It, and the corrected revision / raw transcript it traces to, are read only for provenance.
        readiness = self._readiness.get(source_readiness_id)
        if readiness is None:
            raise KeyError("unknown transcript readiness evaluation")
        if not isinstance(readiness, TranscriptReadinessEvaluation):
            raise LectureAnalysisInputError(
                "lecture analysis input must derive from a canonical Readiness Evaluation"
            )
        self._require_running_execution(run_id, unit_execution_id)

        revision = self._transcripts.get_corrected_revision(readiness.source_revision_id)
        if revision is None:
            raise KeyError("unknown corrected transcript revision")
        raw = self._transcripts.get_raw_transcript(revision.transcript_id)
        if raw is None:
            raise KeyError("unknown source raw transcript")

        eligibility = eligibility_for_readiness_outcome(readiness.outcome)
        resolved_reason = reason if reason is not None else _default_reason(eligibility)

        eligible_input = EligibleAnalysisInput(
            identity=identities.input_id,
            domain_result_id=identities.input_result_id,
            source_readiness_id=readiness.identity,
            readiness_outcome=readiness.outcome,
            eligibility=eligibility,
            source_selection_id=readiness.source_selection_id,
            source_applicability_id=readiness.source_applicability_id,
            source_decision_id=readiness.source_decision_id,
            review_item_id=readiness.review_item_id,
            candidate_reference_id=readiness.candidate_reference_id,
            source_transcript_id=revision.transcript_id,
            source_revision_id=readiness.source_revision_id,
            source_media_id=raw.source_media_id,
            source_timeline_id=raw.source_timeline_id,
            validation_id=readiness.validation_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            previous_input_id=previous_input_id,
        )
        input_result = DomainResultReference(
            identity=identities.input_result_id,
            kind=ELIGIBLE_ANALYSIS_INPUT_RESULT_KIND,
            source_media=raw.source_media_id,
            source_timeline=raw.source_timeline_id,
            upstream_results=(readiness.domain_result_id,),
        )
        return PreparedEligibleAnalysisInput(
            eligible_input=eligible_input, input_result=input_result
        )

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise LectureAnalysisInputError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise LectureAnalysisInputError(
                "recording lecture analysis input requires a running unit execution"
            )


def _default_reason(eligibility: LectureAnalysisEligibility) -> str:
    return {
        LectureAnalysisEligibility.ELIGIBLE: (
            "validated selected transcript is an eligible lecture analysis input"
        ),
        LectureAnalysisEligibility.NOT_ELIGIBLE: (
            "transcript is not ready and is not an eligible lecture analysis input"
        ),
    }[eligibility]


__all__ = [
    "ELIGIBLE_ANALYSIS_INPUT_RESULT_KIND",
    "AtomicEligibleAnalysisInputPersistence",
    "EligibleAnalysisInput",
    "LectureAnalysisEligibility",
    "LectureAnalysisInputError",
    "LectureAnalysisInputIdentityPlan",
    "LectureAnalysisInputService",
    "PreparedEligibleAnalysisInput",
    "eligibility_for_readiness_outcome",
]
