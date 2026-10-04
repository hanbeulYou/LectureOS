"""Same-Source Text + Timing Composition generation (040 §19 `PATCH-0050`, TX-1…TX-39).

An **explicit pair request** names exactly one text correction candidate and exactly one timing
correction candidate that target the **same** original source segment of the **same** Raw
Transcript, and applies both accepted values into **one** composed replacement segment inside
**one** complete immutable Corrected Revision (TX-1/TX-2).

Authority is model B (TX-5…TX-9): the two candidates' *current* Accepted `§18` authority plus the
explicit request. No composition approval entity, no new Decision kind, no requester provenance.
Each role's authorizing Decision is derived from current authority at request time — no input names
a past Decision (TX-7) — and whether the two corrections were judged by the same reviewer or in the
same listening session is evidence context, never a guard (TX-9).

Identity derives from the **role-tagged** anchor ``{base, source, text: (candidate, Decision),
timing: (candidate, Decision)}`` (TX-14); the composed replacement is a **new entity** that never
reuses a sibling's replacement identity, and uniqueness holds over the complete anchor so a
re-Accept of either candidate is a new anchor (TX-15…TX-17). Reuse — on the pre-persist lookup and
on the post-collision re-read alike — requires the complete-result integrity of TX-28; a matching
content fingerprint never substitutes (TX-29).

This module composes **from the Raw source directly**. It never builds or consults a text-only or
timing-only sibling, inherits nothing from a selected revision, and performs no selection and no
subtitle work (TX-12, TX-38). The released text and timing generation paths are untouched.
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
    CorrectionCandidateId,
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
from .correction_candidate_decision import (
    CorrectionCandidateDecisionError,
    require_canonical_correction_candidate_id,
)
from .identities import SameSourceCompositionGenerationId, TimingCorrectionCandidateId
from .timing_correction_candidate_admission import same_instant
from .timing_correction_candidate_decision import (
    TimingCorrectionDecisionError,
    require_canonical_timing_candidate_id,
)
from .timing_correction_revision_generation import _require_combined_validity, _same_replacement

SAME_SOURCE_COMPOSITION_GENERATION_IDENTITY_PREFIX = "same-source-composition-generation"
_DOMAIN_RESULT_PREFIX = "domain-result:corrected-revision"
_APPLICATION_RUN_PREFIX = "correction-application-run"
_APPLICATION_EXECUTION_PREFIX = "correction-application-execution"
_SEGMENT_PREFIX = "transcript-segment"

TEXT_ROLE = "text"
TIMING_ROLE = "timing"


class SameSourceCompositionError(ValueError):
    """A composition request that cannot proceed (malformed, unknown, or unsupported input)."""


class CompositionRoleError(SameSourceCompositionError):
    """A role is missing, repeated, or carries a candidate of the wrong kind (TX-2)."""


class CompositionCandidateNotAcceptedError(SameSourceCompositionError):
    """A role's current Human Authority is not Accepted (Undecided or Rejected)."""


class CompositionNotApplicableError(SameSourceCompositionError):
    """The pair is not structurally applicable to its common source (different source/base, stale)."""


class CompositionCombinedValidityError(SameSourceCompositionError):
    """The composed segment or the complete snapshot is structurally invalid (TX-23)."""


class CompositionRevisionConflictError(SameSourceCompositionError):
    """The same anchor exists with different content (released V-10 conflict, no overwrite)."""


class CompositionIntegrityError(SameSourceCompositionError):
    """A stored result under this anchor fails complete-result integrity (TX-28/TX-29)."""


class CompositionStaleAuthorityError(CompositionNotApplicableError):
    """The authority or source snapshot moved between verification and persist (TX-24)."""


