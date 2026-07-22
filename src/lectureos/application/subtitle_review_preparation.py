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

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.review.identities import (
    CandidateReferenceId,
    ReviewContextId,
    ReviewItemId,
)
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


__all__ = [
    "SUBTITLE_REVIEW_PREPARATION_RESULT_KIND",
    "SUBTITLE_VALIDATION_FINDING_KIND",
    "SUBTITLE_VALIDATION_FINDING_SOURCE_DOMAIN",
    "SubtitleReviewItemLink",
    "SubtitleReviewPreparation",
    "SubtitleReviewPreparationIdentityPlan",
    "SubtitleReviewTargetIdentityPlan",
]
