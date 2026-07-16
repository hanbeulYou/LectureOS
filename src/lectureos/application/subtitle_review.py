"""Cross-domain integration from Subtitle Candidate to Human Review."""

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.review.boundaries import ReviewCommandBoundary, ReviewQueryBoundary
from lectureos.review.identities import (
    CandidateReferenceId,
    ReviewContextId,
    ReviewItemId,
)
from lectureos.review.models import (
    CandidateReconciliation,
    CandidateReference,
    ReviewConflict,
    ReviewContext,
    ReviewHistoryEntry,
    ReviewItem,
    StaleCandidateRecord,
)
from lectureos.subtitle.boundaries import SubtitleQueryBoundary
from lectureos.subtitle.identities import SubtitleCandidateId
from lectureos.subtitle.models import SubtitleApplicability, SubtitleCandidate


SUBTITLE_CANDIDATE_KIND = "subtitle_candidate"
SUBTITLE_SOURCE_DOMAIN = "subtitle"


class SubtitleReviewIntegrationError(ValueError):
    """The requested cross-domain relationship is not internally consistent."""


class SubtitleReviewIntegrationService:
    """Prepares Subtitle evidence for Review without exercising Human Authority."""

    def __init__(
        self,
        subtitle_query: SubtitleQueryBoundary,
        review_command: ReviewCommandBoundary,
        review_query: ReviewQueryBoundary,
        execution_query: ExecutionQueryBoundary,
    ) -> None:
        self._subtitle_query = subtitle_query
        self._review_command = review_command
        self._review_query = review_query
        self._execution_query = execution_query

    def create_subtitle_review_item(
        self,
        *,
        candidate_id: SubtitleCandidateId,
        review_item_id: ReviewItemId,
        review_context_id: ReviewContextId,
        source_evidence_references: tuple[str, ...] = (),
    ) -> ReviewItem:
        candidate = self._require_candidate(candidate_id)
        candidate_reference = self._candidate_reference(candidate)
        context = self._review_context(
            candidate, review_context_id, source_evidence_references
        )
        item = ReviewItem(
            identity=review_item_id,
            candidate_id=candidate_reference.identity,
            context_id=context.identity,
            applicability_at_creation=candidate.applicability.value,
            run_id=candidate.run_id,
            unit_execution_id=candidate.unit_execution_id,
        )

        existing_reference = self._review_query.get_candidate_reference(
            candidate_reference.identity
        )
        if existing_reference is not None and existing_reference != candidate_reference:
            raise SubtitleReviewIntegrationError(
                "existing Candidate Reference does not match Subtitle Candidate"
            )
        if self._review_query.get_review_context(context.identity) is not None:
            raise SubtitleReviewIntegrationError(
                "review context identity already exists"
            )
        if self._review_query.get_review_item(item.identity) is not None:
            raise SubtitleReviewIntegrationError("review item identity already exists")

        if existing_reference is None:
            self._review_command.register_candidate_reference(candidate_reference)
        self._review_command.create_review_context(context)
        self._review_command.create_review_item(item)
        return item

    def mark_subtitle_candidate_stale(
        self, record: StaleCandidateRecord
    ) -> None:
        self._require_subtitle_reference(record.candidate_id)
        self._review_command.mark_candidate_stale(record)

    def record_subtitle_review_conflict(
        self, conflict: ReviewConflict
    ) -> None:
        for candidate_id in conflict.candidate_ids:
            self._require_subtitle_reference(candidate_id)
        if conflict.review_item_id is not None:
            item = self._review_query.get_review_item(conflict.review_item_id)
            if item is None:
                raise KeyError("unknown Subtitle Review Item")
            self._require_subtitle_reference(item.candidate_id)
        self._review_command.record_conflict(conflict)

    def reconcile_subtitle_candidates(
        self, reconciliation: CandidateReconciliation
    ) -> None:
        self._require_subtitle_reference(reconciliation.previous_candidate_id)
        self._require_subtitle_reference(reconciliation.new_candidate_id)
        self._review_command.record_reconciliation(reconciliation)

    def get_review_items_for_subtitle_candidate(
        self, candidate_id: SubtitleCandidateId
    ) -> tuple[ReviewItem, ...]:
        self._require_candidate(candidate_id)
        return self._review_query.get_review_items_for_candidate(
            self._candidate_reference_id(candidate_id)
        )

    def get_subtitle_candidate_review_history(
        self, candidate_id: SubtitleCandidateId
    ) -> tuple[ReviewHistoryEntry, ...]:
        entries = []
        for item in self.get_review_items_for_subtitle_candidate(candidate_id):
            entries.extend(self._review_query.get_review_history(item.identity))
        return tuple(sorted(entries, key=lambda entry: entry.sequence))

    def _candidate_reference(
        self, candidate: SubtitleCandidate
    ) -> CandidateReference:
        run = self._execution_query.get_run(candidate.run_id)
        execution = self._execution_query.get_unit_execution(
            candidate.unit_execution_id
        )
        if run is None or execution is None or execution.run_id != candidate.run_id:
            raise SubtitleReviewIntegrationError(
                "Subtitle Candidate execution provenance is inconsistent"
            )
        domain_result = self._subtitle_query.get_domain_result_reference(
            candidate.domain_result_id
        )
        if domain_result is None or domain_result.kind != SUBTITLE_CANDIDATE_KIND:
            raise SubtitleReviewIntegrationError(
                "Subtitle Candidate Domain Result reference is inconsistent"
            )
        if domain_result.identity != candidate.domain_result_id:
            raise SubtitleReviewIntegrationError(
                "Subtitle Candidate Domain Result identity is inconsistent"
            )
        if domain_result.source_media != candidate.source_media_id:
            raise SubtitleReviewIntegrationError(
                "Subtitle Candidate Source Media provenance is inconsistent"
            )
        if domain_result.source_timeline != candidate.source_timeline_id:
            raise SubtitleReviewIntegrationError(
                "Subtitle Candidate Source Timeline provenance is inconsistent"
            )
        revision_reference = (
            f"transcript_revision:{candidate.source_revision_id.value}"
            if candidate.source_revision_id is not None
            else f"transcript:{candidate.source_transcript_id.value}"
        )
        return CandidateReference(
            identity=self._candidate_reference_id(candidate.identity),
            kind=SUBTITLE_CANDIDATE_KIND,
            source_domain=SUBTITLE_SOURCE_DOMAIN,
            domain_result_id=candidate.domain_result_id,
            source_media_id=candidate.source_media_id,
            source_timeline_id=candidate.source_timeline_id,
            run_id=candidate.run_id,
            unit_execution_id=candidate.unit_execution_id,
            revision_reference=revision_reference,
            applicability=candidate.applicability.value,
        )

    def _review_context(
        self,
        candidate: SubtitleCandidate,
        context_id: ReviewContextId,
        source_evidence_references: tuple[str, ...],
    ) -> ReviewContext:
        cue_references = []
        validation_references = []
        blocking_reason = None
        for cue_id in candidate.cue_ids:
            cue = self._subtitle_query.get_cue(cue_id)
            if cue is None:
                raise SubtitleReviewIntegrationError(
                    "Subtitle Candidate contains a missing Cue reference"
                )
            if (
                cue.subtitle_id != candidate.subtitle_id
                or cue.source_timeline_id != candidate.source_timeline_id
                or cue.source_transcript_id != candidate.source_transcript_id
                or cue.source_revision_id != candidate.source_revision_id
            ):
                raise SubtitleReviewIntegrationError(
                    "Subtitle Cue provenance does not match Candidate"
                )
            cue_references.append(f"subtitle_cue:{cue.identity.value}")
            cue_references.extend(
                f"transcript_segment:{segment_id.value}"
                for segment_id in cue.source_segment_ids
            )
        if candidate.validation_id is not None:
            validation = self._subtitle_query.get_validation(candidate.validation_id)
            if (
                validation is None
                or validation.target_candidate_id != candidate.identity
            ):
                raise SubtitleReviewIntegrationError(
                    "Subtitle Validation does not match Candidate"
                )
            validation_references.append(
                f"subtitle_validation:{validation.identity.value}"
            )
            validation_references.extend(
                f"subtitle_validation_finding:{finding_id.value}"
                for finding_id in validation.finding_ids
            )
            if not validation.structural_valid:
                blocking_reason = "subtitle candidate has blocking validation findings"
        transcript_reference = (
            f"transcript_revision:{candidate.source_revision_id.value}"
            if candidate.source_revision_id is not None
            else f"transcript:{candidate.source_transcript_id.value}"
        )
        return ReviewContext(
            identity=context_id,
            source_media_id=candidate.source_media_id,
            source_timeline_id=candidate.source_timeline_id,
            domain_result_references=(candidate.domain_result_id,),
            evidence_references=(
                transcript_reference,
                *cue_references,
                *source_evidence_references,
            ),
            validation_references=tuple(validation_references),
            blocking_reason=blocking_reason,
        )

    def _require_candidate(
        self, candidate_id: SubtitleCandidateId
    ) -> SubtitleCandidate:
        candidate = self._subtitle_query.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError("unknown Subtitle Candidate")
        if candidate.applicability is not SubtitleApplicability.UNDETERMINED:
            raise SubtitleReviewIntegrationError(
                "unsupported Subtitle Candidate applicability"
            )
        return candidate

    def _require_subtitle_reference(
        self, candidate_id: CandidateReferenceId
    ) -> CandidateReference:
        reference = self._review_query.get_candidate_reference(candidate_id)
        if reference is None:
            raise KeyError("unknown Candidate Reference")
        if (
            reference.kind != SUBTITLE_CANDIDATE_KIND
            or reference.source_domain != SUBTITLE_SOURCE_DOMAIN
        ):
            raise SubtitleReviewIntegrationError(
                "Candidate Reference is not a Subtitle Candidate"
            )
        subtitle_id = SubtitleCandidateId(reference.identity.value)
        candidate = self._require_candidate(subtitle_id)
        if self._candidate_reference(candidate) != reference:
            raise SubtitleReviewIntegrationError(
                "Candidate Reference provenance does not match Subtitle Candidate"
            )
        return reference

    @staticmethod
    def _candidate_reference_id(
        candidate_id: SubtitleCandidateId,
    ) -> CandidateReferenceId:
        return CandidateReferenceId(candidate_id.value)
