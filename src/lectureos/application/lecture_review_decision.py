"""Review Foundation — effective-transcript generation (043 §7.5, GOAL-028).

The effective-transcript generation's canonical Review admission boundary, implementing the
Architect Decisions confirmed by `patches/PATCH-0033` (R-1…R-12). One explicit command records one
**human** judgment against exactly one current-generation Edit Candidate and appends one immutable
`ReviewDecision` plus — for `accept` and `modify` — exactly one immutable `ApprovedEditDecision`,
atomically.

**Nothing is reviewed here and nothing is edited here.** This boundary runs no UI, no external
Review API, no provider-assisted review, and no edit: the judgment is supplied by a caller acting as
Human Authority and is recorded verbatim as canonical Application-owned meaning. None of the three
decisions executes an edit (`§7.4` Decision Kind, inherited by R-8), and no cut, NLE operation,
rendering, export serialization, Review Session, Review Item, Review History model, revision,
withdrawal, or current-selection exists in this contract.

**Anchor (R-2).** Every `ReviewDecision` anchors to exactly one `LectureAnalysisEditCandidate`
(`042 §9.3`) — never the legacy `EditCandidate` (`042 §9.1`), and never directly to an Analysis
Finding, a `LectureAnalysisInputAdmission`, or a Lecture Segment. `§7.4`'s cardinality and direction
are unchanged; only the Candidate's *generation* changes.

**Current-only standing (R-3).** A stored Candidate's mere existence never suffices. Every command
re-derives the standing of the admission at the root of the chain —
`ReviewDecision → Edit Candidate → Analysis Finding → Lecture Analysis Input Admission` — through
the released GOAL-027/GOAL-025/GOAL-023 path, and admits only at `current`. A missing or malformed
Candidate reference is refused *before* standing is evaluated, never as a fourth standing value.

**No stored currentness (R-4).** Alternative A is preserved: no status field, state machine,
transition model, current flag, stale flag, or selection flag exists on either record. Review never
writes state onto the Candidate it anchors to.

**Historical semantics (R-5).** Existing Review records are never mutated, deleted, or rewritten
when upstream authority changes — a reject stays a durable, auditable human decision. Only *new*
admission against a non-current chain is refused, and returning authority restores admissibility.

**Execution-free provenance (R-6).** No `ProcessingRun`, `ProcessingUnit`, `UnitExecution`, RUNNING
state, or `DomainResult` is created, required, or fabricated. `§7.4` required each record to own its
own Domain Result identity *and* to chain them directly; the `§9.3` Candidate creates no Domain
Result, so in this generation there is nothing to own and nothing to reference. Provenance is the
contract kind (bound into each identity), the recorded contract version, and the immutable anchor.

**Upstream provenance through the anchor chain (R-7).** `§7.4`'s inherited Source Media and Source
Timeline provenance still applies; only its *form* changes. It is secured through
`ReviewDecision → Edit Candidate → Analysis Finding → Lecture Analysis Input Admission → current
applicable corrected revision → parent raw transcript → Source Timeline → Source Media`, so neither
record duplicates it as a column.

**No canonical ordinal (R-9).** Neither record stores a per-admission `sequence`. `040 §18`'s
per-anchor authority-history ordinal is a different concept and is neither introduced nor denied
here; it stays deferred (`§15.4`). Consequence, recorded deliberately: when a person reverses a
judgment (`accept` → `reject` → `accept`), the third submission converges on the first identity and
two contradicting records coexist as history. This contract does not adjudicate which is operative,
and `list_for_candidate` deliberately exposes only that they coexist.

**Identity, reachability, and replay (R-10, R-11).**

* `ReviewDecision` identity derives from the anchor Candidate, the decision kind, and the **human
  actor reference** — the actor must participate, or two people's identical-kind judgments would
  collide and Human Authority would lose its meaning.
* `ApprovedEditDecision` identity derives from its `ReviewDecision`, the anchor Candidate, and the
  entire approved snapshot.
* **Per row this is Option B**: every persisted canonical field of each record participates in that
  record's identity, so a divergent stored payload for an existing identity is structurally
  unreachable short of a hash collision.
* **Per admission this is Option A**, and it matters: the approved snapshot is canonical content of
  the *admission* that does **not** participate in the `ReviewDecision` identity. So a semantic
  mismatch is reachable through ordinary input — the same actor submitting `modify` twice on one
  Candidate with different approved values — and R-11 requires exactly what happens: an explicit
  conflict, never an overwrite, nothing written. Recording two differing approvals for one
  `ReviewDecision` is impossible by contract (`§7.4` allows at most one), and revising a human
  judgment is `§15.4`-deferred, so refusal is the only faithful outcome.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.review.identities import HumanActorReference

from .canonical_timeline_value import canonical_timeline_value
from .identities import (
    LectureAnalysisEditCandidateId,
    LectureApprovedEditDecisionId,
    LectureReviewDecisionId,
)
from .lecture_analysis_edit_candidate import (
    LectureAnalysisEditCandidate,
    LectureAnalysisEditCandidateError,
    LectureAnalysisEditCandidateService,
    require_canonical_candidate_id,
    require_canonical_candidate_type,
)
from .lecture_analysis_input_admission import AdmissionAuthorityMatch

LECTURE_REVIEW_DECISION_IDENTITY_PREFIX = "lecture-review-decision"
LECTURE_APPROVED_EDIT_DECISION_IDENTITY_PREFIX = "lecture-approved-edit-decision"

REVIEW_DECISION_CONTRACT_KIND = "lecture_review_decision"
REVIEW_DECISION_CONTRACT_VERSION = 1
APPROVED_EDIT_DECISION_CONTRACT_KIND = "lecture_approved_edit_decision"
APPROVED_EDIT_DECISION_CONTRACT_VERSION = 1


class LectureReviewError(ValueError):
    """A Review command that cannot proceed (malformed, unknown, or unsupported input)."""


class ReviewAnchorNotAdmissibleError(LectureReviewError):
    """The anchor Candidate's chain no longer binds the current effective authority."""


