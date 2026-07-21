"""Provider-independent Application contract for Subtitle Transcript Intake.

The first Subtitle Pipeline stage (041_SUBTITLE_PIPELINE.md §4.1). It evaluates
deterministically, from a canonical Transcript Readiness Evaluation, whether the selected
Corrected Transcript revision is eligible to begin subtitle work, and records it as an immutable
aggregate. Recording intake starts no downstream capability (no candidate generation) and mutates
no upstream record. Application owns intake identity, evaluation, lifecycle, provenance,
persistence and reconstruction. Intake is a pure function of canonical records; no wall-clock is
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
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from .transcript_readiness_evaluation import (
    ReadinessOutcome,
    TranscriptReadinessEvaluation,
)

SUBTITLE_TRANSCRIPT_INTAKE_RESULT_KIND = "subtitle_transcript_intake"


class SubtitleIntakeOutcome(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"


_INTAKE_BY_READINESS = {
    ReadinessOutcome.READY: SubtitleIntakeOutcome.ELIGIBLE,
    ReadinessOutcome.NOT_READY: SubtitleIntakeOutcome.NOT_ELIGIBLE,
}


def intake_for_readiness_outcome(outcome: ReadinessOutcome) -> SubtitleIntakeOutcome:
    """The deterministic subtitle-intake outcome for a readiness outcome."""

    try:
        return _INTAKE_BY_READINESS[outcome]
    except KeyError:
        raise ValueError(f"unsupported readiness outcome: {outcome}") from None


@dataclass(frozen=True, slots=True)
class SubtitleTranscriptIntake:
    """Immutable subtitle-eligibility record derived from one Readiness Evaluation."""

    identity: SubtitleTranscriptIntakeId
    domain_result_id: DomainResultId
    source_readiness_id: TranscriptReadinessEvaluationId
    readiness_outcome: ReadinessOutcome
    outcome: SubtitleIntakeOutcome
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
    previous_intake_id: SubtitleTranscriptIntakeId | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("subtitle intake sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("subtitle intake reason must not be empty")
        if self.outcome is not intake_for_readiness_outcome(self.readiness_outcome):
            raise ValueError(
                "subtitle intake outcome must match the deterministic readiness mapping"
            )
        if (
            self.outcome is SubtitleIntakeOutcome.ELIGIBLE
            and self.readiness_outcome is not ReadinessOutcome.READY
        ):
            raise ValueError("ELIGIBLE intake requires a READY readiness outcome")
        if self.previous_intake_id is not None and self.sequence == 0:
            raise ValueError(
                "first subtitle intake must not reference a previous intake"
            )


@dataclass(frozen=True, slots=True)
class SubtitleIntakeIdentityPlan:
    """Application-owned intake identities for one evaluation."""

    intake_id: SubtitleTranscriptIntakeId
    intake_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedSubtitleIntake:
    """Immutable canonical intake records; not yet persisted."""

    intake: SubtitleTranscriptIntake
    intake_result: DomainResultReference


class ReadinessEvaluationQuery(Protocol):
    def get(self, identity): ...


class AtomicSubtitleIntakePersistence(Protocol):
    def persist_subtitle_intake(
        self,
        *,
        intake: SubtitleTranscriptIntake,
        intake_result: DomainResultReference,
    ) -> None: ...


class SubtitleTranscriptIntakeError(ValueError):
    """A structurally valid request that cannot become a canonical intake record."""


class SubtitleTranscriptIntakeService:
    """Derives subtitle eligibility from a canonical Readiness Evaluation."""

    def __init__(
        self,
        readiness_query: ReadinessEvaluationQuery,
        transcript_query: TranscriptQueryBoundary,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicSubtitleIntakePersistence | None = None,
    ) -> None:
        self._readiness = readiness_query
        self._transcripts = transcript_query
        self._executions = execution_query
        self._persistence = persistence

    def record_intake(self, **kwargs) -> PreparedSubtitleIntake:
        prepared = self.evaluate_intake(**kwargs)
        if self._persistence is None:
            raise RuntimeError("subtitle intake persistence is not configured")
        self._persistence.persist_subtitle_intake(
            intake=prepared.intake,
            intake_result=prepared.intake_result,
        )
        return prepared

    def evaluate_intake(
        self,
        *,
        source_readiness_id: TranscriptReadinessEvaluationId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: SubtitleIntakeIdentityPlan,
        sequence: int = 0,
        previous_intake_id: SubtitleTranscriptIntakeId | None = None,
        reason: str | None = None,
    ) -> PreparedSubtitleIntake:
        readiness = self._readiness.get(source_readiness_id)
        if readiness is None:
            raise KeyError("unknown transcript readiness evaluation")
        if not isinstance(readiness, TranscriptReadinessEvaluation):
            raise SubtitleTranscriptIntakeError(
                "subtitle intake must derive from a canonical Readiness Evaluation"
            )
        self._require_running_execution(run_id, unit_execution_id)

        revision = self._transcripts.get_corrected_revision(readiness.source_revision_id)
        if revision is None:
            raise KeyError("unknown corrected transcript revision")
        raw = self._transcripts.get_raw_transcript(revision.transcript_id)
        if raw is None:
            raise KeyError("unknown source raw transcript")

        outcome = intake_for_readiness_outcome(readiness.outcome)
        resolved_reason = reason if reason is not None else _default_reason(outcome)

        intake = SubtitleTranscriptIntake(
            identity=identities.intake_id,
            domain_result_id=identities.intake_result_id,
            source_readiness_id=readiness.identity,
            readiness_outcome=readiness.outcome,
            outcome=outcome,
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
            previous_intake_id=previous_intake_id,
        )
        intake_result = DomainResultReference(
            identity=identities.intake_result_id,
            kind=SUBTITLE_TRANSCRIPT_INTAKE_RESULT_KIND,
            source_media=raw.source_media_id,
            source_timeline=raw.source_timeline_id,
            upstream_results=(readiness.domain_result_id,),
        )
        return PreparedSubtitleIntake(intake=intake, intake_result=intake_result)

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise SubtitleTranscriptIntakeError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise SubtitleTranscriptIntakeError(
                "recording subtitle intake requires a running unit execution"
            )


def _default_reason(outcome: SubtitleIntakeOutcome) -> str:
    return {
        SubtitleIntakeOutcome.ELIGIBLE: (
            "ready transcript revision is eligible to begin subtitle work"
        ),
        SubtitleIntakeOutcome.NOT_ELIGIBLE: (
            "transcript revision is not ready and is not eligible for subtitle work"
        ),
    }[outcome]


__all__ = [
    "SUBTITLE_TRANSCRIPT_INTAKE_RESULT_KIND",
    "AtomicSubtitleIntakePersistence",
    "PreparedSubtitleIntake",
    "SubtitleIntakeIdentityPlan",
    "SubtitleIntakeOutcome",
    "SubtitleTranscriptIntake",
    "SubtitleTranscriptIntakeError",
    "SubtitleTranscriptIntakeService",
    "intake_for_readiness_outcome",
]
