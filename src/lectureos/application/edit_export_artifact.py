"""Provider-neutral, format-neutral Edit-Pipeline Export Artifact Foundation (044 §21).

The first Edit Export Artifact milestone (044_EXPORT_PIPELINE.md §21, PATCH-0017). From exactly one durable
:class:`EditExportAssembly` (044 §20), read only, it deterministically derives one
:class:`EditExportArtifact`: the canonical, format-neutral **external representation** of the Assembly's
complete approved edit meaning. The Assembly only *references* its member representations; the Artifact
*presents* their approved meaning — for every member, in the Assembly's canonical order, the approved Source
Timeline range, approved Candidate Type/label, approved rationale, approving decision kind, and human actor —
as one self-contained external representation.

The Artifact is **derived, regenerable, and non-authoritative**: it is reconstructed from the preserved
approved sources, it creates/alters/reinterprets no approved meaning, it holds authority over no canonical
record, and its loss damages no `ApprovedEditDecision`, `ApprovedEditExportRepresentation`, or
`EditExportAssembly`. It is **descriptive, never executable** — it carries no cut/keep/delete/transform command,
output-timeline coordinate, or NLE/rendering instruction. It fixes *what* is communicated (the approved edit
meaning); *how* it is written (concrete serialization syntax) is deferred to future serializer projections.

Representation Failure is explicit: if the complete approved meaning cannot be presented faithfully — a member
representation is missing or its lineage is inconsistent with the Assembly — an :class:`EditExportArtifactError`
is raised naming the failure; approved meaning is never silently omitted. No wall-clock is read, so derivation
is deterministic and regeneration from the same upstream preserves the same Product meaning.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from lectureos.execution.identities import SourceMediaId, SourceTimelineId
from lectureos.review.identities import HumanActorReference

from .edit_candidate import require_canonical_candidate_type
from .edit_export import ApprovedEditExportRepresentation
from .edit_export_assembly import EditExportAssembly
from .edit_review import EditReviewDecisionKind
from .identities import (
    ApprovedEditExportRepresentationId,
    EditExportArtifactId,
    EditExportAssemblyId,
)

_APPROVING_KINDS = (EditReviewDecisionKind.ACCEPT, EditReviewDecisionKind.MODIFY)


def _validate_time_range(start: float, end: float) -> None:
    for name, value in (("start", start), ("end", end)):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"export artifact entry range {name} must be a real number")
    if not isfinite(start) or not isfinite(end):
        raise ValueError("export artifact entry time range must be finite")
    if start < 0 or end < 0:
        raise ValueError("export artifact entry time range must not be negative")
    if start > end:
        raise ValueError("export artifact entry start must not be after end")


@dataclass(frozen=True, slots=True)
class EditExportArtifactEntry:
    """One member's approved edit meaning, presented (copied faithfully) within the Artifact."""

    source_representation_id: ApprovedEditExportRepresentationId
    decision_kind: EditReviewDecisionKind
    approved_range_start: float
    approved_range_end: float
    approved_candidate_type: str
    approved_rationale: str
    actor: HumanActorReference

    def __post_init__(self) -> None:
        if self.decision_kind not in _APPROVING_KINDS:
            raise ValueError("export artifact entry kind must be accept or modify")
        require_canonical_candidate_type(self.approved_candidate_type)
        if not self.approved_rationale.strip():
            raise ValueError("export artifact entry rationale must not be empty")
        if not isinstance(self.actor, HumanActorReference):
            raise ValueError("export artifact entry requires a human actor reference")
        _validate_time_range(self.approved_range_start, self.approved_range_end)


@dataclass(frozen=True, slots=True)
class EditExportArtifact:
    """Canonical, format-neutral, derived external representation of one Edit Export Assembly's meaning."""

    identity: EditExportArtifactId
    source_assembly_id: EditExportAssemblyId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    entries: tuple[EditExportArtifactEntry, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise ValueError("export artifact entries must be a tuple")
        if not self.entries:
            raise ValueError("export artifact must present at least one approved edit")
        member_ids = tuple(entry.source_representation_id for entry in self.entries)
        if len(set(member_ids)) != len(member_ids):
            raise ValueError("export artifact members must be unique")
        if member_ids != tuple(sorted(member_ids, key=lambda identity: identity.value)):
            raise ValueError("export artifact entries must be in canonical member order")


class EditExportAssemblyQuery(Protocol):
    def get(self, identity): ...


class ApprovedEditExportRepresentationQuery(Protocol):
    def get(self, identity): ...


class EditExportArtifactError(ValueError):
    """A structurally valid request whose approved meaning cannot be represented as a canonical Artifact."""


class EditExportArtifactService:
    """Derives one canonical external Artifact representation from one Edit Export Assembly, read only."""

    def __init__(
        self,
        assembly_query: EditExportAssemblyQuery,
        representation_query: ApprovedEditExportRepresentationQuery,
    ) -> None:
        self._assemblies = assembly_query
        self._representations = representation_query

    def derive_artifact(
        self,
        *,
        source_assembly_id: EditExportAssemblyId,
        identity: EditExportArtifactId,
    ) -> EditExportArtifact:
        # Consume exactly one canonical Assembly, read only; the Assembly and its member representations are
        # never mutated, and the Assembly remains authoritative for the coherent grouping.
        assembly = self._assemblies.get(source_assembly_id)
        if assembly is None:
            raise KeyError("unknown edit export assembly")
        if not isinstance(assembly, EditExportAssembly):
            raise EditExportArtifactError(
                "edit export artifact must derive from a canonical Edit Export Assembly"
            )

        entries = tuple(
            self._present_member(assembly, member_id)
            for member_id in assembly.member_representation_ids
        )
        return EditExportArtifact(
            identity=identity,
            source_assembly_id=assembly.identity,
            source_media_id=assembly.source_media_id,
            source_timeline_id=assembly.source_timeline_id,
            entries=entries,
        )

    def _present_member(
        self,
        assembly: EditExportAssembly,
        member_id: ApprovedEditExportRepresentationId,
    ) -> EditExportArtifactEntry:
        representation = self._representations.get(member_id)
        if representation is None:
            # Representation Failure: the approved meaning cannot be presented completely — never silently omit.
            raise EditExportArtifactError(
                "approved edit meaning could not be represented: member representation is missing"
            )
        if not isinstance(representation, ApprovedEditExportRepresentation):
            raise EditExportArtifactError(
                "edit export artifact member must be a canonical export representation"
            )
        if (
            representation.source_timeline_id != assembly.source_timeline_id
            or representation.source_media_id != assembly.source_media_id
        ):
            raise EditExportArtifactError(
                "member representation lineage is inconsistent with the assembly"
            )
        # Faithful presentation — the approved snapshot is copied, never re-derived or reinterpreted.
        return EditExportArtifactEntry(
            source_representation_id=representation.identity,
            decision_kind=representation.decision_kind,
            approved_range_start=representation.approved_range_start,
            approved_range_end=representation.approved_range_end,
            approved_candidate_type=representation.approved_candidate_type,
            approved_rationale=representation.approved_rationale,
            actor=representation.actor,
        )


__all__ = [
    "ApprovedEditExportRepresentationQuery",
    "EditExportArtifact",
    "EditExportArtifactEntry",
    "EditExportArtifactError",
    "EditExportArtifactService",
    "EditExportAssemblyQuery",
]
