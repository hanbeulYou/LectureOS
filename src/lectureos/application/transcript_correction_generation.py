"""Provider-independent Application contract for Transcript correction proposals."""

from dataclasses import dataclass
from typing import Protocol

from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    PluginReference,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)


@dataclass(frozen=True, slots=True)
class CorrectionSegmentContext:
    """One canonical source Segment exposed to a correction capability."""

    identity: TranscriptSegmentId
    text: str
    source_order: int
    source_timeline_id: SourceTimelineId | None
    start: float | None = None
    end: float | None = None
    speaker_label: str | None = None
    confidence: float | None = None
    uncertainty: float | None = None


@dataclass(frozen=True, slots=True)
class CorrectionGenerationRequest:
    """Immutable Application context; never a provider-specific payload."""

    transcript_id: TranscriptId
    parent_revision_id: TranscriptRevisionId | None
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    capability: CapabilityReference
    segments: tuple[CorrectionSegmentContext, ...]


@dataclass(frozen=True, slots=True)
class CorrectionProposal:
    """Provider-neutral suggestion that has not become canonical Domain state."""

    target_segment_id: TranscriptSegmentId
    proposed_text: str
    rationale: str
    evidence: tuple[str, ...] = ()
    confidence: float | None = None
    uncertainty: float | None = None
    capability: CapabilityReference | None = None
    plugin_reference: PluginReference | None = None
    provider_reference: str | None = None


class CorrectionGenerationFailure(RuntimeError):
    """The correction capability could not produce a usable response."""


class CorrectionGenerationPort(Protocol):
    def generate_corrections(
        self, request: CorrectionGenerationRequest
    ) -> tuple[CorrectionProposal, ...]: ...


@dataclass(frozen=True, slots=True)
class CorrectionCandidateIdentityPlan:
    candidate_id: CorrectionCandidateId
    candidate_result_id: DomainResultId
    replacement_segment_id: TranscriptSegmentId


@dataclass(frozen=True, slots=True)
class CorrectionGenerationIdentityPlan:
    candidates: tuple[CorrectionCandidateIdentityPlan, ...]
    revision_id: TranscriptRevisionId
    revision_result_id: DomainResultId
    validation_id: TranscriptValidationId


__all__ = [
    "CorrectionCandidateIdentityPlan",
    "CorrectionGenerationFailure",
    "CorrectionGenerationIdentityPlan",
    "CorrectionGenerationPort",
    "CorrectionGenerationRequest",
    "CorrectionProposal",
    "CorrectionSegmentContext",
]