class ReviewConflictError(LectureReviewError):
    """An existing Review record with this identity records a divergent payload."""


class ReviewApprovalConflictError(ReviewConflictError):
    """This `ReviewDecision` already owns a different approved snapshot.

    The reachable arm of R-11's conflict branch (Option A at the admission level): the approved
    snapshot does not participate in the `ReviewDecision` identity, so the same actor submitting a
    second, differing `modify` for one Candidate lands on the existing decision. `§7.4` permits at
    most one `ApprovedEditDecision` per `ReviewDecision` and revision is `§15.4`-deferred, so the
    submission is refused and nothing is written.
    """


class ReviewDecisionKind(str, Enum):
    """`§7.4`'s closed first-slice human-action vocabulary, inherited unchanged by R-8.

    Deliberately re-declared here instead of imported from the legacy execution-coupled
    `application.edit_review` module: this generation must carry **no source-level dependency** on
    that module's execution boundary (`ExecutionQueryBoundary`, `ProcessingRunId`,
    `UnitExecutionId`). The two vocabularies must never drift, so a test asserts value-for-value
    equality with the released legacy enum.

    Closed set: unknown values are refused. No alias mapping, no coercion, no lowercasing into a
    valid value, and no provider- or interface-native term mapping. This closed human-action
    vocabulary does not change `042 §9.1`/`§9.3`'s **open** canonical Candidate Type contract.
    """

    ACCEPT = "accept"
    REJECT = "reject"
    MODIFY = "modify"


#: `§7.4` ApprovedEditDecision Creation, inherited by R-8: accept creates exactly one, modify
#: creates exactly one, reject creates none. No split, merge, or multi-output approval exists.
_APPROVING_KINDS = (ReviewDecisionKind.ACCEPT, ReviewDecisionKind.MODIFY)


