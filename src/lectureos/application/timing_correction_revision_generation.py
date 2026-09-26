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

**Composition is not performed here** (TC-18). A text correction and a timing correction on the same
segment produce two independent sibling revisions and `§20` selection chooses one. Nothing merges
them, applies them in an implementation-chosen order, or re-targets a candidate; resolving what the
product should do with competing corrections is Deferred to its own decision.

**Cardinality (`PATCH-0049`, MG-1).** One generation contract serves both cardinalities: the caller
enumerates an explicit, non-empty set of timing candidates over **one** Raw Transcript, at most one
per source segment, and the set is applied into **one** immutable revision. A set of one keeps the
released single-candidate identity encoding and the released singleton relation exactly (MG-21); two
or more members derive their identity from the base plus the canonical member authority set (MG-22)
and are persisted through the additive aggregate relations. Membership is fixed at request intake;
canonical order is the base transcript's source segment ordinal, so identity never depends on input
order, wall clock, or database return order (MG-16/MG-17).
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


class TimingCorrectionSetError(TimingCorrectionGenerationError):
    """The explicit candidate set is malformed (empty, repeated, or spanning different bases)."""


class TimingCorrectionCompetingCandidatesError(TimingCorrectionSetError):
    """Two named candidates target one source segment — never both applied, never merged (MG-14)."""


class TimingCorrectionCombinedValidityError(TimingCorrectionGenerationError):
    """The complete snapshot is structurally invalid once every replacement is applied (MG-18).

    Individual `§17` TC-7 admission judges a proposal against the **original** neighbours, so two
    individually admissible corrections can conflict together. The whole request is refused; nothing
    is clamped, trimmed, averaged, or re-estimated, because that would change Human-approved values.
    """


class TimingCorrectionRevisionIntegrityError(TimingCorrectionGenerationError):
    """A stored result under this anchor fails complete-result integrity (MG-25/MG-29/MG-31).

    Distinct from `TimingCorrectionRevisionConflictError`, which is the released content-identity
    conflict. This one fires when content matches but the anchor, member authority provenance,
    source-to-replacement mapping, or the revision's ordered membership does not — a matching
    content fingerprint never substitutes for those conditions.
    """


class TimingCorrectionStaleAuthorityError(TimingCandidateNotApplicableError):
    """The authority snapshot moved between verification and persist (MG-13) — the whole request fails."""


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
class TimingCorrectionGenerationMember:
    """One member's complete authority provenance and source-to-replacement mapping (MG-19/MG-29)."""

    member_ordinal: int
    timing_correction_candidate_id: TimingCorrectionCandidateId
    authorizing_decision_id: object  # TimingCorrectionCandidateDecisionId (avoids an import cycle)
    replaced_segment_id: TranscriptSegmentId
    replacement_segment_id: TranscriptSegmentId

    def __post_init__(self) -> None:
        if self.member_ordinal < 0:
            raise ValueError("member ordinal must not be negative")
        if self.replaced_segment_id == self.replacement_segment_id:
            raise ValueError("replacement segment must differ from the replaced segment")


@dataclass(frozen=True, slots=True)
class TimingCorrectionRevisionAggregateGeneration:
    """Immutable binding for two or more members applied into one revision (`PATCH-0049`).

    The generation is the single owner of *which* corrections were applied: one generation holds the
    complete, canonically ordered member provenance. The revision's ordered segment membership is a
    different relationship and is never read as member provenance.
    """

    identity: TimingCorrectionRevisionGenerationId
    corrected_revision_id: TranscriptRevisionId
    parent_raw_transcript_id: object  # TranscriptId
    members: tuple[TimingCorrectionGenerationMember, ...]
    content_fingerprint: str

    def __post_init__(self) -> None:
        if len(self.content_fingerprint) != 64:
            raise ValueError("generation content fingerprint must be a 64-hex SHA-256 digest")
        if len(self.members) < 2:
            raise ValueError(
                "an aggregate generation carries two or more members "
                "(a single member keeps the released singleton relation)"
            )
        if tuple(member.member_ordinal for member in self.members) != tuple(
            range(len(self.members))
        ):
            raise ValueError("member ordinals must be a dense canonical sequence starting at 0")
        for field in ("timing_correction_candidate_id", "replaced_segment_id", "replacement_segment_id"):
            values = [getattr(member, field) for member in self.members]
            if len(set(values)) != len(values):
                raise ValueError(f"an aggregate generation must not repeat a member {field}")


