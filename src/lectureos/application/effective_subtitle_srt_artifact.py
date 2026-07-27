"""Deterministic logical SRT Artifact generation from Effective Final Selections (GOAL-017).

The export boundary of the effective-transcript subtitle contract generation: an explicit request
over one exact, current, applicable `EffectiveSubtitleFinalSelection` serializes the selected
candidate's immutable cue graph into a canonical SRT payload and records it as an immutable
**logical** artifact. **Final Selection ≠ Artifact ≠ physical file**: artifact existence never
implies a file, path, URL, materialization, or delivery — physical materialization is a later,
separately scoped goal, and the legacy export pipeline is a separate contract generation, never
read or written.

Serialization reuses the released pure primitives (`application.srt_payload`) verbatim: cues are
numbered from 1 in canonical ordinal order; timestamps are `HH:MM:SS,mmm` with ROUND_HALF_UP
millisecond conversion; blocks are LF-separated with one blank line between blocks and a single
trailing LF on non-empty payloads; text is preserved exactly (no rewriting, wrapping, merging,
splitting, or timing correction); durations that collapse at millisecond precision and negative or
non-finite times are rejected. Export eligibility is derived, never persisted: the selection must
be the current selection of its scope and its GOAL-016 applicability must be `applicable` —
superseded, stale, or inapplicable selections never generate a new artifact, while existing
artifacts remain immutable historical evidence whose currentness is derived. Identity is
deterministic and selection-sensitive; the content fingerprint witnesses the exact payload but
never replaces identity (byte-identical SRT under different selections stays distinct). No
wall-clock, randomness, ProcessingRun, or UnitExecution participates.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError

from .effective_subtitle_final_selection import (
    EffectiveSubtitleFinalSelection,
    EffectiveSubtitleFinalSelectionService,
    SelectionApplicability,
    require_canonical_final_selection_id,
)
from .effective_subtitle_generation import (
    EffectiveSubtitleCue,
    EffectiveSubtitleGenerationService,
)
from .identities import (
    EffectiveSubtitleCandidateId,
    EffectiveSubtitleFinalSelectionId,
    EffectiveSubtitleSrtArtifactId,
    TranscriptSourceIntakeId,
)
from .provider_transcript_admission import (
    ProviderTranscriptAdmissionError,
    require_canonical_intake_id,
)
from .srt_payload import serialize_srt_cues

EFFECTIVE_SRT_ARTIFACT_IDENTITY_PREFIX = "subtitle-effective-srt-artifact"

ARTIFACT_CONTRACT_KIND = "effective_subtitle_srt_artifact"
ARTIFACT_CONTRACT_VERSION = 1
SRT_SERIALIZER_KIND = "canonical_srt"
SRT_SERIALIZER_VERSION = 1
SRT_SERIALIZATION_PARAMETERS_VERSION = 1


class EffectiveSubtitleSrtArtifactError(ValueError):
    """An export request that cannot proceed (malformed, unknown, or unsupported input)."""


class FinalSelectionNotExportableError(EffectiveSubtitleSrtArtifactError):
    """The final selection is not eligible for a new SRT artifact under current authority."""


class ArtifactCandidateGraphError(EffectiveSubtitleSrtArtifactError):
    """The selected candidate's cue graph cannot be serialized (broken or untimed)."""


class SrtArtifactConflictError(EffectiveSubtitleSrtArtifactError):
    """The deterministic replay anchor maps to a structurally different persisted artifact."""


class ArtifactOutcome(str, Enum):
    CREATED = "created"   # a new logical artifact row was persisted
    REUSED = "reused"     # the identical canonical artifact already existed; no new row


class ExportBlockingReason(str, Enum):
    SELECTION_NOT_FOUND = "selection_not_found"
    SELECTION_NOT_CURRENT = "selection_not_current"
    SELECTION_NOT_APPLICABLE = "selection_not_applicable"


class ArtifactCurrentness(str, Enum):
    """Derived, never stored. Materialization state is a separate, deferred concern."""

    CURRENT = "current"
    SUPERSEDED_BY_FINAL_SELECTION = "superseded_by_final_selection"
    SUPPORTING_DECISION_SUPERSEDED = "supporting_decision_superseded"
    STALE_DUE_TO_CANDIDATE_SOURCE = "stale_due_to_candidate_source"
    UNRESOLVABLE = "unresolvable"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_srt_content_fingerprint(srt_content: str) -> str:
    """SHA-256 of the canonical UTF-8 payload — an integrity witness, never artifact identity."""

    return _sha256(srt_content)


