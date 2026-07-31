"""Edit Export Assembly — effective-transcript generation (044 §23, GOAL-030).

Implements the Architect Decisions confirmed by `patches/PATCH-0035` (EA-1…EA-11): the Export
**admission boundary** of the effective-transcript generation, and nothing downstream of it.

**Members are `ApprovedEditDecision` records directly (EA-2).** `044 §19`'s
`ApprovedEditExportRepresentation` atom stage is *not* reproduced here. Its D-2 minimum — an owned
Domain Result identity, execution provenance, and a per-admission ordinal — is exactly what
`043 §7.5` R-6 declared unsatisfiable in this generation and R-9 declared meaningless, and its D-3
purpose (owning the approved snapshot) is already discharged by the `ApprovedEditDecision` under R-8.
`§20` A-1's cardinality and direction are unchanged: one Assembly, one Source Timeline, upstream
consumed read-only. Only the generation of the record occupying the member position changes.

**Membership is total and derived, never chosen (EA-3, EA-7).** One Assembly denotes *every*
export-eligible approved edit of its Source Timeline. There is no subset, filter, ranking, selection
record, or selection flag — and no Final Selection concept exists in this pipeline at all (EA-11).

**Export eligibility is the conjunction of three conditions (EA-4).** An `ApprovedEditDecision` is
eligible when it is owned by its Candidate's current operative judgment (`043 §7.6` AH-8), that
Candidate has exactly one actor holding authority history (AH-9), and the derived admission standing
at the root of the anchor chain is `current` (`§7.5` R-3). `reject` owns no approval and is outside
the predicate by construction.

**Nothing is arbitrated (EA-5).** Where AH-9 derives no current operative judgment, neither does
this module. No priority among actors, no recency across actors, no role ranking, no merge, no
selection.

**Nothing is executed (EA-8).** No `ProcessingRun`, `ProcessingUnit`, `UnitExecution`, RUNNING state,
or `DomainResult` is required, referenced, or fabricated. Construction is deterministic and
replay-safe: it reads no wall clock and no randomness, and the same persisted state yields the same
Assembly.

**Three product policies are deliberately absent.** `PATCH-0035` leaves undecided (a) the product
behaviour when a Source Timeline holds a cross-actor Conflict, (b) whether overlapping approved edits
require adjudication, and (c) how a scope with no eligible member is treated. This module therefore
**declines to act** in those situations rather than choosing one — see
`EditExportUndecidedPolicyError`. Deriving the observation is always permitted; only admission stops.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.review.identities import HumanActorReference
from lectureos.execution.identities import SourceTimelineId

from .identities import (
    LectureAnalysisEditCandidateId,
    LectureApprovedEditDecisionId,
    LectureEditExportAssemblyId,
)
from .lecture_analysis_input_admission import AdmissionAuthorityMatch
from .lecture_review_decision import (
    CandidateAuthorityStatus,
    LectureApprovedEditDecision,
    LectureReviewApplicationService,
)

LECTURE_EDIT_EXPORT_ASSEMBLY_IDENTITY_PREFIX = "lecture-edit-export-assembly"

EDIT_EXPORT_ASSEMBLY_CONTRACT_KIND = "lecture_edit_export_assembly"
EDIT_EXPORT_ASSEMBLY_CONTRACT_VERSION = 1


class LectureEditExportAssemblyError(ValueError):
    """An Edit Export Assembly operation that cannot proceed."""


class EditExportAssemblyConflictError(LectureEditExportAssemblyError):
    """A different Assembly already holds this identity.

    The released collision-convergence idiom (`040 §18` H-9, `043 §7.5` R-11): an identical
    re-admission converges on the stored Assembly, a semantically different one is refused and
    nothing is overwritten.
    """


class EditExportUndecidedPolicyError(LectureEditExportAssemblyError):
    """The situation reached is one `PATCH-0035` deliberately left to a future approved PATCH.

    **This is not a product refusal.** It does not mean "this timeline cannot be exported"; it means
    the contract does not yet say what should happen, and `044 §23`'s Deferred section prohibits an
    implementation from settling the question by picking a behaviour and shipping it — the chosen
    behaviour would be read back as the contract. It is the runtime form of the AGENTS.md Stop
    Condition "product policy materially undefined by current contracts".

    Two situations raise it, both named by `044 §23`'s Deferred section:

    - the Source Timeline holds at least one Candidate in a `§3.12` cross-actor Review Conflict, so
      whether an Assembly is admitted at all, admitted without that Candidate, or refused outright is
      undecided;
    - the derived scope has no eligible member, so whether a zero-member Assembly, an explicit
      refusal, or something else is correct is undecided.

    Observing the scope is always permitted and never raises this — only admission stops.
    """


class ExportEligibility(str, Enum):
    """Why one `ApprovedEditDecision` is or is not export-eligible (EA-4) — derived, never stored.

    This is the *export eligibility* vocabulary and is deliberately distinct from the released
    three-value **admission standing** vocabulary of `043 §7.5` R-3
    (`current` / `superseded_by_authority_change` / `current_authority_ineligible`), which this
    module reads but never extends. Two members below carry a standing value as a *reason*; that
    reports which standing caused ineligibility and adds no fourth standing.
    """

    ELIGIBLE = "eligible"
    NO_RECORDED_AUTHORITY = "no_recorded_authority"
    CROSS_ACTOR_CONFLICT = "cross_actor_conflict"
    CURRENT_JUDGMENT_APPROVES_NOTHING = "current_judgment_approves_nothing"
    SUPERSEDED_BY_AUTHORITY_CHANGE = "superseded_by_authority_change"
    CURRENT_AUTHORITY_INELIGIBLE = "current_authority_ineligible"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def require_source_timeline(value: str) -> SourceTimelineId:
    if not isinstance(value, str) or not value.strip():
        raise LectureEditExportAssemblyError(
            "edit export assembly requires a non-empty Source Timeline identity"
        )
    return SourceTimelineId(value)


def derive_edit_export_assembly_identity(
    source_timeline_id: SourceTimelineId,
    approved_edit_decision_ids: tuple[LectureApprovedEditDecisionId, ...],
) -> LectureEditExportAssemblyId:
    """Deterministic, Application-owned Assembly identity (EA-10).

    Binds the Source Timeline anchor and the exact membership. Both are required: membership is
    derived and total (EA-3), so an authority change upstream legitimately changes what a *new*
    Assembly gathers. Binding only the timeline would make that second, different Assembly collide
    with the first and be unrecordable; binding the membership makes an identical re-admission
    converge and a genuinely different scope a new immutable record.

    No provider identifier, execution identifier, `DomainResult`, UUID, timestamp, wall clock,
    rowid, path, or mutable currentness participates (`043 §7.5` R-10, `§7.6` AH-11, EA-8).
    """

    digest = hashlib.sha256(
        _canonical_json(
            {
                "contract": EDIT_EXPORT_ASSEMBLY_CONTRACT_KIND,
                "contract_version": EDIT_EXPORT_ASSEMBLY_CONTRACT_VERSION,
                "source_timeline": source_timeline_id.value,
                "members": [identity.value for identity in approved_edit_decision_ids],
            }
        ).encode("utf-8")
    ).hexdigest()
    return LectureEditExportAssemblyId(
        f"{LECTURE_EDIT_EXPORT_ASSEMBLY_IDENTITY_PREFIX}:{digest}"
    )


def require_canonical_assembly_id(value: str) -> LectureEditExportAssemblyId:
    prefix = LECTURE_EDIT_EXPORT_ASSEMBLY_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise LectureEditExportAssemblyError(
            "lecture edit export assembly identity is malformed "
            "(expected 'lecture-edit-export-assembly:<64 hex digest>')"
        )
    return LectureEditExportAssemblyId(value)


def canonical_member_order(
    approved: tuple[LectureApprovedEditDecision, ...],
) -> tuple[LectureApprovedEditDecision, ...]:
    """A deterministic member order, by approved decision identity.

    `044 §23`'s Deferred section requires a deterministic order for `§20` A-8 replay-safety and fixes
    it as a **presentation** matter: it is never an execution order, a timeline order, or an overlap
    order (`§22` C-3 idiom). Because the order is a pure function of the member set, it adds no
    information to the identity beyond the set itself.
    """

    return tuple(sorted(approved, key=lambda decision: decision.identity.value))


@dataclass(frozen=True, slots=True)
class LectureEditExportAssemblyMember:
    """One member position — a **reference**, never a copy of the approved snapshot.

    `044 §20` A-10 has the Assembly reference its members without restating their owned snapshots as
    new authority, and `§23` EA-2 keeps this generation's "inherit through the anchor, never
    duplicate" idiom (`042 §8.2` D-2, `§9.3` C-8, `043 §7.5` R-7). The approved kind, range, label,
    and rationale stay owned by the `ApprovedEditDecision`.
    """

    assembly_id: LectureEditExportAssemblyId
    ordinal: int
    approved_edit_decision_id: LectureApprovedEditDecisionId

    def __post_init__(self) -> None:
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool):
            raise LectureEditExportAssemblyError(
                "edit export assembly member ordinal must be an integer"
            )
        if self.ordinal < 0:
            raise LectureEditExportAssemblyError(
                "edit export assembly member ordinal must be non-negative"
            )


@dataclass(frozen=True, slots=True)
class LectureEditExportAssembly:
    """A durable, immutable, insert-only, identity-owning, provenance-bearing Export Scope.

    Owns its identity, its single Source Timeline anchor, and its ordered membership. Owns **no**
    status, lifecycle, currentness, selection flag, wall clock, execution provenance, or
    `DomainResult` (EA-7, EA-8; `§20` A-12). Source Media provenance is reached through the anchor
    chain rather than denormalized — `§23` EA-8 leaves that an implementation choice, and not copying
    keeps the released "inherit, never duplicate" idiom intact.
    """

    identity: LectureEditExportAssemblyId
    source_timeline_id: SourceTimelineId
    members: tuple[LectureEditExportAssemblyMember, ...]
    assembly_contract_version: int = EDIT_EXPORT_ASSEMBLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.assembly_contract_version != EDIT_EXPORT_ASSEMBLY_CONTRACT_VERSION:
            raise LectureEditExportAssemblyError(
                "unsupported edit export assembly contract version"
            )
        require_source_timeline(self.source_timeline_id.value)
        if not self.members:
            # Not a policy about empty scopes: this guards the *record*, whose identity binds a
            # membership. Whether an empty scope should yield an Assembly at all is undecided and
            # is refused earlier, by the service, as an undecided-policy situation.
            raise LectureEditExportAssemblyError(
                "an edit export assembly record must carry at least one member"
            )
        ordinals = [member.ordinal for member in self.members]
        if ordinals != list(range(len(self.members))):
            raise LectureEditExportAssemblyError(
                "edit export assembly member ordinals must be contiguous from zero"
            )
        identities = [member.approved_edit_decision_id.value for member in self.members]
        if len(set(identities)) != len(identities):
            raise LectureEditExportAssemblyError(
                "an approved edit decision must not appear twice in one assembly"
            )
        if any(member.assembly_id != self.identity for member in self.members):
            raise LectureEditExportAssemblyError(
                "edit export assembly members must belong to their assembly"
            )
        expected = derive_edit_export_assembly_identity(
            self.source_timeline_id,
            tuple(member.approved_edit_decision_id for member in self.members),
        )
        if self.identity != expected:
            raise LectureEditExportAssemblyError(
                "edit export assembly identity must derive from its Source Timeline and its exact "
                "membership"
            )

    @property
    def member_ids(self) -> tuple[LectureApprovedEditDecisionId, ...]:
        return tuple(member.approved_edit_decision_id for member in self.members)


@dataclass(frozen=True, slots=True)
class CandidateExportStanding:
    """One Candidate's derived contribution to the scope — an observation, never a decision."""

    candidate_id: LectureAnalysisEditCandidateId
    eligibility: ExportEligibility
    actors: tuple[HumanActorReference, ...]
    approved: LectureApprovedEditDecision | None

    @property
    def is_eligible(self) -> bool:
        return self.eligibility is ExportEligibility.ELIGIBLE

    @property
    def is_conflict(self) -> bool:
        return self.eligibility is ExportEligibility.CROSS_ACTOR_CONFLICT


