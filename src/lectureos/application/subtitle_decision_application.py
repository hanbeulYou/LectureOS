"""Provider-independent Application contract for Subtitle Decision Application (041 §4.7).

From exactly one canonical ``SubtitleReviewDecision``, it deterministically applies the recorded Human
Accept/Reject/Modify and produces the next Subtitle revision — a new immutable ``SubtitleDecisionRevision``
reflecting the applied outcome (and, for Modify, the user's modified text) — together with its provenance.

Application is a pure deterministic transformation. The consumed decision remains immutable, and no
existing canonical artifact is modified: the ``SubtitleReviewDecision``, its ``ReviewItem``, its
``SubtitleReviewPreparation`` and the ``SubtitleValidation`` are never mutated. The only newly created
canonical artifact is the ``SubtitleDecisionRevision`` and its ``DomainResultReference``. This stage
never records a decision, never selects a Final Subtitle, and derives no current-selection / readiness /
applicability; it is entirely deterministic and provider-free (no wall-clock is read).
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
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .identities import (
    SubtitleCandidateId,
    SubtitleDecisionRevisionId,
    SubtitleReadingRevisionId,
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from .subtitle_review_decision import SubtitleReviewDecision
from .subtitle_structural_validation import SubtitleValidation

SUBTITLE_DECISION_REVISION_RESULT_KIND = "subtitle_decision_revision"


class SubtitleAppliedOutcome(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"


_OUTCOME_BY_KIND = {
    DecisionKind.ACCEPT: SubtitleAppliedOutcome.ACCEPTED,
    DecisionKind.REJECT: SubtitleAppliedOutcome.REJECTED,
    DecisionKind.MODIFY: SubtitleAppliedOutcome.MODIFIED,
}


def applied_outcome_for_kind(kind: DecisionKind) -> SubtitleAppliedOutcome:
    """The deterministic applied outcome for a recorded Human decision kind."""

    try:
        return _OUTCOME_BY_KIND[kind]
    except KeyError:
        raise ValueError(f"unsupported decision kind: {kind}") from None


@dataclass(frozen=True, slots=True)
class SubtitleDecisionRevision:
    """Immutable next Subtitle revision produced by applying one Human Review Decision."""

    identity: SubtitleDecisionRevisionId
    domain_result_id: DomainResultId
    source_review_decision_id: SubtitleReviewDecisionId
    decision_kind: DecisionKind
    outcome: SubtitleAppliedOutcome
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_preparation_id: SubtitleReviewPreparationId
    source_validation_id: SubtitleValidationId
    source_time_revision_id: SubtitleTimeRevisionId
    source_reading_revision_id: SubtitleReadingRevisionId
    source_candidate_id: SubtitleCandidateId
    source_finding_id: SubtitleValidationFindingId
    rule: str
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    target_timed_unit_id: SubtitleTimedUnitId | None = None
    applied_text: str | None = None
    previous_revision_id: SubtitleDecisionRevisionId | None = None

    def __post_init__(self) -> None:
        if self.outcome is not applied_outcome_for_kind(self.decision_kind):
            raise ValueError(
                "decision revision outcome must match the deterministic decision mapping"
            )
        if not self.rule.strip():
            raise ValueError("decision revision rule must not be empty")
        if not self.reason.strip():
            raise ValueError("decision revision reason must not be empty")
        if self.sequence < 0:
            raise ValueError("decision revision sequence must not be negative")
        if self.outcome is SubtitleAppliedOutcome.MODIFIED:
            if self.applied_text is None or not self.applied_text.strip():
                raise ValueError("Modified decision revision requires non-empty applied text")
        elif self.applied_text is not None:
            raise ValueError(
                "Accepted and Rejected decision revisions must not carry applied text"
            )
        if self.previous_revision_id is not None and self.sequence == 0:
            raise ValueError(
                "first decision revision must not reference a previous revision"
            )


@dataclass(frozen=True, slots=True)
class SubtitleDecisionRevisionIdentityPlan:
    """Application-owned identities for one decision application."""

    revision_id: SubtitleDecisionRevisionId
    revision_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedSubtitleDecisionRevision:
    """Immutable canonical next-revision record; not yet persisted."""

    revision: SubtitleDecisionRevision
    revision_result: DomainResultReference


class SubtitleReviewDecisionQuery(Protocol):
    def get(self, identity): ...


class SubtitleValidationQuery(Protocol):
    def get(self, identity): ...

    def get_finding(self, identity): ...


class AtomicSubtitleDecisionRevisionPersistence(Protocol):
    def persist_subtitle_decision_revision(
        self,
        *,
        revision: SubtitleDecisionRevision,
        revision_result: DomainResultReference,
    ) -> None: ...


class SubtitleDecisionApplicationError(ValueError):
    """A structurally valid request that cannot become a canonical next revision."""


class SubtitleDecisionRevisionService:
    """Applies one recorded Human decision into the next Subtitle revision, mutating nothing."""

    def __init__(
        self,
        decision_query: SubtitleReviewDecisionQuery,
        validation_query: SubtitleValidationQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicSubtitleDecisionRevisionPersistence | None = None,
    ) -> None:
        self._decisions = decision_query
        self._validations = validation_query
        self._executions = execution_query
        self._persistence = persistence

    def record_application(self, **kwargs) -> PreparedSubtitleDecisionRevision:
        prepared = self.apply_decision(**kwargs)
        if self._persistence is None:
            raise RuntimeError("subtitle decision application persistence is not configured")
        self._persistence.persist_subtitle_decision_revision(
            revision=prepared.revision,
            revision_result=prepared.revision_result,
        )
        return prepared

    def apply_decision(
        self,
        *,
        source_review_decision_id: SubtitleReviewDecisionId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: SubtitleDecisionRevisionIdentityPlan,
        sequence: int = 0,
        previous_revision_id: SubtitleDecisionRevisionId | None = None,
        reason: str | None = None,
    ) -> PreparedSubtitleDecisionRevision:
        # Admit exactly one canonical review decision. It, its review item, its preparation and the
        # validation are read only for provenance and are never mutated.
        decision = self._decisions.get(source_review_decision_id)
        if decision is None:
            raise KeyError("unknown subtitle review decision")
        if not isinstance(decision, SubtitleReviewDecision):
            raise SubtitleDecisionApplicationError(
                "decision application must derive from a canonical Subtitle Review Decision"
            )
        self._require_running_execution(run_id, unit_execution_id)

        validation = self._validations.get(decision.source_validation_id)
        if validation is None:
            raise KeyError("unknown subtitle validation")
        if not isinstance(validation, SubtitleValidation):
            raise SubtitleDecisionApplicationError(
                "decision application must trace to a canonical Subtitle Validation"
            )
        finding = self._validations.get_finding(decision.source_finding_id)
        if finding is None:
            raise KeyError("unknown subtitle validation finding")

        outcome = applied_outcome_for_kind(decision.kind)
        applied_text = decision.modified_text  # non-null only for Modify (guaranteed by the decision)
        resolved_reason = reason if reason is not None else _default_reason(outcome)

        revision = SubtitleDecisionRevision(
            identity=identities.revision_id,
            domain_result_id=identities.revision_result_id,
            source_review_decision_id=decision.identity,
            decision_kind=decision.kind,
            outcome=outcome,
            review_item_id=decision.review_item_id,
            candidate_reference_id=decision.candidate_reference_id,
            source_preparation_id=decision.source_preparation_id,
            source_validation_id=decision.source_validation_id,
            source_time_revision_id=decision.source_time_revision_id,
            source_reading_revision_id=validation.source_reading_revision_id,
            source_candidate_id=validation.source_candidate_id,
            source_finding_id=decision.source_finding_id,
            rule=decision.rule,
            source_transcript_id=validation.source_transcript_id,
            source_revision_id=validation.source_revision_id,
            source_media_id=validation.source_media_id,
            source_timeline_id=validation.source_timeline_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            target_timed_unit_id=finding.target_timed_unit_id,
            applied_text=applied_text,
            previous_revision_id=previous_revision_id,
        )
        revision_result = DomainResultReference(
            identity=identities.revision_result_id,
            kind=SUBTITLE_DECISION_REVISION_RESULT_KIND,
            source_media=validation.source_media_id,
            source_timeline=validation.source_timeline_id,
            upstream_results=(decision.domain_result_id,),
        )
        return PreparedSubtitleDecisionRevision(
            revision=revision, revision_result=revision_result
        )

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise SubtitleDecisionApplicationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise SubtitleDecisionApplicationError(
                "applying a review decision requires a running unit execution"
            )


def _default_reason(outcome: SubtitleAppliedOutcome) -> str:
    return f"applied review decision into next subtitle revision ({outcome.value})"


__all__ = [
    "SUBTITLE_DECISION_REVISION_RESULT_KIND",
    "AtomicSubtitleDecisionRevisionPersistence",
    "PreparedSubtitleDecisionRevision",
    "SubtitleAppliedOutcome",
    "SubtitleDecisionApplicationError",
    "SubtitleDecisionRevision",
    "SubtitleDecisionRevisionIdentityPlan",
    "SubtitleDecisionRevisionService",
    "SubtitleReviewDecisionQuery",
    "SubtitleValidationQuery",
    "applied_outcome_for_kind",
]
