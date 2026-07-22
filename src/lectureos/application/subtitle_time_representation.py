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
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from .subtitle_reading_representation import SubtitleReadingRevision

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


@dataclass(frozen=True, slots=True)
class PreparedSubtitleTiming:
    """Immutable canonical time revision + ordered timed units; not yet persisted."""

    revision: SubtitleTimeRevision
    units: tuple[SubtitleTimedUnit, ...]
    revision_result: DomainResultReference


class SubtitleReadingRevisionQuery(Protocol):
    def get(self, identity): ...

    def get_unit(self, identity): ...


class SubtitleCandidateCueQuery(Protocol):
    def get_cue(self, identity): ...


class AtomicSubtitleTimePersistence(Protocol):
    def persist_subtitle_timing(
        self,
        *,
        revision: SubtitleTimeRevision,
        units: tuple[SubtitleTimedUnit, ...],
        revision_result: DomainResultReference,
    ) -> None: ...


class SubtitleTimeRepresentationError(ValueError):
    """A structurally valid request that cannot become a canonical time revision."""


def anchor_source_timeline_extent(cues):
    """Deterministic provenance representation: the minimal enclosing Source-Timeline extent.

    Returns ``(status, timeline, start, end)``. ANCHORED with ``[min(start), max(end)]`` over the
    given source cues iff every cue is timed and shares one ``source_timeline_id``; otherwise
    UNRESOLVED with null range. This records the provenance-derived interval only — it applies no
    padding, snapping, overlap resolution, gap insertion, or other timing adjustment.
    """

    timelines = {cue.source_timeline_id for cue in cues}
    all_timed = all(
        cue.start is not None
        and cue.end is not None
        and cue.source_timeline_id is not None
        for cue in cues
    )
    if all_timed and len(timelines) == 1:
        timeline = next(iter(timelines))
        start = min(cue.start for cue in cues)
        end = max(cue.end for cue in cues)
        return SubtitleTimingStatus.ANCHORED, timeline, start, end
    return SubtitleTimingStatus.UNRESOLVED, None, None, None


