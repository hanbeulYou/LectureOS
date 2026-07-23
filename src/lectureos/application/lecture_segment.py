"""Provider-independent Application foundation for durable canonical Lecture Segments (042 §7.1).

The third Lecture Intelligence Pipeline milestone (042_LECTURE_INTELLIGENCE_PIPELINE.md §7.1, PATCH-0011).
From an already-normalized, provider-independent segmentation result — admitted read-only against exactly one
``ELIGIBLE`` :class:`EligibleAnalysisInput` (042 §5.1) — it deterministically records one or more immutable,
canonical :class:`LectureSegment` records: bounded semantic/functional regions of the Source Timeline that
later Lecture Intelligence stages build on.

It performs **no segmentation** and does **not** invoke AI, implement a provider, define prompts or models, or
create a Segment Label, Analysis Finding, Edit Candidate, or Review Item. Raw provider output, provider
classifications, model or prompt identifiers, and provider internal reasoning never reach this boundary: the
normalized result it admits is a provider-independent Application contract, not a provider API. It establishes
no Segment Label, confidence, uncertainty, or rationale semantics. It starts no downstream capability and
mutates no upstream record. Application owns Segment identity, admission, provenance, persistence and
reconstruction. No wall-clock is read, so reconstruction and replay are deterministic.
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

from .identities import EligibleAnalysisInputId, LectureSegmentId
from .lecture_analysis_input import EligibleAnalysisInput, LectureAnalysisEligibility

LECTURE_SEGMENT_RESULT_KIND = "lecture_segment"


def _validate_time_range(start: float, end: float) -> None:
    # Every Lecture Segment carries exactly one required, single Source Timeline Time Range (042 §7.1).
    for name, value in (("start", start), ("end", end)):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"lecture segment range {name} must be a real number")
    if not isfinite(start) or not isfinite(end):
        raise ValueError("lecture segment time range must be finite")
    if start < 0 or end < 0:
        raise ValueError("lecture segment time range must not be negative")
    if start > end:
        raise ValueError("lecture segment start must not be after end")


@dataclass(frozen=True, slots=True)
class LectureSegment:
    """Immutable, provenance-bearing canonical Lecture Segment anchored to one Eligible Analysis Input."""

    identity: LectureSegmentId
    domain_result_id: DomainResultId
    source_input_id: EligibleAnalysisInputId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    range_start: float
    range_end: float

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("lecture segment sequence must not be negative")
        _validate_time_range(self.range_start, self.range_end)


@dataclass(frozen=True, slots=True)
class NormalizedLectureSegment:
    """One provider-independent proposed segment within a normalized segmentation result."""

    range_start: float
    range_end: float

    def __post_init__(self) -> None:
        _validate_time_range(self.range_start, self.range_end)


@dataclass(frozen=True, slots=True)
class NormalizedSegmentationResult:
    """A validated, provider-independent segmentation result for one Eligible Analysis Input.

    This is an internal Application contract, never a provider API contract. It carries no provider
    identifier, model, prompt, transport metadata, raw provider JSON, classification, or internal reasoning.
    Its ``source_timeline_id`` records the Source Timeline the segmentation was performed against so admission
    can verify lineage against the anchoring Eligible Analysis Input.
    """

    source_timeline_id: SourceTimelineId
    segments: tuple[NormalizedLectureSegment, ...]

    def __post_init__(self) -> None:
        if not self.segments:
            raise ValueError("normalized segmentation result must contain at least one segment")


@dataclass(frozen=True, slots=True)
class LectureSegmentIdentityPlan:
    """Application-owned identities for one canonical Lecture Segment."""

    segment_id: LectureSegmentId
    segment_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedLectureSegment:
    """One immutable canonical Lecture Segment and its Domain Result; not yet persisted."""

    segment: LectureSegment
    segment_result: DomainResultReference


@dataclass(frozen=True, slots=True)
class PreparedLectureSegments:
    """All prepared canonical Segments for one admission; persisted together atomically."""

    source_input_id: EligibleAnalysisInputId
    segments: tuple[PreparedLectureSegment, ...]


class EligibleAnalysisInputQuery(Protocol):
    def get(self, identity): ...


class AtomicLectureSegmentPersistence(Protocol):
    def persist_lecture_segments(
        self, *, prepared: tuple[PreparedLectureSegment, ...]
    ) -> None: ...


class LectureSegmentError(ValueError):
    """A structurally valid request that cannot become canonical Lecture Segment records."""


class LectureSegmentationApplicationService:
    """Admits a normalized segmentation result and records durable canonical Lecture Segments."""

    def __init__(
        self,
        input_query: EligibleAnalysisInputQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicLectureSegmentPersistence | None = None,
    ) -> None:
        self._inputs = input_query
        self._executions = execution_query
        self._persistence = persistence

    def record_segments(self, **kwargs) -> PreparedLectureSegments:
        prepared = self.evaluate_segments(**kwargs)
        if self._persistence is None:
            raise RuntimeError("lecture segment persistence is not configured")
        self._persistence.persist_lecture_segments(prepared=prepared.segments)
        return prepared

    def evaluate_segments(
        self,
        *,
        source_input_id: EligibleAnalysisInputId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        result: NormalizedSegmentationResult,
        identities: tuple[LectureSegmentIdentityPlan, ...],
    ) -> PreparedLectureSegments:
        # Admit the segmentation basis through its canonical Eligible Analysis Input, read only for
        # provenance. The input, and the transcript lineage it traces to, are never mutated.
        eligible_input = self._inputs.get(source_input_id)
        if eligible_input is None:
            raise KeyError("unknown eligible analysis input")
        if not isinstance(eligible_input, EligibleAnalysisInput):
            raise LectureSegmentError(
                "lecture segment must anchor to a canonical Eligible Analysis Input"
            )
        if eligible_input.eligibility is not LectureAnalysisEligibility.ELIGIBLE:
            raise LectureSegmentError(
                "lecture segment requires an ELIGIBLE eligible analysis input"
            )
        self._require_running_execution(run_id, unit_execution_id)

        if result.source_timeline_id != eligible_input.source_timeline_id:
            raise LectureSegmentError(
                "normalized segmentation result source timeline must match the eligible analysis input"
            )
        if len(identities) != len(result.segments):
            raise LectureSegmentError(
                "lecture segment identity plan count must match the normalized segments"
            )

        prepared = tuple(
            self._prepare_one(
                eligible_input=eligible_input,
                run_id=run_id,
                unit_execution_id=unit_execution_id,
                normalized=normalized,
                identity=identity,
                sequence=sequence,
            )
            for sequence, (normalized, identity) in enumerate(
                zip(result.segments, identities)
            )
        )
        return PreparedLectureSegments(
            source_input_id=eligible_input.identity, segments=prepared
        )

    def _prepare_one(
        self,
        *,
        eligible_input: EligibleAnalysisInput,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        normalized: NormalizedLectureSegment,
        identity: LectureSegmentIdentityPlan,
        sequence: int,
    ) -> PreparedLectureSegment:
        segment = LectureSegment(
            identity=identity.segment_id,
            domain_result_id=identity.segment_result_id,
            source_input_id=eligible_input.identity,
            source_media_id=eligible_input.source_media_id,
            source_timeline_id=eligible_input.source_timeline_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            range_start=normalized.range_start,
            range_end=normalized.range_end,
        )
        segment_result = DomainResultReference(
            identity=identity.segment_result_id,
            kind=LECTURE_SEGMENT_RESULT_KIND,
            source_media=eligible_input.source_media_id,
            source_timeline=eligible_input.source_timeline_id,
            upstream_results=(eligible_input.domain_result_id,),
        )
        return PreparedLectureSegment(segment=segment, segment_result=segment_result)

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise LectureSegmentError("unit execution must belong to processing run")
        if execution.state is not ProcessingState.RUNNING:
            raise LectureSegmentError(
                "recording lecture segments requires a running unit execution"
            )


__all__ = [
    "LECTURE_SEGMENT_RESULT_KIND",
    "AtomicLectureSegmentPersistence",
    "LectureSegment",
    "LectureSegmentError",
    "LectureSegmentIdentityPlan",
    "LectureSegmentationApplicationService",
    "NormalizedLectureSegment",
    "NormalizedSegmentationResult",
    "PreparedLectureSegment",
    "PreparedLectureSegments",
]