class ReviewOutcome(str, Enum):
    RECORDED = "recorded"  # new immutable canonical Review record(s) were created
    REUSED = "reused"      # the identical canonical judgment already exists; no new row


def require_decision_kind(value: object) -> ReviewDecisionKind:
    """Admit exactly one of the three canonical tokens; refuse everything else.

    An exact match only: `"Accept"`, `" accept"`, `"ACCEPT"`, `"approve"`, and any
    interface-native synonym are refused rather than coerced (`§7.4` Decision Kind).
    """

    if isinstance(value, ReviewDecisionKind):
        return value
    for kind in ReviewDecisionKind:
        if value == kind.value and isinstance(value, str):
            return kind
    raise LectureReviewError(
        "review decision kind must be exactly one of 'accept', 'reject', or 'modify' "
        "(unknown values are refused, never coerced)"
    )


def require_human_actor(value: str) -> HumanActorReference:
    """The `§7.4` human actor reference, required as provenance and part of identity (R-10).

    Reuses the released Human Authority precedent (`040 §18`'s decision reviewer): a non-empty
    reference, stored verbatim and unnormalized. This boundary defines no UI authentication and no
    comprehensive authority-policy system, and an AI Candidate is never promoted to a decision — the
    actor is always the human whose judgment this record is.
    """

    if not isinstance(value, str) or not value.strip():
        raise LectureReviewError(
            "review decision requires a non-empty Human actor reference"
        )
    return HumanActorReference(value)


def require_approved_label(value: str) -> str:
    """The approved Candidate Type or approved edit label — one owned canonical key.

    `§7.4` names them as alternatives for a single owned value, not as two fields, so one field
    carries either and no second column or free-text alternative is introduced. Its grammar is the
    released open Application-owned key rule (`^[a-z][a-z0-9_]*$`) that `042 §9.3` uses for
    Candidate Type, so an approved label is expressible without inventing a vocabulary this
    Blueprint has not defined. Still an open vocabulary: never a closed enum.
    """

    try:
        return require_canonical_candidate_type(value)
    except LectureAnalysisEditCandidateError as error:
        raise LectureReviewError(
            "approved candidate type or edit label must be a canonical Application-owned token "
            "(^[a-z][a-z0-9_]*$)"
        ) from error


def require_approved_rationale(value: str) -> str:
    """The approved, human-reviewable rationale owned by the `ApprovedEditDecision`.

    Required, non-empty, stored verbatim and unnormalized, and it participates in that record's
    identity: an approval given for a different stated reason is a different approval.
    """

    if not isinstance(value, str) or not value.strip():
        raise LectureReviewError("approved rationale must not be empty")
    return value


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_bound(name: str, value: float) -> float:
    return canonical_timeline_value(
        value, error=LectureReviewError, subject=f"approved {name}"
    )


def normalize_approved_range(start: float, end: float) -> tuple[float, float]:
    """The released `042 §9.1`/`§9.3` range contract, reused verbatim for the approved range.

    Finite, non-negative, ``start <= end``, routed through the shared canonical primitive so an
    integral (`1`) or negative-zero (`-0.0`) spelling can never produce a row whose identity fails
    to re-derive. R-8 forbids adding media-duration validation, transcript-boundary alignment,
    containment against the Candidate's range, or range reconciliation here.
    """

    canonical_start = _canonical_bound("range start", start)
    canonical_end = _canonical_bound("range end", end)
    if canonical_start > canonical_end:
        raise LectureReviewError("approved range start must not be after end")
    return canonical_start, canonical_end


