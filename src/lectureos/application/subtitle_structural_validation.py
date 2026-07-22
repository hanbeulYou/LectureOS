"""Provider-independent Application contract for Subtitle Structural Validation.

The fifth Subtitle Pipeline stage (041_SUBTITLE_PIPELINE.md §4.5, §9). From a canonical
`SubtitleTimeRevision` and its ordered timed units, it deterministically diagnoses the subtitle
revision's structural correctness and produces one immutable Validation Result plus a collection of
immutable Findings traceable to affected timed units.

Validation diagnoses only. It records structural defects (provenance integrity, timeline
traceability, unresolved timing, ordering, overlap) and a derived ``structural_valid`` verdict
(= no blocking finding); it modifies nothing, creates no Review Item, adjudicates no uncertainty,
approves nothing, and applies no numeric quality threshold. Diagnosis is entirely deterministic and
provider-free.

Each finding carries a stable ``rule`` identifier independent of its human-readable ``description``:
the rule identifier is the finding's stable rule identity that downstream layers consume, while the
description is explanatory text only and is not part of the rule identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)

from .identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
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

SUBTITLE_VALIDATION_RESULT_KIND = "subtitle_validation"


class SubtitleValidationCategory(str, Enum):
    PROVENANCE_INTEGRITY = "provenance_integrity"
    TIMELINE_TRACEABILITY = "timeline_traceability"
    UNRESOLVED_TIMING = "unresolved_timing"
    ORDERING = "ordering"
    OVERLAP = "overlap"


# Stable rule identifiers — the deterministic rule identity that produced a finding. Downstream
# layers consume these rather than parsing descriptions; they remain stable across wording changes.
RULE_PROVENANCE_READING_REVISION_MISSING = "provenance.reading_revision_missing"
RULE_PROVENANCE_READING_UNIT_MISSING = "provenance.reading_unit_missing"
RULE_PROVENANCE_COVERAGE_MISMATCH = "provenance.coverage_mismatch"
RULE_TIMELINE_MISMATCH = "traceability.timeline_mismatch"
RULE_UNRESOLVED_TIMING = "timing.unresolved"
RULE_ORDERING_NON_MONOTONIC = "ordering.non_monotonic"
RULE_OVERLAP_ADJACENT = "overlap.adjacent"


@dataclass(frozen=True, slots=True)
class SubtitleValidationFinding:
    """One immutable structural finding: a stable rule plus an explanatory description."""

    identity: SubtitleValidationFindingId
    validation_id: SubtitleValidationId
    rule: str
    category: SubtitleValidationCategory
    blocking: bool
    description: str
    target_timed_unit_id: SubtitleTimedUnitId | None = None

    def __post_init__(self) -> None:
        if not self.rule.strip():
            raise ValueError("subtitle validation finding rule must not be empty")
        if not self.description.strip():
            raise ValueError("subtitle validation finding description must not be empty")


@dataclass(frozen=True, slots=True)
class SubtitleValidation:
    """Immutable structural validation result diagnosing one canonical Subtitle Time Revision."""

    identity: SubtitleValidationId
    domain_result_id: DomainResultId
    source_time_revision_id: SubtitleTimeRevisionId
    source_reading_revision_id: SubtitleReadingRevisionId
    source_candidate_id: SubtitleCandidateId
    source_intake_id: SubtitleTranscriptIntakeId
    source_readiness_id: TranscriptReadinessEvaluationId
    source_selection_id: TranscriptCurrentSelectionId
    source_applicability_id: TranscriptApplicabilityEvaluationId
    source_decision_id: TranscriptReviewDecisionId
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    source_transcript_validation_id: TranscriptValidationId
    structural_valid: bool
    provenance_complete: bool
    timeline_traceable: bool
    ordering_consistent: bool
    time_consistent: bool
    finding_ids: tuple[SubtitleValidationFindingId, ...]
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_validation_id: SubtitleValidationId | None = None

    def __post_init__(self) -> None:
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("subtitle validation finding ids must be unique")
        if self.sequence < 0:
            raise ValueError("subtitle validation sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("subtitle validation reason must not be empty")
        if self.previous_validation_id is not None and self.sequence == 0:
            raise ValueError(
                "first subtitle validation must not reference a previous validation"
            )


@dataclass(frozen=True, slots=True)
class SubtitleValidationIdentityPlan:
    """Application-owned validation identities for one diagnosis.

    Only the validation and its Result identity are caller-owned; because the finding count is
    defect-dependent, finding identities are deterministically derived from the validation identity
    plus their ordinal (see ``finding_identity``).
    """

    validation_id: SubtitleValidationId
    validation_result_id: DomainResultId


def finding_identity(
    validation_id: SubtitleValidationId, ordinal: int
) -> SubtitleValidationFindingId:
    """Deterministic finding identity derived from the caller-owned validation identity + ordinal."""

    if ordinal < 0:
        raise ValueError("finding ordinal must not be negative")
    return SubtitleValidationFindingId(f"{validation_id.value}::finding::{ordinal}")


__all__ = [
    "RULE_ORDERING_NON_MONOTONIC",
    "RULE_OVERLAP_ADJACENT",
    "RULE_PROVENANCE_COVERAGE_MISMATCH",
    "RULE_PROVENANCE_READING_REVISION_MISSING",
    "RULE_PROVENANCE_READING_UNIT_MISSING",
    "RULE_TIMELINE_MISMATCH",
    "RULE_UNRESOLVED_TIMING",
    "SUBTITLE_VALIDATION_RESULT_KIND",
    "SubtitleValidation",
    "SubtitleValidationCategory",
    "SubtitleValidationFinding",
    "SubtitleValidationIdentityPlan",
    "finding_identity",
]
