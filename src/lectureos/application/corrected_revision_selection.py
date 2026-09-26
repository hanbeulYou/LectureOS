"""Current Corrected Transcript Revision Selection and effective transcript resolution (040 §20, PATCH-0027).

Answers exactly one question — *which immutable Corrected Transcript Revision, if any, is currently selected for
an intake's transcript context?* — and its inverse: *has the user explicitly fallen back to the authoritative Raw
Transcript?* Revision existence (040 §19) and revision selection are separate authority facts: a revision never
becomes current merely because it was generated, is newest, is the only one, or its candidate is Accepted.
Selection is **explicit** and **append-only** (the §16/§18 authority idiom): each change is a new immutable record
with a per-intake ``sequence`` superseding the prior via ``previous_selection_id``; the current selection is the
highest-``sequence`` record, always derived, never a mutable pointer or ``is_current`` flag.

Two authority actions exist: **select a Corrected Revision** and **select Raw Transcript fallback** (an explicit
authority fact, historically distinguishable from never-having-selected; never a fake revision). Identical replay
reuses; changed selection appends; nothing is ever updated, deleted, or auto-promoted, and no revision, candidate,
decision, raw transcript, or current Raw Transcript selection is mutated.

**Selection ≠ applicability.** Selection records what the authority chose; applicability derives whether that
choice can currently be used (the selected revision's parent must be the intake's current Raw Transcript and its
candidate's current §18 authority must be Accepted). A later Candidate Reject or Raw-selection switch makes a
selected revision *inapplicable* — never corruption, never an automatic fallback or reselection. **New** selection,
however, must pass eligibility at selection time: an inapplicable or currently-rejected-candidate revision cannot
be newly selected (no ``--force``). The deterministic effective-transcript resolver returns an explicit structured
result — raw (no history), raw (explicit fallback), corrected (selected + applicable), or selected-but-inapplicable
with a reason — never a silent fallback that hides an authority conflict. No wall-clock/randomness participates.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.review.identities import HumanActorReference
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .identities import (
    CorrectedRevisionSelectionId,
    CurrentRawTranscriptSelectionId,
    TranscriptSourceIntakeId,
)
from .provider_transcript_admission import (
    ProviderTranscriptAdmissionError,
    require_canonical_intake_id,
)

CORRECTED_REVISION_SELECTION_IDENTITY_PREFIX = "corrected-revision-selection"
_CORRECTED_REVISION_PREFIX = "corrected-revision:"


class CorrectedRevisionSelectionError(ValueError):
    """A selection request that cannot proceed (malformed, unknown, or unsupported input)."""


class RevisionNotEligibleError(CorrectedRevisionSelectionError):
    """The revision cannot be newly selected under current upstream authority (not applicable/accepted)."""


class SelectionKind(str, Enum):
    CORRECTED_REVISION = "corrected_revision"
    RAW_FALLBACK = "raw_fallback"


class SelectionOutcome(str, Enum):
    RECORDED = "recorded"   # first authority for the context (sequence 0)
    REUSED = "reused"       # requested semantic state is already current
    CHANGED = "changed"     # new authority differs from the previous current state


class SelectionState(str, Enum):
    NO_HISTORY = "no_history"
    RAW_FALLBACK = "raw_fallback"
    CORRECTED_SELECTED = "corrected_revision_selected"


class EffectiveKind(str, Enum):
    RAW_TRANSCRIPT = "raw_transcript"
    CORRECTED_REVISION = "corrected_revision"
    INAPPLICABLE_SELECTION = "inapplicable_selection"


def require_canonical_corrected_revision_id(value: str) -> TranscriptRevisionId:
    """Return a `TranscriptRevisionId` if the value is a well-formed corrected revision identity, else reject."""

    if not isinstance(value, str) or not value.startswith(_CORRECTED_REVISION_PREFIX):
        raise CorrectedRevisionSelectionError(
            "corrected revision identity is malformed (expected 'corrected-revision:<digest>')"
        )
    digest = value[len(_CORRECTED_REVISION_PREFIX):]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise CorrectedRevisionSelectionError(
            "corrected revision identity is malformed (expected 'corrected-revision:<64 hex digest>')"
        )
    return TranscriptRevisionId(value)


def derive_selection_identity(
    intake_id: TranscriptSourceIntakeId,
    kind: SelectionKind,
    corrected_revision_id: TranscriptRevisionId | None,
    sequence: int,
) -> CorrectedRevisionSelectionId:
    """Deterministic selection identity from the context, kind, target revision, and per-context sequence."""

    payload = json.dumps(
        {
            "intake": intake_id.value,
            "kind": kind.value,
            "revision": corrected_revision_id.value if corrected_revision_id else None,
            "sequence": sequence,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return CorrectedRevisionSelectionId(
        f"{CORRECTED_REVISION_SELECTION_IDENTITY_PREFIX}:{digest}"
    )


@dataclass(frozen=True, slots=True)
class CorrectedRevisionSelection:
    """Immutable selection authority fact: what the authority chose for one intake at one sequence."""

    identity: CorrectedRevisionSelectionId
    transcript_source_intake_id: TranscriptSourceIntakeId
    kind: SelectionKind
    reviewer: HumanActorReference
    sequence: int
    corrected_revision_id: TranscriptRevisionId | None = None
    previous_selection_id: CorrectedRevisionSelectionId | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reviewer, HumanActorReference):
            raise ValueError("selection reviewer must be a Human actor reference")
        if (self.kind is SelectionKind.CORRECTED_REVISION) != (
            self.corrected_revision_id is not None
        ):
            raise ValueError(
                "a corrected-revision selection requires a revision; raw fallback must not carry one"
            )
        if self.sequence < 0:
            raise ValueError("selection sequence must not be negative")
        if (self.sequence == 0) != (self.previous_selection_id is None):
            raise ValueError(
                "the first selection (sequence 0) has no previous; later selections require one"
            )
        expected = derive_selection_identity(
            self.transcript_source_intake_id, self.kind, self.corrected_revision_id, self.sequence
        )
        if self.identity != expected:
            raise ValueError(
                "selection identity must be derived from its context, kind, revision, and sequence"
            )
        if self.rationale is not None and not self.rationale.strip():
            raise ValueError("selection rationale, when present, must not be blank")


@dataclass(frozen=True, slots=True)
class CorrectedRevisionSelectionResult:
    """The outcome of one selection command."""

    selection: CorrectedRevisionSelection
    outcome: SelectionOutcome
    previous: CorrectedRevisionSelection | None = None


@dataclass(frozen=True, slots=True)
class SelectionApplicability:
    """Derived at query time: can the selected revision currently be used?"""

    applicable: bool
    reason: str | None = None  # 'parent_raw_transcript_not_current' | 'candidate_not_accepted'


@dataclass(frozen=True, slots=True)
class EffectiveTranscript:
    """Explicit structured result of effective-transcript resolution (never a hidden nullable).

    ``raw_selection_id`` and ``corrected_selection_id`` are the exact authority records the resolver
    observed (040 §21 provenance for downstream consumption); they add no new resolution meaning.
    ``corrected_selection_id`` is ``None`` exactly when no selection history exists.
    """

    transcript_source_intake_id: TranscriptSourceIntakeId
    selection_state: SelectionState
    effective_kind: EffectiveKind
    raw_transcript_id: TranscriptId
    corrected_revision_id: TranscriptRevisionId | None = None
    inapplicability_reason: str | None = None
    raw_selection_id: CurrentRawTranscriptSelectionId | None = None
    corrected_selection_id: CorrectedRevisionSelectionId | None = None


class TranscriptSourceIntakeQuery(Protocol):
    def get(self, identity): ...


class CorrectedRevisionGenerationQuery(Protocol):
    def get_by_revision(self, revision_id: TranscriptRevisionId): ...


class TimingCorrectionGenerationQuery(Protocol):
    """The `PATCH-0047` sibling generation relation, consulted only when the text one has no binding."""

    def view_by_revision(self, revision_id: TranscriptRevisionId): ...

    def candidate(self, candidate_id): ...


class TimingCorrectionDecisionQuery(Protocol):
    def get_current(self, candidate_id): ...


class CorrectionCandidateAdmissionQuery(Protocol):
    def get_by_candidate(self, candidate_id): ...


class CorrectionCandidateDecisionQuery(Protocol):
    def get_current(self, candidate_id): ...


class RawTranscriptSelectionQuery(Protocol):
    def get_current(self, intake_id): ...


class CorrectedRevisionSelectionQuery(Protocol):
    def get(self, identity): ...

    def get_current(self, intake_id): ...

    def history(self, intake_id) -> tuple: ...


class AtomicCorrectedRevisionSelectionPersistence(Protocol):
    def persist_selection(self, *, selection: CorrectedRevisionSelection) -> None: ...


@dataclass(frozen=True, slots=True)
class _RevisionLineage:
    """A revision's generation binding, normalised across correction kinds (`PATCH-0047` TC-13/§20 note).

    Selection is **correction-kind-agnostic**: `§20` chooses a revision and never asks what produced
    its timing. The released S2-8 eligibility facts — the revision's parent raw transcript and its
    candidate's current `§18` authority — exist for both kinds, so they are resolved here through the
    kind's own generation relation and decision history, and the released rules then apply unchanged.

    A generation may apply more than one timing candidate (`PATCH-0049`), so the released singular
    "candidate" fact generalises to the generation's complete member set: the revision is applicable
    when **every** member's current `§18` authority is Accepted (MG-33). A text generation and a
    legacy timing singleton carry exactly one member, so their behaviour is unchanged. Agreement
    between a member's *current* Accepted Decision identity and the Decision that authorized the
    generation is deliberately **not** a condition (MG-34).
    """

    parent_raw_transcript_id: TranscriptId
    candidate_ids: tuple
    decisions: object  # the decision query owning this candidate kind


class CorrectedRevisionSelectionService:
    """Explicit append-only selection of the current corrected revision, with effective resolution."""

    def __init__(
        self,
        intake_query: TranscriptSourceIntakeQuery,
        generation_query: CorrectedRevisionGenerationQuery,
        admission_query: CorrectionCandidateAdmissionQuery,
        decision_query: CorrectionCandidateDecisionQuery,
        raw_selection_query: RawTranscriptSelectionQuery,
        selection_query: CorrectedRevisionSelectionQuery,
        persistence: AtomicCorrectedRevisionSelectionPersistence | None = None,
        timing_generation_query: "TimingCorrectionGenerationQuery | None" = None,
        timing_decision_query: "TimingCorrectionDecisionQuery | None" = None,
    ) -> None:
        self._intakes = intake_query
        self._generations = generation_query
        self._admissions = admission_query
        self._decisions = decision_query
        self._raw_selections = raw_selection_query
        self._selections = selection_query
        self._persistence = persistence
        # Optional so every released construction keeps its exact behaviour; when absent, a timing
        # revision simply has no resolvable lineage, exactly as before this capability existed.
        self._timing_generations = timing_generation_query
        self._timing_decisions = timing_decision_query

    # -- context resolution -------------------------------------------------------------------------

    def _resolve_intake(self, intake_id: str) -> TranscriptSourceIntakeId:
        try:
            identity = require_canonical_intake_id(intake_id)
        except ProviderTranscriptAdmissionError as error:
            raise CorrectedRevisionSelectionError(str(error)) from error
        if self._intakes.get(identity) is None:
            raise CorrectedRevisionSelectionError(
                "unknown transcript source intake: admit the Source Media as an intake first"
            )
        return identity

    def _revision_context(self, revision_id: TranscriptRevisionId):
        """Resolve a revision's generation binding + owning intake (its own authoritative lineage)."""

        generation = self._generations.get_by_revision(revision_id)
        if generation is not None:
            admission = self._admissions.get_by_candidate(generation.correction_candidate_id)
            if admission is None:
                raise CorrectedRevisionSelectionError(
                    "corrected revision lineage is incomplete: its candidate admission is missing"
                )
            return (
                _RevisionLineage(
                    parent_raw_transcript_id=generation.parent_raw_transcript_id,
                    candidate_ids=(generation.correction_candidate_id,),
                    decisions=self._decisions,
                ),
                admission.transcript_source_intake_id,
            )
        timing = self._timing_lineage(revision_id)
        if timing is None:
            raise CorrectedRevisionSelectionError(
                "unknown corrected revision: no generation binding exists for this identity"
            )
        return timing

    def _timing_lineage(self, revision_id: TranscriptRevisionId):
        """The `PATCH-0047` sibling lineage, when this revision came from a timing correction."""

        if self._timing_generations is None or self._timing_decisions is None:
            return None
        generation = self._timing_generations.view_by_revision(revision_id)
        if generation is None:
            return None
        # Every member must resolve; the intake is the one they share (MG-2 guarantees it is one).
        intake_id = None
        for member in generation.members:
            candidate = self._timing_generations.candidate(
                member.timing_correction_candidate_id
            )
            if candidate is None:
                raise CorrectedRevisionSelectionError(
                    "corrected revision lineage is incomplete: its timing candidate is missing"
                )
            if intake_id is None:
                intake_id = candidate.transcript_source_intake_id
            elif candidate.transcript_source_intake_id != intake_id:
                raise CorrectedRevisionSelectionError(
                    "corrected revision lineage is inconsistent: its members span different intakes"
                )
        if intake_id is None:
            raise CorrectedRevisionSelectionError(
                "corrected revision lineage is incomplete: its generation carries no member"
            )
        return (
            _RevisionLineage(
                parent_raw_transcript_id=generation.parent_raw_transcript_id,
                candidate_ids=generation.candidate_ids,
                decisions=self._timing_decisions,
            ),
            intake_id,
        )

    def _lineage_for(self, revision_id: TranscriptRevisionId) -> "_RevisionLineage":
        """The lineage of an already-selected revision (a missing one is repository corruption)."""

        generation = self._generations.get_by_revision(revision_id)
        if generation is not None:
            return _RevisionLineage(
                parent_raw_transcript_id=generation.parent_raw_transcript_id,
                candidate_ids=(generation.correction_candidate_id,),
                decisions=self._decisions,
            )
        timing = self._timing_lineage(revision_id)
        if timing is None:
            raise CorrectedRevisionSelectionError(
                "selected corrected revision has no generation binding (repository integrity failure)"
            )
        return timing[0]

    # -- applicability (shared derivation; never mutates history) ----------------------------------

    def _applicability_of(self, lineage: "_RevisionLineage", intake_id) -> SelectionApplicability:
        current_raw = self._raw_selections.get_current(intake_id)
        if current_raw is None or (
            current_raw.raw_transcript_id != lineage.parent_raw_transcript_id
        ):
            return SelectionApplicability(
                applicable=False, reason="parent_raw_transcript_not_current"
            )
        # Every member must be currently Accepted — one Rejected member makes the whole aggregate
        # inapplicable (MG-33). No Decision-identity agreement condition is added (MG-34).
        for candidate_id in lineage.candidate_ids:
            decision = lineage.decisions.get_current(candidate_id)
            if decision is None or decision.kind is not DecisionKind.ACCEPT:
                return SelectionApplicability(applicable=False, reason="candidate_not_accepted")
        return SelectionApplicability(applicable=True)

    # -- authority commands -------------------------------------------------------------------------

    def select_revision(
        self, *, revision_id: str, reviewer: str, rationale: str | None = None
    ) -> CorrectedRevisionSelectionResult:
        revision_identity = require_canonical_corrected_revision_id(revision_id)
        lineage, intake_identity = self._revision_context(revision_identity)
        if self._intakes.get(intake_identity) is None:
            raise CorrectedRevisionSelectionError(
                "corrected revision lineage references an unknown intake"
            )

        # Eligibility at selection time: new selection must be applicable NOW (no --force).
        applicability = self._applicability_of(lineage, intake_identity)
        if not applicability.applicable:
            raise RevisionNotEligibleError(
                "corrected revision is not currently eligible for selection: "
                + (applicability.reason or "not applicable")
            )
        return self._append(
            intake_identity,
            SelectionKind.CORRECTED_REVISION,
            revision_identity,
            reviewer,
            rationale,
        )

    def select_raw_fallback(
        self, *, intake_id: str, reviewer: str, rationale: str | None = None
    ) -> CorrectedRevisionSelectionResult:
        intake_identity = self._resolve_intake(intake_id)
        return self._append(
            intake_identity, SelectionKind.RAW_FALLBACK, None, reviewer, rationale
        )

    def _append(
        self,
        intake_identity: TranscriptSourceIntakeId,
        kind: SelectionKind,
        revision_identity: TranscriptRevisionId | None,
        reviewer: str,
        rationale: str | None,
    ) -> CorrectedRevisionSelectionResult:
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise CorrectedRevisionSelectionError(
                "reviewer must be a non-empty Human actor reference"
            )
        current = self._selections.get_current(intake_identity)
        if (
            current is not None
            and current.kind is kind
            and current.corrected_revision_id == revision_identity
        ):
            # The requested semantic state is already current — reuse, no new history row.
            return CorrectedRevisionSelectionResult(
                selection=current, outcome=SelectionOutcome.REUSED, previous=None
            )

        sequence = 0 if current is None else current.sequence + 1
        selection = CorrectedRevisionSelection(
            identity=derive_selection_identity(
                intake_identity, kind, revision_identity, sequence
            ),
            transcript_source_intake_id=intake_identity,
            kind=kind,
            reviewer=HumanActorReference(reviewer),
            sequence=sequence,
            corrected_revision_id=revision_identity,
            previous_selection_id=current.identity if current is not None else None,
            rationale=rationale,
        )
        if self._persistence is None:
            raise RuntimeError("corrected revision selection persistence is not configured")
        try:
            self._persistence.persist_selection(selection=selection)
        except PersistenceIdentityCollisionError:
            # A near-concurrent selection advanced the history; converge if it chose our target,
            # otherwise surface the conflict for an explicit retry (never resolved by timestamp).
            resolved = self._selections.get_current(intake_identity)
            if (
                resolved is not None
                and resolved.kind is kind
                and resolved.corrected_revision_id == revision_identity
            ):
                return CorrectedRevisionSelectionResult(
                    selection=resolved, outcome=SelectionOutcome.REUSED, previous=None
                )
            raise
        outcome = SelectionOutcome.RECORDED if current is None else SelectionOutcome.CHANGED
        return CorrectedRevisionSelectionResult(
            selection=selection, outcome=outcome, previous=current
        )

    # -- queries ------------------------------------------------------------------------------------

    def current(self, intake_id: str) -> CorrectedRevisionSelection | None:
        return self._selections.get_current(self._resolve_intake(intake_id))

    def history(self, intake_id: str) -> tuple[CorrectedRevisionSelection, ...]:
        return self._selections.history(self._resolve_intake(intake_id))

    def selection_state(self, intake_id: str) -> SelectionState:
        current = self._selections.get_current(self._resolve_intake(intake_id))
        if current is None:
            return SelectionState.NO_HISTORY
        if current.kind is SelectionKind.RAW_FALLBACK:
            return SelectionState.RAW_FALLBACK
        return SelectionState.CORRECTED_SELECTED

    def applicability(self, intake_id: str) -> SelectionApplicability | None:
        """Applicability of the currently selected revision (None when no corrected revision is selected)."""

        intake_identity = self._resolve_intake(intake_id)
        current = self._selections.get_current(intake_identity)
        if current is None or current.kind is not SelectionKind.CORRECTED_REVISION:
            return None
        return self._applicability_of(
            self._lineage_for(current.corrected_revision_id), intake_identity
        )

    def resolve_effective_transcript(self, intake_id: str) -> EffectiveTranscript:
        intake_identity = self._resolve_intake(intake_id)
        current_raw = self._raw_selections.get_current(intake_identity)
        if current_raw is None:
            raise CorrectedRevisionSelectionError(
                "intake has no current raw transcript selection: select a Raw Transcript first"
            )
        current = self._selections.get_current(intake_identity)
        if current is None or current.kind is SelectionKind.RAW_FALLBACK:
            return EffectiveTranscript(
                transcript_source_intake_id=intake_identity,
                selection_state=(
                    SelectionState.NO_HISTORY if current is None else SelectionState.RAW_FALLBACK
                ),
                effective_kind=EffectiveKind.RAW_TRANSCRIPT,
                raw_transcript_id=current_raw.raw_transcript_id,
                raw_selection_id=current_raw.identity,
                corrected_selection_id=None if current is None else current.identity,
            )
        applicability = self._applicability_of(
            self._lineage_for(current.corrected_revision_id), intake_identity
        )
        if applicability.applicable:
            return EffectiveTranscript(
                transcript_source_intake_id=intake_identity,
                selection_state=SelectionState.CORRECTED_SELECTED,
                effective_kind=EffectiveKind.CORRECTED_REVISION,
                raw_transcript_id=current_raw.raw_transcript_id,
                corrected_revision_id=current.corrected_revision_id,
                raw_selection_id=current_raw.identity,
                corrected_selection_id=current.identity,
            )
        # Never silently fall back: an inapplicable selected revision is an explicit state.
        return EffectiveTranscript(
            transcript_source_intake_id=intake_identity,
            selection_state=SelectionState.CORRECTED_SELECTED,
            effective_kind=EffectiveKind.INAPPLICABLE_SELECTION,
            raw_transcript_id=current_raw.raw_transcript_id,
            corrected_revision_id=current.corrected_revision_id,
            inapplicability_reason=applicability.reason,
            raw_selection_id=current_raw.identity,
            corrected_selection_id=current.identity,
        )


__all__ = [
    "CORRECTED_REVISION_SELECTION_IDENTITY_PREFIX",
    "AtomicCorrectedRevisionSelectionPersistence",
    "CorrectedRevisionSelection",
    "CorrectedRevisionSelectionError",
    "CorrectedRevisionSelectionQuery",
    "CorrectedRevisionSelectionResult",
    "CorrectedRevisionSelectionService",
    "EffectiveKind",
    "EffectiveTranscript",
    "RevisionNotEligibleError",
    "SelectionApplicability",
    "SelectionKind",
    "SelectionOutcome",
    "SelectionState",
    "derive_selection_identity",
    "require_canonical_corrected_revision_id",
]