@dataclass(frozen=True, slots=True)
class SameSourceCompositionGeneration:
    """Immutable binding: the single canonical owner of one revision's two-role provenance (TX-18)."""

    identity: SameSourceCompositionGenerationId
    corrected_revision_id: TranscriptRevisionId
    parent_raw_transcript_id: object  # TranscriptId
    replaced_segment_id: TranscriptSegmentId
    text_correction_candidate_id: CorrectionCandidateId
    text_authorizing_decision_id: object  # CorrectionCandidateDecisionId
    timing_correction_candidate_id: TimingCorrectionCandidateId
    timing_authorizing_decision_id: object  # TimingCorrectionCandidateDecisionId
    replacement_segment_id: TranscriptSegmentId
    content_fingerprint: str

    def __post_init__(self) -> None:
        if len(self.content_fingerprint) != 64:
            raise ValueError("generation content fingerprint must be a 64-hex SHA-256 digest")
        if self.replaced_segment_id == self.replacement_segment_id:
            raise ValueError("composed replacement must differ from the replaced segment")

    @property
    def roles(self) -> tuple[tuple[str, object, object], ...]:
        """``(role, candidate identity, authorizing Decision identity)`` for both roles, text first."""

        return (
            (TEXT_ROLE, self.text_correction_candidate_id, self.text_authorizing_decision_id),
            (TIMING_ROLE, self.timing_correction_candidate_id, self.timing_authorizing_decision_id),
        )


@dataclass(frozen=True, slots=True)
class SameSourceCompositionResult:
    generation: SameSourceCompositionGeneration
    revision: CorrectedTranscriptRevision
    outcome: str  # GenerationOutcome.CREATED / REUSED


class CorrectionCandidateAdmissionQuery(Protocol):
    def get_by_candidate(self, candidate_id): ...

    def candidate(self, candidate_id): ...


class CorrectionCandidateDecisionQuery(Protocol):
    def get_current(self, candidate_id): ...


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


class SameSourceCompositionQuery(Protocol):
    def get(self, identity): ...

    def revision(self, revision_id: TranscriptRevisionId): ...


class AtomicSameSourceCompositionPersistence(Protocol):
    def persist_same_source_composition(
        self,
        *,
        generation: SameSourceCompositionGeneration,
        revision: CorrectedTranscriptRevision,
        replacement_segment: TranscriptSegment,
        result: DomainResultReference,
        revalidate=None,
    ) -> None: ...


def derive_composition_digest(
    base_raw_transcript_id,
    source_segment_id,
    text_candidate_id,
    text_decision_id,
    timing_candidate_id,
    timing_decision_id,
) -> str:
    """The SHA-256 digest of the role-tagged composition anchor (TX-14).

    Roles are named keys, not positions, so the digest cannot depend on the order in which the caller
    listed the two candidates, and swapping the roles is a different (and invalid) anchor rather than
    the same one.
    """

    return _sha256(
        _canonical_json(
            {
                "base": base_raw_transcript_id.value,
                "source": source_segment_id.value,
                TEXT_ROLE: {
                    "candidate": text_candidate_id.value,
                    "authorizing_decision": text_decision_id.value,
                },
                TIMING_ROLE: {
                    "candidate": timing_candidate_id.value,
                    "authorizing_decision": timing_decision_id.value,
                },
            }
        )
    )


@dataclass(frozen=True, slots=True)
class _AuthoritySnapshot:
    """The authority/applicability facts a request fixes as its anchor (TX-24).

    These are gathered by sequential reads on the caller's autocommit connection — not by one
    database read transaction. What makes them a *consistent* anchor for a new result is the
    revalidation that `_require_snapshot_unchanged` performs inside the write transaction, which
    compares the current state against exactly these fixed values before anything is persisted.
    """

    intake_id: object
    raw_transcript: object
    source_segment: TranscriptSegment
    text_candidate: object
    text_admission: object
    text_decision: object
    timing_candidate: object
    timing_decision: object


@dataclass(frozen=True, slots=True)
class _ExpectedResult:
    generation: SameSourceCompositionGeneration
    replacement: TranscriptSegment
    segment_ids: tuple[TranscriptSegmentId, ...]