def derive_srt_artifact_identity(
    final_selection_id: EffectiveSubtitleFinalSelectionId,
    candidate_id: EffectiveSubtitleCandidateId,
    content_fingerprint: str,
) -> EffectiveSubtitleSrtArtifactId:
    """Deterministic artifact identity — selection-, candidate-, serializer-, and content-sensitive.

    The authority lineage (exact final selection) keeps byte-identical payloads under different
    selections distinct; the serializer contract keeps future incompatible serializers distinct.
    """

    digest = _sha256(
        _canonical_json(
            {
                "contract_kind": ARTIFACT_CONTRACT_KIND,
                "contract_version": ARTIFACT_CONTRACT_VERSION,
                "final_selection": final_selection_id.value,
                "candidate": candidate_id.value,
                "serializer_kind": SRT_SERIALIZER_KIND,
                "serializer_version": SRT_SERIALIZER_VERSION,
                "serialization_parameters_version": SRT_SERIALIZATION_PARAMETERS_VERSION,
                "content_fingerprint": content_fingerprint,
            }
        )
    )
    return EffectiveSubtitleSrtArtifactId(
        f"{EFFECTIVE_SRT_ARTIFACT_IDENTITY_PREFIX}:{digest}"
    )


def serialize_effective_cues(cues: tuple[EffectiveSubtitleCue, ...]) -> str:
    """Serialize the immutable ordered cue graph with the released canonical SRT primitives."""

    ordered = sorted(cues, key=lambda cue: cue.ordinal)
    for cue in ordered:
        if cue.start is None or cue.end is None:
            raise ArtifactCandidateGraphError(
                "candidate cue graph contains an untimed cue; SRT serialization requires "
                "exact timings (generation refused; nothing persisted)"
            )
    return serialize_srt_cues((cue.start, cue.end, cue.text) for cue in ordered)


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleSrtArtifact:
    """Immutable logical SRT artifact — never a file, path, URL, or materialization record."""

    identity: EffectiveSubtitleSrtArtifactId
    transcript_source_intake_id: TranscriptSourceIntakeId
    final_selection_id: EffectiveSubtitleFinalSelectionId
    candidate_id: EffectiveSubtitleCandidateId
    serializer_kind: str
    serializer_version: int
    serialization_parameters_version: int
    cue_count: int
    content_fingerprint: str
    srt_content: str

    def __post_init__(self) -> None:
        if self.serializer_kind != SRT_SERIALIZER_KIND:
            raise ValueError("unsupported SRT serializer kind")
        if (
            self.serializer_version != SRT_SERIALIZER_VERSION
            or self.serialization_parameters_version != SRT_SERIALIZATION_PARAMETERS_VERSION
        ):
            raise ValueError("unsupported SRT serializer version")
        if self.cue_count < 1:
            raise ValueError("an SRT artifact requires at least one cue")
        if not self.srt_content:
            raise ValueError("an SRT artifact payload must not be empty")
        if self.content_fingerprint != derive_srt_content_fingerprint(self.srt_content):
            raise ValueError(
                "SRT artifact content fingerprint must match its canonical payload"
            )
        if self.identity != derive_srt_artifact_identity(
            self.final_selection_id, self.candidate_id, self.content_fingerprint
        ):
            raise ValueError(
                "SRT artifact identity must derive from its selection, candidate, "
                "serializer contract, and content fingerprint"
            )


@dataclass(frozen=True, slots=True)
class ExportEligibility:
    """Derived, never persisted: may this final selection generate a NEW SRT artifact now?"""

    eligible: bool
    final_selection_id: EffectiveSubtitleFinalSelectionId | None
    selection_is_current: bool
    selection_applicability: SelectionApplicability | None
    candidate_id: EffectiveSubtitleCandidateId | None
    serializer_kind: str
    serializer_version: int
    blocking_reason: ExportBlockingReason | None


@dataclass(frozen=True, slots=True)
class SrtArtifactResult:
    """One export command outcome: the immutable artifact plus derived currentness."""

    artifact: EffectiveSubtitleSrtArtifact
    outcome: ArtifactOutcome
    currentness: ArtifactCurrentness


class SrtArtifactQuery(Protocol):
    def get(self, identity): ...

    def get_for_selection(self, final_selection_id): ...

    def list_for_intake(self, intake_id) -> tuple: ...


