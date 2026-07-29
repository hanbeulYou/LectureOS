"""Lecture Segmentation Foundation — effective-transcript generation (042 §7.2, GOAL-026).

The effective-transcript generation's canonical Lecture Segment contract, implementing the
Architect Decisions confirmed by `patches/PATCH-0031` (S-1…S-13). One explicit command admits an
**ordered batch** of provider-independent segment payloads against exactly one immutable Lecture
Analysis Input Admission (GOAL-023) and appends one **immutable, identity-owning,
provenance-bearing** canonical record per segment, atomically.

**No segmentation happens here.** This boundary performs no segmentation and does not invoke AI,
implement a provider, define prompts or models, or create a Segment Label, Analysis Finding, Edit
Candidate, or Review Item. The payload is supplied by the caller and recorded verbatim as canonical
Application-owned meaning.

**Anchor and independence (S-2, S-3).** Every Segment anchors to exactly one
`LectureAnalysisInputAdmission`, never to the legacy `EligibleAnalysisInput` and — as `§7.1`
states outright — **never to an Analysis Finding**. Segmentation and Analysis Finding are siblings:
neither requires the other, and a Segment may be admitted against an Admission that has no Finding
at all. Upstream provenance (intake, source media, corrected revision, parent raw transcript, both
selections, the `040 §19` fingerprint) is obtained *through* the anchor and never duplicated here.

**Current-only standing (S-4).** A stored admission's mere existence never suffices: every command
re-derives the anchor's authority standing and admits only at `current`. A missing or malformed
admission reference is refused before standing is evaluated — never a fourth standing value.

**Historical semantics (S-5, S-6).** Existing Segments are never mutated or deleted when upstream
authority changes; a Segment legitimately anchored to a then-current admission stays valid
immutable history. No `current`/`stale`/`active`/`ready`/`superseded` state is stored; present
applicability is derived externally from the anchor's standing.

**Ordered batch (S-9).** One command admits one or more Segments; the batch position *is* the
`sequence`, so sequences are contiguous from 0 by construction and can never collide within a
command. The batch is recorded atomically — a partially recorded segmentation may never appear
valid. No aggregate, collection, or view entity is introduced: the identity-owning canonical object
is the individual Segment.

**No canonical-set constraint (S-8).** `§7.1` forbids canonical-set/uniqueness constraints, so one
Admission may carry several independent batches. Two batches legitimately share a `sequence` value
whenever their ranges differ, which is why no uniqueness constraint over (admission, sequence)
exists anywhere in this contract.

**Execution-free deterministic provenance (S-7).** No `ProcessingRun`, `ProcessingUnit`,
`UnitExecution`, RUNNING state, or `DomainResult` chaining is created or required, and none is
fabricated. Following the GOAL-023/GOAL-025 marker-free precedent, generation provenance is the
contract kind (cryptographically bound into the identity), the recorded contract version, and the
immutable admitted source (the anchor).

**Identity and replay (S-10, S-11).** Identity is Application-owned and derives from the exact
anchor plus the stable segmentation semantics — contract kind/version, admission identity, sequence,
and the canonical range. Every persisted canonical field participates, so a divergent payload for an
existing identity is structurally unreachable through this command (see `admit_segmentation`); the
semantic-equality check is retained regardless, as an integrity guard. No wall-clock, randomness,
path, or rowid participates.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Protocol, Sequence

from lectureos.persistence.errors import PersistenceIdentityCollisionError

from .canonical_timeline_value import canonical_timeline_value

from .identities import LectureAnalysisInputAdmissionId, LectureAnalysisSegmentId
from .lecture_analysis_input_admission import (
    AdmissionAuthorityMatch,
    LectureAnalysisInputAdmission,
    LectureAnalysisInputAdmissionError,
    LectureAnalysisInputAdmissionService,
    require_canonical_admission_id,
)

LECTURE_ANALYSIS_SEGMENT_IDENTITY_PREFIX = "lecture-analysis-segment"

SEGMENT_CONTRACT_KIND = "lecture_analysis_segment"
SEGMENT_CONTRACT_VERSION = 1


class LectureAnalysisSegmentError(ValueError):
    """A segmentation command that cannot proceed (malformed, unknown, or unsupported input)."""


class SegmentationAnchorNotAdmissibleError(LectureAnalysisSegmentError):
    """The anchoring admission does not currently bind the current effective authority."""


class SegmentationConflictError(LectureAnalysisSegmentError):
    """An existing segment with this identity records a divergent payload."""


class SegmentationOutcome(str, Enum):
    RECORDED = "recorded"  # at least one new canonical segment record was created
    REUSED = "reused"      # every segment of the batch already existed; no new row


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_bound(name: str, value: float) -> float:
    """Validate one range bound and return it in its canonical ``float`` form.

    Delegates to the shared effective-generation primitive so this contract cannot drift from the
    sibling ones: the int/float and negative-zero collapses are load-bearing for identity (see
    `canonical_timeline_value`), not cosmetic.
    """

    return canonical_timeline_value(
        value, error=LectureAnalysisSegmentError, subject=f"lecture segment {name}"
    )


def normalize_range(start: float, end: float) -> tuple[float, float]:
    """The released §7.1 Minimum Boundary, reused verbatim: exactly one required range, finite,
    non-negative, ``start <= end``.

    A zero-duration range is structurally valid and a whole-recording range is merely a valid range.
    No media-duration, transcript-boundary, coverage, gap, or overlap validation is applied: `§7.2`
    S-8 forbids introducing any of them at this Foundation, and the anchor records no timeline
    extent to check against.
    """

    canonical_start = canonical_bound("range start", start)
    canonical_end = canonical_bound("range end", end)
    if canonical_start > canonical_end:
        raise LectureAnalysisSegmentError(
            "lecture segment range start must not be after end"
        )
    return canonical_start, canonical_end


def derive_segment_identity(
    admission_id: LectureAnalysisInputAdmissionId,
    sequence: int,
    range_start: float,
    range_end: float,
) -> LectureAnalysisSegmentId:
    """Deterministic, Application-owned segment identity (042 §7.2 S-10).

    Derives from the exact immutable anchor plus the stable segmentation semantics only: the
    contract kind and version, the admission, the batch ordinal, and the canonical range. No
    timestamp, randomness, rowid, path, provider identifier, or mutable currentness participates.
    """

    canonical_start, canonical_end = normalize_range(range_start, range_end)
    digest = hashlib.sha256(
        _canonical_json(
            {
                "contract": SEGMENT_CONTRACT_KIND,
                "contract_version": SEGMENT_CONTRACT_VERSION,
                "admission": admission_id.value,
                "sequence": sequence,
                "range_start": canonical_start,
                "range_end": canonical_end,
            }
        ).encode("utf-8")
    ).hexdigest()
    return LectureAnalysisSegmentId(
        f"{LECTURE_ANALYSIS_SEGMENT_IDENTITY_PREFIX}:{digest}"
    )


def require_canonical_segment_id(value: str) -> LectureAnalysisSegmentId:
    prefix = LECTURE_ANALYSIS_SEGMENT_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise LectureAnalysisSegmentError(
            "lecture analysis segment identity is malformed "
            "(expected 'lecture-analysis-segment:<64 hex digest>')"
        )
    return LectureAnalysisSegmentId(value)


def _require_anchor_identity(value: str) -> LectureAnalysisInputAdmissionId:
    """Validate the anchor reference, reporting it as a *segmentation* refusal.

    The released admission-identity rule is reused verbatim, but its error is re-raised in this
    boundary's own type: a malformed anchor is a refusal of the reference supplied to this command
    (042 §7.2 S-4), never a fourth admission standing value.
    """

    try:
        return require_canonical_admission_id(value)
    except LectureAnalysisInputAdmissionError as error:
        raise LectureAnalysisSegmentError(str(error)) from error


@dataclass(frozen=True, slots=True)
class LectureAnalysisSegment:
    """Immutable canonical Lecture Segment anchored to one Lecture Analysis Input Admission.

    Carries no currentness, lifecycle, review, or supersession state (042 §7.2 S-5), no Segment
    Label (deferred by §7.1), and no duplicated upstream provenance (S-2) — the anchor supplies it.
    """

    identity: LectureAnalysisSegmentId
    admission_id: LectureAnalysisInputAdmissionId
    sequence: int
    range_start: float
    range_end: float
    segment_contract_version: int = SEGMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.segment_contract_version != SEGMENT_CONTRACT_VERSION:
            raise LectureAnalysisSegmentError(
                "unsupported lecture analysis segment contract version"
            )
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool):
            raise LectureAnalysisSegmentError("lecture segment sequence must be an integer")
        if self.sequence < 0:
            raise LectureAnalysisSegmentError("lecture segment sequence must not be negative")
        start, end = normalize_range(self.range_start, self.range_end)
        object.__setattr__(self, "range_start", start)
        object.__setattr__(self, "range_end", end)
        if self.identity != derive_segment_identity(
            self.admission_id, self.sequence, start, end
        ):
            raise LectureAnalysisSegmentError(
                "lecture segment identity must derive from its anchoring admission, sequence, "
                "and canonical range"
            )


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    """One segmentation command outcome: the ordered canonical batch and the anchor observed."""

    segments: tuple[LectureAnalysisSegment, ...]
    outcome: SegmentationOutcome
    admission: LectureAnalysisInputAdmission
    recorded_count: int
    reused_count: int


class SegmentQuery(Protocol):
    def get(self, identity): ...

    def list_for_admission(self, admission_id) -> tuple: ...


class AtomicSegmentPersistence(Protocol):
    def persist_segments(
        self, *, segments: Sequence[LectureAnalysisSegment]
    ) -> None: ...


class LectureAnalysisSegmentationService:
    """The single canonical Lecture Segmentation admission path of the effective generation."""

    def __init__(
        self,
        admission_service: LectureAnalysisInputAdmissionService,
        segment_query: SegmentQuery,
        persistence: AtomicSegmentPersistence,
    ) -> None:
        self._admissions = admission_service
        self._segments = segment_query
        self._persistence = persistence

    # -- explicit segmentation admission command -----------------------------------------------

    def admit_segmentation(
        self, *, admission_id: str, ranges: Iterable[tuple[float, float]]
    ) -> SegmentationResult:
        """Admit one ordered batch of segments against a CURRENT analysis input admission.

        Order (042 §7.2): validate the batch, resolve the canonical anchor, re-derive its standing,
        derive identities, verify every pre-existing row for semantic equality *before* writing
        anything, then persist the missing ones atomically.
        """

        canonical_ranges = self._canonical_batch(ranges)
        admission = self._require_current_admission(admission_id)

        segments = tuple(
            LectureAnalysisSegment(
                identity=derive_segment_identity(
                    admission.identity, sequence, start, end
                ),
                admission_id=admission.identity,
                sequence=sequence,
                range_start=start,
                range_end=end,
            )
            for sequence, (start, end) in enumerate(canonical_ranges)
        )

        # Verify every pre-existing member first: a divergent one must fail the whole command
        # before any new row is written (S-9 atomicity).
        pending: list[LectureAnalysisSegment] = []
        resolved: list[LectureAnalysisSegment] = []
        for segment in segments:
            existing = self._segments.get(segment.identity)
            if existing is None:
                pending.append(segment)
                resolved.append(segment)
            else:
                resolved.append(self._verify_same(existing, segment))

        if not pending:
            return SegmentationResult(
                segments=tuple(resolved),
                outcome=SegmentationOutcome.REUSED,
                admission=admission,
                recorded_count=0,
                reused_count=len(resolved),
            )

        try:
            self._persistence.persist_segments(segments=tuple(pending))
        except PersistenceIdentityCollisionError as error:
            # A near-concurrent command won the insert. If it recorded every pending member, this
            # command converges on the stored rows (S-11). If it recorded only some — a partially
            # overlapping racing batch — nothing of this command was written (the transaction
            # rolled back), and the caller must retry; S-11 only mandates convergence for
            # identical admissions, so this is reported honestly rather than silently retried.
            for segment in pending:
                stored = self._segments.get(segment.identity)
                if stored is None:
                    raise LectureAnalysisSegmentError(
                        "a concurrent segmentation admission recorded part of this batch; "
                        "nothing of this command was written — retry it"
                    ) from error
                self._verify_same(stored, segment)
            return SegmentationResult(
                segments=tuple(resolved),
                outcome=SegmentationOutcome.REUSED,
                admission=admission,
                recorded_count=0,
                reused_count=len(resolved),
            )

        return SegmentationResult(
            segments=tuple(resolved),
            outcome=SegmentationOutcome.RECORDED,
            admission=admission,
            recorded_count=len(pending),
            reused_count=len(resolved) - len(pending),
        )

    @staticmethod
    def _canonical_batch(
        ranges: Iterable[tuple[float, float]]
    ) -> tuple[tuple[float, float], ...]:
        """Canonicalize the ordered batch. The batch position *is* the sequence (S-9), so
        sequences are contiguous from 0 and can never collide within one command."""

        canonical: list[tuple[float, float]] = []
        for entry in ranges:
            if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                raise LectureAnalysisSegmentError(
                    "each lecture segment payload must be exactly one (start, end) range"
                )
            canonical.append(normalize_range(entry[0], entry[1]))
        if not canonical:
            raise LectureAnalysisSegmentError(
                "a segmentation admission requires at least one lecture segment"
            )
        return tuple(canonical)

    def _require_current_admission(
        self, admission_id: str
    ) -> LectureAnalysisInputAdmission:
        """Resolve the anchor and re-derive its standing at command time (042 §7.2 S-4)."""

        identity = _require_anchor_identity(admission_id)
        admission = self._admissions.get(identity.value)
        if admission is None:
            raise LectureAnalysisSegmentError("unknown lecture analysis input admission")
        match = self._admissions.authority_match(admission)
        if match is not AdmissionAuthorityMatch.CURRENT:
            raise SegmentationAnchorNotAdmissibleError(
                "lecture segments may only be admitted against an admission that still binds "
                f"the current effective authority (derived standing: {match.value}); the "
                "admission and its existing segments remain valid immutable history"
            )
        return admission

    @staticmethod
    def _verify_same(
        existing: LectureAnalysisSegment, expected: LectureAnalysisSegment
    ) -> LectureAnalysisSegment:
        """Integrity guard on an existing row with the same identity (S-11).

        Every persisted canonical field participates in identity, so a legitimate divergence is
        structurally unreachable through this command — this is the Option B reading recorded in
        the implementation document. The check is kept anyway: it is the only thing standing
        between a corrupted or hand-edited row and silent acceptance, and removing it because the
        happy path cannot reach it would trade an integrity guarantee for nothing.
        """

        if (
            existing.admission_id != expected.admission_id
            or existing.sequence != expected.sequence
            or existing.range_start != expected.range_start
            or existing.range_end != expected.range_end
            or existing.segment_contract_version != expected.segment_contract_version
        ):
            raise SegmentationConflictError(
                "an existing lecture segment with this identity records a different payload "
                "(repository integrity failure); it is never overwritten"
            )
        return existing

    # -- queries (derived; never mutate history) -----------------------------------------------

    def get(self, segment_id: str) -> LectureAnalysisSegment | None:
        return self._segments.get(require_canonical_segment_id(segment_id))

    def list_for_admission(self, admission_id: str) -> tuple[LectureAnalysisSegment, ...]:
        return self._segments.list_for_admission(_require_anchor_identity(admission_id))

    def anchor_status(
        self, segment: LectureAnalysisSegment
    ) -> AdmissionAuthorityMatch:
        """Derived only: does this segment's anchor still bind the current authority?

        A segment whose anchor became superseded is NOT stale data and NOT corruption — it is valid
        immutable history (042 §7.2 S-6). Nothing is mutated by this observation, and no such state
        is ever stored on the segment (S-5).
        """

        admission = self._admissions.get(segment.admission_id.value)
        if admission is None:
            raise LectureAnalysisSegmentError(
                "lecture segment anchor is missing (repository integrity failure)"
            )
        return self._admissions.authority_match(admission)


__all__ = [
    "LECTURE_ANALYSIS_SEGMENT_IDENTITY_PREFIX",
    "SEGMENT_CONTRACT_KIND",
    "SEGMENT_CONTRACT_VERSION",
    "AtomicSegmentPersistence",
    "LectureAnalysisSegment",
    "LectureAnalysisSegmentError",
    "LectureAnalysisSegmentationService",
    "SegmentQuery",
    "SegmentationAnchorNotAdmissibleError",
    "SegmentationConflictError",
    "SegmentationOutcome",
    "SegmentationResult",
    "canonical_bound",
    "derive_segment_identity",
    "normalize_range",
    "require_canonical_segment_id",
]
