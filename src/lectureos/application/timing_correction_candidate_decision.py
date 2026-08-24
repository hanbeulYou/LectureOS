"""Human Authority decision on a Timing Correction Candidate (040 §18 forward note, PATCH-0047 TC-10/TC-11).

`§18`'s released semantics apply to timing candidates **unchanged**: the decision records that a
person accepted or rejected one candidate, reusing `DecisionKind(accept/reject)` and
`HumanActorReference`, with append-only supersession and H-2's three states — Undecided derived from
absence, Accepted, Rejected. **Modify stays deferred** exactly as H-2 left it.

A sibling persistence relation exists for one reason only: `correction_candidate_decisions`
foreign-keys to `correction_candidates(identity)`, so it cannot reference a timing candidate living
in its own record. H-1 met the analogous problem, declined to wrap one candidate layer in another,
and introduced the smallest additive aggregate reusing the existing value types; the same move is
taken here, and no new authority, role, or hierarchy is created (TC-10).

**Rejection is a normal outcome and gets no special state** (TC-11). About half of the timing
diagnostic's findings are expected to be dismissed, and "the source timing is correct" is a complete
human judgement fully expressed by `reject`. No `ignored`, `dismissed`, or `false_positive` state
exists — inventing one would imply the diagnostic had made a claim that turned out wrong, and
`PATCH-0046` TD-2 is explicit that it made no claim at all.

Identity is deterministic from ``(timing_correction_candidate_id, kind, sequence)`` — the released
H-7 recipe over a distinct candidate identity, so a timing decision can never collide with a text one.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.review.identities import HumanActorReference
from lectureos.review.models import DecisionKind

from .correction_candidate_decision import DecisionOutcome, HumanDecisionStatus
from .identities import (
    TimingCorrectionCandidateDecisionId,
    TimingCorrectionCandidateId,
)
from .timing_correction_candidate_admission import (
    TIMING_CORRECTION_CANDIDATE_IDENTITY_PREFIX,
)

TIMING_CORRECTION_DECISION_IDENTITY_PREFIX = "timing-correction-candidate-decision"

# Only these two Human judgements exist, exactly as H-2 fixed them (Modify is deferred).
_DECIDABLE_KINDS = (DecisionKind.ACCEPT, DecisionKind.REJECT)


class TimingCorrectionDecisionError(ValueError):
    """A request that cannot become a canonical Human Decision (malformed, unknown, or unsupported)."""


class TimingCorrectionDecisionConflictError(TimingCorrectionDecisionError):
    """The same decision anchor was re-submitted with different provenance (no silent overwrite)."""


def require_canonical_timing_candidate_id(value: str) -> TimingCorrectionCandidateId:
    """Return a `TimingCorrectionCandidateId` if the value is a well-formed identity, else reject."""

    prefix = f"{TIMING_CORRECTION_CANDIDATE_IDENTITY_PREFIX}:"
    if not isinstance(value, str) or not value.startswith(prefix):
        raise TimingCorrectionDecisionError(
            "timing correction candidate identity is malformed "
            f"(expected '{TIMING_CORRECTION_CANDIDATE_IDENTITY_PREFIX}:<digest>')"
        )
    digest = value[len(prefix):]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise TimingCorrectionDecisionError(
            "timing correction candidate identity is malformed "
            f"(expected '{TIMING_CORRECTION_CANDIDATE_IDENTITY_PREFIX}:<64 hex digest>')"
        )
    return TimingCorrectionCandidateId(value)


def require_timing_decision_kind(value: str) -> DecisionKind:
    """Return the Accept/Reject `DecisionKind` for a value, rejecting Modify and anything else."""

    try:
        kind = DecisionKind(value)
    except ValueError:
        raise TimingCorrectionDecisionError(
            "decision kind must be 'accept' or 'reject'"
        ) from None
    if kind not in _DECIDABLE_KINDS:
        raise TimingCorrectionDecisionError(
            "only 'accept' or 'reject' are supported (Modify is deferred)"
        )
    return kind


def derive_timing_decision_identity(
    candidate_id: TimingCorrectionCandidateId, kind: DecisionKind, sequence: int
) -> TimingCorrectionCandidateDecisionId:
    """Deterministic decision identity from the candidate, judgement kind, and per-candidate sequence."""

    payload = json.dumps(
        {"candidate": candidate_id.value, "kind": kind.value, "sequence": sequence},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return TimingCorrectionCandidateDecisionId(
        f"{TIMING_CORRECTION_DECISION_IDENTITY_PREFIX}:{digest}"
    )


@dataclass(frozen=True, slots=True)
class TimingCorrectionCandidateDecision:
    """Immutable Human Authority fact: one Accept/Reject judgement on one Timing Correction Candidate."""

    identity: TimingCorrectionCandidateDecisionId
    timing_correction_candidate_id: TimingCorrectionCandidateId
    kind: DecisionKind
    reviewer: HumanActorReference
    sequence: int
    content_fingerprint: str
    previous_decision_id: TimingCorrectionCandidateDecisionId | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _DECIDABLE_KINDS:
            raise ValueError("timing correction decision kind must be accept or reject")
        if not isinstance(self.reviewer, HumanActorReference):
            raise ValueError("decision reviewer must be a Human actor reference")
        if self.sequence < 0:
            raise ValueError("decision sequence must not be negative")
        if (self.sequence == 0) != (self.previous_decision_id is None):
            raise ValueError(
                "the first decision (sequence 0) has no previous; later decisions require one"
            )
        expected = derive_timing_decision_identity(
            self.timing_correction_candidate_id, self.kind, self.sequence
        )
        if self.identity != expected:
            raise ValueError(
                "decision identity must be derived from its candidate, kind, and sequence"
            )
        if self.rationale is not None and not self.rationale.strip():
            raise ValueError("decision rationale, when present, must not be blank")
        if len(self.content_fingerprint) != 64:
            raise ValueError("decision content fingerprint must be a 64-hex SHA-256 digest")


@dataclass(frozen=True, slots=True)
class TimingCorrectionDecisionResult:
    """The outcome of one decision command: the current record, the outcome, and the superseded record."""

    decision: TimingCorrectionCandidateDecision
    outcome: DecisionOutcome
    previous: TimingCorrectionCandidateDecision | None = None


@dataclass(frozen=True, slots=True)
class TimingCorrectionAuthority:
    """Derived current Human Authority for one timing candidate (never stored redundantly)."""

    timing_correction_candidate_id: TimingCorrectionCandidateId
    status: HumanDecisionStatus
    decision_count: int
    current_decision_id: TimingCorrectionCandidateDecisionId | None = None
    eligible_for_revision: bool = False


class TimingCorrectionCandidateQuery(Protocol):
    def get(self, identity): ...


class TimingCorrectionDecisionQuery(Protocol):
    def get(self, identity): ...

    def get_current(self, candidate_id: TimingCorrectionCandidateId): ...

    def history(self, candidate_id: TimingCorrectionCandidateId) -> tuple: ...


class AtomicTimingCorrectionDecisionPersistence(Protocol):
    def persist_timing_decision(
        self, *, decision: TimingCorrectionCandidateDecision
    ) -> None: ...


def _content_fingerprint(
    candidate_id: TimingCorrectionCandidateId,
    kind: DecisionKind,
    sequence: int,
    reviewer: HumanActorReference,
    rationale: str | None,
) -> str:
    payload = json.dumps(
        {
            "candidate": candidate_id.value,
            "kind": kind.value,
            "sequence": sequence,
            "reviewer": reviewer.value,
            "rationale": rationale,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class TimingCorrectionDecisionService:
    """Records append-only Human Accept/Reject authority on admitted Timing Correction Candidates."""

    def __init__(
        self,
        candidate_query: TimingCorrectionCandidateQuery,
        decision_query: TimingCorrectionDecisionQuery,
        persistence: AtomicTimingCorrectionDecisionPersistence | None = None,
    ) -> None:
        self._candidates = candidate_query
        self._decisions = decision_query
        self._persistence = persistence

    def _resolve_candidate(self, candidate_id: str) -> TimingCorrectionCandidateId:
        identity = require_canonical_timing_candidate_id(candidate_id)
        if self._candidates.get(identity) is None:
            raise TimingCorrectionDecisionError(
                "unknown timing correction candidate: admit the candidate before deciding on it"
            )
        return identity

    def decide(
        self,
        *,
        candidate_id: str,
        kind: str,
        reviewer: str,
        rationale: str | None = None,
    ) -> TimingCorrectionDecisionResult:
        candidate_identity = self._resolve_candidate(candidate_id)
        decision_kind = require_timing_decision_kind(kind)
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise TimingCorrectionDecisionError(
                "reviewer must be a non-empty Human actor reference"
            )
        actor = HumanActorReference(reviewer)

        current = self._decisions.get_current(candidate_identity)
        if current is not None and current.kind == decision_kind:
            # The current authority is already this kind — reuse (idempotent), no new record.
            return TimingCorrectionDecisionResult(
                decision=current, outcome=DecisionOutcome.REUSED, previous=None
            )

        sequence = 0 if current is None else current.sequence + 1
        previous_id = current.identity if current is not None else None
        identity = derive_timing_decision_identity(
            candidate_identity, decision_kind, sequence
        )
        content_fingerprint = _content_fingerprint(
            candidate_identity, decision_kind, sequence, actor, rationale
        )
        existing = self._decisions.get(identity)
        if existing is not None:
            if existing.content_fingerprint != content_fingerprint:
                raise TimingCorrectionDecisionConflictError(
                    "a different decision was already recorded for this candidate/kind/sequence "
                    "(LectureOS does not overwrite an immutable decision)"
                )
            return self._existing_result(existing, current)

        decision = TimingCorrectionCandidateDecision(
            identity=identity,
            timing_correction_candidate_id=candidate_identity,
            kind=decision_kind,
            reviewer=actor,
            sequence=sequence,
            content_fingerprint=content_fingerprint,
            previous_decision_id=previous_id,
            rationale=rationale,
        )
        if self._persistence is None:
            raise RuntimeError("timing correction decision persistence is not configured")
        try:
            self._persistence.persist_timing_decision(decision=decision)
        except PersistenceIdentityCollisionError:
            resolved = self._decisions.get(identity)
            if resolved is not None and resolved.content_fingerprint == content_fingerprint:
                return self._existing_result(resolved, current)
            raise
        outcome = DecisionOutcome.RECORDED if current is None else DecisionOutcome.CHANGED
        return TimingCorrectionDecisionResult(
            decision=decision, outcome=outcome, previous=current
        )

    def _existing_result(
        self,
        decision: TimingCorrectionCandidateDecision,
        previous: TimingCorrectionCandidateDecision | None,
    ) -> TimingCorrectionDecisionResult:
        # A near-concurrent insert landed our exact record; report it as the outcome it represents.
        outcome = (
            DecisionOutcome.RECORDED if decision.sequence == 0 else DecisionOutcome.CHANGED
        )
        return TimingCorrectionDecisionResult(
            decision=decision,
            outcome=outcome,
            previous=previous if decision.sequence > 0 else None,
        )

    def authority(self, candidate_id: str) -> TimingCorrectionAuthority:
        candidate_identity = self._resolve_candidate(candidate_id)
        history = self._decisions.history(candidate_identity)
        current = self._decisions.get_current(candidate_identity)
        if current is None:
            return TimingCorrectionAuthority(
                timing_correction_candidate_id=candidate_identity,
                status=HumanDecisionStatus.UNDECIDED,
                decision_count=0,
            )
        status = (
            HumanDecisionStatus.ACCEPTED
            if current.kind is DecisionKind.ACCEPT
            else HumanDecisionStatus.REJECTED
        )
        return TimingCorrectionAuthority(
            timing_correction_candidate_id=candidate_identity,
            status=status,
            decision_count=len(history),
            current_decision_id=current.identity,
            eligible_for_revision=current.kind is DecisionKind.ACCEPT,
        )

    def history(self, candidate_id: str) -> tuple[TimingCorrectionCandidateDecision, ...]:
        return self._decisions.history(self._resolve_candidate(candidate_id))


__all__ = [
    "TIMING_CORRECTION_DECISION_IDENTITY_PREFIX",
    "AtomicTimingCorrectionDecisionPersistence",
    "TimingCorrectionAuthority",
    "TimingCorrectionCandidateDecision",
    "TimingCorrectionDecisionConflictError",
    "TimingCorrectionDecisionError",
    "TimingCorrectionDecisionQuery",
    "TimingCorrectionDecisionResult",
    "TimingCorrectionDecisionService",
    "derive_timing_decision_identity",
    "require_canonical_timing_candidate_id",
    "require_timing_decision_kind",
]
