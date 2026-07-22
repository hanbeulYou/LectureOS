"""Provider-independent Application contract for Subtitle Review Preparation.

The sixth Subtitle Pipeline stage (041_SUBTITLE_PIPELINE.md §4.6, §10). From the supplied canonical
`SubtitleValidation` revision and its ordered findings, it deterministically materializes canonical
human-review work: one common `ReviewItem` (with its `CandidateReference` and a shared `ReviewContext`)
per validation finding, wrapped by a `SubtitleReviewPreparation` aggregate that traces each item to its
source finding and stable rule identifier.

Admission boundary: Review Preparation consumes the supplied validation revision. Whether it is the
latest, currently selected, superseded, or otherwise eligible is outside this stage — Review Preparation
neither determines nor enforces currency, selection, or supersession; that belongs to an upstream
lifecycle authority.

It reuses the common Review activity (`review/`): items are created OPEN (no decisions yet); no new
status enum is introduced; allowed actions are the common ``DecisionKind``. It records no Review
Decision, mutates no upstream record, and is entirely deterministic and provider-free. A clean
validation (zero findings) yields a valid empty preparation.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from lectureos.review.identities import (
    CandidateReferenceId,
    ReviewContextId,
    ReviewItemId,
)
from lectureos.review.models import CandidateReference, ReviewContext, ReviewItem
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)

from .identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleTranscriptIntakeId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from .subtitle_structural_validation import SubtitleValidation

SUBTITLE_REVIEW_PREPARATION_RESULT_KIND = "subtitle_review_preparation"
SUBTITLE_VALIDATION_FINDING_KIND = "subtitle_validation_finding"
SUBTITLE_VALIDATION_FINDING_SOURCE_DOMAIN = "subtitle"


@dataclass(frozen=True, slots=True)
class SubtitleReviewItemLink:
    """Traceability from one common Review Item back to its source validation finding."""

    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_finding_id: SubtitleValidationFindingId
    rule: str
    target_timed_unit_id: SubtitleTimedUnitId | None = None

    def __post_init__(self) -> None:
        if not self.rule.strip():
            raise ValueError("subtitle review item link rule must not be empty")


@dataclass(frozen=True, slots=True)
class SubtitleReviewPreparation:
    """Application-owned aggregate presenting a validation's findings as human-review work."""

    identity: SubtitleReviewPreparationId
    domain_result_id: DomainResultId
    source_validation_id: SubtitleValidationId
    source_time_revision_id: SubtitleTimeRevisionId
    source_reading_revision_id: SubtitleReadingRevisionId
    source_candidate_id: SubtitleCandidateId
    source_intake_id: SubtitleTranscriptIntakeId
    source_readiness_id: TranscriptReadinessEvaluationId
    source_selection_id: TranscriptCurrentSelectionId
    source_applicability_id: TranscriptApplicabilityEvaluationId
    source_decision_id: TranscriptReviewDecisionId
    source_review_item_id: ReviewItemId
    source_candidate_reference_id: CandidateReferenceId
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    source_transcript_validation_id: TranscriptValidationId
    context_id: ReviewContextId
    item_links: tuple[SubtitleReviewItemLink, ...]
    item_count: int
    source_structural_valid: bool
    provenance_complete: bool
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_preparation_id: SubtitleReviewPreparationId | None = None

    def __post_init__(self) -> None:
        if self.item_count != len(self.item_links):
            raise ValueError("review preparation item count must match the item links")
        review_item_ids = tuple(link.review_item_id for link in self.item_links)
        candidate_ids = tuple(link.candidate_reference_id for link in self.item_links)
        finding_ids = tuple(link.source_finding_id for link in self.item_links)
        if len(set(review_item_ids)) != len(review_item_ids):
            raise ValueError("review preparation review item ids must be unique")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("review preparation candidate reference ids must be unique")
        if len(set(finding_ids)) != len(finding_ids):
            raise ValueError("review preparation source finding ids must be unique")
        if self.sequence < 0:
            raise ValueError("review preparation sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("review preparation reason must not be empty")
        if self.previous_preparation_id is not None and self.sequence == 0:
            raise ValueError(
                "first review preparation must not reference a previous preparation"
            )


@dataclass(frozen=True, slots=True)
class SubtitleReviewTargetIdentityPlan:
    """Application-owned common-Review identities for one prepared finding."""

    candidate_reference_id: CandidateReferenceId
    review_item_id: ReviewItemId


@dataclass(frozen=True, slots=True)
class SubtitleReviewPreparationIdentityPlan:
    """Deterministic Application-owned identities for one preparation (targets may be empty)."""

    preparation_id: SubtitleReviewPreparationId
    preparation_result_id: DomainResultId
    context_id: ReviewContextId
    targets: tuple[SubtitleReviewTargetIdentityPlan, ...] = ()

    def __post_init__(self) -> None:
        candidate_ids = tuple(target.candidate_reference_id for target in self.targets)
        item_ids = tuple(target.review_item_id for target in self.targets)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("review preparation candidate reference plan must be unique")
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("review preparation review item plan must be unique")


@dataclass(frozen=True, slots=True)
class PreparedSubtitleReview:
    """Immutable canonical review-preparation records; not yet persisted."""

    preparation: SubtitleReviewPreparation
    preparation_result: DomainResultReference
    context: ReviewContext
    candidate_references: tuple[CandidateReference, ...]
    review_items: tuple[ReviewItem, ...]


class SubtitleValidationQuery(Protocol):
    def get(self, identity): ...

    def get_finding(self, identity): ...


class AtomicSubtitleReviewPreparationPersistence(Protocol):
    def persist_subtitle_review_preparation(
        self,
        *,
        preparation: SubtitleReviewPreparation,
        preparation_result: DomainResultReference,
        context: ReviewContext,
        candidate_references: tuple[CandidateReference, ...],
        review_items: tuple[ReviewItem, ...],
    ) -> None: ...


class SubtitleReviewPreparationError(ValueError):
    """A structurally valid request that cannot become canonical review preparation."""


class SubtitleReviewPreparationService:
    """Materializes a validation's findings as canonical open Review Items, deciding nothing."""

    def __init__(
        self,
        validation_query: SubtitleValidationQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicSubtitleReviewPreparationPersistence | None = None,
    ) -> None:
        self._validations = validation_query
        self._executions = execution_query
        self._persistence = persistence

    def generate_review(self, **kwargs) -> PreparedSubtitleReview:
        prepared = self.prepare_review(**kwargs)
        if self._persistence is None:
            raise RuntimeError("subtitle review preparation persistence is not configured")
        self._persistence.persist_subtitle_review_preparation(
            preparation=prepared.preparation,
            preparation_result=prepared.preparation_result,
            context=prepared.context,
            candidate_references=prepared.candidate_references,
            review_items=prepared.review_items,
        )
        return prepared

    def prepare_review(
        self,
        *,
        source_validation_id: SubtitleValidationId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: SubtitleReviewPreparationIdentityPlan,
        sequence: int = 0,
        previous_preparation_id: SubtitleReviewPreparationId | None = None,
        reason: str | None = None,
    ) -> PreparedSubtitleReview:
        # Consume the supplied validation revision. Currency, selection, and supersession are the
        # responsibility of an upstream lifecycle authority, not of Review Preparation.
        validation = self._validations.get(source_validation_id)
        if validation is None:
            raise KeyError("unknown subtitle validation")
        if not isinstance(validation, SubtitleValidation):
            raise SubtitleReviewPreparationError(
                "subtitle review preparation must derive from a canonical Subtitle Validation"
            )
        self._require_running_execution(run_id, unit_execution_id)

        findings = tuple(
            self._require_finding(finding_id) for finding_id in validation.finding_ids
        )
        if len(identities.targets) != len(findings):
            raise SubtitleReviewPreparationError(
                "identity plan target count must match the validation finding count"
            )

        candidate_references: list[CandidateReference] = []
        review_items: list[ReviewItem] = []
        item_links: list[SubtitleReviewItemLink] = []
        revision_reference = (
            f"subtitle_time_revision:{validation.source_time_revision_id.value}"
        )
        for finding, target in zip(findings, identities.targets):
            reference = CandidateReference(
                identity=target.candidate_reference_id,
                kind=SUBTITLE_VALIDATION_FINDING_KIND,
                source_domain=SUBTITLE_VALIDATION_FINDING_SOURCE_DOMAIN,
                domain_result_id=validation.domain_result_id,
                source_media_id=validation.source_media_id,
                source_timeline_id=validation.source_timeline_id,
                run_id=validation.run_id,
                unit_execution_id=validation.unit_execution_id,
                revision_reference=revision_reference,
                applicability="undetermined",
            )
            item = ReviewItem(
                identity=target.review_item_id,
                candidate_id=reference.identity,
                context_id=identities.context_id,
                applicability_at_creation="undetermined",
                run_id=validation.run_id,
                unit_execution_id=validation.unit_execution_id,
            )
            candidate_references.append(reference)
            review_items.append(item)
            item_links.append(
                SubtitleReviewItemLink(
                    review_item_id=item.identity,
                    candidate_reference_id=reference.identity,
                    source_finding_id=finding.identity,
                    rule=finding.rule,
                    target_timed_unit_id=finding.target_timed_unit_id,
                )
            )

        context = ReviewContext(
            identity=identities.context_id,
            source_media_id=validation.source_media_id,
            source_timeline_id=validation.source_timeline_id,
            domain_result_references=(validation.domain_result_id,),
            evidence_references=(
                f"subtitle_validation:{validation.identity.value}",
                *(
                    f"{SUBTITLE_VALIDATION_FINDING_KIND}:{finding.identity.value}"
                    for finding in findings
                ),
            ),
        )
        resolved_reason = (
            reason if reason is not None else _default_reason(len(review_items))
        )
        preparation = SubtitleReviewPreparation(
            identity=identities.preparation_id,
            domain_result_id=identities.preparation_result_id,
            source_validation_id=validation.identity,
            source_time_revision_id=validation.source_time_revision_id,
            source_reading_revision_id=validation.source_reading_revision_id,
            source_candidate_id=validation.source_candidate_id,
            source_intake_id=validation.source_intake_id,
            source_readiness_id=validation.source_readiness_id,
            source_selection_id=validation.source_selection_id,
            source_applicability_id=validation.source_applicability_id,
            source_decision_id=validation.source_decision_id,
            source_review_item_id=validation.review_item_id,
            source_candidate_reference_id=validation.candidate_reference_id,
            source_transcript_id=validation.source_transcript_id,
            source_revision_id=validation.source_revision_id,
            source_media_id=validation.source_media_id,
            source_timeline_id=validation.source_timeline_id,
            source_transcript_validation_id=validation.source_transcript_validation_id,
            context_id=context.identity,
            item_links=tuple(item_links),
            item_count=len(item_links),
            source_structural_valid=validation.structural_valid,
            provenance_complete=True,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            previous_preparation_id=previous_preparation_id,
        )
        preparation_result = DomainResultReference(
            identity=identities.preparation_result_id,
            kind=SUBTITLE_REVIEW_PREPARATION_RESULT_KIND,
            source_media=validation.source_media_id,
            source_timeline=validation.source_timeline_id,
            upstream_results=(validation.domain_result_id,),
        )
        return PreparedSubtitleReview(
            preparation=preparation,
            preparation_result=preparation_result,
            context=context,
            candidate_references=tuple(candidate_references),
            review_items=tuple(review_items),
        )

    def _require_finding(self, finding_id: SubtitleValidationFindingId):
        finding = self._validations.get_finding(finding_id)
        if finding is None:
            raise KeyError("unknown subtitle validation finding")
        return finding

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise SubtitleReviewPreparationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise SubtitleReviewPreparationError(
                "review preparation requires a running unit execution"
            )


def _default_reason(item_count: int) -> str:
    return (
        f"review preparation materializing {item_count} open review item(s), one per "
        "validation finding"
    )


__all__ = [
    "SUBTITLE_REVIEW_PREPARATION_RESULT_KIND",
    "SUBTITLE_VALIDATION_FINDING_KIND",
    "SUBTITLE_VALIDATION_FINDING_SOURCE_DOMAIN",
    "AtomicSubtitleReviewPreparationPersistence",
    "PreparedSubtitleReview",
    "SubtitleReviewItemLink",
    "SubtitleReviewPreparation",
    "SubtitleReviewPreparationError",
    "SubtitleReviewPreparationIdentityPlan",
    "SubtitleReviewPreparationService",
    "SubtitleReviewTargetIdentityPlan",
    "SubtitleValidationQuery",
]
