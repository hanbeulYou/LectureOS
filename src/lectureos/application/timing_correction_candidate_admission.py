"""Human Timing Correction Candidate admission (040 §17 sibling subsection, PATCH-0047).

Records a **human-authored proposal to replace one source segment's presentation timing**, without
applying it. It is the sibling of the released text Correction Candidate (§17 K-1…K-14), not an
extension of it: `correction_candidates.proposed_text` is `TEXT NOT NULL` and K-2 rejects a no-op, so
a timing proposal carrying the source text unchanged would be refused by released admission, and
serialising an interval into `proposed_text` is the meaning distortion K-2 exists to prevent (TC-2).
Nothing in the released text-correction family changes here.

Admission checks **structure, never acoustic truth** (TC-6). It verifies what it can know without
media: the target segment exists, belongs to the intake's current Raw Transcript, and is timed; the
proposed values are finite with ``start >= 0`` and ``end > start``; the proposal does not overlap its
neighbours (TC-7); it is not a no-op (TC-8); and the carried source-timing snapshot still matches the
persisted segment (TC-9). It never decides whether the proposed interval matches actual speech —
that judgement belongs to the person and becomes canonical at §18. No drift, anchor-gap or
readability threshold participates, no diagnostic is consulted, and no media is read.

Same-instant comparisons reuse the released `PATCH-0039` ``TIMING_BOUNDARY_TOLERANCE_SECONDS``; no
new tolerance is introduced. Identity is deterministic from the anchor
``(intake, raw_transcript, segment, author, candidate_ref)`` — the released K-5 idiom with `author`
in the place of `(source_type, source_reference)`, because TC-4 admits **only** human-authored
proposals and the record therefore has no machine-source vocabulary to express. Distinct proposals
for one segment are distinct ``candidate_ref`` values and therefore distinct identities (K-8, TC-15);
re-admitting one anchor with a different payload is a conflict, never an overwrite (K-7).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.review.identities import HumanActorReference
from lectureos.transcript.identities import TranscriptId, TranscriptSegmentId

from .correction_candidate_admission import (
    CorrectionCandidateAdmissionError,
    require_canonical_segment_id,
)
from .current_raw_transcript_selection import require_canonical_raw_transcript_id
from .identities import TimingCorrectionCandidateId, TranscriptSourceIntakeId
from .provider_transcript_admission import (
    TIMING_BOUNDARY_TOLERANCE_SECONDS,
    ProviderTranscriptAdmissionError,
    require_canonical_intake_id,
)

TIMING_CORRECTION_CANDIDATE_IDENTITY_PREFIX = "timing-correction-candidate"


class TimingCorrectionCandidateError(ValueError):
    """A timing proposal that cannot be admitted (malformed, not ready, unrelated, stale, or a no-op)."""


class TimingIntakeNotReadyError(TimingCorrectionCandidateError):
    """The intake has no valid current Raw Transcript selection, so no candidate may be admitted."""


class TimingRawTranscriptNotCurrentError(TimingCorrectionCandidateError):
    """The target Raw Transcript is not the intake's current selection."""


class TimingSegmentLineageError(TimingCorrectionCandidateError):
    """The target segment is unknown, unrelated to the target Raw Transcript, or carries no timing."""


class TimingSourceSnapshotMismatchError(TimingCorrectionCandidateError):
    """The supplied source-timing snapshot does not match the persisted segment (stale target)."""


class TimingProposalNoOpError(TimingCorrectionCandidateError):
    """The proposed interval is the source interval — it proposes nothing (TC-8, mirroring K-2)."""


class TimingProposalOverlapError(TimingCorrectionCandidateError):
    """The proposed interval overlaps an adjacent segment of the target transcript (TC-7)."""


class TimingCorrectionCandidateConflictError(TimingCorrectionCandidateError):
    """The same candidate anchor was re-admitted with a different payload (no silent overwrite)."""


