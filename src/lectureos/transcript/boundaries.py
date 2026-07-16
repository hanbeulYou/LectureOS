"""Transport-independent Transcript boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference

from .identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
    TranscriptValidationFindingId,
)
from .models import (
    CorrectionCandidate,
    CorrectedTranscriptRevision,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
    TranscriptValidation,
    TranscriptValidationFinding,
)

if TYPE_CHECKING:
    from .applicability import (
        CurrentTranscriptSelection,
        RevisionApplicabilityRecord,
        RevisionTarget,
    )


class TranscriptProcessingBoundary(Protocol):
    def register_provider_result(self, result: ProviderTranscriptResult) -> None: ...

    def create_raw_transcript(
        self, transcript: RawTranscript, segments: tuple[TranscriptSegment, ...]
    ) -> None: ...

    def create_correction_candidate(self, candidate: CorrectionCandidate) -> None: ...

    def create_corrected_revision(
        self,
        revision: CorrectedTranscriptRevision,
        segments: tuple[TranscriptSegment, ...],
    ) -> None: ...

    def record_validation(self, validation: TranscriptValidation) -> None: ...


class TranscriptQueryBoundary(Protocol):
    def get_provider_result(
        self, identity: ProviderTranscriptResultId
    ) -> ProviderTranscriptResult | None: ...

    def get_raw_transcript(self, identity: TranscriptId) -> RawTranscript | None: ...

    def get_corrected_revision(
        self, identity: TranscriptRevisionId
    ) -> CorrectedTranscriptRevision | None: ...

    def get_segment(self, identity: TranscriptSegmentId) -> TranscriptSegment | None: ...

    def get_candidate(self, identity: CorrectionCandidateId) -> CorrectionCandidate | None: ...

    def get_validation(
        self, identity: TranscriptValidationId
    ) -> TranscriptValidation | None: ...

    def get_domain_result_reference(
        self, identity: DomainResultId
    ) -> DomainResultReference | None: ...

    def get_lineage(
        self, transcript_id: TranscriptId
    ) -> tuple[RawTranscript, tuple[CorrectedTranscriptRevision, ...]] | None: ...


class TranscriptValidationStoreBoundary(TranscriptQueryBoundary, Protocol):
    """Shared query and persistence boundary for computed Validation Results."""

    def record_validation(self, validation: TranscriptValidation) -> None: ...


class TranscriptStructuralValidationBoundary(Protocol):
    def validate_raw_transcript(
        self,
        *,
        validation_id: TranscriptValidationId,
        transcript_id: TranscriptId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
    ) -> TranscriptValidation: ...

    def validate_corrected_revision(
        self,
        *,
        validation_id: TranscriptValidationId,
        revision_id: TranscriptRevisionId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
    ) -> TranscriptValidation: ...


class TranscriptValidationQueryBoundary(Protocol):
    def get_validation(
        self, identity: TranscriptValidationId
    ) -> TranscriptValidation | None: ...

    def get_validation_finding(
        self, identity: TranscriptValidationFindingId
    ) -> TranscriptValidationFinding | None: ...


class TranscriptApplicabilityCommandBoundary(Protocol):
    def register_undetermined_revision(self, **kwargs) -> RevisionApplicabilityRecord: ...

    def select_current_revision(self, **kwargs) -> CurrentTranscriptSelection: ...

    def mark_revision_stale(self, **kwargs) -> RevisionApplicabilityRecord: ...

    def supersede_revision(self, **kwargs) -> RevisionApplicabilityRecord: ...

    def mark_historical(self, **kwargs) -> RevisionApplicabilityRecord: ...


class TranscriptApplicabilityQueryBoundary(Protocol):
    def get_current_revision(
        self,
        working_context,
        transcript_id: TranscriptId,
    ) -> RevisionTarget | None: ...

    def get_applicability_history(
        self,
        working_context,
        transcript_id: TranscriptId,
    ) -> tuple[RevisionApplicabilityRecord | CurrentTranscriptSelection, ...]: ...
