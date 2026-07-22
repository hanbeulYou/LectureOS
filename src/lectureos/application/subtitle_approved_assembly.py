"""Provider-independent Application contract for Approved Subtitle Assembly (044 §Export, PATCH-0006).

The first stage of the Export Pipeline. From exactly one canonical subtitle document (its
``SubtitleTimeRevision`` and ``SubtitleReadingRevision``), it deterministically reconstructs the complete,
ordered, approved subtitle representation — the ``SubtitleApprovedDocument`` — by reconciling the base
timed/reading representation with the applicable finalized decisions (``SubtitleFinalSubtitle``), and it
establishes export eligibility.

Assembly is a pure deterministic reconstruction. Every upstream record is read read-only and never
mutated: the time revision, reading revision, final subtitles and decision revisions are unchanged. The
only newly created canonical artifact is the ``SubtitleApprovedDocument`` (with its ordered approved units
and their approved lines) and its ``DomainResultReference``. This stage generates no artifact, writes no
file, and serializes no format (no SRT/WebVTT/bytes); it performs no Review, no Validation, no Human
Decision, no AI, and uses no provider. It becomes the canonical Export Input.

Reconciliation (approved PATCH-0006 §4), applying each unit's current finalization:
- Modify (FINAL)   -> unit included, text = approved applied_text
- Accept (FINAL)   -> unit included, text = original reading text
- Reject (NOT_FINAL)-> unit omitted; the document remains eligible
- Untouched        -> unit included, text = original reading text
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .identities import (
    SubtitleApprovedDocumentId,
    SubtitleApprovedUnitId,
    SubtitleCandidateId,
    SubtitleFinalSubtitleId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
)

SUBTITLE_APPROVED_DOCUMENT_RESULT_KIND = "subtitle_approved_document"


class SubtitleExportEligibility(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class SubtitleApprovedUnitOrigin(str, Enum):
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    UNTOUCHED = "untouched"


@dataclass(frozen=True, slots=True)
class SubtitleApprovedUnit:
    """One immutable approved subtitle unit in canonical display order."""

    identity: SubtitleApprovedUnitId
    document_id: SubtitleApprovedDocumentId
    source_timed_unit_id: SubtitleTimedUnitId
    source_reading_unit_id: SubtitleReadingUnitId
    origin: SubtitleApprovedUnitOrigin
    display_order: int
    start: float
    end: float
    lines: tuple[str, ...]
    source_final_subtitle_id: SubtitleFinalSubtitleId | None = None

    def __post_init__(self) -> None:
        if self.display_order < 0:
            raise ValueError("approved unit display order must not be negative")
        if self.start < 0 or self.end < self.start:
            raise ValueError("approved unit requires resolved timing with end >= start >= 0")
        if not self.lines:
            raise ValueError("approved unit requires at least one line")
        if any(not line.strip() for line in self.lines):
            raise ValueError("approved unit lines must not be blank")
        if self.origin is SubtitleApprovedUnitOrigin.UNTOUCHED:
            if self.source_final_subtitle_id is not None:
                raise ValueError("untouched approved unit must not reference a final subtitle")
        elif self.source_final_subtitle_id is None:
            raise ValueError(
                "accepted and modified approved units must reference a final subtitle"
            )


@dataclass(frozen=True, slots=True)
class SubtitleApprovedDocument:
    """Immutable, document-level approved subtitle representation — the canonical Export Input."""

    identity: SubtitleApprovedDocumentId
    domain_result_id: DomainResultId
    source_time_revision_id: SubtitleTimeRevisionId
    source_reading_revision_id: SubtitleReadingRevisionId
    eligibility: SubtitleExportEligibility
    source_candidate_id: SubtitleCandidateId
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    approved_unit_ids: tuple[SubtitleApprovedUnitId, ...]
    omitted_unit_count: int
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    ineligibility_reason: str | None = None
    previous_document_id: SubtitleApprovedDocumentId | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("approved document reason must not be empty")
        if self.sequence < 0:
            raise ValueError("approved document sequence must not be negative")
        if self.omitted_unit_count < 0:
            raise ValueError("approved document omitted unit count must not be negative")
        if self.eligibility is SubtitleExportEligibility.ELIGIBLE:
            if self.ineligibility_reason is not None:
                raise ValueError("eligible approved document must not carry an ineligibility reason")
        else:
            if self.ineligibility_reason is None or not self.ineligibility_reason.strip():
                raise ValueError("ineligible approved document requires a non-empty reason")
            if self.approved_unit_ids:
                raise ValueError("ineligible approved document must not carry approved units")
        if len(set(self.approved_unit_ids)) != len(self.approved_unit_ids):
            raise ValueError("approved document unit ids must be unique")
        if self.previous_document_id is not None and self.sequence == 0:
            raise ValueError("first approved document must not reference a previous document")


@dataclass(frozen=True, slots=True)
class SubtitleApprovedAssemblyIdentityPlan:
    """Application-owned identities for one assembly; unit ids match the time revision positionally."""

    document_id: SubtitleApprovedDocumentId
    document_result_id: DomainResultId
    unit_ids: tuple[SubtitleApprovedUnitId, ...]

    def __post_init__(self) -> None:
        if not self.unit_ids:
            raise ValueError("approved assembly identity plan requires unit ids")
        if len(set(self.unit_ids)) != len(self.unit_ids):
            raise ValueError("approved assembly identity plan unit ids must be unique")


@dataclass(frozen=True, slots=True)
class PreparedSubtitleApprovedDocument:
    """Immutable canonical approved document with its ordered units; not yet persisted."""

    document: SubtitleApprovedDocument
    units: tuple[SubtitleApprovedUnit, ...]
    document_result: DomainResultReference


__all__ = [
    "SUBTITLE_APPROVED_DOCUMENT_RESULT_KIND",
    "PreparedSubtitleApprovedDocument",
    "SubtitleApprovedAssemblyIdentityPlan",
    "SubtitleApprovedDocument",
    "SubtitleApprovedUnit",
    "SubtitleApprovedUnitOrigin",
    "SubtitleExportEligibility",
]