class SameSourceCompositionGenerationService:
    """Explicitly applies one text candidate and one timing candidate on one source into one revision."""

    def __init__(
        self,
        admission_query: CorrectionCandidateAdmissionQuery,
        text_decision_query: CorrectionCandidateDecisionQuery,
        timing_candidate_query: TimingCorrectionCandidateQuery,
        timing_decision_query: TimingCorrectionDecisionQuery,
        selection_query: RawTranscriptSelectionQuery,
        raw_transcript_query: RawTranscriptQuery,
        segment_query: TranscriptSegmentQuery,
        composition_query: SameSourceCompositionQuery,
        persistence: AtomicSameSourceCompositionPersistence | None = None,
    ) -> None:
        self._admissions = admission_query
        self._text_decisions = text_decision_query
        self._timing_candidates = timing_candidate_query
        self._timing_decisions = timing_decision_query
        self._selections = selection_query
        self._raw_transcripts = raw_transcript_query
        self._segments = segment_query
        self._compositions = composition_query
        self._persistence = persistence

    def generate(
        self, *, text_candidate_id: str, timing_candidate_id: str
    ) -> SameSourceCompositionResult:
        # 1. Explicit roles. The caller names the text candidate as text and the timing candidate as
        #    timing; a kind that does not match its role is a malformed request, not an ordering
        #    variation (TX-2).
        text_identity, timing_identity = self._require_roles(text_candidate_id, timing_candidate_id)

        # 2+3. Fix the request's authority/applicability anchor over both roles (TX-10, TX-24).
        #    These are sequential reads; for a NEW result they are re-verified inside the write
        #    transaction (step 8). A reused result (steps 7 and the collision branch) is not
        #    re-read under a transaction: it consumes the authority as read by the guard here, and
        #    is accepted only under complete-result integrity (TX-28).
        snapshot = self._snapshot(text_identity, timing_identity)
        source = snapshot.source_segment
        raw_transcript = snapshot.raw_transcript

        # 4. Role-tagged anchor and deterministic identities (TX-14/TX-15).
        digest = derive_composition_digest(
            raw_transcript.identity,
            source.identity,
            snapshot.text_candidate.identity,
            snapshot.text_decision.identity,
            snapshot.timing_candidate.identity,
            snapshot.timing_decision.identity,
        )
        generation_identity = SameSourceCompositionGenerationId(
            f"{SAME_SOURCE_COMPOSITION_GENERATION_IDENTITY_PREFIX}:{digest}"
        )
        revision_identity = TranscriptRevisionId(f"{CORRECTED_REVISION_IDENTITY_PREFIX}:{digest}")

        # 5. Composed replacement, built from the Raw source directly: text from the text candidate,
        #    interval from the timing candidate, carried fields from the source, no confidence or
        #    uncertainty fabricated (TX-12).
        replacement = TranscriptSegment(
            identity=TranscriptSegmentId(f"{_SEGMENT_PREFIX}:{digest}:0"),
            transcript_id=raw_transcript.identity,
            source_timeline_id=source.source_timeline_id,
            text=snapshot.text_candidate.proposed_text,
            source_order=source.source_order,
            start=snapshot.timing_candidate.proposed_start,
            end=snapshot.timing_candidate.proposed_end,
            speaker_label=source.speaker_label,
            replaces_segment_id=source.identity,
        )
        corrected_segment_ids = tuple(
            replacement.identity if segment_id == source.identity else segment_id
            for segment_id in raw_transcript.segment_ids
        )
        resulting_segments = tuple(
            replacement if segment_id == replacement.identity else self._segments.get(segment_id)
            for segment_id in corrected_segment_ids
        )

        # 6. Structural validity of the composed segment and of the complete snapshot (TX-23).
        self._require_composed_validity(replacement)
        try:
            _require_combined_validity(resulting_segments)
        except SameSourceCompositionError:
            raise
        except ValueError as error:
            raise CompositionCombinedValidityError(str(error)) from error
        fingerprint = content_fingerprint_for(resulting_segments)

        generation = SameSourceCompositionGeneration(
            identity=generation_identity,
            corrected_revision_id=revision_identity,
            parent_raw_transcript_id=raw_transcript.identity,
            replaced_segment_id=source.identity,
            text_correction_candidate_id=snapshot.text_candidate.identity,
            text_authorizing_decision_id=snapshot.text_decision.identity,
            timing_correction_candidate_id=snapshot.timing_candidate.identity,
            timing_authorizing_decision_id=snapshot.timing_decision.identity,
            replacement_segment_id=replacement.identity,
            content_fingerprint=fingerprint,
        )
        expected = _ExpectedResult(
            generation=generation, replacement=replacement, segment_ids=corrected_segment_ids
        )

        # 7. An existing result under this anchor is reused only under complete-result integrity.
        stored = self._compositions.get(generation_identity)
        if stored is not None:
            return self._resolve_existing(stored, expected)

        revision = CorrectedTranscriptRevision(
            identity=revision_identity,
            transcript_id=raw_transcript.identity,
            domain_result_id=DomainResultId(f"{_DOMAIN_RESULT_PREFIX}:{digest}"),
            run_id=ProcessingRunId(f"{_APPLICATION_RUN_PREFIX}:{digest}"),
            unit_execution_id=UnitExecutionId(f"{_APPLICATION_EXECUTION_PREFIX}:{digest}"),
            segment_ids=corrected_segment_ids,
            parent_raw_transcript_id=raw_transcript.identity,
            # The released text-only field keeps its meaning: the one applied text candidate. It is
            # not the composition's authority provenance and never carries a timing identity (TX-19).
            correction_candidate_ids=(snapshot.text_candidate.identity,),
        )
        result = DomainResultReference(
            identity=revision.domain_result_id,
            kind=CORRECTED_REVISION_RESULT_KIND,
            source_media=raw_transcript.source_media_id,
            source_timeline=raw_transcript.source_timeline_id,
            upstream_results=(raw_transcript.domain_result_id,),
        )
        if self._persistence is None:
            raise RuntimeError("same-source composition persistence is not configured")

        # 8. The snapshot must still hold at persist time; the check runs INSIDE the write
        #    transaction and compares against the Decisions fixed above (TX-24).
        def revalidate() -> None:
            self._require_snapshot_unchanged(snapshot)

        try:
            self._persistence.persist_same_source_composition(
                generation=generation,
                revision=revision,
                replacement_segment=replacement,
                result=result,
                revalidate=revalidate,
            )
        except PersistenceIdentityCollisionError:
            # A near-concurrent identical request won the race. Converge only under the SAME
            # complete-result integrity standard the pre-persist lookup applies (TX-28).
            resolved = self._compositions.get(generation_identity)
            if resolved is not None:
                return self._resolve_existing(resolved, expected)
            raise
        return SameSourceCompositionResult(
            generation=generation, revision=revision, outcome=GenerationOutcome.CREATED
        )

    # -- roles, authority snapshot, staleness --------------------------------------------------------

    def _require_roles(self, text_candidate_id, timing_candidate_id):
        if not isinstance(text_candidate_id, str) or not text_candidate_id:
            raise CompositionRoleError("the text role must name exactly one text correction candidate")
        if not isinstance(timing_candidate_id, str) or not timing_candidate_id:
            raise CompositionRoleError(
                "the timing role must name exactly one timing correction candidate"
            )
        try:
            text_identity = require_canonical_correction_candidate_id(text_candidate_id)
        except CorrectionCandidateDecisionError as error:
            raise CompositionRoleError(
                f"the text role does not carry a text correction candidate identity: {error}"
            ) from error
        try:
            timing_identity = require_canonical_timing_candidate_id(timing_candidate_id)
        except TimingCorrectionDecisionError as error:
            raise CompositionRoleError(
                f"the timing role does not carry a timing correction candidate identity: {error}"
            ) from error
        return text_identity, timing_identity

    def _snapshot(self, text_identity, timing_identity) -> "_AuthoritySnapshot":
        """Resolve both roles' candidates, current Accepted Decisions, the current Raw selection and the
        source segment, and check each role with the snapshot it actually carries (TX-10).

        Each role's current authority is read from its own Decision store. The reads are sequential
        and not wrapped in a read transaction; the values returned here become the fixed anchor that
        `_require_snapshot_unchanged` re-verifies inside the write transaction before a new result is
        persisted. Nothing here re-derives or replaces an anchor once fixed.
        """

        admission = self._admissions.get_by_candidate(text_identity)
        if admission is None:
            raise SameSourceCompositionError(
                "unknown text correction candidate: admit the candidate before composing"
            )
        text_candidate = self._admissions.candidate(text_identity)
        if text_candidate is None:
            raise SameSourceCompositionError("text correction candidate record could not be resolved")
        timing_candidate = self._timing_candidates.get(timing_identity)
        if timing_candidate is None:
            raise SameSourceCompositionError(
                "unknown timing correction candidate: admit the candidate before composing"
            )

        # Each role's current authority is read from ITS OWN decision store; a text Decision never
        # authorizes a timing candidate and vice versa (TX-5/TX-7).
        text_decision = self._text_decisions.get_current(text_identity)
        if text_decision is None:
            raise CompositionCandidateNotAcceptedError(
                "text candidate is undecided: an explicit human Accept is required before composition"
            )
        if text_decision.kind is not DecisionKind.ACCEPT:
            raise CompositionCandidateNotAcceptedError(
                "text candidate is currently rejected: only a currently accepted candidate can be applied"
            )
        timing_decision = self._timing_decisions.get_current(timing_identity)
        if timing_decision is None:
            raise CompositionCandidateNotAcceptedError(
                "timing candidate is undecided: an explicit human Accept is required before composition"
            )
        if timing_decision.kind is not DecisionKind.ACCEPT:
            raise CompositionCandidateNotAcceptedError(
                "timing candidate is currently rejected: only a currently accepted candidate can be applied"
            )

        # Same intake, same Raw Transcript, same canonical source segment (TX-10).
        if (
            admission.transcript_source_intake_id != timing_candidate.transcript_source_intake_id
            or admission.raw_transcript_id != timing_candidate.raw_transcript_id
        ):
            raise CompositionNotApplicableError(
                "the pair is not composable: the text and timing candidates belong to different "
                "intakes or raw transcripts"
            )
        if admission.segment_id != timing_candidate.segment_id:
            raise CompositionNotApplicableError(
                "the pair is not composable: the text and timing candidates target different "
                "source segments (same-source composition applies both to one original segment)"
            )
        intake_id = admission.transcript_source_intake_id
        current_selection = self._selections.get_current(intake_id)
        if current_selection is None or (
            current_selection.raw_transcript_id != admission.raw_transcript_id
        ):
            raise CompositionNotApplicableError(
                "the pair is not applicable: its raw transcript is no longer the intake's current selection"
            )
        raw_transcript = self._raw_transcripts.get(admission.raw_transcript_id)
        if raw_transcript is None:
            raise CompositionNotApplicableError(
                "the pair is not applicable: its source raw transcript could not be resolved"
            )
        if admission.segment_id not in raw_transcript.segment_ids:
            raise CompositionNotApplicableError(
                "the pair is not applicable: its target segment is not part of the source transcript "
                "(a corrected revision's replacement segment is not an original source)"
            )
        source = self._segments.get(admission.segment_id)
        if source is None:
            raise CompositionNotApplicableError(
                "the pair is not applicable: its target segment could not be resolved"
            )
        # Each candidate is checked with the snapshot it actually carries (TX-10): text snapshot for
        # the text role, interval snapshot for the timing role. No cross-kind snapshot exists.
        if source.text != admission.source_text_snapshot:
            raise CompositionNotApplicableError(
                "text candidate is stale: the persisted segment text no longer matches the source snapshot"
            )
        if source.start is None or source.end is None:
            raise CompositionNotApplicableError(
                "the pair is not applicable: its target segment carries no timing"
            )
        if not (
            same_instant(timing_candidate.source_start_snapshot, float(source.start))
            and same_instant(timing_candidate.source_end_snapshot, float(source.end))
        ):
            raise CompositionNotApplicableError(
                "timing candidate is stale: the persisted segment timing no longer matches the source snapshot"
            )
        return _AuthoritySnapshot(
            intake_id=intake_id,
            raw_transcript=raw_transcript,
            source_segment=source,
            text_candidate=text_candidate,
            text_admission=admission,
            text_decision=text_decision,
            timing_candidate=timing_candidate,
            timing_decision=timing_decision,
        )

    def _require_snapshot_unchanged(self, snapshot: "_AuthoritySnapshot") -> None:
        """Re-derive the fixed facts inside the write transaction; any movement fails the request (TX-24).

        Called by the persistence layer after ``BEGIN IMMEDIATE`` on the same connection, so the
        comparison and the write see one consistent database state. The comparison is against the
        Decision identities fixed at request time — a different Accepted Decision (Accept → Reject →
        Accept) is a different authority anchor and is refused, never silently adopted. This runs only
        on the path that persists a new result; reuse of an existing result is governed by
        complete-result integrity instead.
        """

        current_selection = self._selections.get_current(snapshot.intake_id)
        if current_selection is None or (
            current_selection.raw_transcript_id != snapshot.raw_transcript.identity
        ):
            raise CompositionStaleAuthorityError(
                "the intake's current raw transcript selection changed during composition: "
                "the whole request is refused (no automatic rebase or retarget)"
            )
        text_decision = self._text_decisions.get_current(snapshot.text_candidate.identity)
        if (
            text_decision is None
            or text_decision.kind is not DecisionKind.ACCEPT
            or text_decision.identity != snapshot.text_decision.identity
        ):
            raise CompositionStaleAuthorityError(
                "the text candidate's current Human Authority changed during composition: the whole "
                "request is refused (no silent re-binding to a different authorizing decision)"
            )
        timing_decision = self._timing_decisions.get_current(snapshot.timing_candidate.identity)
        if (
            timing_decision is None
            or timing_decision.kind is not DecisionKind.ACCEPT
            or timing_decision.identity != snapshot.timing_decision.identity
        ):
            raise CompositionStaleAuthorityError(
                "the timing candidate's current Human Authority changed during composition: the whole "
                "request is refused (no silent re-binding to a different authorizing decision)"
            )
        source = self._segments.get(snapshot.source_segment.identity)
        if (
            source is None
            or source.text != snapshot.text_admission.source_text_snapshot
            or source.start is None
            or source.end is None
            or not same_instant(
                snapshot.timing_candidate.source_start_snapshot, float(source.start)
            )
            or not same_instant(snapshot.timing_candidate.source_end_snapshot, float(source.end))
        ):
            raise CompositionStaleAuthorityError(
                "the source segment changed during composition: the whole request is refused"
            )

    # -- structural validity -----------------------------------------------------------------------

    @staticmethod
    def _require_composed_validity(replacement: TranscriptSegment) -> None:
        if not replacement.text or not replacement.text.strip():
            raise CompositionCombinedValidityError("the composed replacement carries empty text")
        start, end = float(replacement.start), float(replacement.end)
        if start < 0 or end <= start and not same_instant(end, start):
            raise CompositionCombinedValidityError(
                "the composed replacement carries a non-positive duration"
            )

    # -- complete-result integrity (TX-28/TX-29; shared by the lookup and collision paths) ----------

    def _resolve_existing(
        self, stored: SameSourceCompositionGeneration, expected: "_ExpectedResult"
    ) -> SameSourceCompositionResult:
        if stored.content_fingerprint != expected.generation.content_fingerprint:
            raise CompositionRevisionConflictError(
                "a corrected revision already exists for this composition anchor with different "
                "content (LectureOS does not overwrite an immutable revision)"
            )
        revision = self._compositions.revision(stored.corrected_revision_id)
        if revision is None:
            raise SameSourceCompositionError(
                "existing composition references a missing corrected revision"
            )
        self._require_complete_result_integrity(stored, revision, expected)
        return SameSourceCompositionResult(
            generation=stored, revision=revision, outcome=GenerationOutcome.REUSED
        )

    def _require_complete_result_integrity(
        self,
        stored: SameSourceCompositionGeneration,
        revision: CorrectedTranscriptRevision,
        expected: "_ExpectedResult",
    ) -> None:
        def refuse(detail: str) -> None:
            raise CompositionIntegrityError(
                "a stored composition under this anchor fails complete-result integrity "
                f"({detail}); a matching content fingerprint does not substitute for provenance, "
                "so the whole generation is refused rather than reused, overwritten, or repaired"
            )

        wanted = expected.generation
        # 1. Anchor and base.
        if stored.identity != wanted.identity:
            refuse("stored anchor identity differs")
        if stored.parent_raw_transcript_id != wanted.parent_raw_transcript_id:
            refuse("stored base raw transcript differs")
        if stored.corrected_revision_id != revision.identity:
            refuse("stored composition does not own the revision it references")
        # 2. Complete two-role authority provenance — nothing missing, swapped, or re-bound.
        if stored.text_correction_candidate_id != wanted.text_correction_candidate_id:
            refuse("the stored text role is bound to a different candidate")
        if stored.text_authorizing_decision_id != wanted.text_authorizing_decision_id:
            refuse("the stored text role is bound to a different authorizing decision")
        if stored.timing_correction_candidate_id != wanted.timing_correction_candidate_id:
            refuse("the stored timing role is bound to a different candidate")
        if stored.timing_authorizing_decision_id != wanted.timing_authorizing_decision_id:
            refuse("the stored timing role is bound to a different authorizing decision")
        # 3. Source-to-composed-replacement mapping and the replacement's complete payload.
        if stored.replaced_segment_id != wanted.replaced_segment_id:
            refuse("the stored composition replaces a different source segment")
        if stored.replacement_segment_id != wanted.replacement_segment_id:
            refuse("the stored composition carries a different replacement segment")
        persisted = self._segments.get(stored.replacement_segment_id)
        if persisted is None:
            refuse("the stored composed replacement segment is missing")
        if not _same_replacement(persisted, expected.replacement):
            refuse("the stored composed replacement's canonical payload or lineage differs")
        # 4. Complete revision ordered membership.
        if tuple(revision.segment_ids) != tuple(expected.segment_ids):
            refuse("the stored revision's ordered segment membership differs")
        if revision.parent_raw_transcript_id != wanted.parent_raw_transcript_id:
            refuse("the stored revision's parent raw transcript differs")
        if tuple(revision.correction_candidate_ids) != (wanted.text_correction_candidate_id,):
            refuse("the stored revision's text candidate reference differs")


__all__ = [
    "SAME_SOURCE_COMPOSITION_GENERATION_IDENTITY_PREFIX",
    "TEXT_ROLE",
    "TIMING_ROLE",
    "AtomicSameSourceCompositionPersistence",
    "CompositionCandidateNotAcceptedError",
    "CompositionCombinedValidityError",
    "CompositionIntegrityError",
    "CompositionNotApplicableError",
    "CompositionRevisionConflictError",
    "CompositionRoleError",
    "CompositionStaleAuthorityError",
    "SameSourceCompositionError",
    "SameSourceCompositionGeneration",
    "SameSourceCompositionGenerationService",
    "SameSourceCompositionQuery",
    "SameSourceCompositionResult",
    "derive_composition_digest",
]
