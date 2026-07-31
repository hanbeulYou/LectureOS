"""Review Authority History — effective-transcript generation (043 §7.6, GOAL-029).

The effective-transcript generation's authority-history and current-selection contract, implementing
the Architect Decisions confirmed by `patches/PATCH-0034` (AH-1…AH-12). It answers the one question
`§7.5` deliberately left open: when a person reverses a judgment on one Edit Candidate, which
judgment is currently valid?

**The two canonical records are untouched (AH-4).** No ordinal, previous link, or status column is
added to `ReviewDecision` or `ApprovedEditDecision`, and their released identity composition and
convergence behaviour are unchanged. The history lives in a separate canonical record because
folding a `sequence` into the released `ReviewDecision` identity would change the identity **value**
of every already-recorded row, mutating released meaning.

**Scope is per (Candidate, actor) (AH-6).** `§7.5` R-10 keeps the human actor in the decision
identity, so each actor's judgments on one Candidate form their own history. `sequence` is
contiguous from 0 within a scope, `sequence = 0` carries no previous, `sequence > 0` requires one,
and no position references itself.

**One decision may occupy several positions (AH-6).** That is the case this contract exists to
close: `accept` → `reject` → `accept` converges to **two** canonical decisions across **three**
positions, with positions 0 and 2 referencing the same `accept` record. A per-decision uniqueness
constraint on this relation is therefore prohibited — it would make reversal history unrepresentable.

**Append rule (AH-7).** No history → insert at `sequence` 0. The submitted judgment's decision equals
the current head's → reuse, nothing written. Different → append at `sequence + 1`, superseding the
head. The `sequence + 1` derivation is authorized here and is **not** what `§7.5` R-9 prohibits: R-9
governs the per-admission ordinal, which still does not exist. Row counts, wall-clock, insertion
order, rowid, and any ordinal derived from anything but this scope's persisted head stay prohibited.

**Current is derived, never stored (AH-8).** Per scope, the current judgment is the highest
`sequence`. Superseded positions remain valid immutable history.

**Cross-actor: observation, never arbitration (AH-9).** For one Candidate, exactly one actor with
history yields that actor's current judgment; two or more yield **no** current — a `§3.12` Review
Conflict that is surfaced and never auto-resolved. Priority among actors, recency across actors, and
role ranking are prohibited, and `§15.3`'s open multi-user question is declined, not answered.

**Identity and reachability (AH-11).** The position identity derives from the immutable scope and
the stable position — `(candidate, actor, sequence)` — following the released precedent
(`040 §18` H-7 and the effective subtitle Review decision, which both bind the position and keep the
referenced payload out). The referenced decision and previous link are persisted canonical fields
that do **not** participate, so this is **Option A**: two competing appends at one position produce
the same identity with different content, which is reachable through ordinary concurrent input and
must be — and is — an explicit conflict, never an overwrite.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from lectureos.review.identities import HumanActorReference

from .identities import (
    LectureAnalysisEditCandidateId,
    LectureReviewAuthorityPositionId,
    LectureReviewDecisionId,
)

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps this module import-cycle free
    from .lecture_review_decision import (
        LectureApprovedEditDecision,
        LectureReviewDecision,
    )

LECTURE_REVIEW_AUTHORITY_POSITION_IDENTITY_PREFIX = "lecture-review-authority-position"

AUTHORITY_POSITION_CONTRACT_KIND = "lecture_review_authority_position"
AUTHORITY_POSITION_CONTRACT_VERSION = 1


class LectureReviewAuthorityError(ValueError):
    """An authority-history operation that cannot proceed."""


class ReviewAuthorityConflictError(LectureReviewAuthorityError):
    """A different position already occupies this place in the history.

    R-11's collision-convergence idiom applied to AH-11's Option A: two near-concurrent appends both
    target `sequence + 1` and therefore derive the **same** identity. If they carry the same
    referenced decision they converge; if they differ, the later one is refused and nothing is
    overwritten (`040 §18` H-9).
    """


class AuthorityPositionOutcome(str, Enum):
    RECORDED = "recorded"  # a new immutable position was appended (or the history was started)
    REUSED = "reused"      # the current head already records this judgment; nothing was written


class CandidateAuthorityStatus(str, Enum):
    """What a Candidate-level observation can report — never an arbitration (AH-9)."""

    NO_HISTORY = "no_history"
    SINGLE_ACTOR = "single_actor"
    CROSS_ACTOR_CONFLICT = "cross_actor_conflict"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def require_authority_actor(value: str) -> HumanActorReference:
    """The scope's human actor, reusing `§7.5`'s released rule: non-empty, stored verbatim."""

    if not isinstance(value, str) or not value.strip():
        raise LectureReviewAuthorityError(
            "review authority history requires a non-empty Human actor reference"
        )
    return HumanActorReference(value)


def require_sequence(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise LectureReviewAuthorityError(
            "review authority position sequence must be a non-negative integer"
        )
    return value


def derive_authority_position_identity(
    candidate_id: LectureAnalysisEditCandidateId,
    actor: HumanActorReference,
    sequence: int,
) -> LectureReviewAuthorityPositionId:
    """Deterministic, Application-owned position identity (043 §7.6 AH-11).

    Binds the immutable scope and the stable history position and nothing else — the released
    precedent's shape (`040 §18` H-7). The referenced decision and the previous link are recorded
    facts that do not participate, which is precisely what makes a competing append at the same
    position collide on one identity and become an explicit conflict rather than a second row.
    """

    digest = hashlib.sha256(
        _canonical_json(
            {
                "contract": AUTHORITY_POSITION_CONTRACT_KIND,
                "contract_version": AUTHORITY_POSITION_CONTRACT_VERSION,
                "candidate": candidate_id.value,
                "actor": actor.value,
                "sequence": sequence,
            }
        ).encode("utf-8")
    ).hexdigest()
    return LectureReviewAuthorityPositionId(
        f"{LECTURE_REVIEW_AUTHORITY_POSITION_IDENTITY_PREFIX}:{digest}"
    )


def require_canonical_authority_position_id(
    value: str,
) -> LectureReviewAuthorityPositionId:
    prefix = LECTURE_REVIEW_AUTHORITY_POSITION_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise LectureReviewAuthorityError(
            "lecture review authority position identity is malformed "
            "(expected 'lecture-review-authority-position:<64 hex digest>')"
        )
    return LectureReviewAuthorityPositionId(value)


@dataclass(frozen=True, slots=True)
class LectureReviewAuthorityPosition:
    """One immutable position in one (Candidate, actor) authority history.

    Duplicates no referenced payload (AH-5): the decision kind, approved range, approved label, and
    approved rationale stay owned by the `ReviewDecision` and `ApprovedEditDecision` and are reached
    through the reference. Carries no status, currentness, wall-clock, execution provenance, or
    `DomainResult`.
    """

    identity: LectureReviewAuthorityPositionId
    candidate_id: LectureAnalysisEditCandidateId
    actor: HumanActorReference
    sequence: int
    review_decision_id: LectureReviewDecisionId
    previous_position_id: LectureReviewAuthorityPositionId | None = None
    position_contract_version: int = AUTHORITY_POSITION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.position_contract_version != AUTHORITY_POSITION_CONTRACT_VERSION:
            raise LectureReviewAuthorityError(
                "unsupported review authority position contract version"
            )
        if not isinstance(self.actor, HumanActorReference):
            raise LectureReviewAuthorityError(
                "review authority position requires a Human actor reference"
            )
        require_authority_actor(self.actor.value)
        sequence = require_sequence(self.sequence)
        if (sequence == 0) != (self.previous_position_id is None):
            raise LectureReviewAuthorityError(
                "the first position (sequence 0) has no previous; later positions require one"
            )
        if self.previous_position_id is not None and (
            self.previous_position_id == self.identity
        ):
            raise LectureReviewAuthorityError(
                "a review authority position must not supersede itself"
            )
        if self.identity != derive_authority_position_identity(
            self.candidate_id, self.actor, sequence
        ):
            raise LectureReviewAuthorityError(
                "review authority position identity must derive from its candidate, human actor, "
                "and history position"
            )


@dataclass(frozen=True, slots=True)
class AuthorityPositionPlan:
    """What an admission intends to do to one scope's history, computed before persisting."""

    position: LectureReviewAuthorityPosition
    outcome: AuthorityPositionOutcome

    @property
    def appends(self) -> bool:
        return self.outcome is AuthorityPositionOutcome.RECORDED


