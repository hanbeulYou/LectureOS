"""Derived Lecture Analysis Input Eligibility (042 §5.1 / PATCH-0009 Milestone 1, GOAL-022).

The first executable contract of the Lecture Intelligence pipeline: for one exact
`TranscriptSourceIntakeId`, derive whether the current effective transcript authority is
admissible as a lecture-analysis input, and expose the exact lineage a later explicit admission
command would bind.

**Admission authority (042 §5.1, Confirmed):** the milestone admits the *validated Corrected
Transcript selected by the Transcript Pipeline* together with its Source Timeline (the ordered
canonical segments) and Source Media reference, in the usable current-selected state that does
not bypass 040 validation. Accordingly, only a **current, applicable corrected-revision
selection** is eligible; an explicit raw-fallback selection or an absent corrected selection is a
truthful ineligible state (`corrected_transcript_not_selected`), never a silent admission — raw
transcripts remain first-class upstream records, but they are not the confirmed analysis
admission authority.

**Eligibility ≠ Analysis Input ≠ Analysis Run.** This module is derived-only: nothing is
persisted, no identity is allocated, no transcript record is touched, and no analysis of any kind
runs. The result is **advisory** — it observes one authority snapshot and does not reserve or
freeze the transcript; a later explicit admission command must revalidate current authority
before persisting anything (the TOCTOU boundary). Within one evaluation, authority is resolved
exactly once through the sole released 040 §20 resolver and the content snapshot is then loaded
by immutable identities only, so a single result never mixes two authority snapshots. The
released §19 content fingerprint is reused verbatim; no second normalization exists. Repository
corruption (broken lineage, missing snapshots) raises — it is never concealed as ordinary
ineligibility.

**Relation to the legacy 042 §5.1 implementation.** The repository's released
`lecture_analysis_input` module (durable `eligible_analysis_inputs` records) realizes PATCH-0009
over the *legacy* execution-coupled transcript pipeline (Transcript Readiness Evaluation,
ProcessingRun/UnitExecution provenance). This module is the **effective-transcript contract
generation's** counterpart — derived-only eligibility over the released 040 §20 effective
authority — exactly as the effective subtitle pipeline coexists with the legacy subtitle path.
It never reads or writes the legacy analysis tables; a later admission Goal owns the durable
Eligible Analysis Input record for this generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .corrected_revision_generation import content_fingerprint_for
from .corrected_revision_selection import (
    CorrectedRevisionSelectionService,
    EffectiveKind,
    SelectionState,
)
from lectureos.execution.identities import SourceMediaId
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .provider_transcript_admission import (
    ProviderTranscriptAdmissionError,
    require_canonical_intake_id,
)


class LectureAnalysisInputEligibilityError(ValueError):
    """Invalid API input or a repository integrity failure — never ordinary ineligibility."""


class AnalysisInputBlockingReason(str, Enum):
    """Closed, stable vocabulary; results order reasons by this definition order."""

    INTAKE_NOT_FOUND = "intake_not_found"
    NO_CURRENT_RAW_TRANSCRIPT = "no_current_raw_transcript"
    CORRECTED_TRANSCRIPT_NOT_SELECTED = "corrected_transcript_not_selected"
    CORRECTED_SELECTION_NOT_APPLICABLE = "corrected_selection_not_applicable"
    TRANSCRIPT_CONTENT_EMPTY = "transcript_content_empty"


_REASON_ORDER = tuple(AnalysisInputBlockingReason)


@dataclass(frozen=True, slots=True)
class LectureAnalysisInputEligibility:
    """Derived, never persisted: one intake's analysis-input admissibility with exact lineage.

    An eligible result identifies the exact authority a later explicit admission would bind
    (intake, source media, corrected revision, parent raw transcript, the observed selection
    records, and the released content fingerprint). The result itself reserves nothing.
    """

    transcript_source_intake_id: str
    eligible: bool
    blocking_reasons: tuple[AnalysisInputBlockingReason, ...]
    source_media_id: SourceMediaId | None = None
    selection_state: SelectionState | None = None
    effective_kind: EffectiveKind | None = None
    corrected_revision_id: TranscriptRevisionId | None = None
    parent_raw_transcript_id: TranscriptId | None = None
    raw_selection_id: object | None = None       # CurrentRawTranscriptSelectionId
    corrected_selection_id: object | None = None  # CorrectedRevisionSelectionId
    inapplicability_reason: str | None = None
    segment_count: int | None = None
    content_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.eligible and self.blocking_reasons:
            raise ValueError("an eligible result must carry no blocking reasons")
        if not self.eligible and not self.blocking_reasons:
            raise ValueError("an ineligible result requires at least one blocking reason")
        ordered = tuple(
            sorted(self.blocking_reasons, key=_REASON_ORDER.index)
        )
        if self.blocking_reasons != ordered:
            raise ValueError("blocking reasons must be deterministically ordered")
        if self.eligible:
            if (
                self.corrected_revision_id is None
                or self.parent_raw_transcript_id is None
                or self.content_fingerprint is None
                or self.segment_count is None
            ):
                raise ValueError(
                    "an eligible result must expose complete corrected-transcript lineage"
                )


class IntakeQuery(Protocol):
    def get(self, identity): ...


class RawSelectionQuery(Protocol):
    def get_current(self, intake_id): ...


class RevisionSnapshotQuery(Protocol):
    def get(self, identity): ...


class SegmentSnapshotQuery(Protocol):
    def get(self, identity): ...


class LectureAnalysisInputEligibilityService:
    """The single canonical analysis-input eligibility query (042 Milestone 1, derived-only)."""

    def __init__(
        self,
        intake_query: IntakeQuery,
        raw_selection_query: RawSelectionQuery,
        selection_service: CorrectedRevisionSelectionService,
        revision_query: RevisionSnapshotQuery,
        segment_query: SegmentSnapshotQuery,
    ) -> None:
        self._intakes = intake_query
        self._raw_selections = raw_selection_query
        self._resolver = selection_service
        self._revisions = revision_query
        self._segments = segment_query

    def evaluate(self, intake_id: str) -> LectureAnalysisInputEligibility:
        try:
            identity = require_canonical_intake_id(intake_id)
        except ProviderTranscriptAdmissionError as error:
            raise LectureAnalysisInputEligibilityError(str(error)) from error

        def _blocked(
            reason: AnalysisInputBlockingReason, **lineage
        ) -> LectureAnalysisInputEligibility:
            return LectureAnalysisInputEligibility(
                transcript_source_intake_id=identity.value,
                eligible=False,
                blocking_reasons=(reason,),
                **lineage,
            )

        intake = self._intakes.get(identity)
        if intake is None:
            return _blocked(AnalysisInputBlockingReason.INTAKE_NOT_FOUND)
        if self._raw_selections.get_current(identity) is None:
            return _blocked(
                AnalysisInputBlockingReason.NO_CURRENT_RAW_TRANSCRIPT,
                source_media_id=intake.source_media_id,
            )
        # One authority snapshot: the sole released 040 §20 resolver, called exactly once.
        # Any error it raises past the guards above is an integrity failure — propagated,
        # never concealed as ineligibility.
        resolution = self._resolver.resolve_effective_transcript(identity.value)
        lineage = dict(
            source_media_id=intake.source_media_id,
            selection_state=resolution.selection_state,
            effective_kind=resolution.effective_kind,
            corrected_revision_id=resolution.corrected_revision_id,
            parent_raw_transcript_id=resolution.raw_transcript_id,
            raw_selection_id=resolution.raw_selection_id,
            corrected_selection_id=resolution.corrected_selection_id,
        )
        if resolution.effective_kind is EffectiveKind.RAW_TRANSCRIPT:
            # 042 §5.1: the admission authority is the validated selected Corrected
            # Transcript; an explicit raw fallback or absent selection is honestly
            # ineligible — never silently admitted.
            return _blocked(
                AnalysisInputBlockingReason.CORRECTED_TRANSCRIPT_NOT_SELECTED, **lineage
            )
        if resolution.effective_kind is EffectiveKind.INAPPLICABLE_SELECTION:
            return _blocked(
                AnalysisInputBlockingReason.CORRECTED_SELECTION_NOT_APPLICABLE,
                inapplicability_reason=resolution.inapplicability_reason,
                **lineage,
            )
        # Corrected revision resolved: load the immutable snapshot by exact identity only
        # (no authority re-read) and reuse the released §19 content fingerprint verbatim.
        revision = self._revisions.get(resolution.corrected_revision_id)
        if revision is None:
            raise LectureAnalysisInputEligibilityError(
                "resolved corrected revision does not exist (repository integrity failure)"
            )
        segments = []
        for segment_id in revision.segment_ids:
            segment = self._segments.get(segment_id)
            if segment is None:
                raise LectureAnalysisInputEligibilityError(
                    "corrected revision snapshot is incomplete: a segment record is "
                    "missing (repository integrity failure)"
                )
            segments.append(segment)
        segments = tuple(segments)
        fingerprint = content_fingerprint_for(segments)
        if not segments or all(not segment.text.strip() for segment in segments):
            # Conservative structural rule only: analysis input requires non-empty content.
            # No token-count, duration, or timing minimum is imposed (042 defines none).
            return _blocked(
                AnalysisInputBlockingReason.TRANSCRIPT_CONTENT_EMPTY,
                segment_count=len(segments),
                content_fingerprint=fingerprint,
                **lineage,
            )
        return LectureAnalysisInputEligibility(
            transcript_source_intake_id=identity.value,
            eligible=True,
            blocking_reasons=(),
            segment_count=len(segments),
            content_fingerprint=fingerprint,
            **lineage,
        )


__all__ = [
    "AnalysisInputBlockingReason",
    "IntakeQuery",
    "LectureAnalysisInputEligibility",
    "LectureAnalysisInputEligibilityError",
    "LectureAnalysisInputEligibilityService",
    "RawSelectionQuery",
    "RevisionSnapshotQuery",
    "SegmentSnapshotQuery",
]
