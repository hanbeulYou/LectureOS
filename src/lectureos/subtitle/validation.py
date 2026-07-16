"""Independent structural validation for persisted Subtitle records."""

from dataclasses import replace
from datetime import datetime, timezone
from math import isfinite

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import (
    ProcessingRunId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import ProcessingState
from lectureos.transcript.boundaries import TranscriptQueryBoundary

from .identities import (
    SubtitleCandidateId,
    SubtitleRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from .boundaries import SubtitleValidationStoreBoundary
from .models import SubtitleCandidate, SubtitleRevision, SubtitleValidation, SubtitleValidationFinding


class SubtitleValidationService:
    def __init__(
        self,
        store: SubtitleValidationStoreBoundary,
        transcript_query: TranscriptQueryBoundary,
        execution_query: ExecutionQueryBoundary,
    ) -> None:
        self._store = store
        self._transcript_query = transcript_query
        self._execution_query = execution_query

    def validate_candidate(
        self,
        *,
        validation_id: SubtitleValidationId,
        candidate_id: SubtitleCandidateId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
    ) -> SubtitleValidation:
        candidate = self._store.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError("unknown subtitle candidate")
        return self._validate(
            validation_id, candidate, run_id, unit_execution_id
        )

    def validate_revision(
        self,
        *,
        validation_id: SubtitleValidationId,
        revision_id: SubtitleRevisionId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
    ) -> SubtitleValidation:
        revision = self._store.get_revision(revision_id)
        if revision is None:
            raise KeyError("unknown subtitle revision")
        return self._validate(
            validation_id, revision, run_id, unit_execution_id
        )

    def validate_revision_in_context(
        self,
        *,
        validation_id: SubtitleValidationId,
        revision_id: SubtitleRevisionId,
        working_context: WorkingContextReference,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
    ) -> SubtitleValidation:
        revision = self._store.get_revision(revision_id)
        if revision is None:
            raise KeyError("unknown subtitle revision")
        self._require_validation_execution(
            working_context, run_id, unit_execution_id
        )
        cues = self._resolve_revision_request(revision, working_context)
        history = self.get_revision_validation_history(revision_id)
        return self._validate(
            validation_id,
            revision,
            run_id,
            unit_execution_id,
            working_context=working_context,
            resolved_cues=cues,
            sequence=len(history),
            previous_validation_id=history[-1].identity if history else None,
        )

    def get_validation_findings(
        self, validation_id: SubtitleValidationId
    ) -> tuple[SubtitleValidationFinding, ...]:
        validation = self._store.get_validation(validation_id)
        if validation is None:
            return ()
        return tuple(
            finding
            for finding_id in validation.finding_ids
            if (finding := self._store.get_validation_finding(finding_id)) is not None
        )

    def get_revision_validation_history(
        self, revision_id: SubtitleRevisionId
    ) -> tuple[SubtitleValidation, ...]:
        return tuple(
            sorted(
                (
                    validation
                    for validation in self._store.get_validations_for_revision(
                        revision_id
                    )
                    if validation.target_revision_id == revision_id
                    and validation.sequence is not None
                ),
                key=lambda validation: validation.sequence,
            )
        )

    def get_latest_revision_validation(
        self, revision_id: SubtitleRevisionId
    ) -> SubtitleValidation | None:
        history = self.get_revision_validation_history(revision_id)
        return history[-1] if history else None

    def _validate(
        self,
        validation_id,
        target,
        run_id,
        execution_id,
        *,
        working_context=None,
        resolved_cues=None,
        sequence=None,
        previous_validation_id=None,
    ):
        if self._store.get_validation(validation_id) is not None:
            raise ValueError("subtitle validation identity already exists")
        findings = []

        def add(rule, description, blocking, cue_id=None):
            findings.append(
                SubtitleValidationFinding(
                    identity=SubtitleValidationFindingId(
                        f"{validation_id.value}:{len(findings)}"
                    ),
                    validation_id=validation_id,
                    rule=rule,
                    description=description,
                    blocking=blocking,
                    cue_id=cue_id,
                )
            )

        cues = []
        resolved = (
            {cue.identity: cue for cue in resolved_cues}
            if resolved_cues is not None
            else None
        )
        candidate = target if isinstance(target, SubtitleCandidate) else None
        if isinstance(target, SubtitleRevision):
            try:
                candidate = self._root_candidate(target)
            except (KeyError, ValueError) as error:
                add("parent_inconsistent", str(error), True)
        expected_timeline = (
            candidate.source_timeline_id if candidate is not None else None
        )
        if len(set(target.cue_ids)) != len(target.cue_ids):
            add("duplicate_cue_reference", "Cue reference is duplicated", True)
        for cue_id in target.cue_ids:
            cue = (
                resolved.get(cue_id)
                if resolved is not None
                else self._store.get_cue(cue_id)
            )
            if cue is None:
                add("missing_cue", "Referenced Cue does not exist", True, cue_id)
                continue
            cues.append(cue)
            if (
                not isfinite(cue.start)
                or not isfinite(cue.end)
                or cue.start < 0
                or cue.end < 0
                or cue.start > cue.end
            ):
                add("invalid_time_range", "Cue time range is invalid", True, cue_id)
            if expected_timeline is not None and cue.source_timeline_id != expected_timeline:
                add("timeline_mismatch", "Cue Source Timeline differs", True, cue_id)
            if candidate is not None and (
                cue.subtitle_id != target.subtitle_id
                or cue.source_transcript_id != candidate.source_transcript_id
                or cue.source_revision_id != candidate.source_revision_id
            ):
                add("lineage_mismatch", "Cue source lineage differs", True, cue_id)
            if not cue.source_segment_ids:
                add("missing_source_segment", "Cue has no Transcript source", True, cue_id)
            for segment_id in cue.source_segment_ids:
                segment = self._transcript_query.get_segment(segment_id)
                if segment is None:
                    add("missing_source_segment", "Transcript Segment is missing", True, cue_id)
                elif segment.transcript_id != cue.source_transcript_id:
                    add("lineage_mismatch", "Transcript Segment lineage differs", True, cue_id)
        orders = [cue.display_order for cue in cues]
        if len(set(orders)) != len(orders):
            add("duplicate_display_order", "Display order is duplicated", True)
        if orders != sorted(orders):
            add("display_order_mismatch", "Cue references contradict display order", True)
        ordered = sorted(cues, key=lambda cue: cue.display_order)
        for previous, current in zip(ordered, ordered[1:]):
            if current.start < previous.end:
                add("cue_overlap", "Cue time ranges overlap", False, current.identity)
            elif current.start > previous.end:
                add("cue_gap", "Cue time ranges contain a gap", False, current.identity)
        if isinstance(target, SubtitleRevision) and candidate is not None:
            try:
                self._validate_revision_parent(target)
            except (KeyError, ValueError) as error:
                add("parent_inconsistent", str(error), True)
        self._validate_provenance(target, add)

        blocking = any(item.blocking for item in findings)
        validation = SubtitleValidation(
            identity=validation_id,
            run_id=run_id,
            unit_execution_id=execution_id,
            structural_valid=not blocking,
            timeline_consistent=not any(
                item.rule == "timeline_mismatch" for item in findings
            ),
            ordering_consistent=not any(
                item.rule in ("duplicate_display_order", "display_order_mismatch")
                for item in findings
            ),
            provenance_complete=not any(
                item.rule
                in (
                    "missing_source_segment",
                    "lineage_mismatch",
                    "parent_inconsistent",
                    "provenance_incomplete",
                )
                for item in findings
            ),
            target_candidate_id=target.identity
            if isinstance(target, SubtitleCandidate)
            else None,
            target_revision_id=target.identity
            if isinstance(target, SubtitleRevision)
            else None,
            finding_ids=tuple(item.identity for item in findings),
            has_warnings=any(not item.blocking for item in findings),
            working_context=working_context,
            target_cue_ids=target.cue_ids if working_context is not None else (),
            recorded_at=(
                datetime.now(timezone.utc) if working_context is not None else None
            ),
            sequence=sequence,
            previous_validation_id=previous_validation_id,
        )
        if isinstance(target, SubtitleRevision) and working_context is not None:
            findings = [
                replace(finding, revision_id=target.identity) for finding in findings
            ]
        self._store.record_validation(validation, tuple(findings))
        return validation

    def _resolve_revision_request(
        self,
        revision: SubtitleRevision,
        working_context: WorkingContextReference,
    ):
        revision_run = self._execution_query.get_run(revision.run_id)
        revision_execution = self._execution_query.get_unit_execution(
            revision.unit_execution_id
        )
        if (
            revision_run is None
            or revision_execution is None
            or revision_execution.run_id != revision.run_id
            or revision_run.working_context != working_context
        ):
            raise ValueError(
                "Subtitle Revision and validation Working Context differ"
            )
        try:
            candidate = self._root_candidate(revision)
        except (KeyError, ValueError):
            candidate = None
        if candidate is not None:
            candidate_run = self._execution_query.get_run(candidate.run_id)
            candidate_execution = self._execution_query.get_unit_execution(
                candidate.unit_execution_id
            )
            if (
                candidate_run is None
                or candidate_execution is None
                or candidate_execution.run_id != candidate.run_id
                or candidate_run.working_context != working_context
            ):
                raise ValueError("Revision source Cue Working Context differs")
        cues = []
        for cue_id in revision.cue_ids:
            cue = self._store.get_cue(cue_id)
            if cue is None:
                raise KeyError("Revision validation request references an unknown Cue")
            if (
                cue.subtitle_id != revision.subtitle_id
                or (
                    candidate is not None
                    and (
                        cue.source_timeline_id != candidate.source_timeline_id
                        or cue.source_transcript_id
                        != candidate.source_transcript_id
                        or cue.source_revision_id != candidate.source_revision_id
                    )
                )
            ):
                raise ValueError("Revision validation Cue lineage differs")
            if cue.replaces_cue_id is not None:
                original = self._store.get_cue(cue.replaces_cue_id)
                if original is None:
                    raise KeyError("Replacement Cue original does not exist")
                if original.identity == cue.identity:
                    raise ValueError("Replacement Cue must have a distinct identity")
                if (
                    original.subtitle_id != cue.subtitle_id
                    or original.source_timeline_id != cue.source_timeline_id
                    or original.source_transcript_id != cue.source_transcript_id
                    or original.source_revision_id != cue.source_revision_id
                    or original.start != cue.start
                    or original.end != cue.end
                    or original.display_order != cue.display_order
                    or original.source_segment_ids != cue.source_segment_ids
                ):
                    raise ValueError("Replacement Cue lineage differs")
            cues.append(cue)
        return tuple(cues)

    def _require_validation_execution(
        self,
        working_context: WorkingContextReference,
        run_id: ProcessingRunId,
        execution_id: UnitExecutionId,
    ) -> None:
        run = self._execution_query.get_run(run_id)
        execution = self._execution_query.get_unit_execution(execution_id)
        if run is None or execution is None:
            raise KeyError("unknown Subtitle validation execution provenance")
        if execution.run_id != run_id or run.working_context != working_context:
            raise ValueError("Subtitle validation execution provenance differs")
        if execution.state is not ProcessingState.RUNNING:
            raise ValueError("Subtitle validation requires a running Unit Execution")

    def _validate_provenance(self, target, add) -> None:
        run = self._execution_query.get_run(target.run_id)
        execution = self._execution_query.get_unit_execution(
            target.unit_execution_id
        )
        if run is None or execution is None or execution.run_id != target.run_id:
            add(
                "provenance_incomplete",
                "Processing Run and Unit Execution provenance is incomplete",
                True,
            )
        try:
            candidate = (
                target
                if isinstance(target, SubtitleCandidate)
                else self._root_candidate(target)
            )
            raw = self._transcript_query.get_raw_transcript(
                candidate.source_transcript_id
            )
            if raw is None:
                raise KeyError("source Transcript is missing")
            if (
                raw.source_media_id != candidate.source_media_id
                or raw.source_timeline_id != candidate.source_timeline_id
            ):
                raise ValueError("source Transcript provenance differs")
            if candidate.source_revision_id is not None:
                revision = self._transcript_query.get_corrected_revision(
                    candidate.source_revision_id
                )
                if (
                    revision is None
                    or revision.transcript_id != candidate.source_transcript_id
                ):
                    raise ValueError("source Transcript revision provenance differs")
        except (KeyError, ValueError) as error:
            add("provenance_incomplete", str(error), True)

    def _validate_revision_parent(self, revision: SubtitleRevision) -> None:
        if revision.parent_revision_id == revision.identity:
            raise ValueError("subtitle revision cannot be its own parent")
        self._root_candidate(revision)

    def _root_candidate(self, revision: SubtitleRevision) -> SubtitleCandidate:
        seen = set()
        current = revision
        while current.parent_revision_id is not None:
            if current.identity in seen:
                raise ValueError("subtitle revision cycle detected")
            seen.add(current.identity)
            current = self._store.get_revision(current.parent_revision_id)
            if current is None:
                raise KeyError("unknown parent Subtitle Revision")
        candidate = self._store.get_candidate(current.parent_candidate_id)
        if candidate is None:
            raise KeyError("unknown parent Subtitle Candidate")
        if candidate.subtitle_id != revision.subtitle_id:
            raise ValueError("Subtitle parent belongs to another lineage")
        return candidate
