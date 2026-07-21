"""Provider-independent Application contract for Subtitle Candidate Generation.

The second Subtitle Pipeline stage (041_SUBTITLE_PIPELINE.md §4.2). From a canonical ELIGIBLE
`SubtitleTranscriptIntake`, it deterministically proposes one durable Subtitle Candidate plus an
ordered collection of candidate Subtitle Units (cues) derived from the source Corrected Transcript
revision's ordered segments, preserving transcript-revision and source-timeline lineage.

A candidate is an unapproved proposal: it carries no reading/time refinement, no structural
validation, no review, no revision, and no human decision, and generating it starts nothing
downstream and mutates no upstream record.

Segment-to-cue cardinality is not a domain invariant. §4.2 forbids assuming a 1:1
Transcript-Unit -> Subtitle-Unit correspondence, and §4.3-4.4 (Reading / Time Representation) may
later merge or split cues. The durable model therefore permanently supports one-to-many and
many-to-one relationships: a cue references an ordered tuple of >=1 source segments (many-to-one),
and several cues may each reference the same segment (one-to-many). The initial deterministic,
provider-free implementation (Slice 3) emits one cue per ordered source segment purely as an
implementation strategy for this milestone's baseline, not as a canonical contract.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    TranscriptSegmentId,
    TranscriptValidationId,
)

from .identities import (
    SubtitleCandidateCueId,
    SubtitleCandidateId,
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)

SUBTITLE_CANDIDATE_RESULT_KIND = "subtitle_candidate"


@dataclass(frozen=True, slots=True)
class SubtitleCandidateCue:
    """One immutable candidate Subtitle Unit traceable to its source Transcript Segment(s)."""

    identity: SubtitleCandidateCueId
    candidate_id: SubtitleCandidateId
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    source_segment_ids: tuple[TranscriptSegmentId, ...]
    text: str
    display_order: int
    source_timeline_id: SourceTimelineId | None = None
    start: float | None = None
    end: float | None = None

    def __post_init__(self) -> None:
        if not self.source_segment_ids:
            raise ValueError("subtitle candidate cue requires a source Transcript Segment")
        if len(set(self.source_segment_ids)) != len(self.source_segment_ids):
            raise ValueError("subtitle candidate cue source segments must be unique")
        if not self.text.strip():
            raise ValueError("subtitle candidate cue text must not be empty")
        if self.display_order < 0:
            raise ValueError("subtitle candidate cue display order must not be negative")
        if (self.start is None) != (self.end is None):
            raise ValueError("subtitle candidate cue time range requires both start and end")
        has_time = self.start is not None and self.end is not None
        if has_time and self.source_timeline_id is None:
            raise ValueError("timed subtitle candidate cue requires a source timeline")
        if has_time:
            if not isfinite(self.start) or not isfinite(self.end):
                raise ValueError("subtitle candidate cue time range must be finite")
            if self.start < 0 or self.end < 0:
                raise ValueError("subtitle candidate cue time range must not be negative")
            if self.start > self.end:
                raise ValueError("subtitle candidate cue start must not be after end")


@dataclass(frozen=True, slots=True)
class SubtitleCandidate:
    """Immutable proposed subtitle candidate derived from one ELIGIBLE Subtitle Transcript Intake."""

    identity: SubtitleCandidateId
    domain_result_id: DomainResultId
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
    cue_ids: tuple[SubtitleCandidateCueId, ...]
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_candidate_id: SubtitleCandidateId | None = None

    def __post_init__(self) -> None:
        if not self.cue_ids:
            raise ValueError("subtitle candidate requires at least one cue")
        if len(set(self.cue_ids)) != len(self.cue_ids):
            raise ValueError("subtitle candidate cue ids must be unique")
        if self.sequence < 0:
            raise ValueError("subtitle candidate sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("subtitle candidate reason must not be empty")
        if self.previous_candidate_id is not None and self.sequence == 0:
            raise ValueError(
                "first subtitle candidate must not reference a previous candidate"
            )


@dataclass(frozen=True, slots=True)
class SubtitleCandidateIdentityPlan:
    """Application-owned candidate identities for one generation."""

    candidate_id: SubtitleCandidateId
    candidate_result_id: DomainResultId
    cue_ids: tuple[SubtitleCandidateCueId, ...]

    def __post_init__(self) -> None:
        if not self.cue_ids:
            raise ValueError("subtitle candidate identity plan requires cue ids")
        if len(set(self.cue_ids)) != len(self.cue_ids):
            raise ValueError("subtitle candidate identity plan cue ids must be unique")


__all__ = [
    "SUBTITLE_CANDIDATE_RESULT_KIND",
    "SubtitleCandidate",
    "SubtitleCandidateCue",
    "SubtitleCandidateIdentityPlan",
]
