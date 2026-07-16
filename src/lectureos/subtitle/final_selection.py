"""Human-authorized, append-only Final Subtitle selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Generic, TypeVar

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import WorkingContextReference
from lectureos.review.identities import HumanActorReference

from .applicability import (
    SubtitleApplicabilityIntegrityError,
    SubtitleConditionState,
    SubtitleSelectionState,
)
from .boundaries import (
    SubtitleApplicabilityQueryBoundary,
    SubtitleQueryBoundary,
    SubtitleRevisionValidationBoundary,
)
from .identities import (
    FinalSubtitleSelectionId,
    SubtitleId,
    SubtitleRevisionApplicabilityId,
    SubtitleRevisionId,
    SubtitleValidationId,
)


class FinalSubtitleSelectionReason(str, Enum):
    MANUAL_SELECTION = "manual_selection"
    REPLACEMENT_SELECTION = "replacement_selection"
    REACTIVATION = "reactivation"
    STALE_OVERRIDE = "stale_override"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class FinalSubtitleSelection:
    identity: FinalSubtitleSelectionId
    working_context: WorkingContextReference
    subtitle_id: SubtitleId
    revision_id: SubtitleRevisionId
    actor: HumanActorReference
    validation_id: SubtitleValidationId
    current_applicability_id: SubtitleRevisionApplicabilityId
    selected_at: datetime
    sequence: int
    reason: FinalSubtitleSelectionReason
    previous_final_selection_id: FinalSubtitleSelectionId | None = None
    reason_note: str | None = None
    stale_condition_acknowledged: bool = False
    stale_condition_id: SubtitleRevisionApplicabilityId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.actor, HumanActorReference):
            raise TypeError("Final Subtitle selection requires a Human Actor")
        if not isinstance(self.reason, FinalSubtitleSelectionReason):
            raise ValueError("Final Subtitle selection requires a typed reason")
        if self.sequence < 0:
            raise ValueError("Final Subtitle selection sequence must not be negative")
        if (
            self.reason is FinalSubtitleSelectionReason.OTHER
            and (self.reason_note is None or not self.reason_note.strip())
        ):
            raise ValueError("other Final Subtitle selection reason requires a note")
        if self.stale_condition_acknowledged and self.stale_condition_id is None:
            raise ValueError("stale acknowledgment requires stale condition evidence")
        if self.stale_condition_id is not None and not self.stale_condition_acknowledged:
            raise ValueError("stale condition evidence requires acknowledgment")


class FinalSubtitleSelectionIntegrityError(RuntimeError):
    pass


IdentityT = TypeVar("IdentityT")
RecordT = TypeVar("RecordT")


class _AppendOnlySelectionRepository(Generic[IdentityT, RecordT]):
    def __init__(self) -> None:
        self._records: dict[IdentityT, RecordT] = {}

    def get(self, identity: IdentityT) -> RecordT | None:
        return self._records.get(identity)

    def save(self, record: RecordT) -> None:
        identity = getattr(record, "identity")
        if identity in self._records:
            raise ValueError("Final Subtitle selection identity already exists")
        self._records[identity] = record

    def all(self) -> tuple[RecordT, ...]:
        return tuple(self._records.values())


class FinalSubtitleSelectionService:
    """Selects a validated current Revision without changing its lifecycle."""

    def __init__(
        self,
        subtitle_query: SubtitleQueryBoundary,
        validation_query: SubtitleRevisionValidationBoundary,
        applicability_query: SubtitleApplicabilityQueryBoundary,
        execution_query: ExecutionQueryBoundary,
    ) -> None:
        self._subtitle_query = subtitle_query
        self._validation_query = validation_query
        self._applicability_query = applicability_query
        self._execution_query = execution_query
        self.selections: _AppendOnlySelectionRepository[
            FinalSubtitleSelectionId, FinalSubtitleSelection
        ] = _AppendOnlySelectionRepository()

    def select_final_subtitle(
        self,
        *,
        identity: FinalSubtitleSelectionId,
        working_context: WorkingContextReference,
        revision_id: SubtitleRevisionId,
        actor: HumanActorReference,
        validation_id: SubtitleValidationId,
        reason: FinalSubtitleSelectionReason,
        stale_condition_acknowledged: bool = False,
        reason_note: str | None = None,
    ) -> FinalSubtitleSelection:
        revision = self._require_revision(
            revision_id, working_context, actor
        )
        current_record, stale_record = self._require_current_applicability(
            revision,
            working_context,
            stale_condition_acknowledged,
        )
        self._require_latest_valid_validation(
            revision,
            working_context,
            validation_id,
        )
        latest = self.get_latest_final_selection(
            working_context, revision.subtitle_id
        )
        if latest is not None and latest.revision_id == revision.identity:
            return latest
        record = FinalSubtitleSelection(
            identity=identity,
            working_context=working_context,
            subtitle_id=revision.subtitle_id,
            revision_id=revision.identity,
            actor=actor,
            validation_id=validation_id,
            current_applicability_id=current_record.identity,
            selected_at=datetime.now(timezone.utc),
            sequence=latest.sequence + 1 if latest is not None else 0,
            reason=reason,
            previous_final_selection_id=latest.identity if latest is not None else None,
            reason_note=reason_note,
            stale_condition_acknowledged=stale_condition_acknowledged,
            stale_condition_id=stale_record.identity if stale_record is not None else None,
        )
        if self.selections.get(identity) is not None:
            raise ValueError("Final Subtitle selection identity already exists")
        self.selections.save(record)
        return record

    def get_final_selection(
        self, identity: FinalSubtitleSelectionId
    ) -> FinalSubtitleSelection | None:
        return self.selections.get(identity)

    def get_final_selection_history(
        self,
        working_context: WorkingContextReference,
        subtitle_id: SubtitleId,
    ) -> tuple[FinalSubtitleSelection, ...]:
        history = tuple(
            sorted(
                (
                    selection
                    for selection in self.selections.all()
                    if selection.working_context == working_context
                    and selection.subtitle_id == subtitle_id
                ),
                key=lambda selection: selection.sequence,
            )
        )
        self._validate_history(history)
        return history

    def get_latest_final_selection(
        self,
        working_context: WorkingContextReference,
        subtitle_id: SubtitleId,
    ) -> FinalSubtitleSelection | None:
        history = self.get_final_selection_history(working_context, subtitle_id)
        return history[-1] if history else None

    def get_final_selections_for_revision(
        self, revision_id: SubtitleRevisionId
    ) -> tuple[FinalSubtitleSelection, ...]:
        selections = tuple(
            selection
            for selection in self.selections.all()
            if selection.revision_id == revision_id
        )
        return tuple(
            sorted(
                selections,
                key=lambda selection: (
                    selection.working_context.value,
                    selection.sequence,
                ),
            )
        )

    def is_active_final(
        self,
        working_context: WorkingContextReference,
        subtitle_id: SubtitleId,
        revision_id: SubtitleRevisionId,
    ) -> bool:
        latest = self.get_latest_final_selection(working_context, subtitle_id)
        return latest is not None and latest.revision_id == revision_id

    def _require_revision(self, revision_id, working_context, actor):
        if not isinstance(actor, HumanActorReference):
            raise TypeError("Final Subtitle selection requires a Human Actor")
        revision = self._subtitle_query.get_revision(revision_id)
        if revision is None:
            raise KeyError("unknown Subtitle Revision")
        run = self._execution_query.get_run(revision.run_id)
        execution = self._execution_query.get_unit_execution(
            revision.unit_execution_id
        )
        if (
            run is None
            or execution is None
            or execution.run_id != revision.run_id
            or run.working_context != working_context
        ):
            raise ValueError(
                "Subtitle Revision and Final Selection Working Context differ"
            )
        domain_result = self._subtitle_query.get_domain_result_reference(
            revision.domain_result_id
        )
        if domain_result is None or domain_result.kind != "subtitle_revision":
            raise ValueError("Subtitle Revision lineage evidence is incomplete")
        if len(set(revision.cue_ids)) != len(revision.cue_ids):
            raise ValueError("Final Subtitle Revision contains duplicate Cue references")
        for cue_id in revision.cue_ids:
            cue = self._subtitle_query.get_cue(cue_id)
            if cue is None:
                raise KeyError("Final Subtitle Revision references an unknown Cue")
            if (
                cue.subtitle_id != revision.subtitle_id
                or cue.source_timeline_id != domain_result.source_timeline
            ):
                raise ValueError("Final Subtitle Revision Cue lineage differs")
            if cue.replaces_cue_id is not None:
                original = self._subtitle_query.get_cue(cue.replaces_cue_id)
                if original is None:
                    raise KeyError("Final Subtitle replacement Cue original is missing")
                if (
                    original.identity == cue.identity
                    or original.subtitle_id != cue.subtitle_id
                    or original.source_timeline_id != cue.source_timeline_id
                    or original.source_transcript_id != cue.source_transcript_id
                    or original.source_revision_id != cue.source_revision_id
                    or original.start != cue.start
                    or original.end != cue.end
                    or original.display_order != cue.display_order
                    or original.source_segment_ids != cue.source_segment_ids
                ):
                    raise ValueError("Final Subtitle replacement Cue lineage differs")
        return revision

    def _require_current_applicability(
        self, revision, working_context, stale_condition_acknowledged
    ):
        try:
            current_revision_id = self._applicability_query.get_current_revision(
                working_context, revision.subtitle_id
            )
        except SubtitleApplicabilityIntegrityError:
            raise
        if current_revision_id != revision.identity:
            raise ValueError("Final Subtitle target must be the current Revision")
        current_record = self._applicability_query.get_latest_selection(
            working_context, revision.identity
        )
        if (
            current_record is None
            or current_record.selection_state is not SubtitleSelectionState.CURRENT
            or current_record.subtitle_id != revision.subtitle_id
        ):
            raise ValueError("Final Subtitle current applicability evidence differs")
        stale_record = self._applicability_query.get_latest_condition(
            working_context, revision.identity
        )
        is_stale = (
            stale_record is not None
            and stale_record.condition_state is SubtitleConditionState.STALE
        )
        if is_stale and not stale_condition_acknowledged:
            raise ValueError("stale current Revision requires Human acknowledgment")
        if not is_stale and stale_condition_acknowledged:
            raise ValueError("stale acknowledgment requires a stale Revision")
        return current_record, stale_record if is_stale else None

    def _require_latest_valid_validation(
        self, revision, working_context, validation_id
    ) -> None:
        history = self._validation_query.get_revision_validation_history(
            revision.identity
        )
        self._validate_validation_history(history, revision.identity)
        if not history:
            raise ValueError("Final Subtitle selection requires Revision Validation")
        latest = history[-1]
        if latest.identity != validation_id:
            raise ValueError("Final Subtitle selection requires latest Revision Validation")
        if (
            latest.target_revision_id != revision.identity
            or latest.target_candidate_id is not None
            or latest.working_context != working_context
            or latest.target_cue_ids != revision.cue_ids
        ):
            raise ValueError("Final Subtitle Validation evidence differs")
        findings = self._validation_query.get_validation_findings(latest.identity)
        if tuple(finding.identity for finding in findings) != latest.finding_ids:
            raise FinalSubtitleSelectionIntegrityError(
                "Final Subtitle Validation findings are incomplete"
            )
        if not latest.structural_valid or any(finding.blocking for finding in findings):
            raise ValueError("structurally invalid Revision cannot be Final Subtitle")

    @staticmethod
    def _validate_validation_history(history, revision_id) -> None:
        for index, validation in enumerate(history):
            expected_previous = history[index - 1].identity if index else None
            if (
                validation.target_revision_id != revision_id
                or validation.sequence != index
                or validation.previous_validation_id != expected_previous
            ):
                raise FinalSubtitleSelectionIntegrityError(
                    "Revision Validation history is corrupt"
                )

    @staticmethod
    def _validate_history(history) -> None:
        for index, selection in enumerate(history):
            expected_previous = history[index - 1].identity if index else None
            if (
                selection.sequence != index
                or selection.previous_final_selection_id != expected_previous
            ):
                raise FinalSubtitleSelectionIntegrityError(
                    "Final Subtitle selection history is corrupt"
                )