@dataclass(frozen=True, slots=True)
class ExportScopeObservation:
    """The derived export scope of one Source Timeline (EA-3, EA-4) — nothing is stored.

    Reports every Candidate on the timeline with its eligibility, so an interface can show a person
    both what would be exported and what is being held back and why. It arbitrates nothing and
    decides nothing: `conflicts` is surfaced, never resolved (EA-5).
    """

    source_timeline_id: SourceTimelineId
    standings: tuple[CandidateExportStanding, ...]

    @property
    def eligible(self) -> tuple[LectureApprovedEditDecision, ...]:
        return tuple(
            standing.approved
            for standing in self.standings
            if standing.is_eligible and standing.approved is not None
        )

    @property
    def conflicts(self) -> tuple[CandidateExportStanding, ...]:
        return tuple(standing for standing in self.standings if standing.is_conflict)

    @property
    def has_conflict(self) -> bool:
        return bool(self.conflicts)

    @property
    def is_admissible(self) -> bool:
        """True only for the situation `044 §23` fully defines.

        False does **not** mean "refused": it means one of the two undecided situations has been
        reached and admission must stop rather than pick a behaviour.
        """

        return bool(self.eligible) and not self.has_conflict


class AssemblyOutcome(str, Enum):
    ADMITTED = "admitted"  # a new immutable Assembly was recorded
    REUSED = "reused"      # this exact scope is already recorded; nothing was written


