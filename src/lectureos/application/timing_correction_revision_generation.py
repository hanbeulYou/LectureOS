"""Corrected revision generation from an accepted Timing Correction Candidate (040 §19 forward note, PATCH-0047).

`§19`'s released model is reused **unchanged** (TC-12). V-5's "text corrections only" and the
generator copying ``start``/``end`` from the source segment reflect the fact that the released
candidate proposes text — not a restriction of the lineage: `TranscriptSegment` carries
``start``/``end``, `CorrectedTranscriptRevision` carries ``segment_ids``, and the replacement declares
``replaces_segment_id``. An accepted timing candidate therefore produces a replacement segment
carrying the **source segment's text exactly** (A-11 preservation — no re-interpretation,
normalisation, or trimming), the accepted proposed interval as its ``start``/``end``, and
``replaces_segment_id`` pointing at its source. No new revision aggregate and no new revision type.

A sibling generation relation exists for the same foreign-key reason as the decision relation
(`corrected_revision_generations` references `correction_candidates`), preserving the provenance
chain candidate → decision → replaced segment → replacement segment → revision (TC-12).

Identity follows the released provenance idiom and fixes no new hash recipe (TC-15): every identity
derives from the anchor ``(timing candidate, authorizing Accepted Decision)`` exactly as `§19` does
over its own candidate, so a timing-only replacement is distinguished from its source automatically
and the released ``replaced_segment_id <> replacement_segment_id`` invariant holds without special
handling. Two different timing proposals for one source segment are two candidates and therefore two
identities.

**Composition is not performed here** (TC-18). Each generation applies exactly one candidate to the
source Raw Transcript, so a text correction and a timing correction on the same segment produce two
independent sibling revisions and `§20` selection chooses one. Nothing merges them, applies them in
an implementation-chosen order, or re-targets a candidate; resolving what the product should do with
competing corrections is Deferred to its own decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import (
    TranscriptRevisionId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import CorrectedTranscriptRevision, TranscriptSegment

from .corrected_revision_generation import (
    CORRECTED_REVISION_IDENTITY_PREFIX,
    CORRECTED_REVISION_RESULT_KIND,
    GenerationOutcome,
    _canonical_json,
    _sha256,
    content_fingerprint_for,
)
from .identities import (
    TimingCorrectionCandidateId,
    TimingCorrectionRevisionGenerationId,
)
from .timing_correction_candidate_admission import same_instant
from .timing_correction_candidate_decision import (
    TimingCorrectionDecisionError,
    require_canonical_timing_candidate_id,
)

TIMING_CORRECTION_GENERATION_IDENTITY_PREFIX = "timing-correction-revision-generation"
_DOMAIN_RESULT_PREFIX = "domain-result:corrected-revision"
_APPLICATION_RUN_PREFIX = "correction-application-run"
_APPLICATION_EXECUTION_PREFIX = "correction-application-execution"
_SEGMENT_PREFIX = "transcript-segment"


class TimingCorrectionGenerationError(ValueError):
    """A generation request that cannot proceed (malformed, unknown, or unsupported input)."""


class TimingCandidateNotAcceptedError(TimingCorrectionGenerationError):
    """The candidate's current Human Authority is not Accepted (Undecided or Rejected)."""


class TimingCandidateNotApplicableError(TimingCorrectionGenerationError):
    """The accepted candidate is no longer structurally applicable to its source state (stale)."""


class TimingCorrectionRevisionConflictError(TimingCorrectionGenerationError):
    """The same generation anchor exists with different content (no silent overwrite)."""


@dataclass(frozen=True, slots=True)
class TimingCorrectionRevisionGeneration:
    """Immutable binding: which accepted timing decision authorized which candidate into which revision."""

    identity: TimingCorrectionRevisionGenerationId
    corrected_revision_id: TranscriptRevisionId
    timing_correction_candidate_id: TimingCorrectionCandidateId
    authorizing_decision_id: object  # TimingCorrectionCandidateDecisionId (avoids an import cycle)
    parent_raw_transcript_id: object  # TranscriptId
    replaced_segment_id: TranscriptSegmentId
    replacement_segment_id: TranscriptSegmentId
    content_fingerprint: str

    def __post_init__(self) -> None:
        if len(self.content_fingerprint) != 64:
            raise ValueError("generation content fingerprint must be a 64-hex SHA-256 digest")
        if self.replaced_segment_id == self.replacement_segment_id:
            raise ValueError("replacement segment must differ from the replaced segment")


@dataclass(frozen=True, slots=True)
class TimingCorrectionRevisionGenerationResult:
    """The outcome of one explicit generation request."""

    generation: TimingCorrectionRevisionGeneration
    revision: CorrectedTranscriptRevision
    outcome: str  # GenerationOutcome.CREATED / REUSED


class TimingCorrectionCandidateQuery(Protocol):
    def get(self, identity): ...


class TimingCorrectionDecisionQuery(Protocol):
    def get_current(self, candidate_id): ...


