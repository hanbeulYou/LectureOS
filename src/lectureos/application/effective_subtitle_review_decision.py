"""Human Decisions over Effective-Source Subtitle Review Subjects (GOAL-015).

Introduces Human Authority for the effective-transcript subtitle contract generation, reusing the
released GOAL-009 authority idiom **exactly**: an explicit command by a truthful
`HumanActorReference` records one immutable, append-only decision about one exact
`EffectiveSubtitleReviewSubject`; the current decision is derived from the immutable history
(per-subject ``sequence`` + ``previous_decision_id`` supersession — highest sequence, never a
latest-row heuristic, never a mutable flag); a request whose kind already matches the current
authority is **reused** (idempotent repeated intent — GOAL-009's released rule: one authority
state, not one row per utterance), while a changed judgment **appends** a new decision that
supersedes the prior authority without mutating or deleting it. Near-concurrent identical requests
converge on the deterministic identity + content-fingerprint verification; a divergent payload for
one (subject, kind, sequence) slot is an explicit conflict, never an overwrite.

The closed decision vocabulary is `accept` / `reject` / `modify` (the canonical `DecisionKind`).
A decision records authority and nothing else: Accept creates no final selection or export
eligibility; Reject deletes and mutates nothing; Modify only records that the reviewed candidate
requires modification — authoring a modified subtitle artifact is a later, separately scoped goal.
Decision **applicability** is derived, never stored, and is separate from kind and from integrity:
a decision over a subject whose candidate source went stale remains valid history
(human historical judgment ≠ current downstream applicability); a superseded decision remains an
immutable record. `HumanActorReference` is provenance, not credential verification — no
authorization system exists here. No wall-clock, randomness, or workflow state participates.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.review.identities import HumanActorReference
from lectureos.review.models import DecisionKind

from .effective_subtitle_generation import EffectiveSubtitleGenerationService
from .effective_subtitle_review_preparation import (
    EffectiveSubtitleReviewPreparationService,
    EffectiveSubtitleReviewSubject,
    ReviewSubjectCurrentness,
    ReviewSubjectStatus,
    derive_candidate_graph_fingerprint,
    require_canonical_review_subject_id,
)
from .identities import (
    EffectiveSubtitleReviewDecisionId,
    EffectiveSubtitleReviewSubjectId,
)

EFFECTIVE_REVIEW_DECISION_IDENTITY_PREFIX = "subtitle-effective-review-decision"

# The closed subtitle-review vocabulary (canonical DecisionKind; all three product judgments).
_DECIDABLE_KINDS = (DecisionKind.ACCEPT, DecisionKind.REJECT, DecisionKind.MODIFY)


class EffectiveSubtitleReviewDecisionError(ValueError):
    """A decision command that cannot proceed (malformed, unknown, or unsupported input)."""


class DecisionSubjectIntegrityError(EffectiveSubtitleReviewDecisionError):
    """The review subject's bound candidate graph is broken — deciding is refused, nothing persists."""


class EffectiveSubtitleReviewDecisionConflictError(EffectiveSubtitleReviewDecisionError):
    """The deterministic decision slot maps to a structurally different persisted payload."""


class DecisionOutcome(str, Enum):
    RECORDED = "recorded"   # first authority for the subject (sequence 0)
    REUSED = "reused"       # the current authority is already this kind (idempotent)
    CHANGED = "changed"     # a new judgment superseding the prior authority


class DecisionApplicability(str, Enum):
    """Derived, never stored. Separate from decision kind and from repository integrity."""

    APPLICABLE = "applicable"
    SUPERSEDED = "superseded"
    STALE_DUE_TO_CANDIDATE_SOURCE = "stale_due_to_candidate_source"
    UNRESOLVABLE = "unresolvable"


def require_decision_kind(value: str) -> DecisionKind:
    """Return a decidable `DecisionKind`, rejecting anything outside the closed set."""

    try:
        kind = DecisionKind(value)
    except ValueError:
        raise EffectiveSubtitleReviewDecisionError(
            f"unsupported decision kind: {value!r} (supported: accept, reject, modify)"
        ) from None
    if kind not in _DECIDABLE_KINDS:
        raise EffectiveSubtitleReviewDecisionError(
            f"unsupported decision kind: {value!r} (supported: accept, reject, modify)"
        )
    return kind


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def derive_decision_identity(
    review_subject_id: EffectiveSubtitleReviewSubjectId,
    kind: DecisionKind,
    sequence: int,
) -> EffectiveSubtitleReviewDecisionId:
    """Deterministic decision identity — the GOAL-009 rule: (subject, judgement kind, sequence).

    The reviewer and rationale are provenance, not identity (verified via the content fingerprint).
    """

    digest = hashlib.sha256(
        _canonical_json(
            {
                "review_subject": review_subject_id.value,
                "kind": kind.value,
                "sequence": sequence,
            }
        ).encode("utf-8")
    ).hexdigest()
    return EffectiveSubtitleReviewDecisionId(
        f"{EFFECTIVE_REVIEW_DECISION_IDENTITY_PREFIX}:{digest}"
    )


