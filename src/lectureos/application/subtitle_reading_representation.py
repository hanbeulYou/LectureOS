"""Provider-independent Application contract for Subtitle Reading Representation.

The third Subtitle Pipeline stage (041_SUBTITLE_PIPELINE.md §4.3, §6). From a canonical
`SubtitleCandidate` and its ordered cues, it deterministically composes one new immutable subtitle
reading revision plus an ordered collection of reading units that carry an explicit,
reading-oriented text form (line composition), preserving complete provenance back to the source
cues and (via the immutable cues) the transcript segments.

Reading Representation produces a new immutable representation, not a mutation of the candidate.
The baseline performs a deterministic, meaning-preserving normalization (whitespace normalization
and line composition that preserves the source text's existing hard-line structure) rather than a
pure structural copy; it applies no policy-driven merge/split or readability-threshold logic, which
the Blueprint defers.

Merge/split cardinality is not a domain invariant. The durable model permanently supports cue merge
(a unit references an ordered tuple of >=1 source cues) and split (distinct units reference the same
cue); only policy-based merge/split is deferred. Timing is inherited metadata, not time authority:
Reading Representation owns no time semantics (§4.4 Time Representation owns time) and computes,
infers, and reorders no timestamps — each unit inherits its source cue's timeline and time range as
provenance-only metadata.
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
    TranscriptValidationId,
)

from .identities import (
    SubtitleCandidateCueId,
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)

SUBTITLE_READING_REVISION_RESULT_KIND = "subtitle_reading_revision"


def compose_reading_lines(text: str) -> tuple[str, ...]:
    """Deterministic, meaning-preserving line composition for one source cue's text.

    Preserves the source text's existing hard-line structure, normalizes whitespace within each
    line (collapse internal runs, trim ends), and drops empty lines. Threshold-independent — it
    applies no readability policy. A non-blank cue text always yields at least one non-empty line.
    """

    lines = tuple(
        normalized
        for raw_line in text.split("\n")
        if (normalized := " ".join(raw_line.split()))
    )
    if lines:
        return lines
    return (" ".join(text.split()),)


@dataclass(frozen=True, slots=True)
class SubtitleReadingUnit:
    """One immutable reading unit: a reading-oriented text form traceable to its source cue(s)."""

    identity: SubtitleReadingUnitId
    reading_revision_id: SubtitleReadingRevisionId
    source_cue_ids: tuple[SubtitleCandidateCueId, ...]
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    lines: tuple[str, ...]
    display_order: int
    source_timeline_id: SourceTimelineId | None = None
    start: float | None = None
    end: float | None = None

    def __post_init__(self) -> None:
        if not self.source_cue_ids:
            raise ValueError("subtitle reading unit requires a source cue")
        if len(set(self.source_cue_ids)) != len(self.source_cue_ids):
            raise ValueError("subtitle reading unit source cues must be unique")
        if not self.lines:
            raise ValueError("subtitle reading unit requires a line")
        if any(not line.strip() for line in self.lines):
            raise ValueError("subtitle reading unit lines must not be empty")
        if self.display_order < 0:
            raise ValueError("subtitle reading unit display order must not be negative")
        if (self.start is None) != (self.end is None):
            raise ValueError("subtitle reading unit time range requires both start and end")
        has_time = self.start is not None and self.end is not None
        if has_time and self.source_timeline_id is None:
            raise ValueError("timed subtitle reading unit requires a source timeline")
        if has_time:
            if not isfinite(self.start) or not isfinite(self.end):
                raise ValueError("subtitle reading unit time range must be finite")
            if self.start < 0 or self.end < 0:
                raise ValueError("subtitle reading unit time range must not be negative")
            if self.start > self.end:
                raise ValueError("subtitle reading unit start must not be after end")


@dataclass(frozen=True, slots=True)
class SubtitleReadingRevision:
    """Immutable reading revision derived from one canonical Subtitle Candidate."""

    identity: SubtitleReadingRevisionId
    domain_result_id: DomainResultId
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
    unit_ids: tuple[SubtitleReadingUnitId, ...]
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_reading_revision_id: SubtitleReadingRevisionId | None = None

    def __post_init__(self) -> None:
        if not self.unit_ids:
            raise ValueError("subtitle reading revision requires at least one unit")
        if len(set(self.unit_ids)) != len(self.unit_ids):
            raise ValueError("subtitle reading revision unit ids must be unique")
        if self.sequence < 0:
            raise ValueError("subtitle reading revision sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("subtitle reading revision reason must not be empty")
        if self.previous_reading_revision_id is not None and self.sequence == 0:
            raise ValueError(
                "first subtitle reading revision must not reference a previous revision"
            )


@dataclass(frozen=True, slots=True)
class SubtitleReadingIdentityPlan:
    """Application-owned reading identities for one composition."""

    reading_revision_id: SubtitleReadingRevisionId
    reading_result_id: DomainResultId
    unit_ids: tuple[SubtitleReadingUnitId, ...]

    def __post_init__(self) -> None:
        if not self.unit_ids:
            raise ValueError("subtitle reading identity plan requires unit ids")
        if len(set(self.unit_ids)) != len(self.unit_ids):
            raise ValueError("subtitle reading identity plan unit ids must be unique")


__all__ = [
    "SUBTITLE_READING_REVISION_RESULT_KIND",
    "SubtitleReadingIdentityPlan",
    "SubtitleReadingRevision",
    "SubtitleReadingUnit",
    "compose_reading_lines",
]