@dataclass(frozen=True, slots=True)
class TimingCorrectionGenerationView:
    """One generation read uniformly, whatever its physical representation (§4.3 projection).

    A released singleton row is **derived** as a one-member generation — never back-filled into the
    member relation — so legacy records and aggregate records answer the same questions (MG-21).
    """

    identity: TimingCorrectionRevisionGenerationId
    corrected_revision_id: TranscriptRevisionId
    parent_raw_transcript_id: object  # TranscriptId
    members: tuple[TimingCorrectionGenerationMember, ...]
    content_fingerprint: str
    is_legacy_singleton: bool

    @property
    def candidate_ids(self) -> tuple[TimingCorrectionCandidateId, ...]:
        return tuple(member.timing_correction_candidate_id for member in self.members)


def view_of_singleton(
    generation: TimingCorrectionRevisionGeneration,
) -> TimingCorrectionGenerationView:
    """Derive the one-member view of a released singleton generation (no row is written)."""

    return TimingCorrectionGenerationView(
        identity=generation.identity,
        corrected_revision_id=generation.corrected_revision_id,
        parent_raw_transcript_id=generation.parent_raw_transcript_id,
        members=(
            TimingCorrectionGenerationMember(
                member_ordinal=0,
                timing_correction_candidate_id=generation.timing_correction_candidate_id,
                authorizing_decision_id=generation.authorizing_decision_id,
                replaced_segment_id=generation.replaced_segment_id,
                replacement_segment_id=generation.replacement_segment_id,
            ),
        ),
        content_fingerprint=generation.content_fingerprint,
        is_legacy_singleton=True,
    )


def view_of_aggregate(
    generation: TimingCorrectionRevisionAggregateGeneration,
) -> TimingCorrectionGenerationView:
    return TimingCorrectionGenerationView(
        identity=generation.identity,
        corrected_revision_id=generation.corrected_revision_id,
        parent_raw_transcript_id=generation.parent_raw_transcript_id,
        members=generation.members,
        content_fingerprint=generation.content_fingerprint,
        is_legacy_singleton=False,
    )


@dataclass(frozen=True, slots=True)
class TimingCorrectionRevisionGenerationResult:
    """The outcome of one explicit generation request."""

    generation: TimingCorrectionRevisionGeneration
    revision: CorrectedTranscriptRevision
    outcome: str  # GenerationOutcome.CREATED / REUSED


@dataclass(frozen=True, slots=True)
class TimingCorrectionSetGenerationResult:
    """The outcome of one explicit set generation request, at either cardinality."""

    view: TimingCorrectionGenerationView
    revision: CorrectedTranscriptRevision
    outcome: str  # GenerationOutcome.CREATED / REUSED
    singleton: TimingCorrectionRevisionGeneration | None = None
    aggregate: TimingCorrectionRevisionAggregateGeneration | None = None


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

    def generations_for_candidate(
        self, candidate_id
    ) -> "tuple[TimingCorrectionGenerationView, ...]": ...

    def view(self, identity) -> "TimingCorrectionGenerationView | None": ...


