"""Provider-neutral, interface-independent Edit-Pipeline Export Assembly Application Foundation (044 §20).

The first Edit Export Assembly milestone (044_EXPORT_PIPELINE.md §20, PATCH-0016). From an explicitly supplied,
non-empty set of existing durable :class:`ApprovedEditExportRepresentation` records (044 §19), admitted
read-only, it deterministically records one immutable :class:`EditExportAssembly`: a durable, canonical,
format-neutral aggregate that establishes the existence of a coherent Export Scope anchored to exactly one
Source Timeline. Aggregation precedes serialization.

The Assembly is authoritative only for the coherent grouping — the existence of the grouping, the immutable
ordered membership snapshot, the Source Timeline anchor, deterministic coherence, and the aggregate's
provenance and lineage. Each :class:`ApprovedEditExportRepresentation` remains authoritative for its own
exported edit meaning; the Assembly references members and never copies, rewrites, or reinterprets that
meaning, chooses which representations belong (the caller supplies the explicit member set), approves
decisions, selects export scope policy, serializes output, creates an Artifact, or materializes a file. No
wall-clock is read, so reconstruction and replay are deterministic. Membership order is a deterministic
storage/replay normalization by canonical identity ordering — not an edit-execution or timeline-transformation
order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference, ProcessingState

from .edit_export import ApprovedEditExportRepresentation
from .identities import (
    ApprovedEditExportRepresentationId,
    EditExportAssemblyId,
)

EDIT_EXPORT_ASSEMBLY_RESULT_KIND = "edit_export_assembly"


def _canonical_order(
    ids: Sequence[ApprovedEditExportRepresentationId],
) -> tuple[ApprovedEditExportRepresentationId, ...]:
    # Deterministic storage/replay normalization only — the stable canonical identity ordering, never an
    # edit-execution, overlap-resolution, or timeline-transformation order.
    return tuple(sorted(ids, key=lambda identity: identity.value))


@dataclass(frozen=True, slots=True)
class EditExportAssembly:
    """Immutable, canonical, format-neutral aggregate of one or more approved edit export representations."""

    identity: EditExportAssemblyId
    domain_result_id: DomainResultId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    member_representation_ids: tuple[ApprovedEditExportRepresentationId, ...]
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId

    def __post_init__(self) -> None:
        members = self.member_representation_ids
        if not isinstance(members, tuple):
            raise ValueError("edit export assembly membership snapshot must be a tuple")
        if not members:
            raise ValueError("edit export assembly requires at least one member representation")
        if len(set(members)) != len(members):
            raise ValueError("edit export assembly members must be unique")
        if members != _canonical_order(members):
            raise ValueError(
                "edit export assembly membership must be in canonical identity order"
            )


@dataclass(frozen=True, slots=True)
class EditExportAssemblyIdentityPlan:
    """Application-owned identities for one Assembly admission."""

    assembly_id: EditExportAssemblyId
    assembly_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedEditExportAssembly:
    """Immutable canonical Assembly records for one admission; not yet persisted."""

    assembly: EditExportAssembly
    assembly_result: DomainResultReference


class ApprovedEditExportRepresentationQuery(Protocol):
    def get(self, identity): ...


class AtomicEditExportAssemblyPersistence(Protocol):
    def persist_edit_export_assembly(
        self, *, prepared: PreparedEditExportAssembly
    ) -> None: ...


class EditExportAssemblyError(ValueError):
    """A structurally valid request that cannot become a canonical edit export assembly."""


class EditExportAssemblyService:
    """Records one durable Edit Export Assembly from an explicitly supplied set of export representations."""

    def __init__(
        self,
        representation_query: ApprovedEditExportRepresentationQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicEditExportAssemblyPersistence | None = None,
    ) -> None:
        self._representations = representation_query
        self._executions = execution_query
        self._persistence = persistence

    def record_assembly(self, **kwargs) -> PreparedEditExportAssembly:
        prepared = self.evaluate_assembly(**kwargs)
        if self._persistence is None:
            raise RuntimeError("edit export assembly persistence is not configured")
        self._persistence.persist_edit_export_assembly(prepared=prepared)
        return prepared

    def evaluate_assembly(
        self,
        *,
        source_timeline_id: SourceTimelineId,
        member_representation_ids: Sequence[ApprovedEditExportRepresentationId],
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: EditExportAssemblyIdentityPlan,
    ) -> PreparedEditExportAssembly:
        # The caller explicitly supplies the intended member representations. The service validates and admits
        # that explicit set; it never discovers, selects, or filters which representations ought to belong.
        supplied = tuple(member_representation_ids)
        if not supplied:
            raise EditExportAssemblyError(
                "edit export assembly requires at least one member representation"
            )
        if len(set(supplied)) != len(supplied):
            raise EditExportAssemblyError(
                "edit export assembly members must be unique"
            )
        self._require_running_execution(run_id, unit_execution_id)

        members = self._require_coherent_members(supplied, source_timeline_id)
        ordered_ids = _canonical_order(supplied)
        source_media_id = members[supplied[0]].source_media_id
        upstream_results = tuple(
            members[identity].domain_result_id for identity in ordered_ids
        )

        assembly = EditExportAssembly(
            identity=identities.assembly_id,
            domain_result_id=identities.assembly_result_id,
            source_media_id=source_media_id,
            source_timeline_id=source_timeline_id,
            member_representation_ids=ordered_ids,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
        )
        assembly_result = DomainResultReference(
            identity=identities.assembly_result_id,
            kind=EDIT_EXPORT_ASSEMBLY_RESULT_KIND,
            source_media=source_media_id,
            source_timeline=source_timeline_id,
            # Multi-upstream lineage: the Assembly derives from the complete admitted membership snapshot,
            # one direct upstream per member representation, in canonical membership order.
            upstream_results=upstream_results,
        )
        return PreparedEditExportAssembly(
            assembly=assembly, assembly_result=assembly_result
        )

    def _require_coherent_members(
        self,
        supplied: tuple[ApprovedEditExportRepresentationId, ...],
        source_timeline_id: SourceTimelineId,
    ) -> dict[ApprovedEditExportRepresentationId, ApprovedEditExportRepresentation]:
        members: dict[
            ApprovedEditExportRepresentationId, ApprovedEditExportRepresentation
        ] = {}
        source_media_id: SourceMediaId | None = None
        for identity in supplied:
            representation = self._representations.get(identity)
            if representation is None:
                raise KeyError("unknown approved edit export representation")
            if not isinstance(representation, ApprovedEditExportRepresentation):
                raise EditExportAssemblyError(
                    "edit export assembly member must be a canonical export representation"
                )
            if representation.source_timeline_id != source_timeline_id:
                raise EditExportAssemblyError(
                    "member representation must belong to the assembly source timeline"
                )
            if source_media_id is None:
                source_media_id = representation.source_media_id
            elif representation.source_media_id != source_media_id:
                raise EditExportAssemblyError(
                    "edit export assembly members must share one source media"
                )
            members[identity] = representation
        return members

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise EditExportAssemblyError("unit execution must belong to processing run")
        if execution.state is not ProcessingState.RUNNING:
            raise EditExportAssemblyError(
                "recording an edit export assembly requires a running unit execution"
            )


__all__ = [
    "EDIT_EXPORT_ASSEMBLY_RESULT_KIND",
    "ApprovedEditExportRepresentationQuery",
    "AtomicEditExportAssemblyPersistence",
    "EditExportAssembly",
    "EditExportAssemblyError",
    "EditExportAssemblyIdentityPlan",
    "EditExportAssemblyService",
    "PreparedEditExportAssembly",
]