def plan_authority_position(
    *,
    candidate_id: LectureAnalysisEditCandidateId,
    actor: HumanActorReference,
    decision_id: LectureReviewDecisionId,
    head: LectureReviewAuthorityPosition | None,
) -> AuthorityPositionPlan:
    """AH-7's append rule as a pure function of the scope's current head.

    No history → start at `sequence` 0. The head already records this exact decision → reuse. A
    different decision → append at `sequence + 1` superseding the head. Nothing here consults a row
    count, wall clock, insertion order, or rowid.
    """

    if head is None:
        return AuthorityPositionPlan(
            position=LectureReviewAuthorityPosition(
                identity=derive_authority_position_identity(candidate_id, actor, 0),
                candidate_id=candidate_id,
                actor=actor,
                sequence=0,
                review_decision_id=decision_id,
            ),
            outcome=AuthorityPositionOutcome.RECORDED,
        )
    if head.review_decision_id == decision_id:
        return AuthorityPositionPlan(
            position=head, outcome=AuthorityPositionOutcome.REUSED
        )
    sequence = head.sequence + 1
    return AuthorityPositionPlan(
        position=LectureReviewAuthorityPosition(
            identity=derive_authority_position_identity(candidate_id, actor, sequence),
            candidate_id=candidate_id,
            actor=actor,
            sequence=sequence,
            review_decision_id=decision_id,
            previous_position_id=head.identity,
        ),
        outcome=AuthorityPositionOutcome.RECORDED,
    )


