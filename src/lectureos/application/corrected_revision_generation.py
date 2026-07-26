"""First Corrected Transcript Revision generation (040 §19, PATCH-0026, GOAL-010).

Applies exactly **one currently Accepted** Correction Candidate (040 §17/§18) to its authoritative source Raw
Transcript and persists the result as one **immutable** canonical `CorrectedTranscriptRevision` (the existing v5
record — complete snapshot via ordered segment references; the corrected segment is a new revision-scoped
`TranscriptSegment` carrying ``replaces_segment_id``; every unaffected segment is referenced unchanged).

Authority principle: acceptance authorizes, generation applies — they are separate boundaries. Accepting a
candidate never creates a revision; generation is an **explicit** request naming one candidate. Generation is
permitted only when the candidate's **current** Human Authority (§18) is Accepted (Undecided/Rejected are
ineligible — historical acceptance is insufficient), and only when the candidate is still structurally
applicable: its Raw Transcript is the intake's current selection (§16/§17 applicability), the target segment
exists in that transcript, and the persisted segment text still equals the candidate's source-text snapshot.
Staleness is application-level ineligibility, never repository corruption.

The revision references the **specific authorizing Accepted Decision** (append-only authority may change later;
a later Reject never rewrites or deletes the historical revision — it only blocks *new* generation). Identity is
deterministic from the anchor ``(candidate, authorizing_decision)``: replaying under the same accepted decision
reuses the existing revision; a *different* accepted decision (after Reject→Accept) is a distinct authority fact
and yields a distinct revision (immutable records cannot acquire new provenance). A same-anchor replay whose
resulting content differs is an explicit conflict — never an overwrite. The revision is **not** selected as
current (Current Corrected Revision Selection is GOAL-011); nothing mutates the candidate, the decision history,
the Raw Transcript, or the current Raw Transcript selection. No wall-clock/randomness participates. Text
replacement is exact (the candidate's proposed text, no normalization); timing, ordering, timeline linkage, and
all unaffected content are preserved.
"""

from __future__ import annotations

import hashlib
import json
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
    CorrectionCandidateId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import CorrectedTranscriptRevision, TranscriptSegment

from .correction_candidate_decision import (
    CorrectionCandidateDecisionError,
    require_canonical_correction_candidate_id,
)
from .identities import CorrectedRevisionGenerationId

CORRECTED_REVISION_IDENTITY_PREFIX = "corrected-revision"
CORRECTED_REVISION_GENERATION_IDENTITY_PREFIX = "corrected-revision-generation"
CORRECTED_REVISION_RESULT_KIND = "corrected_transcript_revision"
_DOMAIN_RESULT_PREFIX = "domain-result:corrected-revision"
_APPLICATION_RUN_PREFIX = "correction-application-run"
_APPLICATION_EXECUTION_PREFIX = "correction-application-execution"
_SEGMENT_PREFIX = "transcript-segment"


class CorrectedRevisionGenerationError(ValueError):
    """A generation request that cannot proceed (malformed, unknown, or unsupported input)."""


class CandidateNotAcceptedError(CorrectedRevisionGenerationError):
    """The candidate's current Human Authority is not Accepted (Undecided or Rejected)."""


class CandidateNotApplicableError(CorrectedRevisionGenerationError):
    """The accepted candidate is no longer structurally applicable to its source state (stale)."""


class CorrectedRevisionConflictError(CorrectedRevisionGenerationError):
    """The same generation anchor exists with different content (no silent overwrite)."""


class GenerationOutcome:
    CREATED = "created"
    REUSED = "reused"


@dataclass(frozen=True, slots=True)
class CorrectedRevisionGeneration:
    """Immutable binding: which accepted decision authorized applying which candidate into which revision."""

    identity: CorrectedRevisionGenerationId
    corrected_revision_id: TranscriptRevisionId
    correction_candidate_id: CorrectionCandidateId
    authorizing_decision_id: object  # CorrectionCandidateDecisionId (kept untyped to avoid an import cycle)
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
class CorrectedRevisionGenerationResult:
    """The outcome of one explicit generation request."""

    generation: CorrectedRevisionGeneration
    revision: CorrectedTranscriptRevision
    outcome: str  # GenerationOutcome.CREATED / REUSED


class CorrectionCandidateAdmissionQuery(Protocol):
    def get_by_candidate(self, candidate_id: CorrectionCandidateId): ...

    def candidate(self, candidate_id: CorrectionCandidateId): ...


