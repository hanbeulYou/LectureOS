"""Final Subtitle Selection Authority for effective-source candidates (GOAL-016).

The explicit selection boundary of the effective-transcript subtitle contract generation: which
exact reviewed candidate is currently the final subtitle for one intake scope. It combines the two
released idioms truthfully — the GOAL-011 append-only selection authority (per-scope ``sequence`` +
``previous_selection_id``; current = highest sequence, derived, never a flag or latest-row
heuristic) and the GOAL-015 Human Authority lineage (explicit `HumanActorReference`,
fingerprint-verified provenance, converge-on-collision).

**Accept ≠ Final Selection.** A new selection requires derived eligibility NOW: the review
subject's current decision must exist, be `accept`, and be applicable (which, per GOAL-015,
requires the subject and candidate source to be current) — reject/modify/superseded-accept/stale
subjects are never eligible for a *new* selection, while existing historical selections remain
immutable valid history whose applicability is derived. The exact supporting Accept decision
observed at command time is persisted — never inferred later from mutable history. Selection
mutates nothing upstream and grants nothing downstream: **Final Selection ≠ export eligibility**;
export is a later goal, and the legacy final-selection pipeline is a separate contract generation,
never read or written. No wall-clock, randomness, or workflow state participates.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.review.identities import HumanActorReference
from lectureos.review.models import DecisionKind

from .effective_subtitle_review_decision import (
    DecisionApplicability,
    EffectiveSubtitleReviewDecision,
    EffectiveSubtitleReviewDecisionService,
)
from .effective_subtitle_review_preparation import (
    EffectiveSubtitleReviewPreparationService,
    require_canonical_review_subject_id,
)
from .effective_transcript_consumption import ConsumptionCurrentness
from .readable_cue_composition import (
    UnknownReadabilityContractError,
    is_readable_candidate,
    readability_contract_for,
)
from .readable_subtitle_validation import evaluate_readable_cues
from .identities import (
    EffectiveSubtitleCandidateId,
    EffectiveSubtitleFinalSelectionId,
    EffectiveSubtitleReviewDecisionId,
    EffectiveSubtitleReviewSubjectId,
    TranscriptSourceIntakeId,
)
from .provider_transcript_admission import (
    ProviderTranscriptAdmissionError,
    require_canonical_intake_id,
)

EFFECTIVE_FINAL_SELECTION_IDENTITY_PREFIX = "subtitle-effective-final-selection"

SELECTION_CONTRACT_KIND = "effective_subtitle_final_selection"
SELECTION_CONTRACT_VERSION = 1


class EffectiveSubtitleFinalSelectionError(ValueError):
    """A selection request that cannot proceed (malformed, unknown, or unsupported input)."""


class ReviewSubjectNotEligibleError(EffectiveSubtitleFinalSelectionError):
    """The review subject is not eligible for a new final selection under current authority."""


class FinalSelectionConflictError(EffectiveSubtitleFinalSelectionError):
    """The deterministic selection slot maps to a structurally different persisted payload."""


class SelectionOutcome(str, Enum):
    RECORDED = "recorded"   # first selection authority for the scope (sequence 0)
    REUSED = "reused"       # the current selection already binds this exact authority state
    CHANGED = "changed"     # a new selection superseding the prior authority


class EligibilityBlockingReason(str, Enum):
    NO_DECISION = "no_decision"
    DECISION_NOT_ACCEPT = "decision_not_accept"
    DECISION_NOT_APPLICABLE = "decision_not_applicable"
    # 041 §16 EN-1/EN-4 (PATCH-0042): a readable candidate carrying any blocking readability
    # finding must not become the Final Subtitle. Extends the released eligibility idiom rather
    # than introducing a second gate, a new lifecycle, or a new aggregate.
    READABILITY_BLOCKING = "readability_blocking"
    READABILITY_CONTRACT_UNKNOWN = "readability_contract_unknown"


class SelectionApplicability(str, Enum):
    """Derived, never stored. Separate from current-selection status and from integrity."""

    APPLICABLE = "applicable"
    SUPERSEDED = "superseded"
    SUPPORTING_DECISION_SUPERSEDED = "supporting_decision_superseded"
    STALE_DUE_TO_CANDIDATE_SOURCE = "stale_due_to_candidate_source"
    UNRESOLVABLE = "unresolvable"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_final_selection_identity(
    intake_id: TranscriptSourceIntakeId,
    candidate_id: EffectiveSubtitleCandidateId,
    review_subject_id: EffectiveSubtitleReviewSubjectId,
    supporting_decision_id: EffectiveSubtitleReviewDecisionId,
    sequence: int,
) -> EffectiveSubtitleFinalSelectionId:
    """Deterministic selection identity — the GOAL-011 idiom over the full authority target.

    Candidate-, review-subject-, supporting-decision-, and sequence-sensitive; the selector and
    rationale are provenance, verified through the content fingerprint, never identity.
    """

    digest = _sha256(
        _canonical_json(
            {
                "contract_kind": SELECTION_CONTRACT_KIND,
                "contract_version": SELECTION_CONTRACT_VERSION,
                "intake": intake_id.value,
                "candidate": candidate_id.value,
                "review_subject": review_subject_id.value,
                "supporting_decision": supporting_decision_id.value,
                "sequence": sequence,
            }
        )
    )
    return EffectiveSubtitleFinalSelectionId(
        f"{EFFECTIVE_FINAL_SELECTION_IDENTITY_PREFIX}:{digest}"
    )


def _content_fingerprint(
    intake_id: TranscriptSourceIntakeId,
    candidate_id: EffectiveSubtitleCandidateId,
    review_subject_id: EffectiveSubtitleReviewSubjectId,
    supporting_decision_id: EffectiveSubtitleReviewDecisionId,
    sequence: int,
    selector: HumanActorReference,
    rationale: str | None,
) -> str:
    return _sha256(
        _canonical_json(
            {
                "intake": intake_id.value,
                "candidate": candidate_id.value,
                "review_subject": review_subject_id.value,
                "supporting_decision": supporting_decision_id.value,
                "sequence": sequence,
                "selector": selector.value,
                "rationale": rationale,
            }
        )
    )


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleFinalSelection:
    """Immutable Human Authority fact: one exact reviewed candidate explicitly selected as final."""

    identity: EffectiveSubtitleFinalSelectionId
    transcript_source_intake_id: TranscriptSourceIntakeId
    candidate_id: EffectiveSubtitleCandidateId
    review_subject_id: EffectiveSubtitleReviewSubjectId
    supporting_decision_id: EffectiveSubtitleReviewDecisionId
    selector: HumanActorReference
    sequence: int
    content_fingerprint: str
    previous_selection_id: EffectiveSubtitleFinalSelectionId | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not self.selector.value.strip():
            raise ValueError("final selection selector must be a non-empty Human actor reference")
        if self.sequence < 0:
            raise ValueError("final selection sequence must not be negative")
        if (self.sequence == 0) != (self.previous_selection_id is None):
            raise ValueError(
                "the first selection (sequence 0) has no previous; later selections require one"
            )
        if self.previous_selection_id == self.identity:
            raise ValueError("a final selection cannot supersede itself")
        if self.rationale is not None and not self.rationale.strip():
            raise ValueError("final selection rationale, when present, must not be blank")
        if self.identity != derive_final_selection_identity(
            self.transcript_source_intake_id,
            self.candidate_id,
            self.review_subject_id,
            self.supporting_decision_id,
            self.sequence,
        ):
            raise ValueError(
                "final selection identity must derive from its scope, candidate, subject, "
                "supporting decision, and sequence"
            )
        if self.content_fingerprint != _content_fingerprint(
            self.transcript_source_intake_id,
            self.candidate_id,
            self.review_subject_id,
            self.supporting_decision_id,
            self.sequence,
            self.selector,
            self.rationale,
        ):
            raise ValueError(
                "final selection content fingerprint must match its immutable payload"
            )


@dataclass(frozen=True, slots=True)
class SelectionEligibility:
    """Derived, never persisted: may this review subject receive a NEW final selection now?"""

    eligible: bool
    review_subject_id: EffectiveSubtitleReviewSubjectId
    candidate_id: EffectiveSubtitleCandidateId
    current_decision_id: EffectiveSubtitleReviewDecisionId | None
    current_decision_kind: DecisionKind | None
    decision_applicability: DecisionApplicability | None
    candidate_source_currentness: ConsumptionCurrentness
    review_subject_currentness: object
    blocking_reason: EligibilityBlockingReason | None
    # Populated only when `blocking_reason` is READABILITY_BLOCKING, so the refusal names what
    # must change instead of stating that something did (041 §16 EN-4/EN-5).
    readability_findings: tuple = ()
    readability_parameters_version: int | None = None


@dataclass(frozen=True, slots=True)
class FinalSelectionResult:
    """One selection command outcome: the authority record, the outcome, and the superseded record."""

    selection: EffectiveSubtitleFinalSelection
    outcome: SelectionOutcome
    previous: EffectiveSubtitleFinalSelection | None


class FinalSelectionQuery(Protocol):
    def get(self, identity): ...

    def get_current(self, intake_id): ...

    def history(self, intake_id) -> tuple: ...


class AtomicFinalSelectionPersistence(Protocol):
    def persist_selection(self, *, selection: EffectiveSubtitleFinalSelection) -> None: ...


class EffectiveSubtitleFinalSelectionService:
    """The single canonical final-selection path of the effective-source generation (GOAL-016)."""

    def __init__(
        self,
        preparation_service: EffectiveSubtitleReviewPreparationService,
        decision_service: EffectiveSubtitleReviewDecisionService,
        selection_query: FinalSelectionQuery,
        persistence: AtomicFinalSelectionPersistence | None = None,
    ) -> None:
        self._subjects = preparation_service
        self._decisions = decision_service
        self._selections = selection_query
        self._persistence = persistence

    # -- derived eligibility (never persisted) --------------------------------------------------------

    def eligibility(self, review_subject_id: str) -> SelectionEligibility:
        subject, candidate = self._resolve_subject(review_subject_id)
        status = self._subjects.status(subject)
        current = self._decisions.current(subject.identity.value)
        if current is None:
            return SelectionEligibility(
                eligible=False,
                review_subject_id=subject.identity,
                candidate_id=subject.candidate_id,
                current_decision_id=None,
                current_decision_kind=None,
                decision_applicability=None,
                candidate_source_currentness=status.candidate_source_currentness,
                review_subject_currentness=status.review_subject_currentness,
                blocking_reason=EligibilityBlockingReason.NO_DECISION,
            )
        applicability = self._decisions.applicability(current)
        blocking = None
        findings: tuple = ()
        parameters_version: int | None = None
        if current.kind is not DecisionKind.ACCEPT:
            blocking = EligibilityBlockingReason.DECISION_NOT_ACCEPT
        elif applicability is not DecisionApplicability.APPLICABLE:
            # Conservative policy: a NEW selection requires a current, applicable Accept — a
            # stale or unresolvable subject blocks new selection (existing selections stay valid).
            blocking = EligibilityBlockingReason.DECISION_NOT_APPLICABLE
        else:
            # 041 §16 EN-4: Final Selection is the ONE readability enforcement boundary. An Accept
            # exists and applies; what remains is whether the proposal is structurally deliverable.
            blocking, findings, parameters_version = self._readability_gate(subject, candidate)
        return SelectionEligibility(
            eligible=blocking is None,
            review_subject_id=subject.identity,
            candidate_id=subject.candidate_id,
            current_decision_id=current.identity,
            current_decision_kind=current.kind,
            decision_applicability=applicability,
            candidate_source_currentness=status.candidate_source_currentness,
            review_subject_currentness=status.review_subject_currentness,
            blocking_reason=blocking,
            readability_findings=findings,
            readability_parameters_version=parameters_version,
        )

    def _readability_gate(self, subject, candidate):
        """Re-derive readability under the candidate's OWN versioned contract (041 §16 EN-4).

        Returns ``(blocking_reason_or_None, findings, parameters_version)``. Passthrough candidates
        are out of scope entirely (EN-9): they were never composed under the readability policy, so
        evaluating them against it would judge them by a contract they never claimed.
        """

        if not is_readable_candidate(candidate):
            return None, (), None
        try:
            parameters = readability_contract_for(candidate)
        except UnknownReadabilityContractError:
            # Never fall back to the newest known set: that would evaluate a released candidate
            # under a policy it was not composed under. Refusing is the safe, explicit outcome.
            return EligibilityBlockingReason.READABILITY_CONTRACT_UNKNOWN, (), None
        cues = self._subjects.cues_of(subject)
        validation = evaluate_readable_cues(cues, parameters=parameters)
        if validation.blocking:
            return (
                EligibilityBlockingReason.READABILITY_BLOCKING,
                validation.blocking,
                validation.parameters_version,
            )
        return None, (), validation.parameters_version

    # -- authority command ---------------------------------------------------------------------------

    def select_final(
        self,
        *,
        review_subject_id: str,
        selector: str,
        rationale: str | None = None,
    ) -> FinalSelectionResult:
        if not isinstance(selector, str) or not selector.strip():
            raise EffectiveSubtitleFinalSelectionError(
                "selector must be a non-empty Human actor reference"
            )
        actor = HumanActorReference(selector)
        report = self.eligibility(review_subject_id)
        if not report.eligible:
            detail = ""
            if report.readability_findings:
                # 041 §16 EN-4/EN-5: the refusal names what must change. A count alone would make
                # the outcome unactionable, which is the difference between a recoverable admission
                # result and an opaque failure.
                enumerated = "; ".join(
                    f"{finding.code}"
                    + ("" if finding.cue_ordinal is None else f" (cue #{finding.cue_ordinal})")
                    + f": {finding.detail}"
                    for finding in report.readability_findings
                )
                detail = (
                    f" ({len(report.readability_findings)} blocking readability finding(s) under "
                    f"parameters v{report.readability_parameters_version}) [{enumerated}]"
                )
            elif report.decision_applicability is not None:
                detail = f" (decision applicability: {report.decision_applicability.value})"
            raise ReviewSubjectNotEligibleError(
                "review subject is not eligible for a new final selection: "
                f"{report.blocking_reason.value}{detail}"
            )
        subject, candidate = self._resolve_subject(review_subject_id)
        intake = candidate.transcript_source_intake_id
        supporting = report.current_decision_id

        current = self._selections.get_current(intake)
        if (
            current is not None
            and current.candidate_id == subject.candidate_id
            and current.review_subject_id == subject.identity
            and current.supporting_decision_id == supporting
        ):
            # The current authority already binds this exact target and supporting lineage —
            # reuse idempotently (the GOAL-011 target-match rule). A changed supporting Accept
            # deliberately does NOT match: new authority lineage appends a new selection.
            return FinalSelectionResult(
                selection=current, outcome=SelectionOutcome.REUSED, previous=None
            )

        sequence = 0 if current is None else current.sequence + 1
        previous_id = current.identity if current is not None else None
        identity = derive_final_selection_identity(
            intake, subject.candidate_id, subject.identity, supporting, sequence
        )
        fingerprint = _content_fingerprint(
            intake, subject.candidate_id, subject.identity, supporting, sequence,
            actor, rationale,
        )
        selection = EffectiveSubtitleFinalSelection(
            identity=identity,
            transcript_source_intake_id=intake,
            candidate_id=subject.candidate_id,
            review_subject_id=subject.identity,
            supporting_decision_id=supporting,
            selector=actor,
            sequence=sequence,
            content_fingerprint=fingerprint,
            previous_selection_id=previous_id,
            rationale=rationale,
        )
        if self._persistence is None:
            raise RuntimeError(
                "effective subtitle final selection persistence is not configured"
            )
        try:
            self._persistence.persist_selection(selection=selection)
        except PersistenceIdentityCollisionError:
            # A near-concurrent command advanced the history. Converge only when the resolved
            # current binds our exact target with an equal payload; a competing DIFFERENT
            # selection surfaces the conflict explicitly — an explicit Human command is never
            # silently discarded (the caller re-evaluates and reissues).
            resolved = self._selections.get_current(intake)
            if (
                resolved is not None
                and resolved.candidate_id == subject.candidate_id
                and resolved.review_subject_id == subject.identity
                and resolved.supporting_decision_id == supporting
                and resolved.content_fingerprint
                == _content_fingerprint(
                    intake, subject.candidate_id, subject.identity, supporting,
                    resolved.sequence, actor, rationale,
                )
            ):
                return FinalSelectionResult(
                    selection=resolved, outcome=SelectionOutcome.REUSED, previous=None
                )
            raise FinalSelectionConflictError(
                "a competing final selection was recorded concurrently; re-evaluate "
                "eligibility and reissue the explicit selection command"
            )
        outcome = SelectionOutcome.RECORDED if current is None else SelectionOutcome.CHANGED
        return FinalSelectionResult(
            selection=selection, outcome=outcome, previous=current
        )

    def _resolve_subject(self, review_subject_id: str):
        try:
            subject = self._subjects.get(review_subject_id)
        except ValueError as error:
            raise EffectiveSubtitleFinalSelectionError(str(error)) from error
        if subject is None:
            raise EffectiveSubtitleFinalSelectionError(
                "unknown effective subtitle review subject: a final selection requires one "
                "exact existing review subject identity"
            )
        candidate = self._subjects.candidate_of(subject)
        return subject, candidate

    # -- queries (derived; never mutate history) ------------------------------------------------------

    def get(self, selection_id: str) -> EffectiveSubtitleFinalSelection | None:
        return self._selections.get(require_canonical_final_selection_id(selection_id))

    def current(self, intake_id: str) -> EffectiveSubtitleFinalSelection | None:
        return self._selections.get_current(self._resolve_intake(intake_id))

    def history(self, intake_id: str) -> tuple[EffectiveSubtitleFinalSelection, ...]:
        return self._selections.history(self._resolve_intake(intake_id))

    def applicability(
        self, selection: EffectiveSubtitleFinalSelection
    ) -> SelectionApplicability:
        """Derived only. Evaluation order: superseded → supporting decision lineage → staleness."""

        current = self._selections.get_current(selection.transcript_source_intake_id)
        if current is None or current.identity != selection.identity:
            return SelectionApplicability.SUPERSEDED
        supporting = self._decisions.get(selection.supporting_decision_id.value)
        if supporting is None:
            raise EffectiveSubtitleFinalSelectionError(
                "final selection references an unknown supporting decision "
                "(repository integrity failure)"
            )
        decision_applicability = self._decisions.applicability(supporting)
        if decision_applicability is DecisionApplicability.SUPERSEDED:
            return SelectionApplicability.SUPPORTING_DECISION_SUPERSEDED
        if decision_applicability is DecisionApplicability.STALE_DUE_TO_CANDIDATE_SOURCE:
            return SelectionApplicability.STALE_DUE_TO_CANDIDATE_SOURCE
        if decision_applicability is DecisionApplicability.UNRESOLVABLE:
            return SelectionApplicability.UNRESOLVABLE
        return SelectionApplicability.APPLICABLE

    def supporting_decision_applicability(
        self, selection: EffectiveSubtitleFinalSelection
    ) -> DecisionApplicability:
        """Derived applicability of the exact persisted supporting decision."""

        return self._decisions.applicability(self.supporting_decision(selection))

    def supporting_decision(
        self, selection: EffectiveSubtitleFinalSelection
    ) -> EffectiveSubtitleReviewDecision:
        supporting = self._decisions.get(selection.supporting_decision_id.value)
        if supporting is None:
            raise EffectiveSubtitleFinalSelectionError(
                "final selection references an unknown supporting decision "
                "(repository integrity failure)"
            )
        return supporting

    def _resolve_intake(self, intake_id: str) -> TranscriptSourceIntakeId:
        try:
            return require_canonical_intake_id(intake_id)
        except ProviderTranscriptAdmissionError as error:
            raise EffectiveSubtitleFinalSelectionError(str(error)) from error


def require_canonical_final_selection_id(value: str) -> EffectiveSubtitleFinalSelectionId:
    prefix = EFFECTIVE_FINAL_SELECTION_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise EffectiveSubtitleFinalSelectionError(
            "effective subtitle final selection identity is malformed "
            "(expected 'subtitle-effective-final-selection:<64 hex digest>')"
        )
    return EffectiveSubtitleFinalSelectionId(value)


__all__ = [
    "EFFECTIVE_FINAL_SELECTION_IDENTITY_PREFIX",
    "SELECTION_CONTRACT_KIND",
    "SELECTION_CONTRACT_VERSION",
    "AtomicFinalSelectionPersistence",
    "EffectiveSubtitleFinalSelection",
    "EffectiveSubtitleFinalSelectionError",
    "EffectiveSubtitleFinalSelectionService",
    "EligibilityBlockingReason",
    "FinalSelectionConflictError",
    "FinalSelectionResult",
    "ReviewSubjectNotEligibleError",
    "SelectionApplicability",
    "SelectionEligibility",
    "SelectionOutcome",
    "derive_final_selection_identity",
    "require_canonical_final_selection_id",
]