@dataclass(frozen=True, slots=True)
class AssemblyAdmissionResult:
    assembly: LectureEditExportAssembly
    outcome: AssemblyOutcome
    observation: ExportScopeObservation


class EditExportScopeQuery(Protocol):
    def candidate_ids_for_source_timeline(
        self, source_timeline_id: SourceTimelineId
    ) -> tuple[LectureAnalysisEditCandidateId, ...]: ...


class EditExportAssemblyQuery(Protocol):
    def get_assembly(self, identity): ...

    def list_members(self, identity) -> tuple: ...

    def list_assemblies_for_timeline(self, source_timeline_id) -> tuple: ...


class AtomicEditExportAssemblyPersistence(Protocol):
    def persist_assembly(self, assembly: LectureEditExportAssembly) -> None: ...


class LectureEditExportAssemblyService:
    """Admits one immutable Edit Export Assembly for one Source Timeline (044 §23).

    Reads the released Review services rather than re-deriving authority or standing: the current
    operative judgment comes from `observe_candidate_authority` (`043 §7.6` AH-8/AH-9) and the chain
    standing from `anchor_status` (`§7.5` R-3). Nothing here reimplements either resolver.
    """

    def __init__(
        self,
        *,
        review_service: LectureReviewApplicationService,
        scope_query: EditExportScopeQuery,
        assembly_query: EditExportAssemblyQuery,
        persistence: AtomicEditExportAssemblyPersistence,
    ) -> None:
        self._reviews = review_service
        self._scope = scope_query
        self._assemblies = assembly_query
        self._persistence = persistence

    def observe_scope(self, source_timeline_id: str) -> ExportScopeObservation:
        """Derive the export scope of one Source Timeline. Always permitted, never mutating.

        Observation is not gated on standing or on the undecided policies: `043 §7.6` AH-10 permits
        observing an ineligible chain, and a person must be able to see a Conflict in order to
        resolve it in Review.
        """

        timeline = require_source_timeline(source_timeline_id)
        standings = tuple(
            self._standing_of(candidate_id)
            for candidate_id in self._scope.candidate_ids_for_source_timeline(timeline)
        )
        return ExportScopeObservation(
            source_timeline_id=timeline, standings=standings
        )

    def _standing_of(
        self, candidate_id: LectureAnalysisEditCandidateId
    ) -> CandidateExportStanding:
        """EA-4's three conditions, evaluated in the order that makes each reason reachable."""

        observation = self._reviews.observe_candidate_authority(candidate_id.value)
        if observation.status is CandidateAuthorityStatus.NO_HISTORY:
            # EA-9: a judgment admitted before PATCH-0034 carries no position. Not corruption, and
            # emphatically not "no judgment exists" — only "no recorded authority history".
            return CandidateExportStanding(
                candidate_id=candidate_id,
                eligibility=ExportEligibility.NO_RECORDED_AUTHORITY,
                actors=observation.actors,
                approved=None,
            )
        if observation.status is CandidateAuthorityStatus.CROSS_ACTOR_CONFLICT:
            # EA-4(ii)/EA-5: AH-9 derives no current operative judgment, so neither do we.
            return CandidateExportStanding(
                candidate_id=candidate_id,
                eligibility=ExportEligibility.CROSS_ACTOR_CONFLICT,
                actors=observation.actors,
                approved=None,
            )
        current = observation.current
        if current is None:  # pragma: no cover - single_actor always resolves a current judgment
            raise LectureEditExportAssemblyError(
                "review authority observation is inconsistent (repository integrity failure)"
            )
        if current.approved is None:
            # The current judgment is `reject`; it owns no approval, so there is nothing to export.
            # `§19` D-7's rule holds without being restated as a filter.
            return CandidateExportStanding(
                candidate_id=candidate_id,
                eligibility=ExportEligibility.CURRENT_JUDGMENT_APPROVES_NOTHING,
                actors=observation.actors,
                approved=None,
            )
        match = self._reviews.anchor_status(current.decision)
        if match is not AdmissionAuthorityMatch.CURRENT:
            # EA-4(iii). The released three-value standing vocabulary is read, never extended, and
            # the approval stays valid immutable history (`§7.5` R-5).
            return CandidateExportStanding(
                candidate_id=candidate_id,
                eligibility=ExportEligibility(match.value),
                actors=observation.actors,
                approved=None,
            )
        return CandidateExportStanding(
            candidate_id=candidate_id,
            eligibility=ExportEligibility.ELIGIBLE,
            actors=observation.actors,
            approved=current.approved,
        )

    def admit_assembly(self, source_timeline_id: str) -> AssemblyAdmissionResult:
        """Record one immutable Assembly for the timeline's complete eligible scope (EA-3).

        Refuses to act — without choosing a behaviour — in the two situations `044 §23` leaves
        undecided. See `EditExportUndecidedPolicyError`.
        """

        observation = self.observe_scope(source_timeline_id)
        self._require_decided(observation)
        members = canonical_member_order(observation.eligible)
        member_ids = tuple(decision.identity for decision in members)
        identity = derive_edit_export_assembly_identity(
            observation.source_timeline_id, member_ids
        )
        assembly = LectureEditExportAssembly(
            identity=identity,
            source_timeline_id=observation.source_timeline_id,
            members=tuple(
                LectureEditExportAssemblyMember(
                    assembly_id=identity,
                    ordinal=ordinal,
                    approved_edit_decision_id=decision.identity,
                )
                for ordinal, decision in enumerate(members)
            ),
        )
        existing = self._assemblies.get_assembly(identity)
        if existing is not None:
            return AssemblyAdmissionResult(
                assembly=self._reuse(existing, assembly),
                outcome=AssemblyOutcome.REUSED,
                observation=observation,
            )
        self._persistence.persist_assembly(assembly)
        return AssemblyAdmissionResult(
            assembly=assembly,
            outcome=AssemblyOutcome.ADMITTED,
            observation=observation,
        )

    @staticmethod
    def _require_decided(observation: ExportScopeObservation) -> None:
        if observation.has_conflict:
            actors = ", ".join(
                sorted(
                    {
                        actor.value
                        for standing in observation.conflicts
                        for actor in standing.actors
                    }
                )
            )
            raise EditExportUndecidedPolicyError(
                "this Source Timeline holds "
                f"{len(observation.conflicts)} edit candidate(s) in a cross-actor Review Conflict "
                f"(actors: {actors}). 044 §23 EA-5 forbids Export from arbitrating between actors, "
                "and its Deferred section leaves the resulting product behaviour undecided — "
                "whether an Assembly is admitted at all, admitted without those candidates, or "
                "refused outright. An implementation may not settle that by choosing one, so "
                "admission stops here. This is a contract gap, not a product refusal: resolve the "
                "Conflict in Review, or record the policy in an approved PATCH"
            )
        if not observation.eligible:
            raise EditExportUndecidedPolicyError(
                "this Source Timeline has no export-eligible approved edit. 044 §23's Deferred "
                "section leaves the treatment of a scope with no eligible member undecided — "
                "a zero-member assembly, an explicit refusal, or something else — so admission "
                "stops here rather than choosing one. This is a contract gap, not a product "
                "refusal; observe the scope to see why each candidate is ineligible"
            )

    @staticmethod
    def _reuse(
        existing: LectureEditExportAssembly, expected: LectureEditExportAssembly
    ) -> LectureEditExportAssembly:
        """Idempotent replay, with the semantic-equality check kept (R-10's Option B proviso).

        Every persisted canonical field participates in the identity, so a divergence here is
        unreachable short of a hash collision — the check is retained anyway, exactly as `§7.5` R-10
        requires under (B), and it never overwrites.
        """

        if (
            existing.source_timeline_id != expected.source_timeline_id
            or existing.member_ids != expected.member_ids
            or existing.assembly_contract_version != expected.assembly_contract_version
        ):
            raise EditExportAssemblyConflictError(
                "a different edit export assembly is already recorded for this identity; "
                "nothing was overwritten"
            )
        return existing

    def get(self, assembly_id: str) -> LectureEditExportAssembly | None:
        return self._assemblies.get_assembly(require_canonical_assembly_id(assembly_id))

    def members(self, assembly_id: str) -> tuple[LectureEditExportAssemblyMember, ...]:
        return self._assemblies.list_members(require_canonical_assembly_id(assembly_id))

    def history(self, source_timeline_id: str) -> tuple[LectureEditExportAssembly, ...]:
        """Every Assembly recorded for one timeline, in a deterministic presentation order.

        Successive Assemblies may differ because membership is derived and total: an upstream
        authority change legitimately changes what a *new* Assembly gathers. That is a difference
        between immutable records, never a mutation of one — no recorded Assembly is ever rewritten.
        """

        return self._assemblies.list_assemblies_for_timeline(
            require_source_timeline(source_timeline_id)
        )


__all__ = [
    "EDIT_EXPORT_ASSEMBLY_CONTRACT_KIND",
    "EDIT_EXPORT_ASSEMBLY_CONTRACT_VERSION",
    "LECTURE_EDIT_EXPORT_ASSEMBLY_IDENTITY_PREFIX",
    "AssemblyAdmissionResult",
    "AssemblyOutcome",
    "AtomicEditExportAssemblyPersistence",
    "CandidateExportStanding",
    "EditExportAssemblyConflictError",
    "EditExportAssemblyQuery",
    "EditExportScopeQuery",
    "EditExportUndecidedPolicyError",
    "ExportEligibility",
    "ExportScopeObservation",
    "LectureEditExportAssembly",
    "LectureEditExportAssemblyError",
    "LectureEditExportAssemblyMember",
    "LectureEditExportAssemblyService",
    "canonical_member_order",
    "derive_edit_export_assembly_identity",
    "require_canonical_assembly_id",
    "require_source_timeline",
]