def same_instant(left: float, right: float) -> bool:
    """Whether two timeline values denote the same instant, under the released `PATCH-0039` ε (T-2)."""

    return abs(left - right) <= TIMING_BOUNDARY_TOLERANCE_SECONDS


@dataclass(frozen=True, slots=True)
class TimingCorrectionCandidateInput:
    """A validated human-authored timing proposal: a complete replacement interval, never a start alone."""

    raw_transcript_id: str
    segment_id: str
    candidate_ref: str
    author: str
    source_start_snapshot: float
    source_end_snapshot: float
    proposed_start: float
    proposed_end: float
    rationale: str

    def __post_init__(self) -> None:
        for label, value in (
            ("candidate_ref", self.candidate_ref),
            ("author", self.author),
            ("rationale", self.rationale),
        ):
            if not isinstance(value, str) or not value.strip():
                raise TimingCorrectionCandidateError(f"{label} must be a non-empty string")
        for label, value in (
            ("source_start_snapshot", self.source_start_snapshot),
            ("source_end_snapshot", self.source_end_snapshot),
            ("proposed_start", self.proposed_start),
            ("proposed_end", self.proposed_end),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TimingCorrectionCandidateError(f"{label} must be a number")
            if not isfinite(float(value)):
                raise TimingCorrectionCandidateError(f"{label} must be finite")
        # A-10's structural vocabulary, applied to the proposal (TC-6).
        if self.proposed_start < 0:
            raise TimingCorrectionCandidateError("proposed start must not be negative")
        if self.proposed_end <= self.proposed_start:
            raise TimingCorrectionCandidateError(
                "proposed end must be after proposed start (a complete replacement interval is required)"
            )
        if self.source_start_snapshot < 0 or self.source_end_snapshot < self.source_start_snapshot:
            raise TimingCorrectionCandidateError("source timing snapshot is not a valid interval")


def build_timing_correction_candidate_input(
    payload: Mapping[str, object],
) -> TimingCorrectionCandidateInput:
    """Build a validated :class:`TimingCorrectionCandidateInput` from a decoded JSON mapping (strict fields)."""

    if not isinstance(payload, Mapping):
        raise TimingCorrectionCandidateError("timing correction candidate must be a JSON object")
    allowed = {
        "raw_transcript_id", "segment_id", "candidate_ref", "author",
        "source_start_snapshot", "source_end_snapshot",
        "proposed_start", "proposed_end", "rationale",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise TimingCorrectionCandidateError(
            f"timing correction candidate has unknown field(s): {', '.join(sorted(unknown))}"
        )
    for field in sorted(allowed):
        if field not in payload:
            raise TimingCorrectionCandidateError(
                f"timing correction candidate requires '{field}'"
            )
    return TimingCorrectionCandidateInput(
        raw_transcript_id=_require_str(payload["raw_transcript_id"], "raw_transcript_id"),
        segment_id=_require_str(payload["segment_id"], "segment_id"),
        candidate_ref=_require_str(payload["candidate_ref"], "candidate_ref"),
        author=_require_str(payload["author"], "author"),
        source_start_snapshot=_require_number(
            payload["source_start_snapshot"], "source_start_snapshot"
        ),
        source_end_snapshot=_require_number(
            payload["source_end_snapshot"], "source_end_snapshot"
        ),
        proposed_start=_require_number(payload["proposed_start"], "proposed_start"),
        proposed_end=_require_number(payload["proposed_end"], "proposed_end"),
        rationale=_require_str(payload["rationale"], "rationale"),
    )


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise TimingCorrectionCandidateError(f"{label} must be a string")
    return value


def _require_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TimingCorrectionCandidateError(f"{label} must be a number")
    return float(value)


@dataclass(frozen=True, slots=True)
class TimingCorrectionCandidate:
    """Durable, immutable human-authored proposal to replace one segment's presentation interval."""

    identity: TimingCorrectionCandidateId
    transcript_source_intake_id: TranscriptSourceIntakeId
    raw_transcript_id: TranscriptId
    segment_id: TranscriptSegmentId
    author: HumanActorReference
    candidate_ref: str
    source_start_snapshot: float
    source_end_snapshot: float
    proposed_start: float
    proposed_end: float
    rationale: str
    content_fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.author, HumanActorReference):
            raise ValueError("timing correction candidate author must be a Human actor reference")
        if not self.candidate_ref.strip() or not self.rationale.strip():
            raise ValueError("candidate reference and rationale must not be empty")
        if self.proposed_end <= self.proposed_start:
            raise ValueError("proposed end must be after proposed start")
        if len(self.content_fingerprint) != 64:
            raise ValueError("candidate content fingerprint must be a 64-hex SHA-256 digest")


@dataclass(frozen=True, slots=True)
class TimingCorrectionCandidateResult:
    """The outcome of one admission: the candidate record and whether it was newly created."""

    candidate: TimingCorrectionCandidate
    created: bool


@dataclass(frozen=True, slots=True)
class TimingCorrectionCandidateView:
    """A read-only view of an admitted timing candidate, with applicability to the current selection."""

    candidate: TimingCorrectionCandidate
    applicable_to_current_selection: bool


class TranscriptSourceIntakeQuery(Protocol):
    def get(self, identity): ...


class RawTranscriptSelectionQuery(Protocol):
    def get_current(self, intake_id): ...


class TranscriptSegmentQuery(Protocol):
    def get(self, identity): ...


class RawTranscriptQuery(Protocol):
    def get(self, identity): ...


class TimingCorrectionCandidateQuery(Protocol):
    def get(self, identity): ...

    def candidates_for_intake(self, intake_id, current_raw_transcript_id) -> tuple: ...


class AtomicTimingCorrectionCandidatePersistence(Protocol):
    def persist_timing_correction_candidate(
        self, *, candidate: TimingCorrectionCandidate
    ) -> None: ...


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_timing_candidate_digest(
    intake_id: TranscriptSourceIntakeId,
    raw_transcript_id: TranscriptId,
    segment_id: TranscriptSegmentId,
    author: HumanActorReference,
    candidate_ref: str,
) -> str:
    """The SHA-256 digest of the candidate anchor — the released K-5 idiom, author-anchored (TC-4)."""

    return _sha256(
        _canonical_json(
            {
                "intake": intake_id.value,
                "raw_transcript": raw_transcript_id.value,
                "segment": segment_id.value,
                "author": author.value,
                "candidate_ref": candidate_ref,
            }
        )
    )


class TimingCorrectionCandidateAdmissionService:
    """Admits a human-authored replacement interval for one current Raw Transcript segment."""

    def __init__(
        self,
        intake_query: TranscriptSourceIntakeQuery,
        selection_query: RawTranscriptSelectionQuery,
        segment_query: TranscriptSegmentQuery,
        raw_transcript_query: RawTranscriptQuery,
        candidate_query: TimingCorrectionCandidateQuery,
        persistence: AtomicTimingCorrectionCandidatePersistence | None = None,
    ) -> None:
        self._intakes = intake_query
        self._selections = selection_query
        self._segments = segment_query
        self._raw_transcripts = raw_transcript_query
        self._candidates = candidate_query
        self._persistence = persistence

    def _resolve_intake(self, intake_id: str) -> TranscriptSourceIntakeId:
        try:
            identity = require_canonical_intake_id(intake_id)
        except ProviderTranscriptAdmissionError as error:
            raise TimingCorrectionCandidateError(str(error)) from error
        if self._intakes.get(identity) is None:
            raise TimingCorrectionCandidateError(
                "unknown transcript source intake: admit the Source Media as an intake first"
            )
        return identity

    def admit(
        self, *, intake_id: str, candidate: TimingCorrectionCandidateInput
    ) -> TimingCorrectionCandidateResult:
        intake_identity = self._resolve_intake(intake_id)

        # Readiness and lineage — K-1's rules, unchanged (TC-6).
        current = self._selections.get_current(intake_identity)
        if current is None:
            raise TimingIntakeNotReadyError(
                "intake is not ready: select a current Raw Transcript before admitting candidates"
            )
        try:
            transcript_identity = require_canonical_raw_transcript_id(candidate.raw_transcript_id)
        except Exception as error:  # malformed identity — reported in this family's vocabulary
            raise TimingCorrectionCandidateError(str(error)) from error
        if transcript_identity != current.raw_transcript_id:
            raise TimingRawTranscriptNotCurrentError(
                "target raw transcript is not the intake's current selection"
            )
        try:
            segment_identity = require_canonical_segment_id(candidate.segment_id)
        except CorrectionCandidateAdmissionError as error:
            raise TimingCorrectionCandidateError(str(error)) from error

        segment = self._segments.get(segment_identity)
        if segment is None:
            raise TimingSegmentLineageError("unknown transcript segment")
        if segment.transcript_id != transcript_identity:
            raise TimingSegmentLineageError(
                "segment does not belong to the target raw transcript"
            )
        if segment.start is None or segment.end is None:
            raise TimingSegmentLineageError(
                "segment carries no timing: there is no presentation interval to correct"
            )
        if segment.source_timeline_id is None:
            # A timed segment always carries one; a proposal must be expressed on that same timeline.
            raise TimingSegmentLineageError(
                "segment has no source timeline: the proposed interval has no timeline to lie on"
            )

        # Stale protection — K-3's purpose, on the interval instead of the text (TC-9).
        if not (
            same_instant(candidate.source_start_snapshot, float(segment.start))
            and same_instant(candidate.source_end_snapshot, float(segment.end))
        ):
            raise TimingSourceSnapshotMismatchError(
                "source timing snapshot does not match the current segment timing (stale target)"
            )

        # A proposal identical to the source proposes nothing (TC-8, mirroring K-2).
        if same_instant(candidate.proposed_start, float(segment.start)) and same_instant(
            candidate.proposed_end, float(segment.end)
        ):
            raise TimingProposalNoOpError(
                "proposed interval equals the source interval (a no-op candidate is not admissible)"
            )

        raw_transcript = self._raw_transcripts.get(transcript_identity)
        if raw_transcript is None:  # defensive: the current selection guarantees this exists
            raise TimingRawTranscriptNotCurrentError(
                "current raw transcript could not be resolved"
            )
        self._require_no_neighbour_overlap(raw_transcript, segment, candidate)

        digest = derive_timing_candidate_digest(
            intake_identity,
            transcript_identity,
            segment_identity,
            HumanActorReference(candidate.author),
            candidate.candidate_ref,
        )
        content_fingerprint = _sha256(
            _canonical_json(
                {
                    "anchor": digest,
                    "source_start_snapshot": candidate.source_start_snapshot,
                    "source_end_snapshot": candidate.source_end_snapshot,
                    "proposed_start": candidate.proposed_start,
                    "proposed_end": candidate.proposed_end,
                    "rationale": candidate.rationale,
                }
            )
        )
        identity = TimingCorrectionCandidateId(
            f"{TIMING_CORRECTION_CANDIDATE_IDENTITY_PREFIX}:{digest}"
        )
        existing = self._candidates.get(identity)
        if existing is not None:
            if existing.content_fingerprint != content_fingerprint:
                raise TimingCorrectionCandidateConflictError(
                    "a different timing correction candidate was already admitted for this candidate "
                    "reference (LectureOS does not overwrite an admitted candidate)"
                )
            return TimingCorrectionCandidateResult(candidate=existing, created=False)

        record = TimingCorrectionCandidate(
            identity=identity,
            transcript_source_intake_id=intake_identity,
            raw_transcript_id=transcript_identity,
            segment_id=segment_identity,
            author=HumanActorReference(candidate.author),
            candidate_ref=candidate.candidate_ref,
            source_start_snapshot=candidate.source_start_snapshot,
            source_end_snapshot=candidate.source_end_snapshot,
            proposed_start=candidate.proposed_start,
            proposed_end=candidate.proposed_end,
            rationale=candidate.rationale,
            content_fingerprint=content_fingerprint,
        )
        if self._persistence is None:
            raise RuntimeError("timing correction candidate persistence is not configured")
        try:
            self._persistence.persist_timing_correction_candidate(candidate=record)
        except PersistenceIdentityCollisionError:
            resolved = self._candidates.get(identity)
            if resolved is not None and resolved.content_fingerprint == content_fingerprint:
                return TimingCorrectionCandidateResult(candidate=resolved, created=False)
            raise
        return TimingCorrectionCandidateResult(candidate=record, created=True)

    def _require_no_neighbour_overlap(
        self, raw_transcript, segment, candidate: TimingCorrectionCandidateInput
    ) -> None:
        """TC-7: the proposal must not overlap its neighbours, judged as instants under the released ε.

        Touching boundaries stay allowed, so this uses the same-instant predicate rather than a new
        tolerance, and it compares only against the segments immediately adjacent in the target
        transcript's order. It is contracted here rather than left to Final Selection because
        `READABILITY_CUES_OVERLAP` is BLOCKING and `PATCH-0042` enforces it at delivery — refusing at
        the point where the person can still adjust the proposal is the earlier honest boundary.
        """

        segment_ids = tuple(raw_transcript.segment_ids)
        try:
            position = segment_ids.index(segment.identity)
        except ValueError:
            raise TimingSegmentLineageError(
                "segment is not part of the target raw transcript's ordered membership"
            ) from None

        if position > 0:
            previous = self._segments.get(segment_ids[position - 1])
            if previous is not None and previous.end is not None:
                if candidate.proposed_start < float(previous.end) and not same_instant(
                    candidate.proposed_start, float(previous.end)
                ):
                    raise TimingProposalOverlapError(
                        "proposed interval starts before the previous segment ends "
                        "(an overlapping correction cannot be delivered as a subtitle)"
                    )
        if position + 1 < len(segment_ids):
            following = self._segments.get(segment_ids[position + 1])
            if following is not None and following.start is not None:
                if candidate.proposed_end > float(following.start) and not same_instant(
                    candidate.proposed_end, float(following.start)
                ):
                    raise TimingProposalOverlapError(
                        "proposed interval ends after the next segment starts "
                        "(an overlapping correction cannot be delivered as a subtitle)"
                    )

    def candidates(self, intake_id: str) -> tuple[TimingCorrectionCandidateView, ...]:
        intake_identity = self._resolve_intake(intake_id)
        current = self._selections.get_current(intake_identity)
        current_raw = current.raw_transcript_id if current is not None else None
        return self._candidates.candidates_for_intake(intake_identity, current_raw)


__all__ = [
    "TIMING_CORRECTION_CANDIDATE_IDENTITY_PREFIX",
    "AtomicTimingCorrectionCandidatePersistence",
    "TimingCorrectionCandidate",
    "TimingCorrectionCandidateAdmissionService",
    "TimingCorrectionCandidateConflictError",
    "TimingCorrectionCandidateError",
    "TimingCorrectionCandidateInput",
    "TimingCorrectionCandidateQuery",
    "TimingCorrectionCandidateResult",
    "TimingCorrectionCandidateView",
    "TimingIntakeNotReadyError",
    "TimingProposalNoOpError",
    "TimingProposalOverlapError",
    "TimingRawTranscriptNotCurrentError",
    "TimingSegmentLineageError",
    "TimingSourceSnapshotMismatchError",
    "build_timing_correction_candidate_input",
    "derive_timing_candidate_digest",
    "same_instant",
]