class SubtitleTimeRepresentationService:
    """Anchors subtitle reading units to their Source-Timeline basis as a time revision."""

    def __init__(
        self,
        reading_query: SubtitleReadingRevisionQuery,
        cue_query: SubtitleCandidateCueQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicSubtitleTimePersistence | None = None,
    ) -> None:
        self._readings = reading_query
        self._cues = cue_query
        self._executions = execution_query
        self._persistence = persistence

    def record_timing(self, **kwargs) -> PreparedSubtitleTiming:
        prepared = self.compose_timing(**kwargs)
        if self._persistence is None:
            raise RuntimeError("subtitle time persistence is not configured")
        self._persistence.persist_subtitle_timing(
            revision=prepared.revision,
            units=prepared.units,
            revision_result=prepared.revision_result,
        )
        return prepared

    def compose_timing(
        self,
        *,
        source_reading_revision_id: SubtitleReadingRevisionId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: SubtitleTimeIdentityPlan,
        sequence: int = 0,
        previous_time_revision_id: SubtitleTimeRevisionId | None = None,
        reason: str | None = None,
    ) -> PreparedSubtitleTiming:
        reading = self._readings.get(source_reading_revision_id)
        if reading is None:
            raise KeyError("unknown subtitle reading revision")
        if not isinstance(reading, SubtitleReadingRevision):
            raise SubtitleTimeRepresentationError(
                "subtitle timing must derive from a canonical Subtitle Reading Revision"
            )
        self._require_running_execution(run_id, unit_execution_id)

        reading_units = tuple(
            self._require_reading_unit(unit_id) for unit_id in reading.unit_ids
        )
        if not reading_units:
            raise SubtitleTimeRepresentationError(
                "source reading revision has no units to represent timing"
            )
        if len(identities.timed_unit_ids) != len(reading_units):
            raise SubtitleTimeRepresentationError(
                "identity plan timed unit count must match the reading unit count"
            )

        # Baseline: anchor each reading unit's authoritative display Time Range to the minimal
        # enclosing Source-Timeline extent of its source cues (span for merged units, cue range for
        # one-to-one units), else UNRESOLVED. Provenance representation only; no timing adjustment,
        # no reordering; display order preserved exactly.
        units = tuple(
            self._compose_unit(timed_unit_id, reading_unit, identities.time_revision_id)
            for timed_unit_id, reading_unit in zip(
                identities.timed_unit_ids, reading_units
            )
        )

        resolved_reason = reason if reason is not None else _default_reason(len(units))
        revision = SubtitleTimeRevision(
            identity=identities.time_revision_id,
            domain_result_id=identities.time_result_id,
            source_reading_revision_id=reading.identity,
            source_candidate_id=reading.source_candidate_id,
            source_intake_id=reading.source_intake_id,
            source_readiness_id=reading.source_readiness_id,
            source_selection_id=reading.source_selection_id,
            source_applicability_id=reading.source_applicability_id,
            source_decision_id=reading.source_decision_id,
            review_item_id=reading.review_item_id,
            candidate_reference_id=reading.candidate_reference_id,
            source_transcript_id=reading.source_transcript_id,
            source_revision_id=reading.source_revision_id,
            source_media_id=reading.source_media_id,
            source_timeline_id=reading.source_timeline_id,
            validation_id=reading.validation_id,
            timed_unit_ids=tuple(identities.timed_unit_ids),
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            previous_time_revision_id=previous_time_revision_id,
        )
        revision_result = DomainResultReference(
            identity=identities.time_result_id,
            kind=SUBTITLE_TIME_REVISION_RESULT_KIND,
            source_media=reading.source_media_id,
            source_timeline=reading.source_timeline_id,
            upstream_results=(reading.domain_result_id,),
        )
        return PreparedSubtitleTiming(
            revision=revision, units=units, revision_result=revision_result
        )

    def _compose_unit(
        self,
        timed_unit_id: SubtitleTimedUnitId,
        reading_unit,
        time_revision_id: SubtitleTimeRevisionId,
    ) -> SubtitleTimedUnit:
        cues = tuple(
            self._require_cue(cue_id) for cue_id in reading_unit.source_cue_ids
        )
        status, timeline, start, end = anchor_source_timeline_extent(cues)
        return SubtitleTimedUnit(
            identity=timed_unit_id,
            time_revision_id=time_revision_id,
            source_reading_unit_id=reading_unit.identity,
            display_order=reading_unit.display_order,
            timing_status=status,
            source_timeline_id=timeline,
            start=start,
            end=end,
        )

    def _require_reading_unit(self, unit_id: SubtitleReadingUnitId):
        unit = self._readings.get_unit(unit_id)
        if unit is None:
            raise KeyError("unknown subtitle reading unit")
        return unit

    def _require_cue(self, cue_id: SubtitleCandidateCueId):
        cue = self._cues.get_cue(cue_id)
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
            raise SubtitleTimeRepresentationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise SubtitleTimeRepresentationError(
                "composing subtitle timing requires a running unit execution"
            )


def _default_reason(unit_count: int) -> str:
    return (
        f"baseline time revision anchored from reading revision with {unit_count} "
        "timed unit(s), each the minimal enclosing source-timeline extent of its source cues"
    )


__all__ = [
    "SUBTITLE_TIME_REVISION_RESULT_KIND",
    "AtomicSubtitleTimePersistence",
    "PreparedSubtitleTiming",
    "SubtitleCandidateCueQuery",
    "SubtitleReadingRevisionQuery",
    "SubtitleTimeIdentityPlan",
    "SubtitleTimeRepresentationError",
    "SubtitleTimeRepresentationService",
    "SubtitleTimeRevision",
    "SubtitleTimedUnit",
    "SubtitleTimingStatus",
    "anchor_source_timeline_extent",
]