def derive_review_decision_identity(
    candidate_id: LectureAnalysisEditCandidateId,
    decision_kind: ReviewDecisionKind,
    actor: HumanActorReference,
) -> LectureReviewDecisionId:
    """Deterministic, Application-owned `ReviewDecision` identity (043 §7.5 R-10).

    Derives from the immutable anchor, the decision kind, and the human actor — every persisted
    canonical field of the record. Caller-owned identity is legacy-only; no provider identifier,
    execution identifier, `DomainResult`, UUID, timestamp, rowid, path, or mutable currentness
    participates, and no ordinal exists to participate (R-9).

    The approved snapshot deliberately does **not** participate: `§7.4` Modify Ownership makes the
    `ApprovedEditDecision` the sole canonical authority for those values, and binding them into this
    identity would represent the same canonical values in both records. The consequence — a
    reachable approval conflict — is handled explicitly by `ReviewApprovalConflictError`.
    """

    digest = hashlib.sha256(
        _canonical_json(
            {
                "contract": REVIEW_DECISION_CONTRACT_KIND,
                "contract_version": REVIEW_DECISION_CONTRACT_VERSION,
                "candidate": candidate_id.value,
                "decision_kind": decision_kind.value,
                "actor": actor.value,
            }
        ).encode("utf-8")
    ).hexdigest()
    return LectureReviewDecisionId(
        f"{LECTURE_REVIEW_DECISION_IDENTITY_PREFIX}:{digest}"
    )


def derive_approved_edit_decision_identity(
    review_decision_id: LectureReviewDecisionId,
    candidate_id: LectureAnalysisEditCandidateId,
    approved_decision_kind: ReviewDecisionKind,
    approved_range_start: float,
    approved_range_end: float,
    approved_label: str,
    approved_rationale: str,
) -> LectureApprovedEditDecisionId:
    """Deterministic, Application-owned `ApprovedEditDecision` identity (043 §7.5 R-10).

    Derives from the originating `ReviewDecision`, the referenced Candidate, and the **whole** owned
    approved snapshot, so every persisted canonical field of this record participates (Option B per
    row).
    """

    canonical_start, canonical_end = normalize_approved_range(
        approved_range_start, approved_range_end
    )
    digest = hashlib.sha256(
        _canonical_json(
            {
                "contract": APPROVED_EDIT_DECISION_CONTRACT_KIND,
                "contract_version": APPROVED_EDIT_DECISION_CONTRACT_VERSION,
                "review_decision": review_decision_id.value,
                "candidate": candidate_id.value,
                "approved_decision_kind": approved_decision_kind.value,
                "approved_range_start": canonical_start,
                "approved_range_end": canonical_end,
                "approved_label": approved_label,
                "approved_rationale": approved_rationale,
            }
        ).encode("utf-8")
    ).hexdigest()
    return LectureApprovedEditDecisionId(
        f"{LECTURE_APPROVED_EDIT_DECISION_IDENTITY_PREFIX}:{digest}"
    )


def _require_canonical_hash_identity(value: str, prefix: str, subject: str):
    if (
        not isinstance(value, str)
        or not value.startswith(prefix + ":")
        or len(value) != len(prefix) + 1 + 64
    ):
        raise LectureReviewError(
            f"{subject} identity is malformed (expected '{prefix}:<64 hex digest>')"
        )
    return value


def require_canonical_review_decision_id(value: str) -> LectureReviewDecisionId:
    return LectureReviewDecisionId(
        _require_canonical_hash_identity(
            value, LECTURE_REVIEW_DECISION_IDENTITY_PREFIX, "lecture review decision"
        )
    )


def require_canonical_approved_edit_decision_id(
    value: str,
) -> LectureApprovedEditDecisionId:
    return LectureApprovedEditDecisionId(
        _require_canonical_hash_identity(
            value,
            LECTURE_APPROVED_EDIT_DECISION_IDENTITY_PREFIX,
            "lecture approved edit decision",
        )
    )


def _require_anchor_identity(value: str) -> LectureAnalysisEditCandidateId:
    """Validate the anchor reference, reporting it as a *Review* refusal.

    The released Candidate-identity rule is reused verbatim, but its error is re-raised in this
    boundary's own type: a malformed anchor is a refusal of the reference supplied to this command
    (R-3), never a fourth admission standing value.
    """

    try:
        return require_canonical_candidate_id(value)
    except LectureAnalysisEditCandidateError as error:
        raise LectureReviewError(str(error)) from error