class RawTranscriptSelectionQuery(Protocol):
    def get_current(self, intake_id): ...


class RawTranscriptQuery(Protocol):
    def get(self, identity): ...


class TranscriptSegmentQuery(Protocol):
    def get(self, identity): ...


class TimingCorrectionGenerationQuery(Protocol):
    def get(self, identity): ...

    def revision(self, revision_id: TranscriptRevisionId): ...

    def generations_for_candidate(self, candidate_id) -> tuple: ...


class AtomicTimingCorrectionGenerationPersistence(Protocol):
    def persist_timing_correction_generation(
        self,
        *,
        generation: TimingCorrectionRevisionGeneration,
        revision: CorrectedTranscriptRevision,
        replacement_segment: TranscriptSegment,
        result: DomainResultReference,
    ) -> None: ...


def derive_timing_generation_digest(
    candidate_id: TimingCorrectionCandidateId, authorizing_decision_id
) -> str:
    """The SHA-256 digest of the generation anchor — the released `§19` recipe over a timing candidate."""

    return _sha256(
        _canonical_json(
            {
                "candidate": candidate_id.value,
                "authorizing_decision": authorizing_decision_id.value,
            }
        )
    )


class TimingCorrectionRevisionGenerationService:
    """Explicitly applies one currently Accepted timing candidate into one immutable corrected revision."""

    def __init__(
        self,
        candidate_query: TimingCorrectionCandidateQuery,
        decision_query: TimingCorrectionDecisionQuery,
        selection_query: RawTranscriptSelectionQuery,
        raw_transcript_query: RawTranscriptQuery,
        segment_query: TranscriptSegmentQuery,
        generation_query: TimingCorrectionGenerationQuery,
        persistence: AtomicTimingCorrectionGenerationPersistence | None = None,
    ) -> None:
        self._candidates = candidate_query
        self._decisions = decision_query
        self._selections = selection_query
        self._raw_transcripts = raw_transcript_query
        self._segments = segment_query
        self._generations = generation_query
        self._persistence = persistence

    def generate(self, *, candidate_id: str) -> TimingCorrectionRevisionGenerationResult:
        # 1. Resolve the candidate through its own authoritative record.
        try:
            candidate_identity = require_canonical_timing_candidate_id(candidate_id)
        except TimingCorrectionDecisionError as error:
            raise TimingCorrectionGenerationError(str(error)) from error
        candidate = self._candidates.get(candidate_identity)
        if candidate is None:
            raise TimingCorrectionGenerationError(
                "unknown timing correction candidate: admit the candidate before generating a revision"
            )

        # 2. Current Human Authority must be Accepted (historical acceptance is insufficient).
        current_decision = self._decisions.get_current(candidate_identity)
        if current_decision is None:
            raise TimingCandidateNotAcceptedError(
                "candidate is undecided: an explicit human Accept is required before generation"
            )
        if current_decision.kind is not DecisionKind.ACCEPT:
            raise TimingCandidateNotAcceptedError(
                "candidate is currently rejected: only a currently accepted candidate can be applied"
            )

        # 3. Structural applicability against the candidate's own source lineage.
        current_selection = self._selections.get_current(
            candidate.transcript_source_intake_id
        )
        if current_selection is None or (
            current_selection.raw_transcript_id != candidate.raw_transcript_id
        ):
            raise TimingCandidateNotApplicableError(
                "candidate is not applicable: its raw transcript is no longer the intake's current selection"
            )
        raw_transcript = self._raw_transcripts.get(candidate.raw_transcript_id)
        if raw_transcript is None:
            raise TimingCandidateNotApplicableError(
                "candidate is not applicable: its source raw transcript could not be resolved"
            )
        if candidate.segment_id not in raw_transcript.segment_ids:
            raise TimingCandidateNotApplicableError(
                "candidate is not applicable: its target segment is not part of the source transcript"
            )
        source_segment = self._segments.get(candidate.segment_id)
        if source_segment is None:
            raise TimingCandidateNotApplicableError(
                "candidate is not applicable: its target segment could not be resolved"
            )
        if source_segment.start is None or source_segment.end is None:
            raise TimingCandidateNotApplicableError(
                "candidate is not applicable: its target segment carries no timing"
            )
        if not (
            same_instant(candidate.source_start_snapshot, float(source_segment.start))
            and same_instant(candidate.source_end_snapshot, float(source_segment.end))
        ):
            raise TimingCandidateNotApplicableError(
                "candidate is stale: the persisted segment timing no longer matches the source snapshot"
            )

        # 4. Deterministic anchor: the candidate plus the specific authorizing Accepted Decision.
        digest = derive_timing_generation_digest(
            candidate_identity, current_decision.identity
        )
        generation_identity = TimingCorrectionRevisionGenerationId(
            f"{TIMING_CORRECTION_GENERATION_IDENTITY_PREFIX}:{digest}"
        )
        revision_identity = TranscriptRevisionId(
            f"{CORRECTED_REVISION_IDENTITY_PREFIX}:{digest}"
        )

        # 5. Deterministic application: the source text exactly, the accepted interval, nothing else.
        replacement_segment = TranscriptSegment(
            identity=TranscriptSegmentId(f"{_SEGMENT_PREFIX}:{digest}:0"),
            transcript_id=raw_transcript.identity,
            source_timeline_id=source_segment.source_timeline_id,
            text=source_segment.text,
            source_order=source_segment.source_order,
            start=candidate.proposed_start,
            end=candidate.proposed_end,
            speaker_label=source_segment.speaker_label,
            replaces_segment_id=source_segment.identity,
        )
        corrected_segment_ids = tuple(
            replacement_segment.identity if segment_id == source_segment.identity else segment_id
            for segment_id in raw_transcript.segment_ids
        )
        resulting_segments = tuple(
            replacement_segment
            if segment_id == replacement_segment.identity
            else self._segments.get(segment_id)
            for segment_id in corrected_segment_ids
        )
        fingerprint = content_fingerprint_for(resulting_segments)

        existing = self._generations.get(generation_identity)
        if existing is not None:
            return self._resolve_existing(existing, fingerprint)

        revision = CorrectedTranscriptRevision(
            identity=revision_identity,
            transcript_id=raw_transcript.identity,
            domain_result_id=DomainResultId(f"{_DOMAIN_RESULT_PREFIX}:{digest}"),
            run_id=ProcessingRunId(f"{_APPLICATION_RUN_PREFIX}:{digest}"),
            unit_execution_id=UnitExecutionId(f"{_APPLICATION_EXECUTION_PREFIX}:{digest}"),
            segment_ids=corrected_segment_ids,
            parent_raw_transcript_id=raw_transcript.identity,
            # No text CorrectionCandidate participates; the timing lineage is carried by the sibling
            # generation relation. The released field keeps its meaning and is simply empty here.
            correction_candidate_ids=(),
        )
        result = DomainResultReference(
            identity=revision.domain_result_id,
            kind=CORRECTED_REVISION_RESULT_KIND,
            source_media=raw_transcript.source_media_id,
            source_timeline=raw_transcript.source_timeline_id,
            upstream_results=(raw_transcript.domain_result_id,),
        )
        generation = TimingCorrectionRevisionGeneration(
            identity=generation_identity,
            corrected_revision_id=revision_identity,
            timing_correction_candidate_id=candidate_identity,
            authorizing_decision_id=current_decision.identity,
            parent_raw_transcript_id=raw_transcript.identity,
            replaced_segment_id=source_segment.identity,
            replacement_segment_id=replacement_segment.identity,
            content_fingerprint=fingerprint,
        )

        if self._persistence is None:
            raise RuntimeError("timing correction generation persistence is not configured")
        try:
            self._persistence.persist_timing_correction_generation(
                generation=generation,
                revision=revision,
                replacement_segment=replacement_segment,
                result=result,
            )
        except PersistenceIdentityCollisionError:
            resolved = self._generations.get(generation_identity)
            if resolved is not None:
                return self._resolve_existing(resolved, fingerprint)
            raise
        return TimingCorrectionRevisionGenerationResult(
            generation=generation, revision=revision, outcome=GenerationOutcome.CREATED
        )

    def _resolve_existing(
        self, generation: TimingCorrectionRevisionGeneration, fingerprint: str
    ) -> TimingCorrectionRevisionGenerationResult:
        if generation.content_fingerprint != fingerprint:
            raise TimingCorrectionRevisionConflictError(
                "a corrected revision already exists for this candidate and authorizing decision "
                "with different content (LectureOS does not overwrite an immutable revision)"
            )
        revision = self._generations.revision(generation.corrected_revision_id)
        if revision is None:
            raise TimingCorrectionGenerationError(
                "existing generation references a missing corrected revision"
            )
        return TimingCorrectionRevisionGenerationResult(
            generation=generation, revision=revision, outcome=GenerationOutcome.REUSED
        )

    def generations_for_candidate(self, candidate_id: str) -> tuple:
        try:
            candidate_identity = require_canonical_timing_candidate_id(candidate_id)
        except TimingCorrectionDecisionError as error:
            raise TimingCorrectionGenerationError(str(error)) from error
        return self._generations.generations_for_candidate(candidate_identity)


__all__ = [
    "TIMING_CORRECTION_GENERATION_IDENTITY_PREFIX",
    "AtomicTimingCorrectionGenerationPersistence",
    "TimingCandidateNotAcceptedError",
    "TimingCandidateNotApplicableError",
    "TimingCorrectionGenerationError",
    "TimingCorrectionGenerationQuery",
    "TimingCorrectionRevisionConflictError",
    "TimingCorrectionRevisionGeneration",
    "TimingCorrectionRevisionGenerationResult",
    "TimingCorrectionRevisionGenerationService",
    "derive_timing_generation_digest",
]
