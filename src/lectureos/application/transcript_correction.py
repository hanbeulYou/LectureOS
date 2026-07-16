"""Apply Human-approved text corrections without moving domain ownership."""

from lectureos.execution.identities import DomainResultId, ProcessingRunId, UnitExecutionId
from lectureos.execution.repositories import InMemoryRepository
from lectureos.review.boundaries import ReviewQueryBoundary
from lectureos.review.identities import ApprovedDecisionId, CandidateReferenceId
from lectureos.review.models import DecisionKind
from lectureos.transcript.boundaries import (
    TranscriptProcessingBoundary,
    TranscriptQueryBoundary,
)
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import CorrectedTranscriptRevision, TranscriptSegment

from .identities import TranscriptCorrectionApplicationResultId
from .models import TranscriptCorrectionApplicationResult


class TranscriptCorrectionApplicationError(ValueError):
    """A structurally valid request that cannot safely apply the approved intent."""


class TranscriptCorrectionApplicationService:
    SUPPORTED_CANDIDATE_KIND = "transcript_correction_candidate"

    def __init__(
        self,
        review_query: ReviewQueryBoundary,
        transcript_query: TranscriptQueryBoundary,
        transcript_commands: TranscriptProcessingBoundary,
    ) -> None:
        self._review_query = review_query
        self._transcript_query = transcript_query
        self._transcript_commands = transcript_commands
        self._results: InMemoryRepository[
            TranscriptCorrectionApplicationResultId,
            TranscriptCorrectionApplicationResult,
        ] = InMemoryRepository()

    def apply_approved_transcript_correction(
        self,
        *,
        approved_decision_id: ApprovedDecisionId,
        application_result_id: TranscriptCorrectionApplicationResultId,
        revision_id: TranscriptRevisionId,
        revision_domain_result_id: DomainResultId,
        replacement_segment_id: TranscriptSegmentId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
    ) -> TranscriptCorrectionApplicationResult:
        previous = self.get_application_result_for_approved_decision(
            approved_decision_id
        )
        if previous is not None:
            return previous

        self._require_new_result(application_result_id)
        self._require_new_transcript_identities(
            revision_id, revision_domain_result_id, replacement_segment_id
        )
        approved = self._review_query.get_approved_decision(approved_decision_id)
        if approved is None:
            raise KeyError("unknown approved decision")
        decision = self._review_query.get_decision(approved.source_decision_id)
        if decision is None:
            raise KeyError("unknown source review decision")
        item = self._review_query.get_review_item(decision.review_item_id)
        if item is None:
            raise KeyError("unknown source review item")
        candidate_reference = self._review_query.get_candidate_reference(
            approved.source_candidate_id
        )
        if candidate_reference is None:
            raise KeyError("unknown source candidate reference")
        context = self._review_query.get_review_context(item.context_id)
        if context is None:
            raise KeyError("unknown source review context")

        self._validate_review_lineage(approved, decision, item, candidate_reference)
        self._validate_review_context(context, candidate_reference)
        self._validate_review_applicability(item.identity, candidate_reference.identity)

        candidate_id = CorrectionCandidateId(candidate_reference.identity.value)
        candidate = self._transcript_query.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError("unknown transcript correction candidate")
        self._validate_candidate_provenance(candidate_reference, candidate)

        raw = self._transcript_query.get_raw_transcript(candidate.transcript_id)
        if raw is None:
            raise KeyError("unknown target raw transcript")
        if candidate_reference.source_media_id != raw.source_media_id:
            raise TranscriptCorrectionApplicationError(
                "candidate source media provenance does not match transcript"
            )
        if candidate_reference.source_timeline_id != raw.source_timeline_id:
            raise TranscriptCorrectionApplicationError(
                "candidate source timeline provenance does not match transcript"
            )
        original_segment = self._transcript_query.get_segment(candidate.segment_id)
        if original_segment is None:
            raise KeyError("unknown target transcript segment")
        if original_segment.transcript_id != raw.identity:
            raise TranscriptCorrectionApplicationError(
                "candidate segment belongs to another transcript lineage"
            )
        if original_segment.source_timeline_id != raw.source_timeline_id:
            raise TranscriptCorrectionApplicationError(
                "candidate segment source timeline does not match transcript"
            )

        parent_revision, parent_segment_ids = self._resolve_parent(candidate, raw.segment_ids)
        if candidate.segment_id not in parent_segment_ids:
            raise TranscriptCorrectionApplicationError(
                "candidate segment is not part of the target parent"
            )
        replacement_text, modification_id = self._resolve_approved_text(
            approved, decision, candidate_reference.identity, candidate.proposed_text
        )

        replacement = TranscriptSegment(
            identity=replacement_segment_id,
            transcript_id=raw.identity,
            source_timeline_id=original_segment.source_timeline_id,
            text=replacement_text,
            source_order=original_segment.source_order,
            start=original_segment.start,
            end=original_segment.end,
            speaker_label=original_segment.speaker_label,
            confidence=original_segment.confidence,
            uncertainty=original_segment.uncertainty,
            replaces_segment_id=original_segment.identity,
        )
        segment_ids = tuple(
            replacement.identity if identity == candidate.segment_id else identity
            for identity in parent_segment_ids
        )
        segments = tuple(
            replacement
            if identity == replacement.identity
            else self._require_segment(identity)
            for identity in segment_ids
        )
        revision = CorrectedTranscriptRevision(
            identity=revision_id,
            transcript_id=raw.identity,
            domain_result_id=revision_domain_result_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            segment_ids=segment_ids,
            parent_raw_transcript_id=raw.identity if parent_revision is None else None,
            parent_revision_id=parent_revision,
            correction_candidate_ids=(candidate.identity,),
            decision_reference=decision.identity,
        )
        result = TranscriptCorrectionApplicationResult(
            identity=application_result_id,
            approved_decision_id=approved.identity,
            source_decision_id=decision.identity,
            candidate_id=candidate_reference.identity,
            modification_id=modification_id,
            source_transcript_id=raw.identity,
            source_revision_id=parent_revision,
            created_revision_id=revision.identity,
            created_segment_ids=(replacement.identity,),
            actor=approved.actor,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
        )

        # All cross-domain references and identities are validated before persistence.
        self._transcript_commands.create_corrected_revision(revision, segments)
        self._results.save(result)
        return result

    def get_application_result(
        self, identity: TranscriptCorrectionApplicationResultId
    ) -> TranscriptCorrectionApplicationResult | None:
        return self._results.get(identity)

    def get_application_result_for_approved_decision(
        self, approved_decision_id: ApprovedDecisionId
    ) -> TranscriptCorrectionApplicationResult | None:
        return next(
            (
                result
                for result in self._results.all()
                if result.approved_decision_id == approved_decision_id
            ),
            None,
        )

    def _validate_review_lineage(self, approved, decision, item, candidate) -> None:
        if decision.kind not in (DecisionKind.ACCEPT, DecisionKind.MODIFY):
            raise TranscriptCorrectionApplicationError(
                "approved decision must originate from Accept or Modify"
            )
        if approved.source_candidate_id != decision.candidate_id:
            raise TranscriptCorrectionApplicationError(
                "approved and review decision candidate references differ"
            )
        if item.candidate_id != decision.candidate_id:
            raise TranscriptCorrectionApplicationError(
                "review item and decision candidate references differ"
            )
        if decision.identity not in item.decision_references:
            raise TranscriptCorrectionApplicationError(
                "review item does not reference the source decision"
            )
        if approved.actor != decision.actor:
            raise TranscriptCorrectionApplicationError(
                "approved and review decision Human Actors differ"
            )
        if candidate.identity != decision.candidate_id:
            raise TranscriptCorrectionApplicationError(
                "candidate reference does not match source decision"
            )
        if candidate.kind != self.SUPPORTED_CANDIDATE_KIND or candidate.source_domain != "transcript":
            raise TranscriptCorrectionApplicationError(
                "only Transcript Correction Candidates can be applied"
            )

    def _validate_review_applicability(self, review_item_id, candidate_id) -> None:
        if self._review_query.get_stale_records_for_candidate(candidate_id):
            raise TranscriptCorrectionApplicationError("stale candidate cannot be applied")
        conflicts = self._review_query.get_conflicts_for_review_item(review_item_id)
        if any(conflict.resolution_status == "unresolved" for conflict in conflicts):
            raise TranscriptCorrectionApplicationError(
                "unresolved review conflict blocks application"
            )
        reconciliations = self._review_query.get_reconciliations_for_candidate(candidate_id)
        if any(item.human_confirmation_required for item in reconciliations):
            raise TranscriptCorrectionApplicationError(
                "candidate reconciliation requires Human confirmation"
            )

    @staticmethod
    def _validate_review_context(context, candidate) -> None:
        if context.blocking_reason is not None:
            raise TranscriptCorrectionApplicationError(
                "review context contains a blocking condition"
            )
        if context.source_media_id != candidate.source_media_id:
            raise TranscriptCorrectionApplicationError(
                "review context source media does not match candidate"
            )
        if context.source_timeline_id != candidate.source_timeline_id:
            raise TranscriptCorrectionApplicationError(
                "review context source timeline does not match candidate"
            )

    @staticmethod
    def _validate_candidate_provenance(reference, candidate) -> None:
        if reference.domain_result_id != candidate.domain_result_id:
            raise TranscriptCorrectionApplicationError(
                "candidate Domain Result provenance does not match review reference"
            )
        if reference.run_id != candidate.run_id or reference.unit_execution_id != candidate.unit_execution_id:
            raise TranscriptCorrectionApplicationError(
                "candidate execution provenance does not match review reference"
            )

    def _resolve_parent(self, candidate, raw_segment_ids):
        if candidate.target_revision_id is None:
            return None, raw_segment_ids
        revision = self._transcript_query.get_corrected_revision(candidate.target_revision_id)
        if revision is None:
            raise KeyError("unknown target corrected transcript revision")
        if revision.transcript_id != candidate.transcript_id:
            raise TranscriptCorrectionApplicationError(
                "target revision belongs to another transcript lineage"
            )
        return revision.identity, revision.segment_ids

    def _resolve_approved_text(self, approved, decision, candidate_id, proposed_text):
        if decision.kind is DecisionKind.ACCEPT:
            if approved.modification_id is not None:
                raise TranscriptCorrectionApplicationError(
                    "Accept approval must not reference a modification"
                )
            return proposed_text, None
        if approved.modification_id is None:
            raise TranscriptCorrectionApplicationError(
                "Modify approval requires a Decision Modification"
            )
        modification = self._review_query.get_modification(approved.modification_id)
        if modification is None:
            raise KeyError("unknown decision modification")
        if modification.decision_id != decision.identity or modification.candidate_id != candidate_id:
            raise TranscriptCorrectionApplicationError(
                "Decision Modification provenance does not match approval"
            )
        if modification.actor != decision.actor:
            raise TranscriptCorrectionApplicationError(
                "Decision Modification Human Actor does not match decision"
            )
        return modification.modified_intent, modification.identity

    def _require_segment(self, identity: TranscriptSegmentId) -> TranscriptSegment:
        segment = self._transcript_query.get_segment(identity)
        if segment is None:
            raise KeyError("unknown transcript segment in target parent")
        return segment

    def _require_new_result(
        self, identity: TranscriptCorrectionApplicationResultId
    ) -> None:
        if self._results.get(identity) is not None:
            raise ValueError("application result identity already exists")

    def _require_new_transcript_identities(
        self,
        revision_id: TranscriptRevisionId,
        domain_result_id: DomainResultId,
        segment_id: TranscriptSegmentId,
    ) -> None:
        if self._transcript_query.get_corrected_revision(revision_id) is not None:
            raise ValueError("corrected transcript revision identity already exists")
        if self._transcript_query.get_domain_result_reference(domain_result_id) is not None:
            raise ValueError("revision Domain Result identity already exists")
        if self._transcript_query.get_segment(segment_id) is not None:
            raise ValueError("replacement transcript segment identity already exists")