@dataclass(frozen=True, slots=True)
class LectureReviewDecision:
    """One immutable human judgment on exactly one current-generation Edit Candidate.

    Records the human's judgment and the Candidate anchor and nothing else: no free-text decision
    note, no modify payload (the `ApprovedEditDecision` owns the approved values), no status field,
    no Review Session identity, no Review History identity, no ordinal (R-9), no execution or
    `DomainResult` provenance (R-6), and no duplicated upstream provenance (R-7).
    """

    identity: LectureReviewDecisionId
    candidate_id: LectureAnalysisEditCandidateId
    decision_kind: ReviewDecisionKind
    actor: HumanActorReference
    review_contract_version: int = REVIEW_DECISION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.review_contract_version != REVIEW_DECISION_CONTRACT_VERSION:
            raise LectureReviewError("unsupported review decision contract version")
        kind = require_decision_kind(self.decision_kind)
        object.__setattr__(self, "decision_kind", kind)
        if not isinstance(self.actor, HumanActorReference):
            raise LectureReviewError(
                "review decision requires a Human actor reference"
            )
        require_human_actor(self.actor.value)
        if self.identity != derive_review_decision_identity(
            self.candidate_id, kind, self.actor
        ):
            raise LectureReviewError(
                "review decision identity must derive from its anchoring edit candidate, "
                "decision kind, and human actor reference"
            )

    @property
    def creates_approved_edit_decision(self) -> bool:
        """Derived from the kind alone — never a stored flag (R-4)."""

        return self.decision_kind in _APPROVING_KINDS


@dataclass(frozen=True, slots=True)
class LectureApprovedEditDecision:
    """The self-contained approved snapshot owned by one `ReviewDecision`'s approval.

    `§7.4` Modify Ownership, inherited by R-8: the approved range, the approved Candidate Type or
    edit label, and the approved rationale live **only** here, and the original Candidate is never
    mutated. Adds no executable edit semantics — no cut or delete command, NLE operation, rendering
    behaviour, export serialization, or automatic edit application.
    """

    identity: LectureApprovedEditDecisionId
    review_decision_id: LectureReviewDecisionId
    candidate_id: LectureAnalysisEditCandidateId
    approved_decision_kind: ReviewDecisionKind
    approved_range_start: float
    approved_range_end: float
    approved_label: str
    approved_rationale: str
    approved_contract_version: int = APPROVED_EDIT_DECISION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.approved_contract_version != APPROVED_EDIT_DECISION_CONTRACT_VERSION:
            raise LectureReviewError(
                "unsupported approved edit decision contract version"
            )
        kind = require_decision_kind(self.approved_decision_kind)
        if kind not in _APPROVING_KINDS:
            raise LectureReviewError(
                "approved edit decisions exist only for 'accept' or 'modify'"
            )
        object.__setattr__(self, "approved_decision_kind", kind)
        require_approved_label(self.approved_label)
        require_approved_rationale(self.approved_rationale)
        start, end = normalize_approved_range(
            self.approved_range_start, self.approved_range_end
        )
        object.__setattr__(self, "approved_range_start", start)
        object.__setattr__(self, "approved_range_end", end)
        if self.identity != derive_approved_edit_decision_identity(
            self.review_decision_id,
            self.candidate_id,
            kind,
            start,
            end,
            self.approved_label,
            self.approved_rationale,
        ):
            raise LectureReviewError(
                "approved edit decision identity must derive from its review decision, edit "
                "candidate, and the whole approved snapshot"
            )


@dataclass(frozen=True, slots=True)
class ReviewAdmissionResult:
    """One Review command outcome: the records, the outcome, and the anchor observed."""

    decision: LectureReviewDecision
    approved: LectureApprovedEditDecision | None
    outcome: ReviewOutcome
    candidate: LectureAnalysisEditCandidate


