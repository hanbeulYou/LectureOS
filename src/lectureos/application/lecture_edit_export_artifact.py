"""Edit Export Artifact — effective-transcript generation (044 §24, GOAL-031).

Implements the Architect Decisions confirmed by `patches/PATCH-0036` (AR-1…AR-11): the canonical
**external representation** of one `§23` Edit Export Assembly's complete approved edit meaning, and
nothing downstream of it.

**One Assembly in, one Artifact out (AR-2).** The Assembly is consumed **immutable and read-only**;
`§21` B-1's cardinality and direction are unchanged — no cross-Assembly Artifact, no partial
Artifact. Only the generation of the record in the source position differs from `§21`.

**Two layers, not three (AR-3).** The `ApprovedEditDecision` **owns** the approved meaning, the
Assembly **references** it, and the Artifact **presents** it. `§19`'s atom layer is absent because
`§23` EA-2 did not reproduce it, so the values presented come from the `ApprovedEditDecision`
directly — which is where they always lived (`043 §7.5` R-8, `§19` D-3).

**The presentation copy is not a duplication violation (AR-4).** This generation's "inherit through
the anchor, never duplicate" idiom governs **canonical records**; the Artifact is expressly derived
and non-authoritative, and presenting a self-contained external product is its entire purpose.

**Nothing is executed (AR-5).** No `ProcessingRun`, `ProcessingUnit`, `UnitExecution`, RUNNING state,
or `DomainResult` is required, referenced, or fabricated — and `§21` never required them either, so
this is an inheritance rather than a new prohibition. Derivation reads no wall clock and no
randomness.

**Nothing is re-decided (AR-8).** Export eligibility, admission standing, authority history, and
cross-actor Conflict are **not re-evaluated**. Membership was fixed when the Assembly was admitted.
An Assembly whose members' judgments were later superseded, or whose chains later lost `current`
standing, therefore still yields a correct Artifact — that is not corruption. `§23`'s three undecided
policies are not reopened here.

**Not persisted, by design (AR-11).** AR-11 requires no durable representation, and none is added:
the Artifact is a pure function of immutable rows that are already stored, so persisting it would
duplicate a derivation without recording a new fact — and would invite the authority AR-9 denies it.
The legacy `§21` realization made the same choice for the same reason. `SQLITE_SCHEMA_VERSION` stays
**53**; no table, migration, or validator code is added.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from lectureos.execution.identities import SourceTimelineId
from lectureos.review.identities import HumanActorReference

from .identities import (
    LectureAnalysisEditCandidateId,
    LectureApprovedEditDecisionId,
    LectureEditExportArtifactId,
    LectureEditExportAssemblyId,
    LectureReviewDecisionId,
)
from .lecture_edit_export_assembly import (
    LectureEditExportAssembly,
    require_canonical_assembly_id,
)
from .lecture_review_decision import ReviewDecisionKind

LECTURE_EDIT_EXPORT_ARTIFACT_IDENTITY_PREFIX = "lecture-edit-export-artifact"

EDIT_EXPORT_ARTIFACT_CONTRACT_KIND = "lecture_edit_export_artifact"
EDIT_EXPORT_ARTIFACT_CONTRACT_VERSION = 1


class LectureEditExportArtifactError(ValueError):
    """An Edit Export Artifact derivation that cannot proceed."""


class ArtifactRepresentationFailureError(LectureEditExportArtifactError):
    """`§21` B-11 / AR-10: the Assembly's approved meaning cannot be presented faithfully.

    Raised when a member cannot be resolved, or when a member's lineage is inconsistent with the
    Assembly it is claimed to belong to. Approved meaning is **never** silently dropped and a
    shortened Artifact is never produced; the approved sources are left untouched.

    This is a **structural** failure, never a judgement about eligibility, standing, authority, or
    Conflict — re-evaluating any of those is what AR-8 prohibits.
    """


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def derive_edit_export_artifact_identity(
    source_assembly_id: LectureEditExportAssemblyId,
) -> LectureEditExportArtifactId:
    """Deterministic, Application-owned Artifact identity (AR-7).

    Binds the source Assembly and nothing else. That is sufficient rather than minimal: the
    Assembly's own identity already binds its Source Timeline and its exact membership (`§23` EA-10),
    and every member `ApprovedEditDecision` is immutable, so the Assembly identity determines the
    presented content completely.

    No provider identifier, execution identifier, `DomainResult`, UUID, timestamp, wall clock, rowid,
    path, or mutable currentness participates. **`§21`'s caller-owned identity is legacy-only**
    (`§7.5` R-10), and **no discriminator is introduced** — AR-7 permits `§21` B-13's plurality
    without providing a route to manufacture it, and a future need for several representations of one
    Assembly belongs to the serializer projecting this Artifact (`§21` B-4, `§22` C-10).
    """

    digest = hashlib.sha256(
        _canonical_json(
            {
                "contract": EDIT_EXPORT_ARTIFACT_CONTRACT_KIND,
                "contract_version": EDIT_EXPORT_ARTIFACT_CONTRACT_VERSION,
                "source_assembly": source_assembly_id.value,
            }
        ).encode("utf-8")
    ).hexdigest()
    return LectureEditExportArtifactId(
        f"{LECTURE_EDIT_EXPORT_ARTIFACT_IDENTITY_PREFIX}:{digest}"
    )


def require_canonical_artifact_id(value: str) -> LectureEditExportArtifactId:
    prefix = LECTURE_EDIT_EXPORT_ARTIFACT_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise LectureEditExportArtifactError(
            "lecture edit export artifact identity is malformed "
            "(expected 'lecture-edit-export-artifact:<64 hex digest>')"
        )
    return LectureEditExportArtifactId(value)


@dataclass(frozen=True, slots=True)
class LectureEditExportArtifactEntry:
    """One member's approved meaning, **presented** (AR-3).

    Carries the values `§21` B-3 requires an Artifact to present — approved Source Timeline range,
    approved Candidate Type or label, approved rationale, approved decision kind, human actor — copied
    faithfully from the owning records and **never re-derived or reinterpreted** (AR-8(b)). The
    approved range is a **Source Timeline** range and is never an output-timeline coordinate (AR-10).
    """

    ordinal: int
    source_approved_edit_decision_id: LectureApprovedEditDecisionId
    source_review_decision_id: LectureReviewDecisionId
    source_edit_candidate_id: LectureAnalysisEditCandidateId
    decision_kind: ReviewDecisionKind
    approved_range_start: float
    approved_range_end: float
    approved_label: str
    approved_rationale: str
    actor: HumanActorReference

    def __post_init__(self) -> None:
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool):
            raise LectureEditExportArtifactError(
                "edit export artifact entry ordinal must be an integer"
            )
        if self.ordinal < 0:
            raise LectureEditExportArtifactError(
                "edit export artifact entry ordinal must be non-negative"
            )


@dataclass(frozen=True, slots=True)
class LectureEditExportArtifact:
    """The canonical external representation of one Assembly's complete approved edit meaning.

    **Immutable, insert-only, derived, regenerable, non-authoritative** (AR-9). It owns no status,
    lifecycle, state machine, Export Profile, Export Configuration, execution provenance, or
    `DomainResult`. Deriving it exercises **no Human Authority** — Review remains the only stage at
    which it is exercised.

    Descriptive, never executable (AR-10): no cut/keep/delete/transform command, no output-timeline
    coordinate or transformation, no rendering instruction, no serialized syntax, no file.
    """

    identity: LectureEditExportArtifactId
    source_assembly_id: LectureEditExportAssemblyId
    source_timeline_id: SourceTimelineId
    entries: tuple[LectureEditExportArtifactEntry, ...]
    artifact_contract_version: int = EDIT_EXPORT_ARTIFACT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.artifact_contract_version != EDIT_EXPORT_ARTIFACT_CONTRACT_VERSION:
            raise LectureEditExportArtifactError(
                "unsupported edit export artifact contract version"
            )
        if not self.entries:
            # Not an empty-scope policy: §23 already refuses to admit an Assembly with no member,
            # and that policy stays exactly where PATCH-0035 left it. This guards the record only.
            raise LectureEditExportArtifactError(
                "an edit export artifact must present at least one member"
            )
        ordinals = [entry.ordinal for entry in self.entries]
        if ordinals != list(range(len(self.entries))):
            raise LectureEditExportArtifactError(
                "edit export artifact entry ordinals must be contiguous from zero"
            )
        if self.identity != derive_edit_export_artifact_identity(self.source_assembly_id):
            raise LectureEditExportArtifactError(
                "edit export artifact identity must derive from its source assembly"
            )

    @property
    def member_ids(self) -> tuple[LectureApprovedEditDecisionId, ...]:
        return tuple(entry.source_approved_edit_decision_id for entry in self.entries)


class ArtifactAssemblyQuery(Protocol):
    def get_assembly(self, identity): ...


class ArtifactApprovedDecisionQuery(Protocol):
    def get_approved(self, identity): ...

    def get_decision(self, identity): ...


class ArtifactScopeQuery(Protocol):
    def candidate_ids_for_source_timeline(self, source_timeline_id) -> tuple: ...


class LectureEditExportArtifactService:
    """Derives one canonical Artifact from one `§23` Assembly, read-only (044 §24).

    Reads; never writes. The Assembly, its members, and every upstream record are consumed
    immutable, and nothing here admits, approves, supersedes, or re-evaluates anything.
    """

    def __init__(
        self,
        *,
        assembly_query: ArtifactAssemblyQuery,
        decision_query: ArtifactApprovedDecisionQuery,
        scope_query: ArtifactScopeQuery,
    ) -> None:
        self._assemblies = assembly_query
        self._decisions = decision_query
        self._scope = scope_query

    def derive_artifact(self, assembly_id: str) -> LectureEditExportArtifact:
        """Present one Assembly's complete approved meaning (AR-2, AR-3).

        Deterministic and replay-safe: the same Assembly always yields the same Artifact, because
        the Assembly and every record it references are immutable. No eligibility, standing,
        authority, or Conflict is consulted (AR-8).
        """

        identity = require_canonical_assembly_id(assembly_id)
        assembly = self._assemblies.get_assembly(identity)
        if assembly is None:
            raise LectureEditExportArtifactError("unknown edit export assembly")
        if not isinstance(assembly, LectureEditExportAssembly):
            raise LectureEditExportArtifactError(
                "an edit export artifact must derive from a canonical Edit Export Assembly"
            )
        timeline_candidates = frozenset(
            candidate.value
            for candidate in self._scope.candidate_ids_for_source_timeline(
                assembly.source_timeline_id
            )
        )
        entries = tuple(
            self._present(assembly, member, timeline_candidates)
            for member in assembly.members
        )
        return LectureEditExportArtifact(
            identity=derive_edit_export_artifact_identity(assembly.identity),
            source_assembly_id=assembly.identity,
            source_timeline_id=assembly.source_timeline_id,
            entries=entries,
        )

    def _present(
        self,
        assembly: LectureEditExportAssembly,
        member,
        timeline_candidates: frozenset[str],
    ) -> LectureEditExportArtifactEntry:
        """Copy one member's approved values faithfully, or fail explicitly (AR-10 / B-11)."""

        approved = self._decisions.get_approved(member.approved_edit_decision_id)
        if approved is None:
            raise ArtifactRepresentationFailureError(
                "edit export assembly member "
                f"{member.approved_edit_decision_id.value} cannot be resolved, so this assembly's "
                "approved meaning cannot be presented completely; nothing was omitted and the "
                "approved sources are unchanged"
            )
        if approved.candidate_id.value not in timeline_candidates:
            raise ArtifactRepresentationFailureError(
                "edit export assembly member "
                f"{member.approved_edit_decision_id.value} does not belong to the assembly's "
                f"Source Timeline {assembly.source_timeline_id.value}; the assembly's approved "
                "meaning cannot be presented faithfully"
            )
        decision = self._decisions.get_decision(approved.review_decision_id)
        if decision is None:
            raise ArtifactRepresentationFailureError(
                "the review decision owning member "
                f"{member.approved_edit_decision_id.value} cannot be resolved, so its human actor "
                "cannot be presented"
            )
        return LectureEditExportArtifactEntry(
            ordinal=member.ordinal,
            source_approved_edit_decision_id=approved.identity,
            source_review_decision_id=approved.review_decision_id,
            source_edit_candidate_id=approved.candidate_id,
            decision_kind=approved.approved_decision_kind,
            approved_range_start=approved.approved_range_start,
            approved_range_end=approved.approved_range_end,
            approved_label=approved.approved_label,
            approved_rationale=approved.approved_rationale,
            actor=decision.actor,
        )


__all__ = [
    "EDIT_EXPORT_ARTIFACT_CONTRACT_KIND",
    "EDIT_EXPORT_ARTIFACT_CONTRACT_VERSION",
    "LECTURE_EDIT_EXPORT_ARTIFACT_IDENTITY_PREFIX",
    "ArtifactApprovedDecisionQuery",
    "ArtifactAssemblyQuery",
    "ArtifactRepresentationFailureError",
    "ArtifactScopeQuery",
    "LectureEditExportArtifact",
    "LectureEditExportArtifactEntry",
    "LectureEditExportArtifactError",
    "LectureEditExportArtifactService",
    "derive_edit_export_artifact_identity",
    "require_canonical_artifact_id",
]