class AtomicSrtArtifactPersistence(Protocol):
    def persist_artifact(self, *, artifact: EffectiveSubtitleSrtArtifact) -> None: ...


class EffectiveSubtitleSrtArtifactService:
    """The single canonical logical-SRT export path of the effective-source generation (GOAL-017)."""

    def __init__(
        self,
        selection_service: EffectiveSubtitleFinalSelectionService,
        generation_service: EffectiveSubtitleGenerationService,
        artifact_query: SrtArtifactQuery,
        persistence: AtomicSrtArtifactPersistence | None = None,
    ) -> None:
        self._selections = selection_service
        self._candidates = generation_service
        self._artifacts = artifact_query
        self._persistence = persistence

    # -- derived export eligibility (never persisted) -------------------------------------------------

    def export_eligibility(self, final_selection_id: str) -> ExportEligibility:
        try:
            identity = require_canonical_final_selection_id(final_selection_id)
        except ValueError as error:
            raise EffectiveSubtitleSrtArtifactError(str(error)) from error
        selection = self._selections.get(identity.value)
        if selection is None:
            return ExportEligibility(
                eligible=False,
                final_selection_id=None,
                selection_is_current=False,
                selection_applicability=None,
                candidate_id=None,
                serializer_kind=SRT_SERIALIZER_KIND,
                serializer_version=SRT_SERIALIZER_VERSION,
                blocking_reason=ExportBlockingReason.SELECTION_NOT_FOUND,
            )
        current = self._selections.current(selection.transcript_source_intake_id.value)
        is_current = current is not None and current.identity == selection.identity
        applicability = self._selections.applicability(selection)
        blocking = None
        if not is_current:
            blocking = ExportBlockingReason.SELECTION_NOT_CURRENT
        elif applicability is not SelectionApplicability.APPLICABLE:
            blocking = ExportBlockingReason.SELECTION_NOT_APPLICABLE
        return ExportEligibility(
            eligible=blocking is None,
            final_selection_id=selection.identity,
            selection_is_current=is_current,
            selection_applicability=applicability,
            candidate_id=selection.candidate_id,
            serializer_kind=SRT_SERIALIZER_KIND,
            serializer_version=SRT_SERIALIZER_VERSION,
            blocking_reason=blocking,
        )

    # -- explicit export command ---------------------------------------------------------------------

    def generate_srt_artifact(self, *, final_selection_id: str) -> SrtArtifactResult:
        report = self.export_eligibility(final_selection_id)
        if not report.eligible:
            raise FinalSelectionNotExportableError(
                "final selection is not eligible for a new SRT artifact: "
                f"{report.blocking_reason.value}"
                + (
                    f" (selection applicability: {report.selection_applicability.value})"
                    if report.selection_applicability is not None
                    else ""
                )
            )
        selection = self._selections.get(report.final_selection_id.value)
        candidate = self._candidates.get(selection.candidate_id.value)
        if candidate is None:
            raise EffectiveSubtitleSrtArtifactError(
                "final selection references an unknown candidate (repository integrity failure)"
            )
        cues = self._candidates.cues(selection.candidate_id.value)
        if len(cues) != candidate.cue_count or [c.ordinal for c in cues] != list(
            range(len(cues))
        ):
            raise ArtifactCandidateGraphError(
                "candidate cue graph is structurally broken (generation refused; "
                "nothing persisted)"
            )
        srt_content = serialize_effective_cues(cues)
        fingerprint = derive_srt_content_fingerprint(srt_content)
        identity = derive_srt_artifact_identity(
            selection.identity, selection.candidate_id, fingerprint
        )
        existing = self._artifacts.get(identity)
        if existing is not None:
            return self._reuse(existing, selection, srt_content)

        artifact = EffectiveSubtitleSrtArtifact(
            identity=identity,
            transcript_source_intake_id=selection.transcript_source_intake_id,
            final_selection_id=selection.identity,
            candidate_id=selection.candidate_id,
            serializer_kind=SRT_SERIALIZER_KIND,
            serializer_version=SRT_SERIALIZER_VERSION,
            serialization_parameters_version=SRT_SERIALIZATION_PARAMETERS_VERSION,
            cue_count=len(cues),
            content_fingerprint=fingerprint,
            srt_content=srt_content,
        )
        if self._persistence is None:
            raise RuntimeError(
                "effective subtitle SRT artifact persistence is not configured"
            )
        try:
            self._persistence.persist_artifact(artifact=artifact)
        except PersistenceIdentityCollisionError:
            # A near-concurrent identical export won the insert (or a tampered row occupies the
            # replay anchor); converge only on complete payload equality.
            resolved = self._artifacts.get_for_selection(selection.identity)
            if resolved is not None:
                return self._reuse(resolved, selection, srt_content)
            raise
        return SrtArtifactResult(
            artifact=artifact,
            outcome=ArtifactOutcome.CREATED,
            currentness=self._currentness_of(selection),
        )

    def _reuse(self, existing, selection, srt_content) -> SrtArtifactResult:
        if (
            existing.final_selection_id != selection.identity
            or existing.candidate_id != selection.candidate_id
            or existing.srt_content != srt_content
            or existing.content_fingerprint != derive_srt_content_fingerprint(srt_content)
        ):
            raise SrtArtifactConflictError(
                "existing SRT artifact for this replay anchor records a different payload "
                "(repository integrity failure)"
            )
        return SrtArtifactResult(
            artifact=existing,
            outcome=ArtifactOutcome.REUSED,
            currentness=self._currentness_of(selection),
        )

    # -- queries (derived; never mutate history) ------------------------------------------------------

    def get(self, artifact_id: str) -> EffectiveSubtitleSrtArtifact | None:
        return self._artifacts.get(require_canonical_srt_artifact_id(artifact_id))

    def list_for_intake(self, intake_id: str) -> tuple[EffectiveSubtitleSrtArtifact, ...]:
        try:
            intake_identity = require_canonical_intake_id(intake_id)
        except ProviderTranscriptAdmissionError as error:
            raise EffectiveSubtitleSrtArtifactError(str(error)) from error
        return self._artifacts.list_for_intake(intake_identity)

    def currentness(self, artifact: EffectiveSubtitleSrtArtifact) -> ArtifactCurrentness:
        """Derived only: the artifact's bound selection evaluated against current authority."""

        selection = self._selections.get(artifact.final_selection_id.value)
        if selection is None:
            raise EffectiveSubtitleSrtArtifactError(
                "artifact references an unknown final selection (repository integrity failure)"
            )
        return self._currentness_of(selection)

    def _currentness_of(
        self, selection: EffectiveSubtitleFinalSelection
    ) -> ArtifactCurrentness:
        applicability = self._selections.applicability(selection)
        if applicability is SelectionApplicability.SUPERSEDED:
            return ArtifactCurrentness.SUPERSEDED_BY_FINAL_SELECTION
        if applicability is SelectionApplicability.SUPPORTING_DECISION_SUPERSEDED:
            return ArtifactCurrentness.SUPPORTING_DECISION_SUPERSEDED
        if applicability is SelectionApplicability.STALE_DUE_TO_CANDIDATE_SOURCE:
            return ArtifactCurrentness.STALE_DUE_TO_CANDIDATE_SOURCE
        if applicability is SelectionApplicability.UNRESOLVABLE:
            return ArtifactCurrentness.UNRESOLVABLE
        return ArtifactCurrentness.CURRENT