class CorrectionCandidateDecisionQuery(Protocol):
    def get_current(self, candidate_id: CorrectionCandidateId): ...


class RawTranscriptSelectionQuery(Protocol):
    def get_current(self, intake_id): ...


class RawTranscriptQuery(Protocol):
    def get(self, identity): ...


class TranscriptSegmentQuery(Protocol):
    def get(self, identity): ...


class CorrectedRevisionGenerationQuery(Protocol):
    def get(self, identity): ...

    def revision(self, revision_id: TranscriptRevisionId): ...

    def generations_for_candidate(self, candidate_id: CorrectionCandidateId) -> tuple: ...


class AtomicCorrectedRevisionGenerationPersistence(Protocol):
    def persist_corrected_revision_generation(
        self,
        *,
        generation: CorrectedRevisionGeneration,
        revision: CorrectedTranscriptRevision,
        replacement_segment: TranscriptSegment,
        result: DomainResultReference,
    ) -> None: ...


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_generation_digest(candidate_id: CorrectionCandidateId, authorizing_decision_id) -> str:
    """The SHA-256 digest of the generation anchor — the basis of every derived identity."""

    return _sha256(
        _canonical_json(
            {
                "candidate": candidate_id.value,
                "authorizing_decision": authorizing_decision_id.value,
            }
        )
    )


def content_fingerprint_for(segments: tuple[TranscriptSegment, ...]) -> str:
    """Deterministic **content** identity of a resulting corrected transcript (order, text, timing).

    Deliberately excludes segment entity identities: content identity and entity identity are distinct (two
    revisions generated under distinct authorizing decisions may carry identical content). Its role here is
    same-anchor conflict detection — identical anchors must reproduce identical content.
    """

    return _sha256(
        _canonical_json(
            [
                {
                    "text": segment.text,
                    "start": segment.start,
                    "end": segment.end,
                    "source_order": segment.source_order,
                }
                for segment in segments
            ]
        )
    )


