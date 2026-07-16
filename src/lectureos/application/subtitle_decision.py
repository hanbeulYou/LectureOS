"""Apply an approved Subtitle decision without selecting a Final Subtitle."""

from dataclasses import replace
from datetime import datetime, timezone

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import DomainResultId, ProcessingRunId, UnitExecutionId
from lectureos.execution.repositories import InMemoryRepository
from lectureos.review.boundaries import ReviewQueryBoundary
from lectureos.review.identities import ApprovedDecisionId
from lectureos.review.models import DecisionKind
from lectureos.subtitle.boundaries import (
    SubtitleProcessingBoundary,
    SubtitleQueryBoundary,
)
from lectureos.subtitle.identities import SubtitleCueId, SubtitleRevisionId
from lectureos.subtitle.models import SubtitleCue, SubtitleRevision

from .identities import SubtitleDecisionApplicationResultId
from .models import SubtitleDecisionApplicationResult, SubtitleTextReplacement
from .subtitle_review import SUBTITLE_CANDIDATE_KIND, SUBTITLE_SOURCE_DOMAIN


class SubtitleDecisionApplicationError(ValueError):
    """An approved review record cannot safely produce a Subtitle Revision."""


class SubtitleDecisionApplicationService:
    def __init__(
        self,
        review_query: ReviewQueryBoundary,
        subtitle_query: SubtitleQueryBoundary,
        subtitle_commands: SubtitleProcessingBoundary,
        execution_query: ExecutionQueryBoundary,
    ) -> None:
        self._review_query = review_query
        self._subtitle_query = subtitle_query
        self._subtitle_commands = subtitle_commands
        self._execution_query = execution_query
        self._results: InMemoryRepository[
            SubtitleDecisionApplicationResultId,
            SubtitleDecisionApplicationResult,
        ] = InMemoryRepository()

    def apply_approved_subtitle_decision(
        self,
        *,
        approved_decision_id: ApprovedDecisionId,
        application_result_id: SubtitleDecisionApplicationResultId,
        revision_id: SubtitleRevisionId,
        revision_domain_result_id: DomainResultId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        text_replacement: SubtitleTextReplacement | None = None,
        replacement_cue_id: SubtitleCueId | None = None,
    ) -> SubtitleDecisionApplicationResult:
        previous = self.get_subtitle_application_result_for_approved_decision(
            approved_decision_id
        )
        if previous is not None:
            return previous

        self._require_new_identities(
            application_result_id,
            revision_id,
            revision_domain_result_id,
            replacement_cue_id,
        )
        approved = self._review_query.get_approved_decision(approved_decision_id)
        if approved is None:
            raise KeyError("unknown approved Subtitle decision")
        decision = self._review_query.get_decision(approved.source_decision_id)
        if decision is None:
            raise KeyError("unknown source Review Decision")
        item = self._review_query.get_review_item(decision.review_item_id)
        if item is None:
            raise KeyError("unknown source Review Item")
        reference = self._review_query.get_candidate_reference(
            approved.source_candidate_id
        )
        if reference is None:
            raise KeyError("unknown Subtitle Candidate Reference")
        context = self._review_query.get_review_context(item.context_id)
        if context is None:
            raise KeyError("unknown Subtitle Review Context")

        self._validate_review_lineage(approved, decision, item, reference)
        self._validate_review_context(context, reference)
        self._validate_review_applicability(item.identity, reference.identity)

        candidate = self._subtitle_query.get_candidate(
            self._subtitle_candidate_id(reference.identity)
        )
        if candidate is None:
            raise KeyError("unknown Subtitle Candidate")
        self._validate_candidate(reference, candidate)
        cues = tuple(self._require_cue(cue_id) for cue_id in candidate.cue_ids)
        self._validate_candidate_cues(candidate, cues)
        self._validate_context_cues(context, cues)
        working_context = self._validate_execution(
            run_id, unit_execution_id, candidate
        )

        replacement = None
        modification_id = None
        revision_cues = cues
        if decision.kind is DecisionKind.ACCEPT:
            if (
                approved.modification_id is not None
                or text_replacement is not None
                or replacement_cue_id is not None
            ):
                raise SubtitleDecisionApplicationError(
                    "Accept application must not contain a Subtitle modification"
                )
        elif decision.kind is DecisionKind.MODIFY:
            replacement, revision_cues, modification_id = self._apply_text_replacement(
                approved,
                decision,
                reference.identity,
                context,
                candidate.cue_ids,
                cues,
                text_replacement,
                replacement_cue_id,
            )
        else:
            raise SubtitleDecisionApplicationError(
                "Rejected Decision Not Applicable"
            )

        revision = SubtitleRevision(
            identity=revision_id,
            subtitle_id=candidate.subtitle_id,
            domain_result_id=revision_domain_result_id,
            cue_ids=tuple(cue.identity for cue in revision_cues),
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            parent_candidate_id=candidate.identity,
            modification_provenance=(
                "approved Subtitle text replacement"
                if replacement is not None
                else "approved Subtitle Candidate"
            ),
            decision_reference=decision.identity,
        )
        result = SubtitleDecisionApplicationResult(
            identity=application_result_id,
            approved_decision_id=approved.identity,
            source_decision_id=decision.identity,
            review_item_id=item.identity,
            candidate_reference_id=reference.identity,
            subtitle_candidate_id=candidate.identity,
            modification_id=modification_id,
            text_replacement=text_replacement,
            original_cue_id=(
                text_replacement.target_cue_id
                if text_replacement is not None
                else None
            ),
            replacement_cue_id=(
                replacement.identity if replacement is not None else None
            ),
            created_revision_id=revision.identity,
            revision_domain_result_id=revision.domain_result_id,
            actor=approved.actor,
            working_context=working_context,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            applied_at=datetime.now(timezone.utc),
        )

        # Every reference and identity is validated before deterministic writes.
        self._subtitle_commands.create_revision(revision, revision_cues)
        self._results.save(result)
        return result

    def get_subtitle_application_result(
        self, identity: SubtitleDecisionApplicationResultId
    ) -> SubtitleDecisionApplicationResult | None:
        return self._results.get(identity)

    def get_subtitle_application_result_for_approved_decision(
        self, approved_decision_id: ApprovedDecisionId
    ) -> SubtitleDecisionApplicationResult | None:
        return next(
            (
                result
                for result in self._results.all()
                if result.approved_decision_id == approved_decision_id
            ),
            None,
        )

    @staticmethod
    def _subtitle_candidate_id(reference_id):
        from lectureos.subtitle.identities import SubtitleCandidateId

        return SubtitleCandidateId(reference_id.value)

    def _validate_review_lineage(self, approved, decision, item, reference) -> None:
        if approved.source_decision_id != decision.identity:
            raise SubtitleDecisionApplicationError(
                "Approved Decision and Review Decision differ"
            )
        if approved.source_candidate_id != decision.candidate_id:
            raise SubtitleDecisionApplicationError(
                "Approved Decision and Review Decision Candidate differ"
            )
        if item.candidate_id != decision.candidate_id:
            raise SubtitleDecisionApplicationError(
                "Review Item and Review Decision Candidate differ"
            )
        if decision.identity not in item.decision_references:
            raise SubtitleDecisionApplicationError(
                "Review Item does not reference the approved Decision"
            )
        if approved.actor != decision.actor:
            raise SubtitleDecisionApplicationError(
                "Approved Decision and Review Decision Human Actors differ"
            )
        if reference.identity != decision.candidate_id:
            raise SubtitleDecisionApplicationError(
                "Candidate Reference does not match Review Decision"
            )
        if (
            reference.kind != SUBTITLE_CANDIDATE_KIND
            or reference.source_domain != SUBTITLE_SOURCE_DOMAIN
        ):
            raise SubtitleDecisionApplicationError(
                "only Subtitle Candidates can be applied"
            )

    def _validate_review_context(self, context, reference) -> None:
        if context.blocking_reason is not None:
            raise SubtitleDecisionApplicationError(
                "Review Context contains a blocking condition"
            )
        if context.source_media_id != reference.source_media_id:
            raise SubtitleDecisionApplicationError(
                "Review Context Source Media differs from Candidate"
            )
        if context.source_timeline_id != reference.source_timeline_id:
            raise SubtitleDecisionApplicationError(
                "Review Context Source Timeline differs from Candidate"
            )
        if reference.domain_result_id not in context.domain_result_references:
            raise SubtitleDecisionApplicationError(
                "Review Context does not reference Candidate Domain Result"
            )

    def _validate_review_applicability(self, review_item_id, candidate_id) -> None:
        if self._review_query.get_stale_records_for_candidate(candidate_id):
            raise SubtitleDecisionApplicationError(
                "stale Subtitle Candidate cannot be applied"
            )
        conflicts = self._review_query.get_conflicts_for_review_item(review_item_id)
        if any(conflict.resolution_status == "unresolved" for conflict in conflicts):
            raise SubtitleDecisionApplicationError(
                "unresolved Review Conflict blocks Subtitle application"
            )
        reconciliations = self._review_query.get_reconciliations_for_candidate(
            candidate_id
        )
        if any(item.human_confirmation_required for item in reconciliations):
            raise SubtitleDecisionApplicationError(
                "Candidate Reconciliation requires Human confirmation"
            )

    def _validate_candidate(self, reference, candidate) -> None:
        if reference.identity.value != candidate.identity.value:
            raise SubtitleDecisionApplicationError(
                "Candidate Reference and Subtitle Candidate identities differ"
            )
        if reference.domain_result_id != candidate.domain_result_id:
            raise SubtitleDecisionApplicationError(
                "Candidate Domain Result provenance differs"
            )
        if (
            reference.source_media_id != candidate.source_media_id
            or reference.source_timeline_id != candidate.source_timeline_id
        ):
            raise SubtitleDecisionApplicationError(
                "Candidate source provenance differs"
            )
        if (
            reference.run_id != candidate.run_id
            or reference.unit_execution_id != candidate.unit_execution_id
        ):
            raise SubtitleDecisionApplicationError(
                "Candidate execution provenance differs"
            )
        domain_result = self._subtitle_query.get_domain_result_reference(
            candidate.domain_result_id
        )
        if domain_result is None:
            raise SubtitleDecisionApplicationError(
                "Candidate Domain Result provenance is missing"
            )
        if (
            domain_result.kind != "subtitle_candidate"
            or domain_result.source_media != candidate.source_media_id
            or domain_result.source_timeline != candidate.source_timeline_id
        ):
            raise SubtitleDecisionApplicationError(
                "Candidate Domain Result provenance differs"
            )

    @staticmethod
    def _validate_candidate_cues(candidate, cues: tuple[SubtitleCue, ...]) -> None:
        for cue in cues:
            if cue.subtitle_id != candidate.subtitle_id:
                raise SubtitleDecisionApplicationError(
                    "Candidate Cue belongs to another Subtitle lineage"
                )
            if cue.source_timeline_id != candidate.source_timeline_id:
                raise SubtitleDecisionApplicationError(
                    "Candidate Cue Source Timeline differs"
                )
            if (
                cue.source_transcript_id != candidate.source_transcript_id
                or cue.source_revision_id != candidate.source_revision_id
            ):
                raise SubtitleDecisionApplicationError(
                    "Candidate Cue Transcript provenance differs"
                )

    @staticmethod
    def _validate_context_cues(context, cues: tuple[SubtitleCue, ...]) -> None:
        evidence = set(context.evidence_references)
        for cue in cues:
            if f"subtitle_cue:{cue.identity.value}" not in evidence:
                raise SubtitleDecisionApplicationError(
                    "Review Context Cue evidence differs from Candidate"
                )

    def _validate_execution(self, run_id, execution_id, candidate):
        run = self._execution_query.get_run(run_id)
        execution = self._execution_query.get_unit_execution(execution_id)
        if run is None or execution is None:
            raise KeyError("unknown Subtitle application execution provenance")
        if execution.run_id != run_id:
            raise SubtitleDecisionApplicationError(
                "Subtitle application Unit Execution belongs to another Run"
            )
        candidate_run = self._execution_query.get_run(candidate.run_id)
        candidate_execution = self._execution_query.get_unit_execution(
            candidate.unit_execution_id
        )
        if (
            candidate_run is None
            or candidate_execution is None
            or candidate_execution.run_id != candidate.run_id
        ):
            raise SubtitleDecisionApplicationError(
                "Subtitle Candidate execution provenance is incomplete"
            )
        return run.working_context

    def _apply_text_replacement(
        self,
        approved,
        decision,
        candidate_reference_id,
        context,
        candidate_cue_ids,
        cues,
        specification,
        replacement_cue_id,
    ):
        if approved.modification_id is None:
            raise SubtitleDecisionApplicationError(
                "Modify approval requires a Decision Modification"
            )
        modification = self._review_query.get_modification(
            approved.modification_id
        )
        if modification is None:
            raise KeyError("unknown Decision Modification")
        if (
            modification.decision_id != decision.identity
            or modification.candidate_id != candidate_reference_id
            or modification.actor != decision.actor
        ):
            raise SubtitleDecisionApplicationError(
                "Decision Modification provenance differs"
            )
        if specification is None or replacement_cue_id is None:
            raise SubtitleDecisionApplicationError(
                "Modify application requires a typed Subtitle text replacement"
            )
        if specification.modification_id != modification.identity:
            raise SubtitleDecisionApplicationError(
                "Subtitle text replacement is not linked to Decision Modification"
            )
        if specification.target_cue_id not in candidate_cue_ids:
            raise SubtitleDecisionApplicationError(
                "Subtitle text replacement targets a Cue outside Candidate"
            )
        if (
            f"subtitle_cue:{specification.target_cue_id.value}"
            not in context.evidence_references
        ):
            raise SubtitleDecisionApplicationError(
                "Subtitle text replacement target is absent from Review Context"
            )
        original = next(
            cue for cue in cues if cue.identity == specification.target_cue_id
        )
        replacement = replace(
            original,
            identity=replacement_cue_id,
            text=specification.replacement_text,
            replaces_cue_id=original.identity,
        )
        revision_cues = tuple(
            replacement if cue.identity == original.identity else cue for cue in cues
        )
        return replacement, revision_cues, modification.identity

    def _require_cue(self, cue_id: SubtitleCueId) -> SubtitleCue:
        cue = self._subtitle_query.get_cue(cue_id)
        if cue is None:
            raise KeyError("unknown Subtitle Cue")
        return cue

    def _require_new_identities(
        self,
        result_id,
        revision_id,
        domain_result_id,
        replacement_cue_id,
    ) -> None:
        if self._results.get(result_id) is not None:
            raise ValueError("Subtitle application result identity already exists")
        if self._subtitle_query.get_revision(revision_id) is not None:
            raise ValueError("Subtitle Revision identity already exists")
        if self._subtitle_query.get_domain_result_reference(domain_result_id) is not None:
            raise ValueError("Subtitle Revision Domain Result identity already exists")
        if (
            replacement_cue_id is not None
            and self._subtitle_query.get_cue(replacement_cue_id) is not None
        ):
            raise ValueError("replacement Subtitle Cue identity already exists")
