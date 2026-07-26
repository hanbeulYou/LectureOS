"""Effective-Transcript-Sourced Subtitle Candidate generation (041 §15, PATCH-0029, GOAL-013).

The first canonical subtitle generation path of the effective-transcript contract generation. One
explicit request acquires its transcript content **only** through the GOAL-012 Effective Transcript
Consumption Boundary (the persisted consumption binding exists before generation and pins the exact
immutable source), runs one deterministic local generator, and persists one immutable
Effective-Source Subtitle Candidate with its ordered immutable cue set and exact source-segment
lineage — atomically.

The generator is `deterministic_segment_passthrough` v1: one ordered cue per ordered effective
transcript segment, with the cue's text, timing, ordinal, and source-segment lineage taken exactly
from the consumed immutable snapshot. No merging, splitting, rewriting, normalization, translation,
or timing change. Corrected replacement lineage is preserved structurally: each cue references the
exact consumed canonical segment, whose own immutable `replaces_segment_id` reaches the underlying
Raw segment — nothing is inferred from text matching, and provider confidence is never fabricated.

This module never resolves transcript authority itself, never falls back to Raw silently, never
re-resolves midway, and never creates ProcessingRun/UnitExecution/review/decision/selection/export
records (041 §15 E5/E6/E12/E13). Candidates are immutable historical facts: later authority changes
derive staleness (GOAL-012 currentness vocabulary) and never rewrite, delete, or regenerate them.
Legacy `subtitle_candidates` records and stages are untouched — the two representations are
distinct contract generations (E1/E2). No wall-clock or randomness participates.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)

from .effective_transcript_consumption import (
    ConsumedSourceKind,
    ConsumptionCurrentness,
    EffectiveTranscriptConsumptionService,
    EffectiveTranscriptInput,
    SUBTITLE_GENERATION_CONSUMER_KIND,
)
from .identities import (
    EffectiveSubtitleCandidateId,
    EffectiveSubtitleCueId,
    EffectiveTranscriptConsumptionId,
    TranscriptSourceIntakeId,
)
from .provider_transcript_admission import (
    ProviderTranscriptAdmissionError,
    require_canonical_intake_id,
)

EFFECTIVE_SUBTITLE_CANDIDATE_IDENTITY_PREFIX = "subtitle-effective-candidate"
EFFECTIVE_SUBTITLE_CUE_IDENTITY_PREFIX = "subtitle-effective-cue"

GENERATOR_KIND = "deterministic_segment_passthrough"
GENERATOR_VERSION = 1
GENERATION_PARAMETERS_VERSION = 1


class EffectiveSubtitleGenerationError(ValueError):
    """A generation request that cannot proceed (malformed, unknown, or unsupported input)."""


class EffectiveSubtitleGenerationConflictError(EffectiveSubtitleGenerationError):
    """The deterministic generation identity maps to a structurally different persisted payload."""


class GenerationOutcome(str, Enum):
    CREATED = "created"   # a new candidate graph was persisted
    REUSED = "reused"     # the identical semantic candidate already existed; no new rows


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_effective_candidate_identity(
    intake_id: TranscriptSourceIntakeId,
    consumption_binding_id: EffectiveTranscriptConsumptionId,
    source_kind: ConsumedSourceKind,
    source_transcript_identity: str,
    generator_kind: str,
    generator_version: int,
    generation_parameters_version: int,
) -> EffectiveSubtitleCandidateId:
    """Deterministic, exact-source-sensitive candidate identity (041 §15 E7).

    The binding identity already pins (consumer kind, intake, source kind, exact source); the
    source facts are still hashed explicitly so identity semantics are self-contained. No
    wall-clock, randomness, current pointer, row order, or content-fingerprint-alone derivation.
    """

    digest = _sha256(
        _canonical_json(
            {
                "consumer_kind": SUBTITLE_GENERATION_CONSUMER_KIND,
                "intake": intake_id.value,
                "consumption_binding": consumption_binding_id.value,
                "source_kind": source_kind.value,
                "source": source_transcript_identity,
                "generator_kind": generator_kind,
                "generator_version": generator_version,
                "generation_parameters_version": generation_parameters_version,
            }
        )
    )
    return EffectiveSubtitleCandidateId(
        f"{EFFECTIVE_SUBTITLE_CANDIDATE_IDENTITY_PREFIX}:{digest}"
    )


def derive_effective_cue_identity(
    candidate_id: EffectiveSubtitleCandidateId,
    ordinal: int,
    source_segment_id: TranscriptSegmentId,
) -> EffectiveSubtitleCueId:
    """Deterministic cue identity scoped to its immutable candidate — insertion timing never participates."""

    digest = _sha256(
        _canonical_json(
            {
                "candidate": candidate_id.value,
                "ordinal": ordinal,
                "source_segment": source_segment_id.value,
            }
        )
    )
    return EffectiveSubtitleCueId(f"{EFFECTIVE_SUBTITLE_CUE_IDENTITY_PREFIX}:{digest}")


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleCue:
    """One immutable ordered cue of an effective-source candidate, with exact segment lineage.

    ``source_segment_ids`` is an ordered tuple (>=1) for permanent compatibility with future
    non-1:1 segmentation contracts (041 §4.2); the v1 passthrough generator always records exactly
    one — the exact consumed canonical segment, whose immutable ``replaces_segment_id`` carries the
    underlying Raw lineage for corrected replacements.
    """

    identity: EffectiveSubtitleCueId
    candidate_id: EffectiveSubtitleCandidateId
    ordinal: int
    text: str
    source_segment_ids: tuple[TranscriptSegmentId, ...]
    start: float | None = None
    end: float | None = None

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("effective subtitle cue ordinal must not be negative")
        if not self.text.strip():
            raise ValueError("effective subtitle cue text must not be empty")
        if not self.source_segment_ids:
            raise ValueError("effective subtitle cue requires a source transcript segment")
        if len(set(self.source_segment_ids)) != len(self.source_segment_ids):
            raise ValueError("effective subtitle cue source segments must be unique")
        if (self.start is None) != (self.end is None):
            raise ValueError("effective subtitle cue time range requires both start and end")
        if self.start is not None and self.end is not None:
            if not isfinite(self.start) or not isfinite(self.end):
                raise ValueError("effective subtitle cue time range must be finite")
            if self.start < 0 or self.end < 0:
                raise ValueError("effective subtitle cue time range must not be negative")
            if self.start > self.end:
                raise ValueError("effective subtitle cue start must not be after end")
        expected = derive_effective_cue_identity(
            self.candidate_id, self.ordinal, self.source_segment_ids[0]
        )
        if self.identity != expected:
            raise ValueError(
                "effective subtitle cue identity must derive from its candidate, ordinal, and source segment"
            )


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleCandidate:
    """Immutable effective-source subtitle candidate (041 §15) — the new contract generation's record."""

    identity: EffectiveSubtitleCandidateId
    transcript_source_intake_id: TranscriptSourceIntakeId
    consumption_binding_id: EffectiveTranscriptConsumptionId
    source_kind: ConsumedSourceKind
    corrected_revision_id: TranscriptRevisionId | None
    parent_raw_transcript_id: TranscriptId
    source_snapshot_fingerprint: str
    generator_kind: str
    generator_version: int
    generation_parameters_version: int
    cue_count: int

    def __post_init__(self) -> None:
        if not self.generator_kind.strip():
            raise ValueError("effective subtitle candidate generator kind must not be empty")
        if self.generator_version < 1 or self.generation_parameters_version < 1:
            raise ValueError("effective subtitle candidate generator versions must be >= 1")
        if self.cue_count < 1:
            raise ValueError("effective subtitle candidate requires at least one cue")
        if len(self.source_snapshot_fingerprint) != 64:
            raise ValueError(
                "effective subtitle candidate snapshot fingerprint must be a 64-hex SHA-256 digest"
            )
        if self.source_kind is ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION:
            if self.corrected_revision_id is None:
                raise ValueError(
                    "a corrected-source candidate requires the exact revision identity"
                )
        elif self.corrected_revision_id is not None:
            raise ValueError("a raw-source candidate must not carry a corrected revision identity")
        expected = derive_effective_candidate_identity(
            self.transcript_source_intake_id,
            self.consumption_binding_id,
            self.source_kind,
            self.source_transcript_identity,
            self.generator_kind,
            self.generator_version,
            self.generation_parameters_version,
        )
        if self.identity != expected:
            raise ValueError(
                "effective subtitle candidate identity must be derived from its binding, "
                "exact source, and generator semantics"
            )

    @property
    def source_transcript_identity(self) -> str:
        """The exact immutable source consumed — never the intake or a selection pointer."""

        if self.source_kind is ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION:
            return self.corrected_revision_id.value
        return self.parent_raw_transcript_id.value


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleGenerationResult:
    """One generation command outcome: the immutable candidate graph plus derived currentness."""

    candidate: EffectiveSubtitleCandidate
    cues: tuple[EffectiveSubtitleCue, ...]
    outcome: GenerationOutcome
    currentness: ConsumptionCurrentness


