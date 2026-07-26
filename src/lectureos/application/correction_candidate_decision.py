"""First Human Authority Decision on a Transcript Correction Candidate (040 §18, PATCH-0025).

Answers exactly one question: *has a human explicitly accepted or rejected this correction candidate?* — nothing
more. A Correction Candidate is only evidence; authority exists only when a human explicitly decides. This layer
records that decision as an **append-only, immutable, deterministic** fact. It **never** mutates the candidate,
the Raw Transcript, the current selection, or any segment; it creates no corrected revision, no candidate
decision beyond itself, and applies nothing. It reuses the admitted `CorrectionCandidate` (040 §17) and the Review
domain's `DecisionKind`/`HumanActorReference` value types — it introduces no second candidate or review hierarchy.

Semantics (040 §16–§25):

* Three states — **Undecided** (no decision record; derived by absence), **Accepted**, **Rejected**. No other
  states; no Modify in this slice.
* History is append-only: each authority change is a new record with a per-candidate ``sequence`` superseding the
  prior via ``previous_decision_id``; the **current** authority is the highest-``sequence`` record (derived, never
  stored). No UPDATE/DELETE — only INSERT.
* Decision matrix — None→Accept/Reject: recorded (sequence 0); Accept→Accept / Reject→Reject: **reused** (the
  authority is already that kind; no new record); Accept→Reject / Reject→Accept: **changed** (appended). Replay is
  idempotent; a conflicting reuse of the same anchor with different provenance is rejected without overwrite.
* Only Accepted candidates become eligible for future corrected-revision generation (established here, not
  implemented). Rejected and Undecided are never eligible.
* Identity is deterministic from ``(correction_candidate_id, kind, sequence)`` — no wall-clock/randomness.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.review.identities import HumanActorReference
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import CorrectionCandidateId

from .identities import CorrectionCandidateDecisionId

CORRECTION_CANDIDATE_DECISION_IDENTITY_PREFIX = "correction-candidate-decision"
_CORRECTION_CANDIDATE_IDENTITY_PREFIX = "correction-candidate:"

# Only these two Human judgements exist in this first authority slice (Modify is deferred).
_DECIDABLE_KINDS = (DecisionKind.ACCEPT, DecisionKind.REJECT)


class CorrectionCandidateDecisionError(ValueError):
    """A request that cannot become a canonical Human Decision (malformed, unknown, or unsupported)."""


class CorrectionCandidateDecisionConflictError(CorrectionCandidateDecisionError):
    """The same decision anchor was re-submitted with different provenance (no silent overwrite)."""


class HumanDecisionStatus(str, Enum):
    UNDECIDED = "undecided"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class DecisionOutcome(str, Enum):
    RECORDED = "recorded"   # first authority for the candidate (sequence 0)
    REUSED = "reused"       # the current authority is already this kind (idempotent)
    CHANGED = "changed"     # authority changed to the other kind (appended)


def require_canonical_correction_candidate_id(value: str) -> CorrectionCandidateId:
    """Return a `CorrectionCandidateId` if the value is a well-formed candidate identity, else reject."""

    if not isinstance(value, str) or not value.startswith(_CORRECTION_CANDIDATE_IDENTITY_PREFIX):
        raise CorrectionCandidateDecisionError(
            "correction candidate identity is malformed (expected 'correction-candidate:<digest>')"
        )
    digest = value[len(_CORRECTION_CANDIDATE_IDENTITY_PREFIX):]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise CorrectionCandidateDecisionError(
            "correction candidate identity is malformed (expected 'correction-candidate:<64 hex digest>')"
        )
    return CorrectionCandidateId(value)


def require_decision_kind(value: str) -> DecisionKind:
    """Return the Accept/Reject `DecisionKind` for a value, rejecting Modify and anything else."""

    try:
        kind = DecisionKind(value)
    except ValueError:
        raise CorrectionCandidateDecisionError(
            "decision kind must be 'accept' or 'reject'"
        ) from None
    if kind not in _DECIDABLE_KINDS:
        raise CorrectionCandidateDecisionError(
            "only 'accept' or 'reject' are supported (Modify is deferred)"
        )
    return kind


def derive_decision_identity(
    correction_candidate_id: CorrectionCandidateId, kind: DecisionKind, sequence: int
) -> CorrectionCandidateDecisionId:
    """Deterministic decision identity from the candidate, judgement kind, and per-candidate sequence."""

    payload = json.dumps(
        {"candidate": correction_candidate_id.value, "kind": kind.value, "sequence": sequence},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return CorrectionCandidateDecisionId(
        f"{CORRECTION_CANDIDATE_DECISION_IDENTITY_PREFIX}:{digest}"
    )


@dataclass(frozen=True, slots=True)
class CorrectionCandidateDecision:
    """Immutable Human Authority fact: one Accept/Reject judgement on one Correction Candidate."""

    identity: CorrectionCandidateDecisionId
    correction_candidate_id: CorrectionCandidateId
    kind: DecisionKind
    reviewer: HumanActorReference
    sequence: int
    content_fingerprint: str
    previous_decision_id: CorrectionCandidateDecisionId | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _DECIDABLE_KINDS:
            raise ValueError("correction candidate decision kind must be accept or reject")
        if not isinstance(self.reviewer, HumanActorReference):
            raise ValueError("decision reviewer must be a Human actor reference")
        if self.sequence < 0:
            raise ValueError("decision sequence must not be negative")
        if (self.sequence == 0) != (self.previous_decision_id is None):
            raise ValueError(
                "the first decision (sequence 0) has no previous; later decisions require one"
            )
        expected = derive_decision_identity(
            self.correction_candidate_id, self.kind, self.sequence
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
class CorrectionCandidateDecisionResult:
    """The outcome of one decision command: the current record, the outcome, and the superseded record."""

    decision: CorrectionCandidateDecision
    outcome: DecisionOutcome
    previous: CorrectionCandidateDecision | None = None


@dataclass(frozen=True, slots=True)
class CorrectionCandidateAuthority:
    """Derived current Human Authority for one candidate (never stored redundantly)."""

    correction_candidate_id: CorrectionCandidateId
    status: HumanDecisionStatus
    decision_count: int
    current_decision_id: CorrectionCandidateDecisionId | None = None
    eligible_for_revision: bool = False


class CorrectionCandidateAdmissionQuery(Protocol):
    def is_admitted_candidate(self, candidate_id: CorrectionCandidateId) -> bool: ...


class CorrectionCandidateDecisionQuery(Protocol):
    def get(self, identity): ...

    def get_current(self, candidate_id: CorrectionCandidateId): ...

    def history(self, candidate_id: CorrectionCandidateId) -> tuple: ...


class AtomicCorrectionCandidateDecisionPersistence(Protocol):
    def persist_decision(self, *, decision: CorrectionCandidateDecision) -> None: ...


def _content_fingerprint(
    candidate_id: CorrectionCandidateId,
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


class CorrectionCandidateDecisionService:
    """Records append-only Human Accept/Reject authority on admitted Correction Candidates."""

    def __init__(
        self,
        admission_query: CorrectionCandidateAdmissionQuery,
        decision_query: CorrectionCandidateDecisionQuery,
        persistence: AtomicCorrectionCandidateDecisionPersistence | None = None,
    ) -> None:
        self._admissions = admission_query
        self._decisions = decision_query
        self._persistence = persistence

    def _resolve_candidate(self, candidate_id: str) -> CorrectionCandidateId:
        identity = require_canonical_correction_candidate_id(candidate_id)
        if not self._admissions.is_admitted_candidate(identity):
            raise CorrectionCandidateDecisionError(
                "unknown correction candidate: admit the candidate before deciding on it"
            )
        return identity

    def decide(
        self,
        *,
        candidate_id: str,
        kind: str,
        reviewer: str,
        rationale: str | None = None,
    ) -> CorrectionCandidateDecisionResult:
        candidate_identity = self._resolve_candidate(candidate_id)
        decision_kind = require_decision_kind(kind)
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise CorrectionCandidateDecisionError("reviewer must be a non-empty Human actor reference")
        actor = HumanActorReference(reviewer)

        current = self._decisions.get_current(candidate_identity)
        if current is not None and current.kind == decision_kind:
            # The current authority is already this kind — reuse (idempotent), no new record.
            return CorrectionCandidateDecisionResult(
                decision=current, outcome=DecisionOutcome.REUSED, previous=None
            )

        sequence = 0 if current is None else current.sequence + 1
        previous_id = current.identity if current is not None else None
        identity = derive_decision_identity(candidate_identity, decision_kind, sequence)
        content_fingerprint = _content_fingerprint(
            candidate_identity, decision_kind, sequence, actor, rationale
        )
        existing = self._decisions.get(identity)
        if existing is not None:
            if existing.content_fingerprint != content_fingerprint:
                raise CorrectionCandidateDecisionConflictError(
                    "a different decision was already recorded for this candidate/kind/sequence "
                    "(LectureOS does not overwrite an immutable decision)"
                )
            return self._existing_result(existing, current)

        decision = CorrectionCandidateDecision(
            identity=identity,
            correction_candidate_id=candidate_identity,
            kind=decision_kind,
            reviewer=actor,
            sequence=sequence,
            content_fingerprint=content_fingerprint,
            previous_decision_id=previous_id,
            rationale=rationale,
        )
        if self._persistence is None:
            raise RuntimeError("correction candidate decision persistence is not configured")
        try:
            self._persistence.persist_decision(decision=decision)
        except PersistenceIdentityCollisionError:
            resolved = self._decisions.get(identity)
            if resolved is not None and resolved.content_fingerprint == content_fingerprint:
                return self._existing_result(resolved, current)
            raise
        outcome = DecisionOutcome.RECORDED if current is None else DecisionOutcome.CHANGED
        return CorrectionCandidateDecisionResult(
            decision=decision, outcome=outcome, previous=current
        )

    def _existing_result(
        self,
        decision: CorrectionCandidateDecision,
        previous: CorrectionCandidateDecision | None,
    ) -> CorrectionCandidateDecisionResult:
        # A near-concurrent insert landed our exact record; report it as the outcome it represents.
        outcome = DecisionOutcome.RECORDED if decision.sequence == 0 else DecisionOutcome.CHANGED
        return CorrectionCandidateDecisionResult(
            decision=decision,
            outcome=outcome,
            previous=previous if decision.sequence > 0 else None,
        )

    def authority(self, candidate_id: str) -> CorrectionCandidateAuthority:
        candidate_identity = self._resolve_candidate(candidate_id)
        history = self._decisions.history(candidate_identity)
        current = self._decisions.get_current(candidate_identity)
        if current is None:
            return CorrectionCandidateAuthority(
                correction_candidate_id=candidate_identity,
                status=HumanDecisionStatus.UNDECIDED,
                decision_count=0,
            )
        status = (
            HumanDecisionStatus.ACCEPTED
            if current.kind is DecisionKind.ACCEPT
            else HumanDecisionStatus.REJECTED
        )
        return CorrectionCandidateAuthority(
            correction_candidate_id=candidate_identity,
            status=status,
            decision_count=len(history),
            current_decision_id=current.identity,
            eligible_for_revision=current.kind is DecisionKind.ACCEPT,
        )

    def history(self, candidate_id: str) -> tuple[CorrectionCandidateDecision, ...]:
        candidate_identity = self._resolve_candidate(candidate_id)
        return self._decisions.history(candidate_identity)


__all__ = [
    "CORRECTION_CANDIDATE_DECISION_IDENTITY_PREFIX",
    "AtomicCorrectionCandidateDecisionPersistence",
    "CorrectionCandidateAdmissionQuery",
    "CorrectionCandidateAuthority",
    "CorrectionCandidateDecision",
    "CorrectionCandidateDecisionConflictError",
    "CorrectionCandidateDecisionError",
    "CorrectionCandidateDecisionQuery",
    "CorrectionCandidateDecisionResult",
    "CorrectionCandidateDecisionService",
    "DecisionOutcome",
    "HumanDecisionStatus",
    "derive_decision_identity",
    "require_canonical_correction_candidate_id",
    "require_decision_kind",
]
