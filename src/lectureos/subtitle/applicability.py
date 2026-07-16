"""Append-only applicability dimensions for Subtitle revisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import (
    ProcessingRunId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.review.boundaries import ReviewQueryBoundary
from lectureos.review.identities import (
    ApprovedDecisionId,
    HumanActorReference,
    ReviewDecisionId,
    ReviewItemId,
)

from .boundaries import SubtitleQueryBoundary
from .identities import (
    SubtitleId,
    SubtitleRevisionApplicabilityId,
    SubtitleRevisionId,
)
from .repositories import InMemoryRepository

if TYPE_CHECKING:
    from lectureos.application.identities import SubtitleDecisionApplicationResultId
    from lectureos.application.models import SubtitleDecisionApplicationResult


class SubtitleApplicationResultQuery(Protocol):
    def get_subtitle_application_result(
        self, identity: SubtitleDecisionApplicationResultId
    ) -> SubtitleDecisionApplicationResult | None: ...


class SubtitleApplicabilityDimension(str, Enum):
    SELECTION = "selection"
    CONDITION = "condition"


class SubtitleSelectionState(str, Enum):
    CURRENT = "current"
    SUPERSEDED = "superseded"
    HISTORICAL = "historical"


class SubtitleConditionState(str, Enum):
    STALE = "stale"


class SubtitleSelectionReason(str, Enum):
    MANUAL_SELECTION = "manual_selection"
    REPLACEMENT_SELECTION = "replacement_selection"
    REACTIVATION = "reactivation"
    MANUAL_HISTORICAL = "manual_historical"


class SubtitleConditionReason(str, Enum):
    MANUAL_STALE = "manual_stale"
    SOURCE_CHANGED = "source_changed"
    TRANSCRIPT_CHANGED = "transcript_changed"
    REVIEW_REOPENED = "review_reopened"
    REPROCESSING_DETECTED = "reprocessing_detected"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SubtitleApplicabilityEvidence:
    application_result_id: SubtitleDecisionApplicationResultId | None = None
    review_item_id: ReviewItemId | None = None
    review_decision_id: ReviewDecisionId | None = None
    approved_decision_id: ApprovedDecisionId | None = None
    run_id: ProcessingRunId | None = None
    unit_execution_id: UnitExecutionId | None = None

    def __post_init__(self) -> None:
        if (self.run_id is None) != (self.unit_execution_id is None):
            raise ValueError(
                "applicability execution provenance requires Run and Unit Execution"
            )


@dataclass(frozen=True, slots=True)
class SubtitleRevisionApplicabilityRecord:
    identity: SubtitleRevisionApplicabilityId
    dimension: SubtitleApplicabilityDimension
    working_context: WorkingContextReference
    subtitle_id: SubtitleId
    revision_id: SubtitleRevisionId
    actor: HumanActorReference
    recorded_at: datetime
    sequence: int
    previous_record_id: SubtitleRevisionApplicabilityId | None = None
    selection_state: SubtitleSelectionState | None = None
    condition_state: SubtitleConditionState | None = None
    selection_reason: SubtitleSelectionReason | None = None
    condition_reason: SubtitleConditionReason | None = None
    reason_note: str | None = None
    stale_condition_acknowledged: bool = False
    evidence: SubtitleApplicabilityEvidence = SubtitleApplicabilityEvidence()

    def __post_init__(self) -> None:
        if not isinstance(self.actor, HumanActorReference):
            raise TypeError("applicability command requires a Human Actor")
        if self.sequence < 0:
            raise ValueError("applicability sequence must not be negative")
        if self.dimension is SubtitleApplicabilityDimension.SELECTION:
            if not isinstance(self.selection_state, SubtitleSelectionState) or not isinstance(
                self.selection_reason, SubtitleSelectionReason
            ):
                raise ValueError("selection record requires state and typed reason")
            if self.condition_state is not None or self.condition_reason is not None:
                raise ValueError("selection and condition dimensions must remain separate")
        else:
            if self.condition_state is not SubtitleConditionState.STALE or not isinstance(
                self.condition_reason, SubtitleConditionReason
            ):
                raise ValueError("condition record requires stale state and typed reason")
            if self.selection_state is not None or self.selection_reason is not None:
                raise ValueError("selection and condition dimensions must remain separate")
        if (
            self.condition_reason is SubtitleConditionReason.OTHER
            and (self.reason_note is None or not self.reason_note.strip())
        ):
            raise ValueError("other stale reason requires a non-empty note")


class SubtitleApplicabilityIntegrityError(RuntimeError):
    pass


class SubtitleApplicabilityService:
    """Records applicability without creating or changing Subtitle revisions."""

    def __init__(
        self,
        subtitle_query: SubtitleQueryBoundary,
        execution_query: ExecutionQueryBoundary,
        review_query: ReviewQueryBoundary | None = None,
        application_query: SubtitleApplicationResultQuery | None = None,
    ) -> None:
        self._subtitle_query = subtitle_query
        self._execution_query = execution_query
        self._review_query = review_query
        self._application_query = application_query
        self.selection_records: InMemoryRepository[
            SubtitleRevisionApplicabilityId,
            SubtitleRevisionApplicabilityRecord,
        ] = InMemoryRepository()
        self.condition_records: InMemoryRepository[
            SubtitleRevisionApplicabilityId,
            SubtitleRevisionApplicabilityRecord,
        ] = InMemoryRepository()

    def select_current_revision(
        self,
        *,
        identity: SubtitleRevisionApplicabilityId,
        working_context: WorkingContextReference,
        revision_id: SubtitleRevisionId,
        actor: HumanActorReference,
        reason: SubtitleSelectionReason,
        superseded_identity: SubtitleRevisionApplicabilityId | None = None,
        stale_condition_acknowledged: bool = False,
        evidence: SubtitleApplicabilityEvidence = SubtitleApplicabilityEvidence(),
    ) -> SubtitleRevisionApplicabilityRecord:
        if reason not in (
            SubtitleSelectionReason.MANUAL_SELECTION,
            SubtitleSelectionReason.REACTIVATION,
        ):
            raise ValueError("current selection requires a current-selection reason")
        revision = self._validate_command(
            working_context, revision_id, actor, evidence
        )
        if (
            self.is_revision_stale(working_context, revision_id)
            and not stale_condition_acknowledged
        ):
            raise ValueError("stale Subtitle revision requires Human acknowledgment")
        latest = self.get_latest_selection(working_context, revision_id)
        if latest is not None and latest.selection_state is SubtitleSelectionState.CURRENT:
            return latest
        self._require_new_identity(identity)

        current = self._get_current_record(working_context, revision.subtitle_id)
        if current is not None and current.revision_id != revision_id:
            if superseded_identity is None:
                raise ValueError(
                    "changing current Subtitle requires a superseded record identity"
                )
            self._require_new_identity(superseded_identity)
        elif superseded_identity is not None:
            raise ValueError(
                "superseded identity is only valid when current Subtitle changes"
            )

        previous = self._latest_scope_record(
            self.selection_records, working_context, revision.subtitle_id
        )
        superseded = None
        if current is not None and current.revision_id != revision_id:
            superseded = self._selection_record(
                identity=superseded_identity,
                working_context=working_context,
                subtitle_id=revision.subtitle_id,
                revision_id=current.revision_id,
                actor=actor,
                state=SubtitleSelectionState.SUPERSEDED,
                reason=SubtitleSelectionReason.REPLACEMENT_SELECTION,
                previous=previous,
                evidence=evidence,
            )
            previous = superseded
        selected = self._selection_record(
            identity=identity,
            working_context=working_context,
            subtitle_id=revision.subtitle_id,
            revision_id=revision_id,
            actor=actor,
            state=SubtitleSelectionState.CURRENT,
            reason=reason,
            previous=previous,
            evidence=evidence,
            stale_condition_acknowledged=stale_condition_acknowledged,
        )
        if superseded is not None:
            self.selection_records.save(superseded)
        self.selection_records.save(selected)
        return selected

    def mark_revision_historical(
        self,
        *,
        identity: SubtitleRevisionApplicabilityId,
        working_context: WorkingContextReference,
        revision_id: SubtitleRevisionId,
        actor: HumanActorReference,
        reason: SubtitleSelectionReason,
        evidence: SubtitleApplicabilityEvidence = SubtitleApplicabilityEvidence(),
    ) -> SubtitleRevisionApplicabilityRecord:
        if reason is not SubtitleSelectionReason.MANUAL_HISTORICAL:
            raise ValueError("historical transition requires manual_historical reason")
        return self._record_selection(
            identity=identity,
            working_context=working_context,
            revision_id=revision_id,
            actor=actor,
            state=SubtitleSelectionState.HISTORICAL,
            reason=reason,
            evidence=evidence,
        )

    def mark_revision_superseded(
        self,
        *,
        identity: SubtitleRevisionApplicabilityId,
        working_context: WorkingContextReference,
        revision_id: SubtitleRevisionId,
        actor: HumanActorReference,
        reason: SubtitleSelectionReason,
        evidence: SubtitleApplicabilityEvidence = SubtitleApplicabilityEvidence(),
    ) -> SubtitleRevisionApplicabilityRecord:
        if reason is not SubtitleSelectionReason.REPLACEMENT_SELECTION:
            raise ValueError("superseded transition requires replacement_selection reason")
        return self._record_selection(
            identity=identity,
            working_context=working_context,
            revision_id=revision_id,
            actor=actor,
            state=SubtitleSelectionState.SUPERSEDED,
            reason=reason,
            evidence=evidence,
        )

    def mark_revision_stale(
        self,
        *,
        identity: SubtitleRevisionApplicabilityId,
        working_context: WorkingContextReference,
        revision_id: SubtitleRevisionId,
        actor: HumanActorReference,
        reason: SubtitleConditionReason,
        reason_note: str | None = None,
        evidence: SubtitleApplicabilityEvidence = SubtitleApplicabilityEvidence(),
    ) -> SubtitleRevisionApplicabilityRecord:
        revision = self._validate_command(
            working_context, revision_id, actor, evidence
        )
        latest = self.get_latest_condition(working_context, revision_id)
        if latest is not None and latest.condition_state is SubtitleConditionState.STALE:
            return latest
        self._require_new_identity(identity)
        previous = self._latest_scope_record(
            self.condition_records, working_context, revision.subtitle_id
        )
        record = SubtitleRevisionApplicabilityRecord(
            identity=identity,
            dimension=SubtitleApplicabilityDimension.CONDITION,
            working_context=working_context,
            subtitle_id=revision.subtitle_id,
            revision_id=revision_id,
            actor=actor,
            recorded_at=datetime.now(timezone.utc),
            sequence=self._next_sequence(previous),
            previous_record_id=previous.identity if previous else None,
            condition_state=SubtitleConditionState.STALE,
            condition_reason=reason,
            reason_note=reason_note,
            evidence=evidence,
        )
        self.condition_records.save(record)
        return record

    def get_current_revision(
        self,
        working_context: WorkingContextReference,
        subtitle_id: SubtitleId,
    ) -> SubtitleRevisionId | None:
        current = self._get_current_record(working_context, subtitle_id)
        return current.revision_id if current is not None else None

    def get_latest_selection(self, working_context, revision_id):
        history = self.get_revision_selection_history(working_context, revision_id)
        return history[-1] if history else None

    def get_latest_condition(self, working_context, revision_id):
        history = self.get_revision_condition_history(working_context, revision_id)
        return history[-1] if history else None

    def get_latest_scope_selection(self, working_context, subtitle_id):
        return self._latest_scope_record(
            self.selection_records, working_context, subtitle_id
        )

    def get_latest_scope_condition(self, working_context, subtitle_id):
        return self._latest_scope_record(
            self.condition_records, working_context, subtitle_id
        )

    def is_revision_stale(self, working_context, revision_id) -> bool:
        latest = self.get_latest_condition(working_context, revision_id)
        return (
            latest is not None
            and latest.condition_state is SubtitleConditionState.STALE
        )

    def get_scope_selection_history(self, working_context, subtitle_id):
        return self._scope_history(
            self.selection_records, working_context, subtitle_id
        )

    def get_scope_condition_history(self, working_context, subtitle_id):
        return self._scope_history(
            self.condition_records, working_context, subtitle_id
        )

    def get_revision_selection_history(self, working_context, revision_id):
        return tuple(
            item
            for item in self.selection_records.all()
            if item.working_context == working_context
            and item.revision_id == revision_id
        )

    def get_revision_condition_history(self, working_context, revision_id):
        return tuple(
            item
            for item in self.condition_records.all()
            if item.working_context == working_context
            and item.revision_id == revision_id
        )

    def get_revision_applicability_history(self, working_context, revision_id):
        return tuple(
            sorted(
                (
                    *self.get_revision_selection_history(
                        working_context, revision_id
                    ),
                    *self.get_revision_condition_history(
                        working_context, revision_id
                    ),
                ),
                key=lambda item: item.recorded_at,
            )
        )

    def _record_selection(self, **values):
        revision = self._validate_command(
            values["working_context"],
            values["revision_id"],
            values["actor"],
            values["evidence"],
        )
        latest = self.get_latest_selection(
            values["working_context"], values["revision_id"]
        )
        if latest is not None and latest.selection_state is values["state"]:
            return latest
        self._require_new_identity(values["identity"])
        previous = self._latest_scope_record(
            self.selection_records,
            values["working_context"],
            revision.subtitle_id,
        )
        record = self._selection_record(
            subtitle_id=revision.subtitle_id, previous=previous, **values
        )
        self.selection_records.save(record)
        return record

    def _selection_record(
        self,
        *,
        identity,
        working_context,
        subtitle_id,
        revision_id,
        actor,
        state,
        reason,
        previous,
        evidence,
        stale_condition_acknowledged=False,
    ):
        return SubtitleRevisionApplicabilityRecord(
            identity=identity,
            dimension=SubtitleApplicabilityDimension.SELECTION,
            working_context=working_context,
            subtitle_id=subtitle_id,
            revision_id=revision_id,
            actor=actor,
            recorded_at=datetime.now(timezone.utc),
            sequence=self._next_sequence(previous),
            previous_record_id=previous.identity if previous else None,
            selection_state=state,
            selection_reason=reason,
            stale_condition_acknowledged=stale_condition_acknowledged,
            evidence=evidence,
        )

    def _validate_command(
        self, working_context, revision_id, actor, evidence
    ):
        if not isinstance(actor, HumanActorReference):
            raise TypeError("applicability command requires a Human Actor")
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
                "Subtitle Revision and applicability Working Context differ"
            )
        self._validate_evidence(revision, working_context, evidence)
        return revision

    def _validate_evidence(self, revision, working_context, evidence) -> None:
        if evidence.run_id is not None:
            run = self._execution_query.get_run(evidence.run_id)
            execution = self._execution_query.get_unit_execution(
                evidence.unit_execution_id
            )
            if (
                run is None
                or execution is None
                or execution.run_id != evidence.run_id
                or run.working_context != working_context
            ):
                raise ValueError("applicability Execution evidence differs")
        application = None
        if evidence.application_result_id is not None:
            if self._application_query is None:
                raise ValueError("Application Result evidence cannot be verified")
            application = self._application_query.get_subtitle_application_result(
                evidence.application_result_id
            )
            if (
                application is None
                or application.created_revision_id != revision.identity
                or application.working_context != working_context
            ):
                raise ValueError("Subtitle Application Result evidence differs")
        if any(
            item is not None
            for item in (
                evidence.review_item_id,
                evidence.review_decision_id,
                evidence.approved_decision_id,
            )
        ):
            if self._review_query is None:
                raise ValueError("Review evidence cannot be verified")
            item = (
                self._review_query.get_review_item(evidence.review_item_id)
                if evidence.review_item_id is not None
                else None
            )
            decision = (
                self._review_query.get_decision(evidence.review_decision_id)
                if evidence.review_decision_id is not None
                else None
            )
            approved = (
                self._review_query.get_approved_decision(
                    evidence.approved_decision_id
                )
                if evidence.approved_decision_id is not None
                else None
            )
            if evidence.review_item_id is not None and item is None:
                raise ValueError("Review Item evidence differs")
            if evidence.review_decision_id is not None and decision is None:
                raise ValueError("Review Decision evidence differs")
            if evidence.approved_decision_id is not None and approved is None:
                raise ValueError("Approved Decision evidence differs")
            if decision is not None and item is not None:
                if decision.review_item_id != item.identity:
                    raise ValueError("Review evidence lineage differs")
            if approved is not None and decision is not None:
                if approved.source_decision_id != decision.identity:
                    raise ValueError("Review evidence lineage differs")
            linked_decision_id = (
                decision.identity
                if decision is not None
                else approved.source_decision_id
                if approved is not None
                else revision.decision_reference
            )
            if (
                linked_decision_id is None
                or revision.decision_reference != linked_decision_id
            ):
                raise ValueError("Review evidence does not belong to Subtitle Revision")
            if item is not None:
                linked_decision = (
                    decision
                    if decision is not None
                    else self._review_query.get_decision(linked_decision_id)
                )
                if (
                    linked_decision is None
                    or linked_decision.review_item_id != item.identity
                ):
                    raise ValueError("Review evidence lineage differs")
        if application is not None:
            pairs = (
                (evidence.review_item_id, application.review_item_id),
                (evidence.review_decision_id, application.source_decision_id),
                (evidence.approved_decision_id, application.approved_decision_id),
                (evidence.run_id, application.run_id),
                (evidence.unit_execution_id, application.unit_execution_id),
            )
            if any(given is not None and given != actual for given, actual in pairs):
                raise ValueError("Application Result evidence lineage differs")

    def _get_current_record(self, working_context, subtitle_id):
        latest_by_revision = {}
        for record in self.get_scope_selection_history(
            working_context, subtitle_id
        ):
            latest_by_revision[record.revision_id] = record
        currents = tuple(
            record
            for record in latest_by_revision.values()
            if record.selection_state is SubtitleSelectionState.CURRENT
        )
        if len(currents) > 1:
            raise SubtitleApplicabilityIntegrityError(
                "multiple current Subtitle revisions exist in one applicability scope"
            )
        return currents[0] if currents else None

    def _require_new_identity(self, identity) -> None:
        if (
            self.selection_records.get(identity) is not None
            or self.condition_records.get(identity) is not None
        ):
            raise ValueError("Subtitle applicability identity already exists")

    @staticmethod
    def _scope_history(repository, working_context, subtitle_id):
        return tuple(
            sorted(
                (
                    item
                    for item in repository.all()
                    if item.working_context == working_context
                    and item.subtitle_id == subtitle_id
                ),
                key=lambda item: item.sequence,
            )
        )

    @staticmethod
    def _latest_scope_record(repository, working_context, subtitle_id):
        history = SubtitleApplicabilityService._scope_history(
            repository, working_context, subtitle_id
        )
        return history[-1] if history else None

    @staticmethod
    def _next_sequence(previous):
        return previous.sequence + 1 if previous is not None else 0
