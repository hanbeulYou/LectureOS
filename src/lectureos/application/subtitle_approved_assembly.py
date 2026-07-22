"""Provider-independent Application contract for Approved Subtitle Assembly (044 §Export, PATCH-0006).

The first stage of the Export Pipeline. From exactly one canonical subtitle document (its
``SubtitleTimeRevision`` and ``SubtitleReadingRevision``), it deterministically reconstructs the complete,
ordered, approved subtitle representation — the ``SubtitleApprovedDocument`` — by reconciling the base
timed/reading representation with the applicable finalized decisions (``SubtitleFinalSubtitle``), and it
establishes export eligibility.

Assembly is a pure deterministic reconstruction. Every upstream record is read read-only and never
mutated: the time revision, reading revision, final subtitles and decision revisions are unchanged. The
only newly created canonical artifact is the ``SubtitleApprovedDocument`` (with its ordered approved units
and their approved lines) and its ``DomainResultReference``. This stage generates no artifact, writes no
file, and serializes no format (no SRT/WebVTT/bytes); it performs no Review, no Validation, no Human
Decision, no AI, and uses no provider. It becomes the canonical Export Input.

Reconciliation (approved PATCH-0006 §4), applying each unit's current finalization:
- Modify (FINAL)   -> unit included, text = approved applied_text
- Accept (FINAL)   -> unit included, text = original reading text
- Reject (NOT_FINAL)-> unit omitted; the document remains eligible
- Untouched        -> unit included, text = original reading text
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference, ProcessingState
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .identities import (
    SubtitleApprovedDocumentId,
    SubtitleApprovedUnitId,
    SubtitleCandidateId,
    SubtitleFinalSubtitleId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
)
from .subtitle_decision_application import SubtitleAppliedOutcome
from .subtitle_final_subtitle import SubtitleFinalOutcome
from .subtitle_time_representation import SubtitleTimingStatus

SUBTITLE_APPROVED_DOCUMENT_RESULT_KIND = "subtitle_approved_document"


class SubtitleExportEligibility(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class SubtitleApprovedUnitOrigin(str, Enum):
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    UNTOUCHED = "untouched"


@dataclass(frozen=True, slots=True)
class SubtitleApprovedUnit:
    """One immutable approved subtitle unit in canonical display order."""

    identity: SubtitleApprovedUnitId
    document_id: SubtitleApprovedDocumentId
    source_timed_unit_id: SubtitleTimedUnitId
    source_reading_unit_id: SubtitleReadingUnitId
    origin: SubtitleApprovedUnitOrigin
    display_order: int
    start: float
    end: float
    lines: tuple[str, ...]
    source_final_subtitle_id: SubtitleFinalSubtitleId | None = None

    def __post_init__(self) -> None:
        if self.display_order < 0:
            raise ValueError("approved unit display order must not be negative")
        if self.start < 0 or self.end < self.start:
            raise ValueError("approved unit requires resolved timing with end >= start >= 0")
        if not self.lines:
            raise ValueError("approved unit requires at least one line")
        if any(not line.strip() for line in self.lines):
            raise ValueError("approved unit lines must not be blank")
        if self.origin is SubtitleApprovedUnitOrigin.UNTOUCHED:
            if self.source_final_subtitle_id is not None:
                raise ValueError("untouched approved unit must not reference a final subtitle")
        elif self.source_final_subtitle_id is None:
            raise ValueError(
                "accepted and modified approved units must reference a final subtitle"
            )


@dataclass(frozen=True, slots=True)
class SubtitleApprovedDocument:
    """Immutable, document-level approved subtitle representation — the canonical Export Input."""

    identity: SubtitleApprovedDocumentId
    domain_result_id: DomainResultId
    source_time_revision_id: SubtitleTimeRevisionId
    source_reading_revision_id: SubtitleReadingRevisionId
    eligibility: SubtitleExportEligibility
    source_candidate_id: SubtitleCandidateId
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    approved_unit_ids: tuple[SubtitleApprovedUnitId, ...]
    omitted_unit_count: int
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    ineligibility_reason: str | None = None
    previous_document_id: SubtitleApprovedDocumentId | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("approved document reason must not be empty")
        if self.sequence < 0:
            raise ValueError("approved document sequence must not be negative")
        if self.omitted_unit_count < 0:
            raise ValueError("approved document omitted unit count must not be negative")
        if self.eligibility is SubtitleExportEligibility.ELIGIBLE:
            if self.ineligibility_reason is not None:
                raise ValueError("eligible approved document must not carry an ineligibility reason")
        else:
            if self.ineligibility_reason is None or not self.ineligibility_reason.strip():
                raise ValueError("ineligible approved document requires a non-empty reason")
            if self.approved_unit_ids:
                raise ValueError("ineligible approved document must not carry approved units")
        if len(set(self.approved_unit_ids)) != len(self.approved_unit_ids):
            raise ValueError("approved document unit ids must be unique")
        if self.previous_document_id is not None and self.sequence == 0:
            raise ValueError("first approved document must not reference a previous document")


@dataclass(frozen=True, slots=True)
class SubtitleApprovedAssemblyIdentityPlan:
    """Application-owned identities for one assembly; unit ids match the time revision positionally."""

    document_id: SubtitleApprovedDocumentId
    document_result_id: DomainResultId
    unit_ids: tuple[SubtitleApprovedUnitId, ...]

    def __post_init__(self) -> None:
        if not self.unit_ids:
            raise ValueError("approved assembly identity plan requires unit ids")
        if len(set(self.unit_ids)) != len(self.unit_ids):
            raise ValueError("approved assembly identity plan unit ids must be unique")


@dataclass(frozen=True, slots=True)
class PreparedSubtitleApprovedDocument:
    """Immutable canonical approved document with its ordered units; not yet persisted."""

    document: SubtitleApprovedDocument
    units: tuple[SubtitleApprovedUnit, ...]
    document_result: DomainResultReference


class SubtitleTimeRevisionQuery(Protocol):
    def get(self, identity): ...

    def get_unit(self, identity): ...


class SubtitleReadingRevisionQuery(Protocol):
    def get(self, identity): ...

    def get_unit(self, identity): ...


class SubtitleFinalSubtitleQuery(Protocol):
    def list_for_time_revision(self, identity): ...


class SubtitleDecisionRevisionQuery(Protocol):
    def get(self, identity): ...


class AtomicSubtitleApprovedDocumentPersistence(Protocol):
    def persist_subtitle_approved_document(
        self,
        *,
        document: SubtitleApprovedDocument,
        units: tuple[SubtitleApprovedUnit, ...],
        document_result: DomainResultReference,
    ) -> None: ...


class SubtitleApprovedAssemblyError(ValueError):
    """A structurally valid request that cannot become a canonical Approved Subtitle Document."""


class SubtitleApprovedSubtitleAssemblyService:
    """Reconstructs the approved subtitle document from one document's finals, mutating nothing."""

    def __init__(
        self,
        time_query: SubtitleTimeRevisionQuery,
        reading_query: SubtitleReadingRevisionQuery,
        final_query: SubtitleFinalSubtitleQuery,
        decision_revision_query: SubtitleDecisionRevisionQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicSubtitleApprovedDocumentPersistence | None = None,
    ) -> None:
        self._time = time_query
        self._reading = reading_query
        self._finals = final_query
        self._decisions = decision_revision_query
        self._executions = execution_query
        self._persistence = persistence

    def record_assembly(self, **kwargs) -> PreparedSubtitleApprovedDocument:
        prepared = self.assemble(**kwargs)
        if self._persistence is None:
            raise RuntimeError("approved subtitle assembly persistence is not configured")
        self._persistence.persist_subtitle_approved_document(
            document=prepared.document,
            units=prepared.units,
            document_result=prepared.document_result,
        )
        return prepared

    def assemble(
        self,
        *,
        source_time_revision_id: SubtitleTimeRevisionId,
        source_reading_revision_id: SubtitleReadingRevisionId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: SubtitleApprovedAssemblyIdentityPlan,
        sequence: int = 0,
        previous_document_id: SubtitleApprovedDocumentId | None = None,
        reason: str | None = None,
    ) -> PreparedSubtitleApprovedDocument:
        # Admit exactly one canonical subtitle document (its time revision + reading revision). Every
        # upstream record is read read-only and never mutated.
        time_revision = self._time.get(source_time_revision_id)
        if time_revision is None:
            raise KeyError("unknown subtitle time revision")
        reading_revision = self._reading.get(source_reading_revision_id)
        if reading_revision is None:
            raise KeyError("unknown subtitle reading revision")
        self._require_running_execution(run_id, unit_execution_id)

        timed_unit_ids = time_revision.timed_unit_ids
        if len(identities.unit_ids) != len(timed_unit_ids):
            raise SubtitleApprovedAssemblyError(
                "identity plan unit count must match the time revision unit count"
            )
        document_units = set(timed_unit_ids)

        # Collect the applicable finalized decisions for this document; keep the current finalization
        # (highest sequence) per target unit.
        ineligibility_reason: str | None = None
        current_by_unit: dict[object, object] = {}
        for final in self._finals.list_for_time_revision(source_time_revision_id):
            problem = self._final_provenance_problem(
                final, source_time_revision_id, source_reading_revision_id, document_units
            )
            if problem is not None:
                ineligibility_reason = ineligibility_reason or problem
                continue
            existing = current_by_unit.get(final.target_timed_unit_id)
            if existing is None or final.sequence > existing.sequence:
                current_by_unit[final.target_timed_unit_id] = final

        approved_units: list[SubtitleApprovedUnit] = []
        omitted = 0
        if ineligibility_reason is None:
            for index, timed_unit_id in enumerate(timed_unit_ids):
                timed_unit = self._time.get_unit(timed_unit_id)
                if timed_unit is None:
                    ineligibility_reason = "timed unit provenance is unresolved"
                    break
                final = current_by_unit.get(timed_unit_id)
                if final is not None and final.final_outcome is SubtitleFinalOutcome.NOT_FINAL:
                    omitted += 1  # Reject -> omit the unit
                    continue
                if (
                    timed_unit.timing_status is not SubtitleTimingStatus.ANCHORED
                    or timed_unit.start is None
                    or timed_unit.end is None
                ):
                    ineligibility_reason = "included unit lacks resolved timing"
                    break
                reading_unit = self._reading.get_unit(timed_unit.source_reading_unit_id)
                if reading_unit is None or not reading_unit.lines:
                    ineligibility_reason = "included unit reading text is unresolvable"
                    break
                origin, lines, final_id = self._resolve_unit(final, reading_unit)
                approved_units.append(
                    SubtitleApprovedUnit(
                        identity=identities.unit_ids[index],
                        document_id=identities.document_id,
                        source_timed_unit_id=timed_unit_id,
                        source_reading_unit_id=timed_unit.source_reading_unit_id,
                        origin=origin,
                        display_order=timed_unit.display_order,
                        start=timed_unit.start,
                        end=timed_unit.end,
                        lines=lines,
                        source_final_subtitle_id=final_id,
                    )
                )

        if ineligibility_reason is not None:
            eligibility = SubtitleExportEligibility.INELIGIBLE
            units: tuple[SubtitleApprovedUnit, ...] = ()
            unit_ids: tuple[SubtitleApprovedUnitId, ...] = ()
            omitted = 0
        else:
            eligibility = SubtitleExportEligibility.ELIGIBLE
            units = tuple(approved_units)
            unit_ids = tuple(unit.identity for unit in units)

        resolved_reason = reason if reason is not None else _default_reason(eligibility)
        document = SubtitleApprovedDocument(
            identity=identities.document_id,
            domain_result_id=identities.document_result_id,
            source_time_revision_id=source_time_revision_id,
            source_reading_revision_id=source_reading_revision_id,
            eligibility=eligibility,
            source_candidate_id=time_revision.source_candidate_id,
            source_transcript_id=time_revision.source_transcript_id,
            source_revision_id=time_revision.source_revision_id,
            source_media_id=time_revision.source_media_id,
            source_timeline_id=time_revision.source_timeline_id,
            approved_unit_ids=unit_ids,
            omitted_unit_count=omitted,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            ineligibility_reason=ineligibility_reason,
            previous_document_id=previous_document_id,
        )
        document_result = DomainResultReference(
            identity=identities.document_result_id,
            kind=SUBTITLE_APPROVED_DOCUMENT_RESULT_KIND,
            source_media=time_revision.source_media_id,
            source_timeline=time_revision.source_timeline_id,
            upstream_results=(time_revision.domain_result_id,),
        )
        return PreparedSubtitleApprovedDocument(
            document=document, units=units, document_result=document_result
        )

    def _final_provenance_problem(
        self, final, time_revision_id, reading_revision_id, document_units
    ) -> str | None:
        if final.source_time_revision_id != time_revision_id:
            return "finalized decision provenance does not match the document time revision"
        if final.source_reading_revision_id != reading_revision_id:
            return "finalized decision provenance does not match the document reading revision"
        if self._decisions.get(final.source_decision_revision_id) is None:
            return "finalized decision revision provenance is unresolved"
        if final.target_timed_unit_id is None or final.target_timed_unit_id not in document_units:
            return "finalized decision targets a unit outside the document"
        return None

    def _resolve_unit(self, final, reading_unit):
        if final is None:
            return SubtitleApprovedUnitOrigin.UNTOUCHED, reading_unit.lines, None
        if final.applied_outcome is SubtitleAppliedOutcome.MODIFIED:
            return (
                SubtitleApprovedUnitOrigin.MODIFIED,
                (final.applied_text,),
                final.identity,
            )
        return SubtitleApprovedUnitOrigin.ACCEPTED, reading_unit.lines, final.identity

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise SubtitleApprovedAssemblyError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise SubtitleApprovedAssemblyError(
                "assembling an approved subtitle document requires a running unit execution"
            )


def _default_reason(eligibility: SubtitleExportEligibility) -> str:
    return f"assembled the approved subtitle document ({eligibility.value})"


__all__ = [
    "SUBTITLE_APPROVED_DOCUMENT_RESULT_KIND",
    "AtomicSubtitleApprovedDocumentPersistence",
    "PreparedSubtitleApprovedDocument",
    "SubtitleApprovedAssemblyError",
    "SubtitleApprovedAssemblyIdentityPlan",
    "SubtitleApprovedDocument",
    "SubtitleApprovedSubtitleAssemblyService",
    "SubtitleApprovedUnit",
    "SubtitleApprovedUnitOrigin",
    "SubtitleDecisionRevisionQuery",
    "SubtitleExportEligibility",
    "SubtitleFinalSubtitleQuery",
    "SubtitleReadingRevisionQuery",
    "SubtitleTimeRevisionQuery",
]
