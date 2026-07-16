"""Application boundaries between Review intent and Transcript revision creation."""

from typing import Protocol

from lectureos.execution.identities import DomainResultId, ProcessingRunId, UnitExecutionId
from lectureos.review.identities import ApprovedDecisionId
from lectureos.review.models import (
    CandidateReconciliation,
    ReviewConflict,
    ReviewHistoryEntry,
    ReviewItem,
    StaleCandidateRecord,
)
from lectureos.subtitle.identities import (
    SubtitleCandidateId,
    SubtitleCueId,
    SubtitleRevisionId,
)
from lectureos.transcript.identities import TranscriptRevisionId, TranscriptSegmentId

from .identities import (
    SubtitleDecisionApplicationResultId,
    TranscriptCorrectionApplicationResultId,
)
from .models import (
    SubtitleDecisionApplicationResult,
    SubtitleTextReplacement,
    TranscriptCorrectionApplicationResult,
)


class TranscriptCorrectionApplicationCommandBoundary(Protocol):
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
    ) -> TranscriptCorrectionApplicationResult: ...


class TranscriptCorrectionApplicationQueryBoundary(Protocol):
    def get_application_result(
        self, identity: TranscriptCorrectionApplicationResultId
    ) -> TranscriptCorrectionApplicationResult | None: ...

    def get_application_result_for_approved_decision(
        self, approved_decision_id: ApprovedDecisionId
    ) -> TranscriptCorrectionApplicationResult | None: ...


class SubtitleReviewIntegrationCommandBoundary(Protocol):
    def create_subtitle_review_item(self, **kwargs) -> ReviewItem: ...

    def mark_subtitle_candidate_stale(
        self, record: StaleCandidateRecord
    ) -> None: ...

    def record_subtitle_review_conflict(
        self, conflict: ReviewConflict
    ) -> None: ...

    def reconcile_subtitle_candidates(
        self, reconciliation: CandidateReconciliation
    ) -> None: ...


class SubtitleReviewIntegrationQueryBoundary(Protocol):
    def get_review_items_for_subtitle_candidate(
        self, candidate_id: SubtitleCandidateId
    ) -> tuple[ReviewItem, ...]: ...

    def get_subtitle_candidate_review_history(
        self, candidate_id: SubtitleCandidateId
    ) -> tuple[ReviewHistoryEntry, ...]: ...


class SubtitleDecisionApplicationCommandBoundary(Protocol):
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
    ) -> SubtitleDecisionApplicationResult: ...


class SubtitleDecisionApplicationQueryBoundary(Protocol):
    def get_subtitle_application_result(
        self, identity: SubtitleDecisionApplicationResultId
    ) -> SubtitleDecisionApplicationResult | None: ...

    def get_subtitle_application_result_for_approved_decision(
        self, approved_decision_id: ApprovedDecisionId
    ) -> SubtitleDecisionApplicationResult | None: ...
