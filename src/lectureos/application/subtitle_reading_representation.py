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
from .subtitle_candidate_generation import SubtitleCandidate

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


@dataclass(frozen=True, slots=True)
class PreparedSubtitleReading:
    """Immutable canonical reading revision + ordered units; not yet persisted."""

    revision: SubtitleReadingRevision
    units: tuple[SubtitleReadingUnit, ...]
    revision_result: DomainResultReference


class SubtitleCandidateQuery(Protocol):
    def get(self, identity): ...

    def get_cue(self, identity): ...


class AtomicSubtitleReadingPersistence(Protocol):
    def persist_subtitle_reading(
        self,
        *,
        revision: SubtitleReadingRevision,
        units: tuple[SubtitleReadingUnit, ...],
        revision_result: DomainResultReference,
    ) -> None: ...


class SubtitleReadingRepresentationError(ValueError):
    """A structurally valid request that cannot become a canonical reading revision."""


class SubtitleReadingRepresentationService:
    """Composes a subtitle reading revision from one canonical Subtitle Candidate."""

    def __init__(
        self,
        candidate_query: SubtitleCandidateQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicSubtitleReadingPersistence | None = None,
    ) -> None:
        self._candidates = candidate_query
        self._executions = execution_query
        self._persistence = persistence

    def record_reading(self, **kwargs) -> PreparedSubtitleReading:
        prepared = self.compose_reading(**kwargs)
        if self._persistence is None:
            raise RuntimeError("subtitle reading persistence is not configured")
        self._persistence.persist_subtitle_reading(
            revision=prepared.revision,
            units=prepared.units,
            revision_result=prepared.revision_result,
        )
        return prepared

    def compose_reading(
        self,
        *,
        source_candidate_id: SubtitleCandidateId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: SubtitleReadingIdentityPlan,
        sequence: int = 0,
        previous_reading_revision_id: SubtitleReadingRevisionId | None = None,
        reason: str | None = None,
    ) -> PreparedSubtitleReading:
        candidate = self._candidates.get(source_candidate_id)
        if candidate is None:
            raise KeyError("unknown subtitle candidate")
        if not isinstance(candidate, SubtitleCandidate):
            raise SubtitleReadingRepresentationError(
                "subtitle reading must derive from a canonical Subtitle Candidate"
            )
        self._require_running_execution(run_id, unit_execution_id)

        cues = tuple(self._require_cue(cue_id) for cue_id in candidate.cue_ids)
        if not cues:
            raise SubtitleReadingRepresentationError(
                "source candidate has no cues to compose reading units"
            )
        if len(identities.unit_ids) != len(cues):
            raise SubtitleReadingRepresentationError(
                "identity plan unit count must match the derived unit count"
            )

        # Baseline deterministic, meaning-preserving transformation (not a domain invariant):
        # one reading unit per ordered source cue, with whitespace-normalized, hard-line-preserving
        # line composition. Timing is inherited metadata only. Policy-driven merge/split/wrap is
        # deferred; downstream Time Representation owns time.
        units = tuple(
            SubtitleReadingUnit(
                identity=unit_id,
                reading_revision_id=identities.reading_revision_id,
                source_cue_ids=(cue.identity,),
                source_transcript_id=cue.source_transcript_id,
                source_revision_id=cue.source_revision_id,
                lines=compose_reading_lines(cue.text),
                display_order=index,
                source_timeline_id=cue.source_timeline_id,
                start=cue.start,
                end=cue.end,
            )
            for index, (unit_id, cue) in enumerate(zip(identities.unit_ids, cues))
        )

        resolved_reason = reason if reason is not None else _default_reason(len(units))
        revision = SubtitleReadingRevision(
            identity=identities.reading_revision_id,
            domain_result_id=identities.reading_result_id,
            source_candidate_id=candidate.identity,
            source_intake_id=candidate.source_intake_id,
            source_readiness_id=candidate.source_readiness_id,
            source_selection_id=candidate.source_selection_id,
            source_applicability_id=candidate.source_applicability_id,
            source_decision_id=candidate.source_decision_id,
            review_item_id=candidate.review_item_id,
            candidate_reference_id=candidate.candidate_reference_id,
            source_transcript_id=candidate.source_transcript_id,
            source_revision_id=candidate.source_revision_id,
            source_media_id=candidate.source_media_id,
            source_timeline_id=candidate.source_timeline_id,
            validation_id=candidate.validation_id,
            unit_ids=tuple(identities.unit_ids),
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            previous_reading_revision_id=previous_reading_revision_id,
        )
        revision_result = DomainResultReference(
            identity=identities.reading_result_id,
            kind=SUBTITLE_READING_REVISION_RESULT_KIND,
            source_media=candidate.source_media_id,
            source_timeline=candidate.source_timeline_id,
            upstream_results=(candidate.domain_result_id,),
        )
        return PreparedSubtitleReading(
            revision=revision, units=units, revision_result=revision_result
        )

    def _require_cue(self, cue_id: SubtitleCandidateCueId):
        cue = self._candidates.get_cue(cue_id)
        if cue is None:
            raise KeyError("unknown subtitle candidate cue")
        return cue

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise SubtitleReadingRepresentationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise SubtitleReadingRepresentationError(
                "composing subtitle reading requires a running unit execution"
            )


def _default_reason(unit_count: int) -> str:
    return (
        f"baseline reading revision derived from candidate with {unit_count} "
        "normalized reading unit(s), one per ordered source cue"
    )


__all__ = [
    "SUBTITLE_READING_REVISION_RESULT_KIND",
    "AtomicSubtitleReadingPersistence",
    "PreparedSubtitleReading",
    "SubtitleCandidateQuery",
    "SubtitleReadingIdentityPlan",
    "SubtitleReadingRepresentationError",
    "SubtitleReadingRepresentationService",
    "SubtitleReadingRevision",
    "SubtitleReadingUnit",
    "compose_reading_lines",
]