class EffectiveSubtitleCandidateQuery(Protocol):
    def get(self, identity): ...

    def cues(self, candidate_id) -> tuple: ...

    def list_for_intake(self, intake_id) -> tuple: ...


class AtomicEffectiveSubtitleCandidatePersistence(Protocol):
    def persist_candidate(
        self,
        *,
        candidate: EffectiveSubtitleCandidate,
        cues: tuple[EffectiveSubtitleCue, ...],
    ) -> None: ...


def build_passthrough_cues(
    candidate_id: EffectiveSubtitleCandidateId, acquired: EffectiveTranscriptInput
) -> tuple[EffectiveSubtitleCue, ...]:
    """The v1 deterministic passthrough: one cue per ordered consumed segment, exact text/timing/lineage."""

    return tuple(
        EffectiveSubtitleCue(
            identity=derive_effective_cue_identity(candidate_id, ordinal, segment.identity),
            candidate_id=candidate_id,
            ordinal=ordinal,
            text=segment.text,
            source_segment_ids=(segment.identity,),
            start=segment.start,
            end=segment.end,
        )
        for ordinal, segment in enumerate(acquired.segments)
    )


class EffectiveSubtitleGenerationService:
    """The single canonical effective-transcript subtitle generation path (041 §15)."""

    def __init__(
        self,
        consumption_service: EffectiveTranscriptConsumptionService,
        candidate_query: EffectiveSubtitleCandidateQuery,
        persistence: AtomicEffectiveSubtitleCandidatePersistence | None = None,
    ) -> None:
        self._consumptions = consumption_service
        self._candidates = candidate_query
        self._persistence = persistence

    # -- generation ----------------------------------------------------------------------------------

    def generate(self, *, intake_id: str) -> EffectiveSubtitleGenerationResult:
        # Source acquisition happens ONLY through the GOAL-012 boundary: the persisted consumption
        # binding is created (or converged on) first and pins the exact immutable source; an
        # inapplicable selected revision or missing current Raw fails here, before any candidate
        # row exists — never a silent fallback.
        consumed = self._consumptions.consume(
            intake_id=intake_id, consumer_kind=SUBTITLE_GENERATION_CONSUMER_KIND
        )
        binding, acquired = consumed.consumption, consumed.input

        identity = derive_effective_candidate_identity(
            binding.transcript_source_intake_id,
            binding.identity,
            binding.source_kind,
            binding.source_transcript_identity,
            GENERATOR_KIND,
            GENERATOR_VERSION,
            GENERATION_PARAMETERS_VERSION,
        )
        existing = self._candidates.get(identity)
        if existing is not None:
            return self._reuse(existing, binding)

        candidate = EffectiveSubtitleCandidate(
            identity=identity,
            transcript_source_intake_id=binding.transcript_source_intake_id,
            consumption_binding_id=binding.identity,
            source_kind=binding.source_kind,
            corrected_revision_id=binding.corrected_revision_id,
            parent_raw_transcript_id=binding.parent_raw_transcript_id,
            source_snapshot_fingerprint=binding.content_fingerprint,
            generator_kind=GENERATOR_KIND,
            generator_version=GENERATOR_VERSION,
            generation_parameters_version=GENERATION_PARAMETERS_VERSION,
            cue_count=len(acquired.segments),
        )
        cues = build_passthrough_cues(identity, acquired)
        if self._persistence is None:
            raise RuntimeError("effective subtitle candidate persistence is not configured")
        try:
            self._persistence.persist_candidate(candidate=candidate, cues=cues)
        except PersistenceIdentityCollisionError:
            # A near-concurrent identical request won the insert; converge on its canonical graph.
            resolved = self._candidates.get(identity)
            if resolved is not None:
                return self._reuse(resolved, binding)
            raise
        return EffectiveSubtitleGenerationResult(
            candidate=candidate,
            cues=cues,
            outcome=GenerationOutcome.CREATED,
            currentness=self._consumptions.currentness(binding),
        )

    def _reuse(self, existing, binding) -> EffectiveSubtitleGenerationResult:
        # The deterministic identity must map to exactly one structural payload; a disagreement is
        # an explicit conflict (repository corruption), never replay and never an overwrite.
        if (
            existing.consumption_binding_id != binding.identity
            or existing.source_snapshot_fingerprint != binding.content_fingerprint
        ):
            raise EffectiveSubtitleGenerationConflictError(
                "existing effective subtitle candidate for this generation identity records a "
                "different source payload (repository integrity failure)"
            )
        cues = self._candidates.cues(existing.identity)
        if len(cues) != existing.cue_count:
            raise EffectiveSubtitleGenerationConflictError(
                "existing effective subtitle candidate cue set is incomplete "
                "(repository integrity failure)"
            )
        return EffectiveSubtitleGenerationResult(
            candidate=existing,
            cues=cues,
            outcome=GenerationOutcome.REUSED,
            currentness=self._consumptions.currentness(binding),
        )

    # -- queries (derived; never mutate history) ------------------------------------------------------

    def get(self, candidate_id: str) -> EffectiveSubtitleCandidate | None:
        return self._candidates.get(require_canonical_candidate_id(candidate_id))

    def cues(self, candidate_id: str) -> tuple[EffectiveSubtitleCue, ...]:
        return self._candidates.cues(require_canonical_candidate_id(candidate_id))

    def list_for_intake(self, intake_id: str) -> tuple[EffectiveSubtitleCandidate, ...]:
        try:
            intake_identity = require_canonical_intake_id(intake_id)
        except ProviderTranscriptAdmissionError as error:
            raise EffectiveSubtitleGenerationError(str(error)) from error
        return self._candidates.list_for_intake(intake_identity)

    def currentness(self, candidate: EffectiveSubtitleCandidate) -> ConsumptionCurrentness:
        """Whether the candidate's exact source binding is still current — derived, never stored."""

        binding = self._consumptions.get_binding(candidate.consumption_binding_id)
        if binding is None:
            raise EffectiveSubtitleGenerationError(
                "candidate references an unknown consumption binding (repository integrity failure)"
            )
        return self._consumptions.currentness(binding)


