"""Provider-independent Application contract for Subtitle Final Subtitle (041 §4.8).

From exactly one canonical ``SubtitleDecisionRevision``, it deterministically distinguishes the
authoritative, approved-state Subtitle representation — the Final Subtitle — reflecting the applicable
Review Decision, and preserves provenance to the Corrected Transcript, Source Timeline, subtitle revision
and user decision.

Final Subtitle is a pure deterministic *selection* stage, not a transformation. The consumed decision
revision remains immutable, and no existing canonical artifact is modified: the ``SubtitleDecisionRevision``,
``SubtitleReviewDecision``, ``ReviewItem``, ``SubtitleReviewPreparation`` and ``SubtitleValidation`` are
never mutated. The only newly created canonical artifact is the ``SubtitleFinalSubtitle`` and its
``DomainResultReference`` — it is a finalization/selection record distinguishing the authoritative
representation, not a separate approved-Subtitle content entity. This stage never records or applies a
decision, performs no structural validation, produces no export or playback artifact, and performs no AI
inference; it is entirely deterministic and provider-free (no wall-clock is read). The FINAL outcome is
the logical "Artifact Generation Ready State" — a status, not an artifact.
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
    SubtitleFinalSubtitleId,
    SubtitleReadingRevisionId,
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from .subtitle_decision_application import (
    SubtitleAppliedOutcome,
    SubtitleDecisionRevision,
    applied_outcome_for_kind,
)

SUBTITLE_FINAL_SUBTITLE_RESULT_KIND = "subtitle_final_subtitle"


class SubtitleFinalOutcome(str, Enum):
    FINAL = "final"
    NOT_FINAL = "not_final"


_FINAL_BY_APPLIED_OUTCOME = {
    SubtitleAppliedOutcome.ACCEPTED: SubtitleFinalOutcome.FINAL,
    SubtitleAppliedOutcome.MODIFIED: SubtitleFinalOutcome.FINAL,
    SubtitleAppliedOutcome.REJECTED: SubtitleFinalOutcome.NOT_FINAL,
}


def final_outcome_for_applied_outcome(
    outcome: SubtitleAppliedOutcome,
) -> SubtitleFinalOutcome:
    """The deterministic Final outcome for one applied decision-revision outcome.

    An Accepted or Modified representation is the authoritative Final Subtitle; a Rejected one is not
    approved and is therefore not Final. This is a pure selection — it constructs no representation.
    """

    try:
        return _FINAL_BY_APPLIED_OUTCOME[outcome]
    except KeyError:
        raise ValueError(f"unsupported applied outcome: {outcome}") from None


@dataclass(frozen=True, slots=True)
class SubtitleFinalSubtitle:
    """Immutable Final Subtitle: the authoritative approved-state representation for one revision."""

    identity: SubtitleFinalSubtitleId
    domain_result_id: DomainResultId
    source_decision_revision_id: SubtitleDecisionRevisionId
    decision_kind: DecisionKind
    applied_outcome: SubtitleAppliedOutcome
    final_outcome: SubtitleFinalOutcome
    source_review_decision_id: SubtitleReviewDecisionId
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
    previous_final_id: SubtitleFinalSubtitleId | None = None

    def __post_init__(self) -> None:
        if self.applied_outcome is not applied_outcome_for_kind(self.decision_kind):
            raise ValueError(
                "final subtitle applied outcome must match the deterministic decision mapping"
            )
        if self.final_outcome is not final_outcome_for_applied_outcome(
            self.applied_outcome
        ):
            raise ValueError(
                "final subtitle outcome must match the deterministic selection mapping"
            )
        if not self.rule.strip():
            raise ValueError("final subtitle rule must not be empty")
        if not self.reason.strip():
            raise ValueError("final subtitle reason must not be empty")
        if self.sequence < 0:
            raise ValueError("final subtitle sequence must not be negative")
        if self.applied_outcome is SubtitleAppliedOutcome.MODIFIED:
            if self.applied_text is None or not self.applied_text.strip():
                raise ValueError("Modified final subtitle requires non-empty applied text")
        elif self.applied_text is not None:
            raise ValueError(
                "Accepted and Rejected final subtitles must not carry applied text"
            )
        if self.previous_final_id is not None and self.sequence == 0:
            raise ValueError("first final subtitle must not reference a previous final")


@dataclass(frozen=True, slots=True)
class SubtitleFinalSubtitleIdentityPlan:
    """Application-owned identities for one Final Subtitle selection."""

    final_id: SubtitleFinalSubtitleId
    final_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedSubtitleFinalSubtitle:
    """Immutable canonical Final Subtitle record; not yet persisted."""

    final: SubtitleFinalSubtitle
    final_result: DomainResultReference


class SubtitleDecisionRevisionQuery(Protocol):
    def get(self, identity): ...


class AtomicSubtitleFinalSubtitlePersistence(Protocol):
    def persist_subtitle_final_subtitle(
        self,
        *,
        final: SubtitleFinalSubtitle,
        final_result: DomainResultReference,
    ) -> None: ...


class SubtitleFinalSubtitleError(ValueError):
    """A structurally valid request that cannot become a canonical Final Subtitle."""


class SubtitleFinalSubtitleService:
    """Selects the Final Subtitle from one decision revision, mutating nothing upstream."""

    def __init__(
        self,
        decision_revision_query: SubtitleDecisionRevisionQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicSubtitleFinalSubtitlePersistence | None = None,
    ) -> None:
        self._revisions = decision_revision_query
        self._executions = execution_query
        self._persistence = persistence

    def record_final(self, **kwargs) -> PreparedSubtitleFinalSubtitle:
        prepared = self.select_final(**kwargs)
        if self._persistence is None:
            raise RuntimeError("subtitle final subtitle persistence is not configured")
        self._persistence.persist_subtitle_final_subtitle(
            final=prepared.final,
            final_result=prepared.final_result,
        )
        return prepared

    def select_final(
        self,
        *,
        source_decision_revision_id: SubtitleDecisionRevisionId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: SubtitleFinalSubtitleIdentityPlan,
        sequence: int = 0,
        previous_final_id: SubtitleFinalSubtitleId | None = None,
        reason: str | None = None,
    ) -> PreparedSubtitleFinalSubtitle:
        # Admit exactly one canonical decision revision. It — and every artifact it traces to — is read
        # only for provenance and is never mutated. It already carries the full lineage Final needs, so
        # nothing else is read.
        revision = self._revisions.get(source_decision_revision_id)
        if revision is None:
            raise KeyError("unknown subtitle decision revision")
        if not isinstance(revision, SubtitleDecisionRevision):
            raise SubtitleFinalSubtitleError(
                "final subtitle must derive from a canonical Subtitle Decision Revision"
            )
        self._require_running_execution(run_id, unit_execution_id)

        final_outcome = final_outcome_for_applied_outcome(revision.outcome)
        resolved_reason = reason if reason is not None else _default_reason(final_outcome)

        final = SubtitleFinalSubtitle(
            identity=identities.final_id,
            domain_result_id=identities.final_result_id,
            source_decision_revision_id=revision.identity,
            decision_kind=revision.decision_kind,
            applied_outcome=revision.outcome,
            final_outcome=final_outcome,
            source_review_decision_id=revision.source_review_decision_id,
            review_item_id=revision.review_item_id,
            candidate_reference_id=revision.candidate_reference_id,
            source_preparation_id=revision.source_preparation_id,
            source_validation_id=revision.source_validation_id,
            source_time_revision_id=revision.source_time_revision_id,
            source_reading_revision_id=revision.source_reading_revision_id,
            source_candidate_id=revision.source_candidate_id,
            source_finding_id=revision.source_finding_id,
            rule=revision.rule,
            source_transcript_id=revision.source_transcript_id,
            source_revision_id=revision.source_revision_id,
            source_media_id=revision.source_media_id,
            source_timeline_id=revision.source_timeline_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            target_timed_unit_id=revision.target_timed_unit_id,
            applied_text=revision.applied_text,
            previous_final_id=previous_final_id,
        )
        final_result = DomainResultReference(
            identity=identities.final_result_id,
            kind=SUBTITLE_FINAL_SUBTITLE_RESULT_KIND,
            source_media=revision.source_media_id,
            source_timeline=revision.source_timeline_id,
            upstream_results=(revision.domain_result_id,),
        )
        return PreparedSubtitleFinalSubtitle(final=final, final_result=final_result)

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise SubtitleFinalSubtitleError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise SubtitleFinalSubtitleError(
                "selecting a final subtitle requires a running unit execution"
            )


def _default_reason(outcome: SubtitleFinalOutcome) -> str:
    return f"selected the authoritative final subtitle representation ({outcome.value})"


__all__ = [
    "SUBTITLE_FINAL_SUBTITLE_RESULT_KIND",
    "AtomicSubtitleFinalSubtitlePersistence",
    "PreparedSubtitleFinalSubtitle",
    "SubtitleDecisionRevisionQuery",
    "SubtitleFinalOutcome",
    "SubtitleFinalSubtitle",
    "SubtitleFinalSubtitleError",
    "SubtitleFinalSubtitleIdentityPlan",
    "SubtitleFinalSubtitleService",
    "final_outcome_for_applied_outcome",
]
