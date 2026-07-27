"""Effective-Source Subtitle Review Preparation (041 §15 E13 downstream stage, GOAL-014).

The first downstream stage of the effective-transcript subtitle contract generation: an explicit
request prepares one exact immutable `EffectiveSubtitleCandidate` graph as an immutable **Review
Subject** — the historical fact "this exact candidate graph was presented for review". Preparation
is preparation only: it grants no authority, creates no Human Decision, reviewer, annotation,
approval/rejection/completion state, final selection, or export eligibility, and it never touches
the legacy review pipeline (no ReviewItem, no CandidateReference, no legacy tables).

The subject binds the exact candidate graph: the candidate identity (a truthful FK into the
effective-source representation) plus a deterministic **graph fingerprint** over the candidate's
immutable provenance and its ordered cue set (identity, ordinal, text, timing, source-segment
lineage) — an integrity anchor, never authority, and never a replacement for the candidate
identity. Structural integrity is verified at preparation time; a structurally valid but
source-stale candidate MAY be prepared explicitly (historical inspectability ≠ current decision
applicability) and its staleness is derived, never stored. Identical replay reuses the one
canonical subject per (candidate, preparation contract); near-concurrent identical requests
converge on the uniqueness anchor; a payload disagreement for one identity is an explicit
conflict. No wall-clock, randomness, mutable status, or workflow state participates.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError

from .effective_subtitle_generation import (
    EffectiveSubtitleCandidate,
    EffectiveSubtitleCue,
    EffectiveSubtitleGenerationService,
    require_canonical_candidate_id,
)
from .effective_transcript_consumption import ConsumptionCurrentness
from .identities import EffectiveSubtitleCandidateId, EffectiveSubtitleReviewSubjectId

EFFECTIVE_REVIEW_SUBJECT_IDENTITY_PREFIX = "subtitle-effective-review-subject"

PREPARATION_KIND = "effective_subtitle_review_preparation"
PREPARATION_VERSION = 1


class EffectiveSubtitleReviewPreparationError(ValueError):
    """A preparation request that cannot proceed (malformed, unknown, or unsupported input)."""


class CandidateGraphIntegrityError(EffectiveSubtitleReviewPreparationError):
    """The candidate graph is structurally broken — preparation is refused and nothing persists."""


class ReviewSubjectConflictError(EffectiveSubtitleReviewPreparationError):
    """The deterministic preparation identity maps to a structurally different persisted subject."""


class PreparationOutcome(str, Enum):
    CREATED = "created"   # a new review subject row was persisted
    REUSED = "reused"     # the identical canonical subject already existed; no new row


class ReviewSubjectCurrentness(str, Enum):
    """Derived comparison of a subject's bound candidate against current authority — never stored."""

    CURRENT = "current"
    STALE_DUE_TO_CANDIDATE_SOURCE = "stale_due_to_candidate_source"
    UNRESOLVABLE = "unresolvable"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_candidate_graph_fingerprint(
    candidate: EffectiveSubtitleCandidate, cues: tuple[EffectiveSubtitleCue, ...]
) -> str:
    """Deterministic integrity anchor over the exact immutable candidate graph (never authority).

    Covers the candidate's provenance and the complete ordered cue set (identity, ordinal, text,
    timing, source-segment lineage). Excludes currentness, timestamps, and storage order.
    """

    return _sha256(
        _canonical_json(
            {
                "candidate": {
                    "identity": candidate.identity.value,
                    "intake": candidate.transcript_source_intake_id.value,
                    "consumption_binding": candidate.consumption_binding_id.value,
                    "source_kind": candidate.source_kind.value,
                    "source": candidate.source_transcript_identity,
                    "parent_raw_transcript": candidate.parent_raw_transcript_id.value,
                    "snapshot_fingerprint": candidate.source_snapshot_fingerprint,
                    "generator_kind": candidate.generator_kind,
                    "generator_version": candidate.generator_version,
                    "generation_parameters_version": candidate.generation_parameters_version,
                    "cue_count": candidate.cue_count,
                },
                "cues": [
                    {
                        "identity": cue.identity.value,
                        "ordinal": cue.ordinal,
                        "text": cue.text,
                        "start": cue.start,
                        "end": cue.end,
                        "source_segments": [s.value for s in cue.source_segment_ids],
                    }
                    for cue in cues
                ],
            }
        )
    )


def derive_preparation_key(candidate_id: EffectiveSubtitleCandidateId) -> str:
    """The human-readable deterministic replay anchor: one subject per (candidate, contract)."""

    return f"{PREPARATION_KIND}:v{PREPARATION_VERSION}:{candidate_id.value}"