def _content_fingerprint(
    review_subject_id: EffectiveSubtitleReviewSubjectId,
    kind: DecisionKind,
    sequence: int,
    reviewer: HumanActorReference,
    rationale: str | None,
) -> str:
    payload = _canonical_json(
        {
            "review_subject": review_subject_id.value,
            "kind": kind.value,
            "sequence": sequence,
            "reviewer": reviewer.value,
            "rationale": rationale,
        }
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleReviewDecision:
    """Immutable Human Authority fact: one Accept/Reject/Modify judgment on one review subject."""

    identity: EffectiveSubtitleReviewDecisionId
    review_subject_id: EffectiveSubtitleReviewSubjectId
    kind: DecisionKind
    reviewer: HumanActorReference
    sequence: int
    content_fingerprint: str
    previous_decision_id: EffectiveSubtitleReviewDecisionId | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _DECIDABLE_KINDS:
            raise ValueError("decision kind must be accept, reject, or modify")
        if not self.reviewer.value.strip():
            raise ValueError("decision reviewer must be a non-empty Human actor reference")
        if self.sequence < 0:
            raise ValueError("decision sequence must not be negative")
        if (self.sequence == 0) != (self.previous_decision_id is None):
            raise ValueError(
                "the first decision (sequence 0) has no previous; later decisions require one"
            )
        if self.previous_decision_id == self.identity:
            raise ValueError("a decision cannot supersede itself")
        if self.rationale is not None and not self.rationale.strip():
            raise ValueError("decision rationale, when present, must not be blank")
        if self.identity != derive_decision_identity(
            self.review_subject_id, self.kind, self.sequence
        ):
            raise ValueError(
                "decision identity must be derived from its subject, kind, and sequence"
            )
        if self.content_fingerprint != _content_fingerprint(
            self.review_subject_id, self.kind, self.sequence, self.reviewer, self.rationale
        ):
            raise ValueError(
                "decision content fingerprint must match its immutable payload"
            )


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleReviewDecisionResult:
    """One decision command outcome: the authority record, the outcome, and the superseded record."""

    decision: EffectiveSubtitleReviewDecision
    outcome: DecisionOutcome
    previous: EffectiveSubtitleReviewDecision | None


class ReviewDecisionQuery(Protocol):
    def get(self, identity): ...

    def get_current(self, review_subject_id): ...

    def history(self, review_subject_id) -> tuple: ...


class AtomicReviewDecisionPersistence(Protocol):
    def persist_decision(self, *, decision: EffectiveSubtitleReviewDecision) -> None: ...


class EffectiveSubtitleReviewDecisionService:
    """The single canonical Human Decision path for effective-source review subjects (GOAL-015)."""

    def __init__(
        self,
        preparation_service: EffectiveSubtitleReviewPreparationService,
        generation_service: EffectiveSubtitleGenerationService,
        decision_query: ReviewDecisionQuery,
        persistence: AtomicReviewDecisionPersistence | None = None,
    ) -> None:
        self._subjects = preparation_service
        self._candidates = generation_service
        self._decisions = decision_query
        self._persistence = persistence

    # -- authority command ---------------------------------------------------------------------------

    def decide(
        self,
        *,
        review_subject_id: str,
        kind: str,
        reviewer: str,
        rationale: str | None = None,
    ) -> EffectiveSubtitleReviewDecisionResult:
        subject = self._resolve_subject(review_subject_id)
        decision_kind = require_decision_kind(kind)
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise EffectiveSubtitleReviewDecisionError(
                "reviewer must be a non-empty Human actor reference"
            )
        actor = HumanActorReference(reviewer)

        current = self._decisions.get_current(subject.identity)
        if current is not None and current.kind == decision_kind:
            # The current authority is already this kind — reuse (idempotent), no new record.
            # This is GOAL-009's released repeated-intent rule: authority is a state, not a ledger
            # of identical utterances.
            return EffectiveSubtitleReviewDecisionResult(
                decision=current, outcome=DecisionOutcome.REUSED, previous=None
            )

        sequence = 0 if current is None else current.sequence + 1
        previous_id = current.identity if current is not None else None
        identity = derive_decision_identity(subject.identity, decision_kind, sequence)
        fingerprint = _content_fingerprint(
            subject.identity, decision_kind, sequence, actor, rationale
        )
        existing = self._decisions.get(identity)
        if existing is not None:
            if existing.content_fingerprint != fingerprint:
                raise EffectiveSubtitleReviewDecisionConflictError(
                    "a different decision was already recorded for this subject/kind/sequence "
                    "(LectureOS does not overwrite an immutable decision)"
                )
            return self._existing_result(existing, current)

        decision = EffectiveSubtitleReviewDecision(
            identity=identity,
            review_subject_id=subject.identity,
            kind=decision_kind,
            reviewer=actor,
            sequence=sequence,
            content_fingerprint=fingerprint,
            previous_decision_id=previous_id,
            rationale=rationale,
        )
        if self._persistence is None:
            raise RuntimeError(
                "effective subtitle review decision persistence is not configured"
            )
        try:
            self._persistence.persist_decision(decision=decision)
        except PersistenceIdentityCollisionError:
            # A near-concurrent identical command won the insert; converge only on payload equality.
            resolved = self._decisions.get(identity)
            if resolved is not None and resolved.content_fingerprint == fingerprint:
                return self._existing_result(resolved, current)
            raise
        outcome = DecisionOutcome.RECORDED if current is None else DecisionOutcome.CHANGED
        return EffectiveSubtitleReviewDecisionResult(
            decision=decision, outcome=outcome, previous=current
        )

    def _existing_result(
        self,
        decision: EffectiveSubtitleReviewDecision,
        previous: EffectiveSubtitleReviewDecision | None,
    ) -> EffectiveSubtitleReviewDecisionResult:
        outcome = (
            DecisionOutcome.RECORDED if decision.sequence == 0 else DecisionOutcome.CHANGED
        )
        return EffectiveSubtitleReviewDecisionResult(
            decision=decision, outcome=outcome, previous=previous
        )

    def _resolve_subject(self, review_subject_id: str) -> EffectiveSubtitleReviewSubject:
        try:
            subject = self._subjects.get(review_subject_id)
        except ValueError as error:
            raise EffectiveSubtitleReviewDecisionError(str(error)) from error
        if subject is None:
            raise EffectiveSubtitleReviewDecisionError(
                "unknown effective subtitle review subject: a decision requires one exact "
                "existing review subject identity"
            )
        # The subject's bound candidate graph must still verify against its immutable anchor —
        # a broken graph refuses new authority with nothing persisted.
        candidate = self._candidates.get(subject.candidate_id.value)
        if candidate is None:
            raise DecisionSubjectIntegrityError(
                "review subject references a missing candidate (repository integrity failure)"
            )
        cues = self._candidates.cues(subject.candidate_id.value)
        if (
            derive_candidate_graph_fingerprint(candidate, cues)
            != subject.candidate_graph_fingerprint
        ):
            raise DecisionSubjectIntegrityError(
                "review subject's candidate graph no longer matches its immutable anchor "
                "(repository integrity failure; deciding is refused)"
            )
        return subject

    # -- queries (derived; never mutate history) ------------------------------------------------------

    def get(self, decision_id: str) -> EffectiveSubtitleReviewDecision | None:
        return self._decisions.get(require_canonical_decision_id(decision_id))

    def current(self, review_subject_id: str) -> EffectiveSubtitleReviewDecision | None:
        return self._decisions.get_current(
            require_canonical_review_subject_id(review_subject_id)
        )

    def history(
        self, review_subject_id: str
    ) -> tuple[EffectiveSubtitleReviewDecision, ...]:
        return self._decisions.history(
            require_canonical_review_subject_id(review_subject_id)
        )

    def applicability(
        self, decision: EffectiveSubtitleReviewDecision
    ) -> DecisionApplicability:
        """Derived only. Kind is never applicability: reject and modify can be applicable."""

        current = self._decisions.get_current(decision.review_subject_id)
        if current is None or current.identity != decision.identity:
            return DecisionApplicability.SUPERSEDED
        subject = self._subjects.get(decision.review_subject_id.value)
        if subject is None:
            raise EffectiveSubtitleReviewDecisionError(
                "decision references an unknown review subject (repository integrity failure)"
            )
        status: ReviewSubjectStatus = self._subjects.status(subject)
        if status.review_subject_currentness is ReviewSubjectCurrentness.CURRENT:
            return DecisionApplicability.APPLICABLE
        if status.review_subject_currentness is ReviewSubjectCurrentness.UNRESOLVABLE:
            return DecisionApplicability.UNRESOLVABLE
        return DecisionApplicability.STALE_DUE_TO_CANDIDATE_SOURCE

    def subject_status(self, decision: EffectiveSubtitleReviewDecision) -> ReviewSubjectStatus:
        subject = self._subjects.get(decision.review_subject_id.value)
        if subject is None:
            raise EffectiveSubtitleReviewDecisionError(
                "decision references an unknown review subject (repository integrity failure)"
            )
        return self._subjects.status(subject)


def require_canonical_decision_id(value: str) -> EffectiveSubtitleReviewDecisionId:
    prefix = EFFECTIVE_REVIEW_DECISION_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise EffectiveSubtitleReviewDecisionError(
            "effective subtitle review decision identity is malformed "
            "(expected 'subtitle-effective-review-decision:<64 hex digest>')"
        )
    return EffectiveSubtitleReviewDecisionId(value)


__all__ = [
    "EFFECTIVE_REVIEW_DECISION_IDENTITY_PREFIX",
    "AtomicReviewDecisionPersistence",
    "DecisionApplicability",
    "DecisionOutcome",
    "DecisionSubjectIntegrityError",
    "EffectiveSubtitleReviewDecision",
    "EffectiveSubtitleReviewDecisionConflictError",
    "EffectiveSubtitleReviewDecisionError",
    "EffectiveSubtitleReviewDecisionResult",
    "EffectiveSubtitleReviewDecisionService",
    "derive_decision_identity",
    "require_canonical_decision_id",
    "require_decision_kind",
]
