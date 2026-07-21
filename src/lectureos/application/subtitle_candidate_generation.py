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
from lectureos.transcript.boundaries import TranscriptQueryBoundary
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
from .subtitle_transcript_intake import SubtitleIntakeOutcome, SubtitleTranscriptIntake

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


@dataclass(frozen=True, slots=True)
class PreparedSubtitleCandidate:
    """Immutable canonical candidate + ordered cues; not yet persisted."""

    candidate: SubtitleCandidate
    cues: tuple[SubtitleCandidateCue, ...]
    candidate_result: DomainResultReference


class SubtitleTranscriptIntakeQuery(Protocol):
    def get(self, identity): ...


class AtomicSubtitleCandidatePersistence(Protocol):
    def persist_subtitle_candidate(
        self,
        *,
        candidate: SubtitleCandidate,
        cues: tuple[SubtitleCandidateCue, ...],
        candidate_result: DomainResultReference,
    ) -> None: ...


class SubtitleCandidateGenerationError(ValueError):
    """A structurally valid request that cannot become a canonical subtitle candidate."""


class SubtitleCandidateGenerationService:
    """Deterministically generates a subtitle candidate from an ELIGIBLE intake."""

    def __init__(
        self,
        intake_query: SubtitleTranscriptIntakeQuery,
        transcript_query: TranscriptQueryBoundary,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicSubtitleCandidatePersistence | None = None,
    ) -> None:
        self._intakes = intake_query
        self._transcripts = transcript_query
        self._executions = execution_query
        self._persistence = persistence

    def record_candidate(self, **kwargs) -> PreparedSubtitleCandidate:
        prepared = self.generate_candidate(**kwargs)
        if self._persistence is None:
            raise RuntimeError("subtitle candidate persistence is not configured")
        self._persistence.persist_subtitle_candidate(
            candidate=prepared.candidate,
            cues=prepared.cues,
            candidate_result=prepared.candidate_result,
        )
        return prepared

    def generate_candidate(
        self,
        *,
        source_intake_id: SubtitleTranscriptIntakeId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: SubtitleCandidateIdentityPlan,
        sequence: int = 0,
        previous_candidate_id: SubtitleCandidateId | None = None,
        reason: str | None = None,
    ) -> PreparedSubtitleCandidate:
        intake = self._intakes.get(source_intake_id)
        if intake is None:
            raise KeyError("unknown subtitle transcript intake")
        if not isinstance(intake, SubtitleTranscriptIntake):
            raise SubtitleCandidateGenerationError(
                "subtitle candidate must derive from a canonical Subtitle Transcript Intake"
            )
        if intake.outcome is not SubtitleIntakeOutcome.ELIGIBLE:
            raise SubtitleCandidateGenerationError(
                "subtitle candidate generation requires an ELIGIBLE intake"
            )
        self._require_running_execution(run_id, unit_execution_id)

        revision = self._transcripts.get_corrected_revision(intake.source_revision_id)
        if revision is None:
            raise KeyError("unknown corrected transcript revision")
        segments = tuple(
            self._require_segment(segment_id) for segment_id in revision.segment_ids
        )
        if not segments:
            raise SubtitleCandidateGenerationError(
                "source revision has no segments to generate subtitle cues"
            )
        if len(identities.cue_ids) != len(segments):
            raise SubtitleCandidateGenerationError(
                "identity plan cue count must match the derived cue count"
            )

        # Baseline deterministic strategy (not a domain invariant): one cue per ordered
        # source segment. Downstream Reading/Time Representation may merge or split cues.
        cues = tuple(
            SubtitleCandidateCue(
                identity=cue_id,
                candidate_id=identities.candidate_id,
                source_transcript_id=revision.transcript_id,
                source_revision_id=revision.identity,
                source_segment_ids=(segment.identity,),
                text=segment.text,
                display_order=index,
                source_timeline_id=segment.source_timeline_id,
                start=segment.start,
                end=segment.end,
            )
            for index, (cue_id, segment) in enumerate(
                zip(identities.cue_ids, segments)
            )
        )

        resolved_reason = reason if reason is not None else _default_reason(len(cues))
        candidate = SubtitleCandidate(
            identity=identities.candidate_id,
            domain_result_id=identities.candidate_result_id,
            source_intake_id=intake.identity,
            source_readiness_id=intake.source_readiness_id,
            source_selection_id=intake.source_selection_id,
            source_applicability_id=intake.source_applicability_id,
            source_decision_id=intake.source_decision_id,
            review_item_id=intake.review_item_id,
            candidate_reference_id=intake.candidate_reference_id,
            source_transcript_id=revision.transcript_id,
            source_revision_id=intake.source_revision_id,
            source_media_id=intake.source_media_id,
            source_timeline_id=intake.source_timeline_id,
            validation_id=intake.validation_id,
            cue_ids=tuple(identities.cue_ids),
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            previous_candidate_id=previous_candidate_id,
        )
        candidate_result = DomainResultReference(
            identity=identities.candidate_result_id,
            kind=SUBTITLE_CANDIDATE_RESULT_KIND,
            source_media=intake.source_media_id,
            source_timeline=intake.source_timeline_id,
            upstream_results=(intake.domain_result_id,),
        )
        return PreparedSubtitleCandidate(
            candidate=candidate, cues=cues, candidate_result=candidate_result
        )

    def _require_segment(self, segment_id: TranscriptSegmentId):
        segment = self._transcripts.get_segment(segment_id)
        if segment is None:
            raise KeyError("unknown source transcript segment")
        return segment

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise SubtitleCandidateGenerationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise SubtitleCandidateGenerationError(
                "generating subtitle candidate requires a running unit execution"
            )


def _default_reason(cue_count: int) -> str:
    return (
        f"baseline subtitle candidate derived from eligible intake with {cue_count} "
        "cue(s), one per ordered source segment"
    )


__all__ = [
    "SUBTITLE_CANDIDATE_RESULT_KIND",
    "AtomicSubtitleCandidatePersistence",
    "PreparedSubtitleCandidate",
    "SubtitleCandidate",
    "SubtitleCandidateCue",
    "SubtitleCandidateGenerationError",
    "SubtitleCandidateGenerationService",
    "SubtitleCandidateIdentityPlan",
    "SubtitleTranscriptIntakeQuery",
]