def derive_review_subject_identity(
    candidate_id: EffectiveSubtitleCandidateId, candidate_graph_fingerprint: str
) -> EffectiveSubtitleReviewSubjectId:
    """Deterministic subject identity from the preparation contract, exact candidate, and graph anchor."""

    digest = _sha256(
        _canonical_json(
            {
                "preparation_kind": PREPARATION_KIND,
                "preparation_version": PREPARATION_VERSION,
                "candidate": candidate_id.value,
                "candidate_graph_fingerprint": candidate_graph_fingerprint,
            }
        )
    )
    return EffectiveSubtitleReviewSubjectId(
        f"{EFFECTIVE_REVIEW_SUBJECT_IDENTITY_PREFIX}:{digest}"
    )


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleReviewSubject:
    """Immutable historical fact: one exact candidate graph was prepared for review.

    Not a Human Decision, not a workflow container, not authority — its existence implies no
    review completion, approval, rejection, applicability, selection, or export eligibility.
    """

    identity: EffectiveSubtitleReviewSubjectId
    candidate_id: EffectiveSubtitleCandidateId
    candidate_graph_fingerprint: str
    preparation_kind: str
    preparation_version: int
    preparation_key: str

    def __post_init__(self) -> None:
        if self.preparation_kind != PREPARATION_KIND:
            raise ValueError("unsupported review preparation kind")
        if self.preparation_version != PREPARATION_VERSION:
            raise ValueError("unsupported review preparation version")
        if len(self.candidate_graph_fingerprint) != 64:
            raise ValueError(
                "review subject graph fingerprint must be a 64-hex SHA-256 digest"
            )
        if self.preparation_key != derive_preparation_key(self.candidate_id):
            raise ValueError(
                "review subject preparation key must derive from its contract and candidate"
            )
        expected = derive_review_subject_identity(
            self.candidate_id, self.candidate_graph_fingerprint
        )
        if self.identity != expected:
            raise ValueError(
                "review subject identity must derive from its preparation contract, "
                "candidate, and graph fingerprint"
            )


@dataclass(frozen=True, slots=True)
class ReviewSubjectStatus:
    """Derived, never stored: the subject's candidate-source and subject currentness."""

    candidate_source_currentness: ConsumptionCurrentness
    review_subject_currentness: ReviewSubjectCurrentness


@dataclass(frozen=True, slots=True)
class ReviewPreparationResult:
    """One preparation command outcome: the immutable subject plus derived currentness."""

    subject: EffectiveSubtitleReviewSubject
    candidate: EffectiveSubtitleCandidate
    outcome: PreparationOutcome
    status: ReviewSubjectStatus


class ReviewSubjectQuery(Protocol):
    def get(self, identity): ...

    def get_for_candidate(self, candidate_id): ...


class AtomicReviewSubjectPersistence(Protocol):
    def persist_review_subject(self, *, subject: EffectiveSubtitleReviewSubject) -> None: ...


def _subject_currentness(source: ConsumptionCurrentness) -> ReviewSubjectCurrentness:
    if source is ConsumptionCurrentness.CURRENT:
        return ReviewSubjectCurrentness.CURRENT
    if source is ConsumptionCurrentness.UNRESOLVABLE:
        return ReviewSubjectCurrentness.UNRESOLVABLE
    return ReviewSubjectCurrentness.STALE_DUE_TO_CANDIDATE_SOURCE


