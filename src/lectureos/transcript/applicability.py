"""Append-only applicability and current-selection records for Transcript lineage."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from lectureos.execution.identities import (
    ProcessingRunId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.repositories import InMemoryRepository
from lectureos.review.identities import ApprovedDecisionId, ReviewDecisionId

from .boundaries import TranscriptQueryBoundary
from .identities import TranscriptApplicabilityId, TranscriptId, TranscriptRevisionId

if TYPE_CHECKING:
    from lectureos.application.identities import TranscriptCorrectionApplicationResultId


class TranscriptApplicabilityKind(str, Enum):
    CURRENT = "current"
    UNDETERMINED = "undetermined"
    STALE = "stale"
    SUPERSEDED = "superseded"
    HISTORICAL = "historical"


@dataclass(frozen=True, slots=True)
class RevisionTarget:
    transcript_id: TranscriptId
    source_timeline_id: SourceTimelineId
    revision_id: TranscriptRevisionId | None = None


@dataclass(frozen=True, slots=True)
class RevisionApplicabilityRecord:
    identity: TranscriptApplicabilityId
    working_context: WorkingContextReference
    target: RevisionTarget
    kind: TranscriptApplicabilityKind
    reason: str
    sequence: int
    previous_record_id: TranscriptApplicabilityId | None = None
    source_decision_id: ReviewDecisionId | None = None
    source_approved_decision_id: ApprovedDecisionId | None = None
    source_application_result_id: TranscriptCorrectionApplicationResultId | None = None
    run_id: ProcessingRunId | None = None
    unit_execution_id: UnitExecutionId | None = None
    human_confirmation_required: bool = False
    superseding_target: RevisionTarget | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("applicability reason must not be empty")
        if self.sequence < 0:
            raise ValueError("applicability sequence must not be negative")
        if (self.run_id is None) != (self.unit_execution_id is None):
            raise ValueError("applicability execution provenance requires run and unit execution")
        if (
            self.kind is TranscriptApplicabilityKind.SUPERSEDED
            and self.superseding_target is None
        ):
            raise ValueError("superseded applicability requires a superseding revision")


@dataclass(frozen=True, slots=True)
class CurrentTranscriptSelection:
    identity: TranscriptApplicabilityId
    working_context: WorkingContextReference
    target: RevisionTarget
    reason: str
    sequence: int
    previous_selection_id: TranscriptApplicabilityId | None = None
    source_decision_id: ReviewDecisionId | None = None
    source_approved_decision_id: ApprovedDecisionId | None = None
    source_application_result_id: TranscriptCorrectionApplicationResultId | None = None
    run_id: ProcessingRunId | None = None
    unit_execution_id: UnitExecutionId | None = None
    human_confirmation: bool = False

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("selection reason must not be empty")
        if self.sequence < 0:
            raise ValueError("selection sequence must not be negative")
        if (self.run_id is None) != (self.unit_execution_id is None):
            raise ValueError("selection execution provenance requires run and unit execution")

    @property
    def kind(self) -> TranscriptApplicabilityKind:
        return TranscriptApplicabilityKind.CURRENT


class TranscriptApplicabilityIntegrityError(RuntimeError):
    pass


class TranscriptApplicabilityService:
    """Manages applicability without changing Transcript or Revision records."""

    def __init__(self, transcript_query: TranscriptQueryBoundary) -> None:
        self._transcript_query = transcript_query
        self.records: InMemoryRepository[
            TranscriptApplicabilityId, RevisionApplicabilityRecord
        ] = InMemoryRepository()
        self.selections: InMemoryRepository[
            TranscriptApplicabilityId, CurrentTranscriptSelection
        ] = InMemoryRepository()

    def register_undetermined_revision(
        self,
        *,
        identity: TranscriptApplicabilityId,
        working_context: WorkingContextReference,
        target: RevisionTarget,
        reason: str,
        source_decision_id: ReviewDecisionId | None = None,
        source_approved_decision_id: ApprovedDecisionId | None = None,
        source_application_result_id: TranscriptCorrectionApplicationResultId | None = None,
        run_id: ProcessingRunId | None = None,
        unit_execution_id: UnitExecutionId | None = None,
    ) -> RevisionApplicabilityRecord:
        return self._record_condition(
            identity=identity,
            working_context=working_context,
            target=target,
            kind=TranscriptApplicabilityKind.UNDETERMINED,
            reason=reason,
            source_decision_id=source_decision_id,
            source_approved_decision_id=source_approved_decision_id,
            source_application_result_id=source_application_result_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
        )

    def select_current_revision(
        self,
        *,
        identity: TranscriptApplicabilityId,
        working_context: WorkingContextReference,
        target: RevisionTarget,
        reason: str,
        superseded_record_id: TranscriptApplicabilityId | None = None,
        source_decision_id: ReviewDecisionId | None = None,
        source_approved_decision_id: ApprovedDecisionId | None = None,
        source_application_result_id: TranscriptCorrectionApplicationResultId | None = None,
        run_id: ProcessingRunId | None = None,
        unit_execution_id: UnitExecutionId | None = None,
        human_confirmation: bool = False,
    ) -> CurrentTranscriptSelection:
        self._require_new_identity(identity)
        self._validate_target(target)
        previous = self.get_current_selection(working_context, target.transcript_id)
        if self._is_stale(working_context, target) and not human_confirmation:
            raise ValueError("stale revision requires explicit Human confirmation")
        if previous is not None and previous.target != target:
            if superseded_record_id is None:
                raise ValueError("new current selection requires a superseded record identity")
            self._require_new_identity(superseded_record_id)
        elif superseded_record_id is not None:
            raise ValueError("superseded record is only valid when current target changes")

        sequence = self._next_sequence(working_context, target.transcript_id)
        selection = CurrentTranscriptSelection(
            identity=identity,
            working_context=working_context,
            target=target,
            reason=reason,
            sequence=sequence,
            previous_selection_id=previous.identity if previous is not None else None,
            source_decision_id=source_decision_id,
            source_approved_decision_id=source_approved_decision_id,
            source_application_result_id=source_application_result_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            human_confirmation=human_confirmation,
        )
        superseded = None
        if previous is not None and previous.target != target:
            superseded = self._build_condition(
                identity=superseded_record_id,
                working_context=working_context,
                target=previous.target,
                kind=TranscriptApplicabilityKind.SUPERSEDED,
                reason=f"superseded by selection {identity.value}",
                sequence=sequence + 1,
                source_decision_id=source_decision_id,
                source_approved_decision_id=source_approved_decision_id,
                source_application_result_id=source_application_result_id,
                run_id=run_id,
                unit_execution_id=unit_execution_id,
                superseding_target=target,
            )

        self.selections.save(selection)
        if superseded is not None:
            self.records.save(superseded)
        return selection

    def mark_revision_stale(
        self,
        *,
        identity: TranscriptApplicabilityId,
        working_context: WorkingContextReference,
        target: RevisionTarget,
        reason: str,
        human_confirmation_required: bool = True,
        run_id: ProcessingRunId | None = None,
        unit_execution_id: UnitExecutionId | None = None,
    ) -> RevisionApplicabilityRecord:
        return self._record_condition(
            identity=identity,
            working_context=working_context,
            target=target,
            kind=TranscriptApplicabilityKind.STALE,
            reason=reason,
            human_confirmation_required=human_confirmation_required,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
        )

    def supersede_revision(
        self,
        *,
        identity: TranscriptApplicabilityId,
        working_context: WorkingContextReference,
        target: RevisionTarget,
        superseding_revision_id: TranscriptRevisionId,
        reason: str,
        source_application_result_id: TranscriptCorrectionApplicationResultId | None = None,
    ) -> RevisionApplicabilityRecord:
        if target.revision_id == superseding_revision_id:
            raise ValueError("revision cannot supersede itself")
        superseding = RevisionTarget(
            transcript_id=target.transcript_id,
            source_timeline_id=target.source_timeline_id,
            revision_id=superseding_revision_id,
        )
        self._validate_target(superseding)
        return self._record_condition(
            identity=identity,
            working_context=working_context,
            target=target,
            kind=TranscriptApplicabilityKind.SUPERSEDED,
            reason=reason,
            source_application_result_id=source_application_result_id,
            superseding_target=superseding,
        )

    def mark_historical(
        self,
        *,
        identity: TranscriptApplicabilityId,
        working_context: WorkingContextReference,
        target: RevisionTarget,
        reason: str,
    ) -> RevisionApplicabilityRecord:
        return self._record_condition(
            identity=identity,
            working_context=working_context,
            target=target,
            kind=TranscriptApplicabilityKind.HISTORICAL,
            reason=reason,
        )

    def record_reprocessing_relationship(
        self,
        *,
        identity: TranscriptApplicabilityId,
        working_context: WorkingContextReference,
        target: RevisionTarget,
        reason: str,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
    ) -> RevisionApplicabilityRecord:
        return self.mark_revision_stale(
            identity=identity,
            working_context=working_context,
            target=target,
            reason=reason,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
        )

    def get_current_selection(
        self,
        working_context: WorkingContextReference,
        transcript_id: TranscriptId,
    ) -> CurrentTranscriptSelection | None:
        selections = tuple(
            item
            for item in self.selections.all()
            if item.working_context == working_context
            and item.target.transcript_id == transcript_id
        )
        if not selections:
            return None
        referenced = {
            item.previous_selection_id
            for item in selections
            if item.previous_selection_id is not None
        }
        heads = tuple(item for item in selections if item.identity not in referenced)
        if len(heads) != 1:
            raise TranscriptApplicabilityIntegrityError(
                "conflicting current selections exist for working context and lineage"
            )
        return heads[0]

    def get_current_revision(
        self,
        working_context: WorkingContextReference,
        transcript_id: TranscriptId,
    ) -> RevisionTarget | None:
        selection = self.get_current_selection(working_context, transcript_id)
        return selection.target if selection is not None else None

    def get_applicability_history(
        self,
        working_context: WorkingContextReference,
        transcript_id: TranscriptId,
    ) -> tuple[RevisionApplicabilityRecord | CurrentTranscriptSelection, ...]:
        entries = tuple(
            item
            for item in (*self.records.all(), *self.selections.all())
            if item.working_context == working_context
            and item.target.transcript_id == transcript_id
        )
        return tuple(sorted(entries, key=lambda item: item.sequence))

    def get_revision_history(
        self,
        working_context: WorkingContextReference,
        target: RevisionTarget,
    ) -> tuple[RevisionApplicabilityRecord | CurrentTranscriptSelection, ...]:
        return tuple(
            item
            for item in self.get_applicability_history(
                working_context, target.transcript_id
            )
            if item.target == target
        )

    def get_stale_revisions(
        self,
        working_context: WorkingContextReference,
        transcript_id: TranscriptId,
    ) -> tuple[RevisionTarget, ...]:
        return tuple(
            record.target
            for record in self.records.all()
            if record.working_context == working_context
            and record.target.transcript_id == transcript_id
            and record.kind is TranscriptApplicabilityKind.STALE
        )

    def get_superseded_relationships(
        self,
        working_context: WorkingContextReference,
        transcript_id: TranscriptId,
    ) -> tuple[RevisionApplicabilityRecord, ...]:
        return tuple(
            record
            for record in self.records.all()
            if record.working_context == working_context
            and record.target.transcript_id == transcript_id
            and record.kind is TranscriptApplicabilityKind.SUPERSEDED
        )

    def _record_condition(self, **values) -> RevisionApplicabilityRecord:
        identity = values["identity"]
        target = values["target"]
        working_context = values["working_context"]
        self._require_new_identity(identity)
        self._validate_target(target)
        record = self._build_condition(
            sequence=self._next_sequence(working_context, target.transcript_id),
            **values,
        )
        self.records.save(record)
        return record

    def _build_condition(self, **values) -> RevisionApplicabilityRecord:
        target = values["target"]
        working_context = values["working_context"]
        previous = self.get_applicability_history(
            working_context, target.transcript_id
        )
        values.setdefault("previous_record_id", previous[-1].identity if previous else None)
        return RevisionApplicabilityRecord(**values)

    def _validate_target(self, target: RevisionTarget) -> None:
        raw = self._transcript_query.get_raw_transcript(target.transcript_id)
        if raw is None:
            raise KeyError("unknown transcript lineage")
        if raw.source_timeline_id != target.source_timeline_id:
            raise ValueError("applicability Source Timeline does not match lineage")
        if target.revision_id is not None:
            revision = self._transcript_query.get_corrected_revision(target.revision_id)
            if revision is None:
                raise KeyError("unknown corrected transcript revision")
            if revision.transcript_id != target.transcript_id:
                raise ValueError("revision belongs to another transcript lineage")

    def _is_stale(
        self,
        working_context: WorkingContextReference,
        target: RevisionTarget,
    ) -> bool:
        return any(
            record.kind is TranscriptApplicabilityKind.STALE
            for record in self.get_revision_history(working_context, target)
            if isinstance(record, RevisionApplicabilityRecord)
        )

    def _require_new_identity(self, identity: TranscriptApplicabilityId) -> None:
        if self.records.get(identity) is not None or self.selections.get(identity) is not None:
            raise ValueError("transcript applicability identity already exists")

    def _next_sequence(
        self,
        working_context: WorkingContextReference,
        transcript_id: TranscriptId,
    ) -> int:
        history = self.get_applicability_history(working_context, transcript_id)
        return max((item.sequence for item in history), default=-1) + 1