class ReviewQuery(Protocol):
    def get_decision(self, identity): ...

    def get_approved_for_decision(self, identity): ...

    def list_decisions_for_candidate(self, candidate_id) -> tuple: ...


class AtomicReviewPersistence(Protocol):
    def persist_review(
        self,
        *,
        decision: LectureReviewDecision,
        approved: LectureApprovedEditDecision | None,
    ) -> None: ...


class LectureReviewApplicationService:
    """The single canonical Review admission path of the effective-transcript generation.

    Canonical admission is owned by the Application layer: an interface, UI, or external API layer
    never persists a canonical Review record directly (`§7.4` Admission Boundary, inherited by R-8).
    """

    def __init__(
        self,
        candidate_service: LectureAnalysisEditCandidateService,
        review_query: ReviewQuery,
        persistence: AtomicReviewPersistence,
    ) -> None:
        self._candidates = candidate_service
        self._reviews = review_query
        self._persistence = persistence

    # -- explicit Review admission command -------------------------------------------------------

    def admit_review_decision(
        self,
        *,
        candidate_id: str,
        decision_kind: object,
        actor: str,
        approved_range_start: float | None = None,
        approved_range_end: float | None = None,
        approved_label: str | None = None,
        approved_rationale: str | None = None,
    ) -> ReviewAdmissionResult:
        """Record one human judgment on a Candidate whose chain is CURRENT.

        Order (043 §7.5): validate the judgment, resolve the canonical Candidate, re-derive the
        standing of the admission at the root of its chain, build the approved snapshot, derive both
        identities, then persist atomically and converge on replay.

        `accept` inherits the Candidate's proposal as the approved snapshot and takes no approved
        arguments. `modify` requires the **complete** approved replacement — range, label, and
        rationale together — because `§7.4` Modify Ownership forbids expressing it as a loose patch
        or delta. `reject` takes none and creates no `ApprovedEditDecision`.
        """

        # The judgment first: a malformed command never reaches the anchor or the repository.
        kind = require_decision_kind(decision_kind)
        actor_reference = require_human_actor(actor)
        approved_arguments = (
            approved_range_start,
            approved_range_end,
            approved_label,
            approved_rationale,
        )
        if kind is ReviewDecisionKind.MODIFY:
            if any(argument is None for argument in approved_arguments):
                raise LectureReviewError(
                    "modify records a complete approved replacement: approved range start, range "
                    "end, candidate type or label, and rationale are all required"
                )
        elif any(argument is not None for argument in approved_arguments):
            raise LectureReviewError(
                f"'{kind.value}' takes no approved values: accept inherits the candidate's "
                "proposal verbatim and reject approves nothing"
            )

        candidate = self._require_current_chain(candidate_id)

        decision = LectureReviewDecision(
            identity=derive_review_decision_identity(
                candidate.identity, kind, actor_reference
            ),
            candidate_id=candidate.identity,
            decision_kind=kind,
            actor=actor_reference,
        )
        approved = self._build_approved(
            decision=decision,
            candidate=candidate,
            kind=kind,
            approved_range_start=approved_range_start,
            approved_range_end=approved_range_end,
            approved_label=approved_label,
            approved_rationale=approved_rationale,
        )

        existing = self._reviews.get_decision(decision.identity)
        if existing is not None:
            return self._reuse(existing, decision, approved, candidate)
        try:
            self._persistence.persist_review(decision=decision, approved=approved)
        except PersistenceIdentityCollisionError:
            # A near-concurrent identical command won the insert; converge on its records.
            resolved = self._reviews.get_decision(decision.identity)
            if resolved is not None:
                return self._reuse(resolved, decision, approved, candidate)
            raise
        return ReviewAdmissionResult(
            decision=decision,
            approved=approved,
            outcome=ReviewOutcome.RECORDED,
            candidate=candidate,
        )

    def _build_approved(
        self,
        *,
        decision: LectureReviewDecision,
        candidate: LectureAnalysisEditCandidate,
        kind: ReviewDecisionKind,
        approved_range_start: float | None,
        approved_range_end: float | None,
        approved_label: str | None,
        approved_rationale: str | None,
    ) -> LectureApprovedEditDecision | None:
        """`§7.4` ApprovedEditDecision Creation: accept one, modify one, reject none.

        For `accept` the approved snapshot **is** the Candidate's proposal — the human accepted it
        as the approved editing intent — so it is copied from the immutable anchor rather than
        re-supplied. For `modify` the caller's complete replacement is recorded instead; the
        original Candidate is never touched either way.
        """

        if kind not in _APPROVING_KINDS:
            return None
        if kind is ReviewDecisionKind.ACCEPT:
            start, end = candidate.range_start, candidate.range_end
            label: str = candidate.candidate_type
            rationale: str = candidate.rationale
        else:
            start, end = normalize_approved_range(
                approved_range_start, approved_range_end
            )
            label = require_approved_label(approved_label)
            rationale = require_approved_rationale(approved_rationale)
        return LectureApprovedEditDecision(
            identity=derive_approved_edit_decision_identity(
                decision.identity, candidate.identity, kind, start, end, label, rationale
            ),
            review_decision_id=decision.identity,
            candidate_id=candidate.identity,
            approved_decision_kind=kind,
            approved_range_start=start,
            approved_range_end=end,
            approved_label=label,
            approved_rationale=rationale,
        )

    def _require_current_chain(self, candidate_id: str) -> LectureAnalysisEditCandidate:
        """Resolve the anchor Candidate and re-derive its chain's standing (043 §7.5 R-3).

        The standing lives at the **root** of the chain — Review → Candidate → Finding →
        Admission — and is obtained through the released GOAL-027/GOAL-025/GOAL-023 path, never by
        re-resolving authority here. A missing or malformed reference is refused *before* standing
        is evaluated.
        """

        identity = _require_anchor_identity(candidate_id)
        candidate = self._candidates.get(identity.value)
        if candidate is None:
            raise LectureReviewError("unknown lecture analysis edit candidate")
        match = self._anchor_status_of(candidate)
        if match is not AdmissionAuthorityMatch.CURRENT:
            raise ReviewAnchorNotAdmissibleError(
                "review decisions may only be admitted against an edit candidate whose analysis "
                f"input admission still binds the current effective authority (derived standing: "
                f"{match.value}); the candidate and every existing review record remain valid "
                "immutable history"
            )
        return candidate

    def _anchor_status_of(
        self, candidate: LectureAnalysisEditCandidate
    ) -> AdmissionAuthorityMatch:
        try:
            return self._candidates.anchor_status(candidate)
        except LectureAnalysisEditCandidateError as error:
            # The Candidate's own upstream is missing — a repository integrity failure, reported in
            # this boundary's error family rather than leaking the sibling's type.
            raise LectureReviewError(str(error)) from error

    def _reuse(
        self,
        existing: LectureReviewDecision,
        expected: LectureReviewDecision,
        approved: LectureApprovedEditDecision | None,
        candidate: LectureAnalysisEditCandidate,
    ) -> ReviewAdmissionResult:
        """Converge on an identical canonical judgment; refuse a divergent one (R-11).

        Two distinct checks, for two distinct reachability classes:

        * The decision row itself is Option B — every persisted canonical field participates in its
          identity, so a divergence here is structurally unreachable and the guard is retained
          because R-10 requires it under Option B and because it would still hold if identity
          composition ever narrowed.
        * The approved snapshot is Option A — it does not participate in the decision identity, so a
          second differing `modify` by the same actor reaches this branch through ordinary input and
          must be an explicit conflict.
        """

        if (
            existing.candidate_id != expected.candidate_id
            or existing.decision_kind != expected.decision_kind
            or existing.actor != expected.actor
            or existing.review_contract_version != expected.review_contract_version
        ):
            raise ReviewConflictError(
                "an existing review decision with this identity records a different judgment "
                "(repository integrity failure); it is never overwritten"
            )
        stored_approved = self._reviews.get_approved_for_decision(existing.identity)
        if approved is None:
            if stored_approved is not None:
                raise ReviewConflictError(
                    "a reject review decision must own no approved edit decision "
                    "(repository integrity failure); it is never overwritten"
                )
        elif stored_approved is None:
            raise ReviewConflictError(
                "an approving review decision exists without its approved edit decision; a "
                "partially recorded review admission is never treated as valid"
            )
        elif stored_approved != approved:
            raise ReviewApprovalConflictError(
                "this review decision already owns a different approved snapshot; one review "
                "decision owns at most one approved edit decision and revising a human judgment "
                "is not part of this contract, so nothing is written"
            )
        return ReviewAdmissionResult(
            decision=existing,
            approved=stored_approved,
            outcome=ReviewOutcome.REUSED,
            candidate=candidate,
        )

    # -- queries (derived; never mutate history) -------------------------------------------------

    def get(self, decision_id: str) -> LectureReviewDecision | None:
        return self._reviews.get_decision(
            require_canonical_review_decision_id(decision_id)
        )

    def get_approved(self, decision_id: str) -> LectureApprovedEditDecision | None:
        return self._reviews.get_approved_for_decision(
            require_canonical_review_decision_id(decision_id)
        )

    def list_for_candidate(self, candidate_id: str) -> tuple[LectureReviewDecision, ...]:
        """Every human judgment recorded against one Candidate, as coexisting history.

        The order is a deterministic presentation order, never a canonical ordinal (R-9), and this
        method deliberately does **not** answer which judgment is currently operative: reversed
        judgments coexist and current-selection is `§15.4`-deferred.
        """

        return self._reviews.list_decisions_for_candidate(
            _require_anchor_identity(candidate_id)
        )

    def anchor_status(
        self, decision: LectureReviewDecision
    ) -> AdmissionAuthorityMatch:
        """Derived only: does this decision's chain still bind the current authority?

        A decision whose chain became superseded is NOT stale data and NOT corruption — it is valid
        immutable history (R-5). Nothing is mutated by this observation and no such state is ever
        stored on either record (R-4).
        """

        candidate = self._candidates.get(decision.candidate_id.value)
        if candidate is None:
            raise LectureReviewError(
                "review decision anchor edit candidate is missing "
                "(repository integrity failure)"
            )
        return self._anchor_status_of(candidate)


__all__ = [
    "APPROVED_EDIT_DECISION_CONTRACT_KIND",
    "APPROVED_EDIT_DECISION_CONTRACT_VERSION",
    "LECTURE_APPROVED_EDIT_DECISION_IDENTITY_PREFIX",
    "LECTURE_REVIEW_DECISION_IDENTITY_PREFIX",
    "REVIEW_DECISION_CONTRACT_KIND",
    "REVIEW_DECISION_CONTRACT_VERSION",
    "AtomicReviewPersistence",
    "LectureApprovedEditDecision",
    "LectureReviewApplicationService",
    "LectureReviewDecision",
    "LectureReviewError",
    "ReviewAdmissionResult",
    "ReviewAnchorNotAdmissibleError",
    "ReviewApprovalConflictError",
    "ReviewConflictError",
    "ReviewDecisionKind",
    "ReviewOutcome",
    "ReviewQuery",
    "derive_approved_edit_decision_identity",
    "derive_review_decision_identity",
    "normalize_approved_range",
    "require_approved_label",
    "require_approved_rationale",
    "require_canonical_approved_edit_decision_id",
    "require_canonical_review_decision_id",
    "require_decision_kind",
    "require_human_actor",
]
