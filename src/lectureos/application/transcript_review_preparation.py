"""Provider-independent Application contract for Transcript Review Preparation.

Review Preparation maps a canonical proposed ``CorrectedTranscriptRevision`` and its
``CorrectionCandidate`` set into canonical review targets for later Human Review. It never
records a Review Decision, never changes Transcript state, and never lets a provider own a
Review identity or the Review lifecycle. Application owns Review identity, provenance,
ordering, grouping, metadata, structural integrity and persistence orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference, ProcessingState
from lectureos.review.identities import (
    CandidateReferenceId,
    ReviewContextId,
    ReviewItemId,
)
from lectureos.review.models import CandidateReference, ReviewContext, ReviewItem
from lectureos.transcript.boundaries import TranscriptQueryBoundary
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    TranscriptId,
    TranscriptRevisionId,
)
from lectureos.transcript.models import CorrectedTranscriptRevision, CorrectionCandidate

from .identities import TranscriptReviewPreparationId

REVIEW_PREPARATION_RESULT_KIND = "transcript_review_preparation"
CORRECTION_CANDIDATE_KIND = "transcript_correction_candidate"
CORRECTION_CANDIDATE_SOURCE_DOMAIN = "transcript"
CORRECTED_REVISION_RESULT_KIND = "corrected_transcript_revision"


@dataclass(frozen=True, slots=True)
class ReviewItemGroup:
    """A deterministic grouping of review targets sharing one grouping key."""

    group_key: str
    review_item_ids: tuple[ReviewItemId, ...]

    def __post_init__(self) -> None:
        if not self.group_key.strip():
            raise ValueError("review item group key must not be empty")
        if not self.review_item_ids:
            raise ValueError("review item group must contain at least one item")
        if len(set(self.review_item_ids)) != len(self.review_item_ids):
            raise ValueError("review item group must not repeat an item")


@dataclass(frozen=True, slots=True)
class TranscriptReviewPreparation:
    """Application-owned aggregate presenting a proposed Revision for Human Review."""

    identity: TranscriptReviewPreparationId
    domain_result_id: DomainResultId
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    context_id: ReviewContextId
    candidate_reference_ids: tuple[CandidateReferenceId, ...]
    ordered_item_ids: tuple[ReviewItemId, ...]
    groups: tuple[ReviewItemGroup, ...]
    item_count: int
    structural_valid: bool
    provenance_complete: bool
    ordering_valid: bool

    def __post_init__(self) -> None:
        if self.item_count < 1:
            raise ValueError("review preparation must contain at least one review item")
        if len(self.ordered_item_ids) != self.item_count:
            raise ValueError("ordered review item count must match item count")
        if len(self.candidate_reference_ids) != self.item_count:
            raise ValueError("candidate reference count must match item count")
        if len(set(self.ordered_item_ids)) != len(self.ordered_item_ids):
            raise ValueError("ordered review items must be unique")
        if len(set(self.candidate_reference_ids)) != len(self.candidate_reference_ids):
            raise ValueError("candidate references must be unique")
        if not self.groups:
            raise ValueError("review preparation must contain at least one group")
        grouped = tuple(item for group in self.groups for item in group.review_item_ids)
        if len(grouped) != self.item_count:
            raise ValueError("each review item must belong to exactly one group")
        if set(grouped) != set(self.ordered_item_ids):
            raise ValueError("grouped review items must match ordered review items")


@dataclass(frozen=True, slots=True)
class ReviewPreparationTargetIdentityPlan:
    """Application-owned Review identities for one prepared candidate."""

    candidate_reference_id: CandidateReferenceId
    review_item_id: ReviewItemId


@dataclass(frozen=True, slots=True)
class ReviewPreparationIdentityPlan:
    """Deterministic Application-owned Review identities for one preparation."""

    preparation_id: TranscriptReviewPreparationId
    preparation_result_id: DomainResultId
    context_id: ReviewContextId
    targets: tuple[ReviewPreparationTargetIdentityPlan, ...]

    def __post_init__(self) -> None:
        if not self.targets:
            raise ValueError("review preparation identity plan requires at least one target")
        candidate_ids = tuple(target.candidate_reference_id for target in self.targets)
        item_ids = tuple(target.review_item_id for target in self.targets)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate reference identity plan must be unique")
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("review item identity plan must be unique")


@dataclass(frozen=True, slots=True)
class PreparedTranscriptReview:
    """Immutable canonical review-preparation records; not yet persisted."""

    preparation: TranscriptReviewPreparation
    preparation_result: DomainResultReference
    context: ReviewContext
    candidate_references: tuple[CandidateReference, ...]
    review_items: tuple[ReviewItem, ...]


class TranscriptReviewPreparationError(ValueError):
    """A structurally valid request that cannot become canonical review preparation."""


class TranscriptReviewPreparationService:
    """Maps a proposed Revision to canonical review targets without deciding anything."""

    def __init__(
        self,
        transcript_query: TranscriptQueryBoundary,
        execution_query: ExecutionQueryBoundary,
    ) -> None:
        self._transcripts = transcript_query
        self._executions = execution_query

    def prepare_review(
        self,
        *,
        revision_id: TranscriptRevisionId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: ReviewPreparationIdentityPlan,
    ) -> PreparedTranscriptReview:
        revision = self._transcripts.get_corrected_revision(revision_id)
        if revision is None:
            raise KeyError("unknown corrected transcript revision")
        self._require_running_execution(run_id, unit_execution_id)
        raw = self._transcripts.get_raw_transcript(revision.transcript_id)
        if raw is None:
            raise KeyError("unknown source raw transcript")

        candidate_ids = revision.correction_candidate_ids
        if not candidate_ids:
            raise TranscriptReviewPreparationError(
                "proposed revision has no correction candidates to review"
            )
        if len(identities.targets) != len(candidate_ids):
            raise TranscriptReviewPreparationError(
                "identity plan target count must match correction candidate count"
            )
        self._require_new_result_identity(identities.preparation_result_id)

        candidate_references: list[CandidateReference] = []
        review_items: list[ReviewItem] = []
        ordered_item_ids: list[ReviewItemId] = []
        grouped: dict[str, list[ReviewItemId]] = {}
        for candidate_id, target in zip(candidate_ids, identities.targets):
            candidate = self._require_candidate(candidate_id)
            self._validate_candidate_lineage(candidate, revision)
            self._validate_candidate_provenance(candidate, raw)
            if target.candidate_reference_id.value != candidate.identity.value:
                raise TranscriptReviewPreparationError(
                    "candidate reference identity must equal correction candidate identity"
                )
            reference = CandidateReference(
                identity=target.candidate_reference_id,
                kind=CORRECTION_CANDIDATE_KIND,
                source_domain=CORRECTION_CANDIDATE_SOURCE_DOMAIN,
                domain_result_id=candidate.domain_result_id,
                source_media_id=raw.source_media_id,
                source_timeline_id=raw.source_timeline_id,
                run_id=candidate.run_id,
                unit_execution_id=candidate.unit_execution_id,
                revision_reference=f"transcript_revision:{revision.identity.value}",
                applicability="undetermined",
            )
            item = ReviewItem(
                identity=target.review_item_id,
                candidate_id=reference.identity,
                context_id=identities.context_id,
                applicability_at_creation="undetermined",
                run_id=candidate.run_id,
                unit_execution_id=candidate.unit_execution_id,
            )
            candidate_references.append(reference)
            review_items.append(item)
            ordered_item_ids.append(item.identity)
            grouped.setdefault(candidate.segment_id.value, []).append(item.identity)

        context = ReviewContext(
            identity=identities.context_id,
            source_media_id=raw.source_media_id,
            source_timeline_id=raw.source_timeline_id,
            domain_result_references=(
                revision.domain_result_id,
                *(reference.domain_result_id for reference in candidate_references),
            ),
            evidence_references=(
                f"transcript_revision:{revision.identity.value}",
                *(
                    f"{CORRECTION_CANDIDATE_KIND}:{candidate_id.value}"
                    for candidate_id in candidate_ids
                ),
            ),
        )
        groups = tuple(
            ReviewItemGroup(group_key=key, review_item_ids=tuple(members))
            for key, members in grouped.items()
        )
        item_count = len(review_items)
        ordering_valid = len(set(ordered_item_ids)) == item_count
        provenance_complete = True
        structural_valid = ordering_valid and provenance_complete

        preparation = TranscriptReviewPreparation(
            identity=identities.preparation_id,
            domain_result_id=identities.preparation_result_id,
            source_transcript_id=revision.transcript_id,
            source_revision_id=revision.identity,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            source_media_id=raw.source_media_id,
            source_timeline_id=raw.source_timeline_id,
            context_id=context.identity,
            candidate_reference_ids=tuple(
                reference.identity for reference in candidate_references
            ),
            ordered_item_ids=tuple(ordered_item_ids),
            groups=groups,
            item_count=item_count,
            structural_valid=structural_valid,
            provenance_complete=provenance_complete,
            ordering_valid=ordering_valid,
        )
        preparation_result = DomainResultReference(
            identity=identities.preparation_result_id,
            kind=REVIEW_PREPARATION_RESULT_KIND,
            source_media=raw.source_media_id,
            source_timeline=raw.source_timeline_id,
            upstream_results=(revision.domain_result_id,),
        )
        return PreparedTranscriptReview(
            preparation=preparation,
            preparation_result=preparation_result,
            context=context,
            candidate_references=tuple(candidate_references),
            review_items=tuple(review_items),
        )

    def _require_candidate(self, identity: CorrectionCandidateId) -> CorrectionCandidate:
        candidate = self._transcripts.get_candidate(identity)
        if candidate is None:
            raise KeyError("unknown correction candidate")
        return candidate

    @staticmethod
    def _validate_candidate_lineage(
        candidate: CorrectionCandidate, revision: CorrectedTranscriptRevision
    ) -> None:
        if candidate.transcript_id != revision.transcript_id:
            raise TranscriptReviewPreparationError(
                "correction candidate belongs to another transcript lineage"
            )
        if candidate.target_revision_id != revision.parent_revision_id:
            raise TranscriptReviewPreparationError(
                "correction candidate parent lineage does not match revision"
            )

    def _validate_candidate_provenance(
        self, candidate: CorrectionCandidate, raw
    ) -> None:
        run = self._executions.get_run(candidate.run_id)
        execution = self._executions.get_unit_execution(candidate.unit_execution_id)
        if run is None or execution is None or execution.run_id != candidate.run_id:
            raise TranscriptReviewPreparationError(
                "correction candidate execution provenance is inconsistent"
            )
        domain_result = self._transcripts.get_domain_result_reference(
            candidate.domain_result_id
        )
        if domain_result is None or domain_result.kind != CORRECTION_CANDIDATE_KIND:
            raise TranscriptReviewPreparationError(
                "correction candidate Domain Result reference is inconsistent"
            )
        if domain_result.identity != candidate.domain_result_id:
            raise TranscriptReviewPreparationError(
                "correction candidate Domain Result identity is inconsistent"
            )
        if domain_result.source_media != raw.source_media_id:
            raise TranscriptReviewPreparationError(
                "correction candidate Source Media provenance is inconsistent"
            )
        if domain_result.source_timeline != raw.source_timeline_id:
            raise TranscriptReviewPreparationError(
                "correction candidate Source Timeline provenance is inconsistent"
            )
        segment = self._transcripts.get_segment(candidate.segment_id)
        if segment is None or segment.transcript_id != raw.identity:
            raise TranscriptReviewPreparationError(
                "correction candidate target Segment does not belong to the transcript"
            )

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise TranscriptReviewPreparationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise TranscriptReviewPreparationError(
                "review preparation requires a running unit execution"
            )

    def _require_new_result_identity(self, identity: DomainResultId) -> None:
        if self._transcripts.get_domain_result_reference(identity) is not None:
            raise TranscriptReviewPreparationError(
                "review preparation Domain Result identity already exists"
            )


__all__ = [
    "CORRECTED_REVISION_RESULT_KIND",
    "CORRECTION_CANDIDATE_KIND",
    "CORRECTION_CANDIDATE_SOURCE_DOMAIN",
    "REVIEW_PREPARATION_RESULT_KIND",
    "PreparedTranscriptReview",
    "ReviewItemGroup",
    "ReviewPreparationIdentityPlan",
    "ReviewPreparationTargetIdentityPlan",
    "TranscriptReviewPreparation",
    "TranscriptReviewPreparationError",
    "TranscriptReviewPreparationService",
]