class CorrectedRevisionGenerationService:
    """Explicitly applies one currently Accepted candidate into one immutable corrected revision."""

    def __init__(
        self,
        admission_query: CorrectionCandidateAdmissionQuery,
        decision_query: CorrectionCandidateDecisionQuery,
        selection_query: RawTranscriptSelectionQuery,
        raw_transcript_query: RawTranscriptQuery,
        segment_query: TranscriptSegmentQuery,
        generation_query: CorrectedRevisionGenerationQuery,
        persistence: AtomicCorrectedRevisionGenerationPersistence | None = None,
    ) -> None:
        self._admissions = admission_query
        self._decisions = decision_query
        self._selections = selection_query
        self._raw_transcripts = raw_transcript_query
        self._segments = segment_query
        self._generations = generation_query
        self._persistence = persistence

    def generate(self, *, candidate_id: str) -> CorrectedRevisionGenerationResult:
        # 1. Resolve the candidate through its admission (the candidate's own authoritative lineage).
        try:
            candidate_identity = require_canonical_correction_candidate_id(candidate_id)
        except CorrectionCandidateDecisionError as error:
            raise CorrectedRevisionGenerationError(str(error)) from error
        admission = self._admissions.get_by_candidate(candidate_identity)
        if admission is None:
            raise CorrectedRevisionGenerationError(
                "unknown correction candidate: admit the candidate before generating a revision"
            )
        candidate = self._admissions.candidate(candidate_identity)
        if candidate is None:
            raise CorrectedRevisionGenerationError(
                "correction candidate record could not be resolved"
            )

        # 2. Current Human Authority must be Accepted (historical acceptance is insufficient).
        current_decision = self._decisions.get_current(candidate_identity)
        if current_decision is None:
            raise CandidateNotAcceptedError(
                "candidate is undecided: an explicit human Accept is required before generation"
            )
        if current_decision.kind is not DecisionKind.ACCEPT:
            raise CandidateNotAcceptedError(
                "candidate is currently rejected: only a currently accepted candidate can be applied"
            )

        # 3. Structural applicability against the candidate's own source lineage.
        current_selection = self._selections.get_current(admission.transcript_source_intake_id)
        if current_selection is None or (
            current_selection.raw_transcript_id != admission.raw_transcript_id
        ):
            raise CandidateNotApplicableError(
                "candidate is not applicable: its raw transcript is no longer the intake's current selection"
            )
        raw_transcript = self._raw_transcripts.get(admission.raw_transcript_id)
        if raw_transcript is None:
            raise CandidateNotApplicableError(
                "candidate is not applicable: its source raw transcript could not be resolved"
            )
        if admission.segment_id not in raw_transcript.segment_ids:
            raise CandidateNotApplicableError(
                "candidate is not applicable: its target segment is not part of the source transcript"
            )
        source_segment = self._segments.get(admission.segment_id)
        if source_segment is None:
            raise CandidateNotApplicableError(
                "candidate is not applicable: its target segment could not be resolved"
            )
        if source_segment.text != admission.source_text_snapshot:
            raise CandidateNotApplicableError(
                "candidate is stale: the persisted segment text no longer matches the source snapshot"
            )

        # 4. Deterministic anchor: the candidate plus the specific authorizing Accepted Decision.
        digest = derive_generation_digest(candidate_identity, current_decision.identity)
        generation_identity = CorrectedRevisionGenerationId(
            f"{CORRECTED_REVISION_GENERATION_IDENTITY_PREFIX}:{digest}"
        )
        revision_identity = TranscriptRevisionId(f"{CORRECTED_REVISION_IDENTITY_PREFIX}:{digest}")

        # 5. Deterministic application: replace exactly the candidate-owned segment, preserve everything else.
        replacement_segment = TranscriptSegment(
            identity=TranscriptSegmentId(f"{_SEGMENT_PREFIX}:{digest}:0"),
            transcript_id=raw_transcript.identity,
            source_timeline_id=source_segment.source_timeline_id,
            text=candidate.proposed_text,
            source_order=source_segment.source_order,
            start=source_segment.start,
            end=source_segment.end,
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
            correction_candidate_ids=(candidate_identity,),
        )
        result = DomainResultReference(
            identity=revision.domain_result_id,
            kind=CORRECTED_REVISION_RESULT_KIND,
            source_media=raw_transcript.source_media_id,
            source_timeline=raw_transcript.source_timeline_id,
            upstream_results=(raw_transcript.domain_result_id,),
        )
        generation = CorrectedRevisionGeneration(
            identity=generation_identity,
            corrected_revision_id=revision_identity,
            correction_candidate_id=candidate_identity,
            authorizing_decision_id=current_decision.identity,
            parent_raw_transcript_id=raw_transcript.identity,
            replaced_segment_id=source_segment.identity,
            replacement_segment_id=replacement_segment.identity,
            content_fingerprint=fingerprint,
        )

        if self._persistence is None:
            raise RuntimeError("corrected revision generation persistence is not configured")
        try:
            self._persistence.persist_corrected_revision_generation(
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
        return CorrectedRevisionGenerationResult(
            generation=generation, revision=revision, outcome=GenerationOutcome.CREATED
        )

    def _resolve_existing(
        self, generation: CorrectedRevisionGeneration, fingerprint: str
    ) -> CorrectedRevisionGenerationResult:
        if generation.content_fingerprint != fingerprint:
            raise CorrectedRevisionConflictError(
                "a corrected revision already exists for this candidate and authorizing decision "
                "with different content (LectureOS does not overwrite an immutable revision)"
            )
        revision = self._generations.revision(generation.corrected_revision_id)
        if revision is None:
            raise CorrectedRevisionGenerationError(
                "existing generation references a missing corrected revision"
            )
        return CorrectedRevisionGenerationResult(
            generation=generation, revision=revision, outcome=GenerationOutcome.REUSED
        )

    def generations_for_candidate(self, candidate_id: str) -> tuple:
        try:
            candidate_identity = require_canonical_correction_candidate_id(candidate_id)
        except CorrectionCandidateDecisionError as error:
            raise CorrectedRevisionGenerationError(str(error)) from error
        return self._generations.generations_for_candidate(candidate_identity)


__all__ = [
    "CORRECTED_REVISION_GENERATION_IDENTITY_PREFIX",
    "CORRECTED_REVISION_IDENTITY_PREFIX",
    "CORRECTED_REVISION_RESULT_KIND",
    "AtomicCorrectedRevisionGenerationPersistence",
    "CandidateNotAcceptedError",
    "CandidateNotApplicableError",
    "CorrectedRevisionConflictError",
    "CorrectedRevisionGeneration",
    "CorrectedRevisionGenerationError",
    "CorrectedRevisionGenerationResult",
    "CorrectedRevisionGenerationService",
    "GenerationOutcome",
    "content_fingerprint_for",
    "derive_generation_digest",
]
