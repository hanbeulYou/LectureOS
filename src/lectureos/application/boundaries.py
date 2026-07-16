"""Application boundaries between Review intent and Transcript revision creation."""

from typing import Protocol

from lectureos.execution.identities import DomainResultId, ProcessingRunId, UnitExecutionId
from lectureos.review.identities import ApprovedDecisionId
from lectureos.transcript.identities import TranscriptRevisionId, TranscriptSegmentId

from .identities import TranscriptCorrectionApplicationResultId
from .models import TranscriptCorrectionApplicationResult


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