def require_canonical_srt_artifact_id(value: str) -> EffectiveSubtitleSrtArtifactId:
    prefix = EFFECTIVE_SRT_ARTIFACT_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise EffectiveSubtitleSrtArtifactError(
            "effective subtitle SRT artifact identity is malformed "
            "(expected 'subtitle-effective-srt-artifact:<64 hex digest>')"
        )
    return EffectiveSubtitleSrtArtifactId(value)


__all__ = [
    "ARTIFACT_CONTRACT_KIND",
    "ARTIFACT_CONTRACT_VERSION",
    "EFFECTIVE_SRT_ARTIFACT_IDENTITY_PREFIX",
    "SRT_SERIALIZATION_PARAMETERS_VERSION",
    "SRT_SERIALIZER_KIND",
    "SRT_SERIALIZER_VERSION",
    "ArtifactCandidateGraphError",
    "ArtifactCurrentness",
    "ArtifactOutcome",
    "AtomicSrtArtifactPersistence",
    "EffectiveSubtitleSrtArtifact",
    "EffectiveSubtitleSrtArtifactError",
    "EffectiveSubtitleSrtArtifactService",
    "ExportBlockingReason",
    "ExportEligibility",
    "FinalSelectionNotExportableError",
    "SrtArtifactConflictError",
    "SrtArtifactResult",
    "derive_srt_artifact_identity",
    "derive_srt_content_fingerprint",
    "require_canonical_srt_artifact_id",
    "serialize_effective_cues",
]
