"""Provider-independent Application contract for Subtitle Time Representation.

The fourth Subtitle Pipeline stage (041_SUBTITLE_PIPELINE.md §4.4, §7). From a canonical
`SubtitleReadingRevision` and its ordered reading units, it deterministically composes one new
immutable subtitle time revision whose timed units carry an authoritative, Source-Timeline-anchored
display Time Range derived from each unit's ordered source cues: the minimal enclosing source-timeline
extent for merged units, the cue range for one-to-one units, and an explicit UNRESOLVED state where
the basis is untimed or spans different timelines.

Time Representation produces a new immutable representation, not a mutation. The reading revision,
reading units and candidate cues are immutable and unchanged.

Source-Timeline anchoring is a canonical representation of provenance, not a timing optimization
strategy: the baseline records the minimal enclosing extent of a unit's source cues. Later timing
policies (padding, snapping, overlap resolution, gap insertion, duration adjustment, redistribution)
may refine the interval but never redefine this provenance-derived baseline, and Structural
Validation (§4.5) evaluates the represented timing rather than constructing it. Timing derivation is
provider-free and threshold-free; §4.4 excludes AI-finalized timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

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
    SubtitleReadingUnitId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)

SUBTITLE_TIME_REVISION_RESULT_KIND = "subtitle_time_revision"


class SubtitleTimingStatus(str, Enum):
    ANCHORED = "anchored"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class SubtitleTimedUnit:
    """One immutable timed unit: a Source-Timeline-anchored display Time Range for a reading unit."""

    identity: SubtitleTimedUnitId
    time_revision_id: SubtitleTimeRevisionId
    source_reading_unit_id: SubtitleReadingUnitId
    display_order: int
    timing_status: SubtitleTimingStatus
    source_timeline_id: SourceTimelineId | None = None
    start: float | None = None
    end: float | None = None

    def __post_init__(self) -> None:
        if self.display_order < 0:
            raise ValueError("subtitle timed unit display order must not be negative")
        anchored = self.timing_status is SubtitleTimingStatus.ANCHORED
        has_range = (
            self.source_timeline_id is not None
            and self.start is not None
            and self.end is not None
        )
        any_range = (
            self.source_timeline_id is not None
            or self.start is not None
            or self.end is not None
        )
        if anchored:
            if not has_range:
                raise ValueError(
                    "anchored subtitle timed unit requires a source timeline and time range"
                )
            if not isfinite(self.start) or not isfinite(self.end):
                raise ValueError("subtitle timed unit time range must be finite")
            if self.start < 0 or self.end < 0:
                raise ValueError("subtitle timed unit time range must not be negative")
            if self.start > self.end:
                raise ValueError("subtitle timed unit start must not be after end")
        else:
            if any_range:
                raise ValueError(
                    "unresolved subtitle timed unit must not carry a time range"
                )


@dataclass(frozen=True, slots=True)
class SubtitleTimeRevision:
    """Immutable time revision derived from one canonical Subtitle Reading Revision."""

    identity: SubtitleTimeRevisionId
    domain_result_id: DomainResultId
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
    validation_id: TranscriptValidationId
    timed_unit_ids: tuple[SubtitleTimedUnitId, ...]
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_time_revision_id: SubtitleTimeRevisionId | None = None

    def __post_init__(self) -> None:
        if not self.timed_unit_ids:
            raise ValueError("subtitle time revision requires at least one timed unit")
        if len(set(self.timed_unit_ids)) != len(self.timed_unit_ids):
            raise ValueError("subtitle time revision timed unit ids must be unique")
        if self.sequence < 0:
            raise ValueError("subtitle time revision sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("subtitle time revision reason must not be empty")
        if self.previous_time_revision_id is not None and self.sequence == 0:
            raise ValueError(
                "first subtitle time revision must not reference a previous revision"
            )


@dataclass(frozen=True, slots=True)
class SubtitleTimeIdentityPlan:
    """Application-owned time identities for one composition."""

    time_revision_id: SubtitleTimeRevisionId
    time_result_id: DomainResultId
    timed_unit_ids: tuple[SubtitleTimedUnitId, ...]

    def __post_init__(self) -> None:
        if not self.timed_unit_ids:
            raise ValueError("subtitle time identity plan requires timed unit ids")
        if len(set(self.timed_unit_ids)) != len(self.timed_unit_ids):
            raise ValueError("subtitle time identity plan timed unit ids must be unique")


__all__ = [
    "SUBTITLE_TIME_REVISION_RESULT_KIND",
    "SubtitleTimeIdentityPlan",
    "SubtitleTimeRevision",
    "SubtitleTimedUnit",
    "SubtitleTimingStatus",
]