class AtomicTimingCorrectionGenerationPersistence(Protocol):
    def persist_timing_correction_generation(
        self,
        *,
        generation: TimingCorrectionRevisionGeneration,
        revision: CorrectedTranscriptRevision,
        replacement_segment: TranscriptSegment,
        result: DomainResultReference,
        revalidate=None,
    ) -> None: ...

    def persist_timing_correction_aggregate_generation(
        self,
        *,
        generation: TimingCorrectionRevisionAggregateGeneration,
        revision: CorrectedTranscriptRevision,
        replacement_segments: tuple[TranscriptSegment, ...],
        result: DomainResultReference,
        revalidate=None,
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


def derive_timing_aggregate_generation_digest(
    base_raw_transcript_id, members: tuple[tuple[object, object], ...]
) -> str:
    """The SHA-256 digest of an aggregate anchor: the base plus the canonical member authority set (MG-22).

    ``members`` is the canonically ordered sequence of ``(candidate identity, authorizing Decision
    identity)`` pairs. Canonical order is the base transcript's source segment ordinal, so the digest
    is independent of input order; every member contributes **both** its candidate and its specific
    authorizing Decision, so adding, removing, or re-authorizing a member is a different anchor.
    """

    return _sha256(
        _canonical_json(
            {
                "base": base_raw_transcript_id.value,
                "members": [
                    {"candidate": candidate.value, "authorizing_decision": decision.value}
                    for candidate, decision in members
                ],
            }
        )
    )


@dataclass(slots=True)
class _MemberEntry:
    """One named member with everything the snapshot resolved for it (mutable during resolution only)."""

    candidate: object
    decision: object
    source_segment: TranscriptSegment | None = None
    source_ordinal: int = -1
    member_digest: str = ""


@dataclass(frozen=True, slots=True)
class _AuthoritySnapshot:
    """The one consistent authority/applicability state the whole request is anchored to (MG-12)."""

    intake_id: object
    raw_transcript: object
    entries: tuple[_MemberEntry, ...]


@dataclass(frozen=True, slots=True)
class _ExpectedResult:
    """What this request would produce — the yardstick for complete-result integrity (MG-29)."""

    identity: TimingCorrectionRevisionGenerationId
    parent_raw_transcript_id: object
    members: tuple[TimingCorrectionGenerationMember, ...]
    fingerprint: str
    segment_ids: tuple[TranscriptSegmentId, ...]
    replacements: dict


def _same_replacement(persisted: TranscriptSegment, expected: TranscriptSegment) -> bool:
    """Complete canonical payload and source lineage equality — never a fingerprint shortcut (MG-25)."""

    return (
        persisted.identity == expected.identity
        and persisted.transcript_id == expected.transcript_id
        and persisted.source_timeline_id == expected.source_timeline_id
        and persisted.text == expected.text
        and persisted.source_order == expected.source_order
        and persisted.speaker_label == expected.speaker_label
        and persisted.replaces_segment_id == expected.replaces_segment_id
        and persisted.start is not None
        and persisted.end is not None
        and same_instant(float(persisted.start), float(expected.start))
        and same_instant(float(persisted.end), float(expected.end))
    )


def _require_combined_validity(segments: tuple[TranscriptSegment | None, ...]) -> None:
    """Revalidate the COMPLETE resulting snapshot against the released structural constraints (MG-18).

    Reuses `§14` A-10's vocabulary — ordering, positive duration, non-overlap — and the released
    `PATCH-0039` ε for same-instant comparison. No new tolerance or threshold is introduced, and
    touching boundaries the released contract allows stay allowed.
    """

    previous: TranscriptSegment | None = None
    for segment in segments:
        if segment is None:
            raise TimingCorrectionGenerationError(
                "the resulting snapshot references a segment that could not be resolved"
            )
        if segment.start is None or segment.end is None:
            continue
        start, end = float(segment.start), float(segment.end)
        if end <= start and not same_instant(end, start):
            raise TimingCorrectionCombinedValidityError(
                f"segment {segment.identity.value} has a non-positive duration once applied"
            )
        if previous is not None:
            previous_start, previous_end = float(previous.start), float(previous.end)
            if start < previous_start and not same_instant(start, previous_start):
                raise TimingCorrectionCombinedValidityError(
                    "the corrections applied together break the transcript's presentation order "
                    f"({previous.identity.value} starts after {segment.identity.value})"
                )
            if start < previous_end and not same_instant(start, previous_end):
                raise TimingCorrectionCombinedValidityError(
                    "the corrections are individually admissible but overlap once applied together "
                    f"({previous.identity.value} ends after {segment.identity.value} starts); "
                    "the whole request is refused and no timing is clamped or re-estimated"
                )
        previous = segment


class TimingCorrectionRevisionGenerationService:
    """Explicitly applies a named set of currently Accepted timing candidates into one revision."""

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
        """Apply one named candidate — the released call, now a singleton of the one contract (MG-21)."""

        result = self.generate_set(candidate_ids=(candidate_id,))
        if result.singleton is None:
            raise TimingCorrectionGenerationError(
                "a one-member generation must be represented by the released singleton relation"
            )
        return TimingCorrectionRevisionGenerationResult(
            generation=result.singleton, revision=result.revision, outcome=result.outcome
        )

    def generate_set(
        self, *, candidate_ids: "tuple[str, ...] | list[str]"
    ) -> TimingCorrectionSetGenerationResult:
        # 1. The caller enumerates the members; nothing is discovered, deduplicated, or inherited.
        members_in = self._require_explicit_set(candidate_ids)

        # 2+3. One consistent authority/applicability snapshot over every named member.
        snapshot = self._snapshot(members_in)

        # 4. Canonical order is the base transcript's source segment ordinal (MG-16) — never input order.
        ordered = tuple(
            sorted(snapshot.entries, key=lambda entry: entry.source_ordinal)
        )

        # 5. Deterministic application: each source text exactly, each accepted interval, nothing else.
        replacements = tuple(
            TranscriptSegment(
                identity=TranscriptSegmentId(f"{_SEGMENT_PREFIX}:{entry.member_digest}:0"),
                transcript_id=snapshot.raw_transcript.identity,
                source_timeline_id=entry.source_segment.source_timeline_id,
                text=entry.source_segment.text,
                source_order=entry.source_segment.source_order,
                start=entry.candidate.proposed_start,
                end=entry.candidate.proposed_end,
                speaker_label=entry.source_segment.speaker_label,
                replaces_segment_id=entry.source_segment.identity,
            )
            for entry in ordered
        )
        by_source = {
            entry.source_segment.identity: replacement
            for entry, replacement in zip(ordered, replacements)
        }
        corrected_segment_ids = tuple(
            by_source[segment_id].identity if segment_id in by_source else segment_id
            for segment_id in snapshot.raw_transcript.segment_ids
        )
        by_identity = {replacement.identity: replacement for replacement in replacements}
        resulting_segments = tuple(
            by_identity.get(segment_id) or self._segments.get(segment_id)
            for segment_id in corrected_segment_ids
        )

        # 6. Combined structural validation of the COMPLETE snapshot (MG-18) — TC-7 judged originals.
        _require_combined_validity(resulting_segments)
        fingerprint = content_fingerprint_for(resulting_segments)

        # 7. Identity: a singleton keeps the released encoding; two or more derive from the base plus
        #    the canonical member authority set.
        if len(ordered) == 1:
            digest = ordered[0].member_digest
        else:
            digest = derive_timing_aggregate_generation_digest(
                snapshot.raw_transcript.identity,
                tuple(
                    (entry.candidate.identity, entry.decision.identity) for entry in ordered
                ),
            )
        generation_identity = TimingCorrectionRevisionGenerationId(
            f"{TIMING_CORRECTION_GENERATION_IDENTITY_PREFIX}:{digest}"
        )
        revision_identity = TranscriptRevisionId(
            f"{CORRECTED_REVISION_IDENTITY_PREFIX}:{digest}"
        )
        members = tuple(
            TimingCorrectionGenerationMember(
                member_ordinal=ordinal,
                timing_correction_candidate_id=entry.candidate.identity,
                authorizing_decision_id=entry.decision.identity,
                replaced_segment_id=entry.source_segment.identity,
                replacement_segment_id=replacement.identity,
            )
            for ordinal, (entry, replacement) in enumerate(zip(ordered, replacements))
        )

        revision = CorrectedTranscriptRevision(
            identity=revision_identity,
            transcript_id=snapshot.raw_transcript.identity,
            domain_result_id=DomainResultId(f"{_DOMAIN_RESULT_PREFIX}:{digest}"),
            run_id=ProcessingRunId(f"{_APPLICATION_RUN_PREFIX}:{digest}"),
            unit_execution_id=UnitExecutionId(f"{_APPLICATION_EXECUTION_PREFIX}:{digest}"),
            segment_ids=corrected_segment_ids,
            parent_raw_transcript_id=snapshot.raw_transcript.identity,
            # No text CorrectionCandidate participates; the timing lineage is carried by the sibling
            # generation relation. The released field keeps its meaning and is simply empty here.
            correction_candidate_ids=(),
        )
        expected = _ExpectedResult(
            identity=generation_identity,
            parent_raw_transcript_id=snapshot.raw_transcript.identity,
            members=members,
            fingerprint=fingerprint,
            segment_ids=corrected_segment_ids,
            replacements=by_identity,
        )

        # 8. An existing result under this anchor is reused only under complete-result integrity.
        stored = self._generations.view(generation_identity)
        if stored is not None:
            return self._resolve_existing(stored, expected)

        result = DomainResultReference(
            identity=revision.domain_result_id,
            kind=CORRECTED_REVISION_RESULT_KIND,
            source_media=snapshot.raw_transcript.source_media_id,
            source_timeline=snapshot.raw_transcript.source_timeline_id,
            upstream_results=(snapshot.raw_transcript.domain_result_id,),
        )
        if self._persistence is None:
            raise RuntimeError("timing correction generation persistence is not configured")

        # 9. The snapshot must still hold at persist time; the check runs INSIDE the write transaction
        #    so guard ordering alone is never mistaken for TOCTOU protection (MG-13).
        def revalidate() -> None:
            self._require_snapshot_unchanged(snapshot)

        singleton = aggregate = None
        try:
            if len(members) == 1:
                singleton = TimingCorrectionRevisionGeneration(
                    identity=generation_identity,
                    corrected_revision_id=revision_identity,
                    timing_correction_candidate_id=members[0].timing_correction_candidate_id,
                    authorizing_decision_id=members[0].authorizing_decision_id,
                    parent_raw_transcript_id=snapshot.raw_transcript.identity,
                    replaced_segment_id=members[0].replaced_segment_id,
                    replacement_segment_id=members[0].replacement_segment_id,
                    content_fingerprint=fingerprint,
                )
                self._persistence.persist_timing_correction_generation(
                    generation=singleton,
                    revision=revision,
                    replacement_segment=replacements[0],
                    result=result,
                    revalidate=revalidate,
                )
                view = view_of_singleton(singleton)
            else:
                aggregate = TimingCorrectionRevisionAggregateGeneration(
                    identity=generation_identity,
                    corrected_revision_id=revision_identity,
                    parent_raw_transcript_id=snapshot.raw_transcript.identity,
                    members=members,
                    content_fingerprint=fingerprint,
                )
                self._persistence.persist_timing_correction_aggregate_generation(
                    generation=aggregate,
                    revision=revision,
                    replacement_segments=replacements,
                    result=result,
                    revalidate=revalidate,
                )
                view = view_of_aggregate(aggregate)
        except PersistenceIdentityCollisionError:
            # A near-concurrent identical request won the race. Converge only under the SAME
            # complete-result integrity standard the pre-persist lookup applies (MG-31).
            resolved = self._generations.view(generation_identity)
            if resolved is not None:
                return self._resolve_existing(resolved, expected)
            raise
        return TimingCorrectionSetGenerationResult(
            view=view,
            revision=revision,
            outcome=GenerationOutcome.CREATED,
            singleton=singleton,
            aggregate=aggregate,
        )

    # -- explicit set, authority snapshot, staleness -------------------------------------------------

    def _require_explicit_set(
        self, candidate_ids
    ) -> tuple[TimingCorrectionCandidateId, ...]:
        if isinstance(candidate_ids, (str, bytes)) or not isinstance(
            candidate_ids, (tuple, list)
        ):
            raise TimingCorrectionSetError(
                "an explicit timing candidate set must be a sequence of candidate identities"
            )
        if not candidate_ids:
            raise TimingCorrectionSetError(
                "an explicit timing candidate set must name at least one candidate"
            )
        identities: list[TimingCorrectionCandidateId] = []
        seen: set[str] = set()
        for value in candidate_ids:
            try:
                identity = require_canonical_timing_candidate_id(value)
            except TimingCorrectionDecisionError as error:
                raise TimingCorrectionGenerationError(str(error)) from error
            if identity.value in seen:
                # No silent deduplication — a repeated identity is a malformed request (MG-7).
                raise TimingCorrectionSetError(
                    "an explicit timing candidate set must not repeat a candidate identity"
                )
            seen.add(identity.value)
            identities.append(identity)
        return tuple(identities)

    def _snapshot(
        self, identities: tuple[TimingCorrectionCandidateId, ...]
    ) -> "_AuthoritySnapshot":
        entries: list[_MemberEntry] = []
        intake_id = raw_transcript_id = None
        for identity in identities:
            candidate = self._candidates.get(identity)
            if candidate is None:
                raise TimingCorrectionGenerationError(
                    "unknown timing correction candidate: admit the candidate before generating a revision"
                )
            # Current Human Authority must be Accepted (historical acceptance is insufficient), and it
            # is derived through the released §18 path — no input names a past Decision (MG-12).
            decision = self._decisions.get_current(identity)
            if decision is None:
                raise TimingCandidateNotAcceptedError(
                    "candidate is undecided: an explicit human Accept is required before generation"
                )
            if decision.kind is not DecisionKind.ACCEPT:
                raise TimingCandidateNotAcceptedError(
                    "candidate is currently rejected: only a currently accepted candidate can be applied"
                )
            if intake_id is None:
                intake_id = candidate.transcript_source_intake_id
                raw_transcript_id = candidate.raw_transcript_id
            elif (
                candidate.transcript_source_intake_id != intake_id
                or candidate.raw_transcript_id != raw_transcript_id
            ):
                raise TimingCorrectionSetError(
                    "an explicit timing candidate set must share one raw transcript and one intake "
                    "(a set spanning different bases or timelines is refused)"
                )
            entries.append(_MemberEntry(candidate=candidate, decision=decision))

        current_selection = self._selections.get_current(intake_id)
        if current_selection is None or (
            current_selection.raw_transcript_id != raw_transcript_id
        ):
            raise TimingCandidateNotApplicableError(
                "candidate is not applicable: its raw transcript is no longer the intake's current selection"
            )
        raw_transcript = self._raw_transcripts.get(raw_transcript_id)
        if raw_transcript is None:
            raise TimingCandidateNotApplicableError(
                "candidate is not applicable: its source raw transcript could not be resolved"
            )
        ordinals = {
            segment_id: ordinal
            for ordinal, segment_id in enumerate(raw_transcript.segment_ids)
        }
        by_source: dict[object, TimingCorrectionCandidateId] = {}
        for entry in entries:
            candidate = entry.candidate
            if candidate.segment_id not in ordinals:
                raise TimingCandidateNotApplicableError(
                    "candidate is not applicable: its target segment is not part of the source transcript"
                )
            if candidate.segment_id in by_source:
                # Two named candidates on one source segment: never both applied, never merged, and
                # naming one never rejects the other (MG-3/MG-14/MG-15).
                raise TimingCorrectionCompetingCandidatesError(
                    "an explicit timing candidate set must name at most one candidate per source "
                    "segment (competing corrections are distinct authority facts and are not merged)"
                )
            by_source[candidate.segment_id] = candidate.identity
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
            entry.source_segment = source_segment
            entry.source_ordinal = ordinals[candidate.segment_id]
            entry.member_digest = derive_timing_generation_digest(
                candidate.identity, entry.decision.identity
            )
        return _AuthoritySnapshot(
            intake_id=intake_id,
            raw_transcript=raw_transcript,
            entries=tuple(entries),
        )

    def _require_snapshot_unchanged(self, snapshot: "_AuthoritySnapshot") -> None:
        """Re-derive the snapshot facts; any movement fails the whole generation (MG-13)."""

        current_selection = self._selections.get_current(snapshot.intake_id)
        if current_selection is None or (
            current_selection.raw_transcript_id != snapshot.raw_transcript.identity
        ):
            raise TimingCorrectionStaleAuthorityError(
                "the intake's current raw transcript selection changed during generation: "
                "the whole request is refused (no automatic rebase or retarget)"
            )
        for entry in snapshot.entries:
            decision = self._decisions.get_current(entry.candidate.identity)
            if (
                decision is None
                or decision.kind is not DecisionKind.ACCEPT
                or decision.identity != entry.decision.identity
            ):
                raise TimingCorrectionStaleAuthorityError(
                    "a member's current Human Authority changed during generation: the whole request "
                    "is refused (no silent re-binding to a different authorizing decision)"
                )
            source_segment = self._segments.get(entry.candidate.segment_id)
            if (
                source_segment is None
                or source_segment.start is None
                or source_segment.end is None
                or not same_instant(
                    entry.candidate.source_start_snapshot, float(source_segment.start)
                )
                or not same_instant(
                    entry.candidate.source_end_snapshot, float(source_segment.end)
                )
            ):
                raise TimingCorrectionStaleAuthorityError(
                    "a member's source segment timing changed during generation: the whole request is refused"
                )

    # -- complete-result integrity (MG-29; shared by the lookup and collision paths, MG-31) ----------

    def _resolve_existing(
        self, stored: TimingCorrectionGenerationView, expected: "_ExpectedResult"
    ) -> TimingCorrectionSetGenerationResult:
        # Condition 5 first, preserving the released V-10 content-identity conflict verbatim.
        if stored.content_fingerprint != expected.fingerprint:
            raise TimingCorrectionRevisionConflictError(
                "a corrected revision already exists for this candidate and authorizing decision "
                "with different content (LectureOS does not overwrite an immutable revision)"
            )
        revision = self._generations.revision(stored.corrected_revision_id)
        if revision is None:
            raise TimingCorrectionGenerationError(
                "existing generation references a missing corrected revision"
            )
        self._require_complete_result_integrity(stored, revision, expected)
        return TimingCorrectionSetGenerationResult(
            view=stored,
            revision=revision,
            outcome=GenerationOutcome.REUSED,
            # The stored record itself — never re-derived content, so a reused result reports the
            # identities that were actually persisted.
            singleton=(
                self._generations.get(stored.identity)
                if stored.is_legacy_singleton
                else None
            ),
            aggregate=(
                None
                if stored.is_legacy_singleton
                else TimingCorrectionRevisionAggregateGeneration(
                    identity=stored.identity,
                    corrected_revision_id=stored.corrected_revision_id,
                    parent_raw_transcript_id=stored.parent_raw_transcript_id,
                    members=stored.members,
                    content_fingerprint=stored.content_fingerprint,
                )
            ),
        )

    def _require_complete_result_integrity(
        self,
        stored: TimingCorrectionGenerationView,
        revision: CorrectedTranscriptRevision,
        expected: "_ExpectedResult",
    ) -> None:
        def refuse(detail: str) -> None:
            raise TimingCorrectionRevisionIntegrityError(
                "a stored generation under this anchor fails complete-result integrity "
                f"({detail}); a matching content fingerprint does not substitute for provenance, "
                "so the whole generation is refused rather than reused, overwritten, or repaired"
            )

        # 1. Generation anchor and base relationship.
        if stored.identity != expected.identity:
            refuse("stored anchor identity differs")
        if stored.parent_raw_transcript_id != expected.parent_raw_transcript_id:
            refuse("stored base raw transcript differs")
        if stored.corrected_revision_id != revision.identity:
            refuse("stored generation does not own the revision it references")

        # 2. Complete member authority provenance, in canonical order.
        if len(stored.members) != len(expected.members):
            refuse("stored member count differs")
        for stored_member, expected_member in zip(stored.members, expected.members):
            if stored_member.member_ordinal != expected_member.member_ordinal:
                refuse("stored canonical member order differs")
            if (
                stored_member.timing_correction_candidate_id
                != expected_member.timing_correction_candidate_id
            ):
                refuse("a stored member is bound to a different candidate")
            if stored_member.authorizing_decision_id != expected_member.authorizing_decision_id:
                refuse("a stored member is bound to a different authorizing decision")
            # 3. Source-to-replacement mapping, per member.
            if stored_member.replaced_segment_id != expected_member.replaced_segment_id:
                refuse("a stored member replaces a different source segment")
            if (
                stored_member.replacement_segment_id
                != expected_member.replacement_segment_id
            ):
                refuse("a stored member carries a different replacement segment")
            persisted = self._segments.get(stored_member.replacement_segment_id)
            if persisted is None:
                refuse("a stored member's replacement segment is missing")
            if not _same_replacement(
                persisted, expected.replacements[expected_member.replacement_segment_id]
            ):
                refuse("a stored replacement segment's canonical payload or lineage differs")

        # 4. Complete revision ordered membership.
        if tuple(revision.segment_ids) != tuple(expected.segment_ids):
            refuse("the stored revision's ordered segment membership differs")
        if revision.parent_raw_transcript_id != expected.parent_raw_transcript_id:
            refuse("the stored revision's parent raw transcript differs")

    def generations_for_candidate(
        self, candidate_id: str
    ) -> "tuple[TimingCorrectionGenerationView, ...]":
        """This candidate's complete generation history: its singleton **and** every aggregate it is
        a member of.

        A malformed identity is rejected as before; a well-formed identity with no history — whether
        the candidate exists or not — returns an empty tuple, exactly as the released query did. This
        is a pure read: it records no generation, member, Decision, or selection, and it applies no
        current-authority guard, because reading what was generated is not generating.
        """

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
    "TimingCorrectionCombinedValidityError",
    "TimingCorrectionCompetingCandidatesError",
    "TimingCorrectionGenerationError",
    "TimingCorrectionGenerationMember",
    "TimingCorrectionGenerationQuery",
    "TimingCorrectionGenerationView",
    "TimingCorrectionRevisionAggregateGeneration",
    "TimingCorrectionRevisionConflictError",
    "TimingCorrectionRevisionGeneration",
    "TimingCorrectionRevisionGenerationResult",
    "TimingCorrectionRevisionGenerationService",
    "TimingCorrectionRevisionIntegrityError",
    "TimingCorrectionSetError",
    "TimingCorrectionSetGenerationResult",
    "TimingCorrectionStaleAuthorityError",
    "derive_timing_aggregate_generation_digest",
    "derive_timing_generation_digest",
    "view_of_aggregate",
    "view_of_singleton",
]