class EffectiveSubtitleReviewPreparationService:
    """The single canonical effective-source review preparation path (GOAL-014)."""

    def __init__(
        self,
        generation_service: EffectiveSubtitleGenerationService,
        subject_query: ReviewSubjectQuery,
        persistence: AtomicReviewSubjectPersistence | None = None,
    ) -> None:
        self._candidates = generation_service
        self._subjects = subject_query
        self._persistence = persistence

    # -- preparation ---------------------------------------------------------------------------------

    def prepare_review(self, *, candidate_id: str) -> ReviewPreparationResult:
        try:
            candidate_identity = require_canonical_candidate_id(candidate_id)
        except ValueError as error:
            raise EffectiveSubtitleReviewPreparationError(str(error)) from error
        candidate = self._candidates.get(candidate_identity.value)
        if candidate is None:
            raise EffectiveSubtitleReviewPreparationError(
                "unknown effective subtitle candidate: preparation requires one exact "
                "existing candidate identity"
            )
        cues = self._candidates.cues(candidate_identity.value)
        self._require_structural_integrity(candidate, cues)
        fingerprint = derive_candidate_graph_fingerprint(candidate, cues)
        identity = derive_review_subject_identity(candidate_identity, fingerprint)

        existing = self._subjects.get(identity)
        if existing is not None:
            return self._reuse(existing, candidate, fingerprint)

        subject = EffectiveSubtitleReviewSubject(
            identity=identity,
            candidate_id=candidate_identity,
            candidate_graph_fingerprint=fingerprint,
            preparation_kind=PREPARATION_KIND,
            preparation_version=PREPARATION_VERSION,
            preparation_key=derive_preparation_key(candidate_identity),
        )
        if self._persistence is None:
            raise RuntimeError("effective subtitle review subject persistence is not configured")
        try:
            self._persistence.persist_review_subject(subject=subject)
        except PersistenceIdentityCollisionError:
            # A near-concurrent identical preparation won the insert; converge on its subject.
            resolved = self._subjects.get_for_candidate(candidate_identity)
            if resolved is not None:
                return self._reuse(resolved, candidate, fingerprint)
            raise
        return ReviewPreparationResult(
            subject=subject,
            candidate=candidate,
            outcome=PreparationOutcome.CREATED,
            status=self._status_of(candidate),
        )

    def _reuse(self, existing, candidate, fingerprint) -> ReviewPreparationResult:
        # One deterministic identity maps to exactly one structural payload; a disagreement is
        # an explicit conflict (repository corruption), never replay and never an overwrite.
        if existing.candidate_graph_fingerprint != fingerprint:
            raise ReviewSubjectConflictError(
                "existing review subject for this candidate records a different candidate "
                "graph fingerprint (repository integrity failure)"
            )
        return ReviewPreparationResult(
            subject=existing,
            candidate=candidate,
            outcome=PreparationOutcome.REUSED,
            status=self._status_of(candidate),
        )

    @staticmethod
    def _require_structural_integrity(candidate, cues) -> None:
        if len(cues) != candidate.cue_count:
            raise CandidateGraphIntegrityError(
                "candidate graph is structurally broken: cue set does not match the "
                "declared cue count (preparation refused; nothing persisted)"
            )
        if [cue.ordinal for cue in cues] != list(range(len(cues))):
            raise CandidateGraphIntegrityError(
                "candidate graph is structurally broken: cue ordinals are not a "
                "contiguous 0..n-1 sequence"
            )
        for cue in cues:
            if not cue.source_segment_ids:
                raise CandidateGraphIntegrityError(
                    "candidate graph is structurally broken: a cue has no source lineage"
                )

    # -- queries (derived; never mutate history) ------------------------------------------------------

    def get(self, review_subject_id: str) -> EffectiveSubtitleReviewSubject | None:
        return self._subjects.get(require_canonical_review_subject_id(review_subject_id))

    def subject_for_candidate(
        self, candidate_id: str
    ) -> EffectiveSubtitleReviewSubject | None:
        return self._subjects.get_for_candidate(require_canonical_candidate_id(candidate_id))

    def status(self, subject: EffectiveSubtitleReviewSubject) -> ReviewSubjectStatus:
        candidate = self._candidates.get(subject.candidate_id.value)
        if candidate is None:
            raise EffectiveSubtitleReviewPreparationError(
                "review subject references an unknown candidate (repository integrity failure)"
            )
        return self._status_of(candidate)

    def candidate_of(self, subject: EffectiveSubtitleReviewSubject) -> EffectiveSubtitleCandidate:
        candidate = self._candidates.get(subject.candidate_id.value)
        if candidate is None:
            raise EffectiveSubtitleReviewPreparationError(
                "review subject references an unknown candidate (repository integrity failure)"
            )
        return candidate

    def _status_of(self, candidate) -> ReviewSubjectStatus:
        source = self._candidates.currentness(candidate)
        return ReviewSubjectStatus(
            candidate_source_currentness=source,
            review_subject_currentness=_subject_currentness(source),
        )


def require_canonical_review_subject_id(value: str) -> EffectiveSubtitleReviewSubjectId:
    prefix = EFFECTIVE_REVIEW_SUBJECT_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise EffectiveSubtitleReviewPreparationError(
            "effective subtitle review subject identity is malformed "
            "(expected 'subtitle-effective-review-subject:<64 hex digest>')"
        )
    return EffectiveSubtitleReviewSubjectId(value)


__all__ = [
    "EFFECTIVE_REVIEW_SUBJECT_IDENTITY_PREFIX",
    "PREPARATION_KIND",
    "PREPARATION_VERSION",
    "AtomicReviewSubjectPersistence",
    "CandidateGraphIntegrityError",
    "EffectiveSubtitleReviewPreparationError",
    "EffectiveSubtitleReviewPreparationService",
    "EffectiveSubtitleReviewSubject",
    "PreparationOutcome",
    "ReviewPreparationResult",
    "ReviewSubjectConflictError",
    "ReviewSubjectCurrentness",
    "ReviewSubjectStatus",
    "derive_candidate_graph_fingerprint",
    "derive_preparation_key",
    "derive_review_subject_identity",
    "require_canonical_review_subject_id",
]