@dataclass(frozen=True, slots=True)
class CurrentReviewAuthority:
    """The derived current judgment of one (Candidate, actor) scope — never stored (AH-8)."""

    candidate_id: LectureAnalysisEditCandidateId
    actor: HumanActorReference
    position: LectureReviewAuthorityPosition
    decision: "LectureReviewDecision"
    approved: "LectureApprovedEditDecision | None"

    @property
    def sequence(self) -> int:
        return self.position.sequence

    @property
    def superseded_count(self) -> int:
        """How many earlier judgments this scope's current one supersedes."""

        return self.position.sequence


@dataclass(frozen=True, slots=True)
class CandidateAuthorityObservation:
    """A Candidate-level observation that deliberately arbitrates nothing (AH-9).

    With one actor it reports that actor's current judgment. With two or more it reports a `§3.12`
    Review Conflict and **no** current judgment: no priority among actors, no recency across actors,
    no role ranking. Surfacing the difference is the whole contract; resolving it is deferred.
    """

    candidate_id: LectureAnalysisEditCandidateId
    status: CandidateAuthorityStatus
    actors: tuple[HumanActorReference, ...]
    current: CurrentReviewAuthority | None

    @property
    def is_conflict(self) -> bool:
        return self.status is CandidateAuthorityStatus.CROSS_ACTOR_CONFLICT


__all__ = [
    "AUTHORITY_POSITION_CONTRACT_KIND",
    "AUTHORITY_POSITION_CONTRACT_VERSION",
    "LECTURE_REVIEW_AUTHORITY_POSITION_IDENTITY_PREFIX",
    "AuthorityPositionOutcome",
    "AuthorityPositionPlan",
    "CandidateAuthorityObservation",
    "CandidateAuthorityStatus",
    "CurrentReviewAuthority",
    "LectureReviewAuthorityError",
    "LectureReviewAuthorityPosition",
    "ReviewAuthorityConflictError",
    "derive_authority_position_identity",
    "plan_authority_position",
    "require_authority_actor",
    "require_canonical_authority_position_id",
    "require_sequence",
]