def require_canonical_candidate_id(value: str) -> EffectiveSubtitleCandidateId:
    prefix = EFFECTIVE_SUBTITLE_CANDIDATE_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise EffectiveSubtitleGenerationError(
            "effective subtitle candidate identity is malformed "
            "(expected 'subtitle-effective-candidate:<64 hex digest>')"
        )
    return EffectiveSubtitleCandidateId(value)


__all__ = [
    "EFFECTIVE_SUBTITLE_CANDIDATE_IDENTITY_PREFIX",
    "EFFECTIVE_SUBTITLE_CUE_IDENTITY_PREFIX",
    "GENERATION_PARAMETERS_VERSION",
    "GENERATOR_KIND",
    "GENERATOR_VERSION",
    "AtomicEffectiveSubtitleCandidatePersistence",
    "EffectiveSubtitleCandidate",
    "EffectiveSubtitleCandidateQuery",
    "EffectiveSubtitleCue",
    "EffectiveSubtitleGenerationConflictError",
    "EffectiveSubtitleGenerationError",
    "EffectiveSubtitleGenerationResult",
    "EffectiveSubtitleGenerationService",
    "GenerationOutcome",
    "build_passthrough_cues",
    "derive_effective_candidate_identity",
    "derive_effective_cue_identity",
    "require_canonical_candidate_id",
]
