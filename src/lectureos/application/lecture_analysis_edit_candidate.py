"""Edit Candidate Foundation — effective-transcript generation (042 §9.3, GOAL-027).

The effective-transcript generation's canonical Edit Candidate contract, implementing the Architect
Decisions confirmed by `patches/PATCH-0032` (C-1…C-13). One explicit command admits one
provider-independent candidate payload against exactly one current-generation Analysis Finding and
appends one **immutable, identity-owning** canonical record.

**Nothing is proposed here.** This boundary generates no candidates and does not invoke AI,
implement a provider, define prompts or models, or create a Review Decision, Approved Edit Decision,
Final Selection, or applied edit. The payload is supplied by the caller and recorded verbatim as
canonical Application-owned meaning.

**Anchor (C-2, C-3).** Every Candidate anchors to exactly one `LectureAnalysisFinding` (`§8.2`) —
never the legacy `AnalysisFinding`, never the `LectureAnalysisInputAdmission` directly, and
**never a Lecture Segment**. `§9.1` already ruled Segment out as anchor and as reference, and
Segmentation (`§7.2`) is a sibling branch: a Candidate is fully valid with no Segment anywhere.

**Provenance through the anchor chain (C-8).** `§9.1`'s mandatory Source Media and Source Timeline
provenance still applies; only its *form* changes. It is secured through
`Edit Candidate → Analysis Finding → Lecture Analysis Input Admission → corrected revision →
parent raw transcript → Source Timeline → Source Media`, so this record duplicates none of it.

**Current-only standing (C-4).** A stored Finding's mere existence never suffices. Every command
re-derives the standing of the admission the anchoring Finding hangs from, and admits only at
`current`. A missing or malformed Finding reference is refused before standing is evaluated — never
a fourth standing value.

**Historical semantics (C-5, C-6).** Existing Candidates are never mutated or deleted when upstream
authority changes; a Candidate legitimately admitted against a then-current chain stays valid
immutable history. No currentness, review, or selection state is stored.

**Execution-free provenance (C-7).** No `ProcessingRun`, `ProcessingUnit`, `UnitExecution`, RUNNING
state, or `DomainResult` is created or required, and none is fabricated. `§9.1` required a
`DomainResultReference` whose sole direct upstream is the anchoring Finding's DomainResult; the
`§8.2` Finding creates no DomainResult, so that requirement is unsatisfiable here and is
legacy-scoped. Provenance is the contract kind (bound into the identity), the recorded contract
version, and the immutable anchor.

**No canonical ordinal (O-1).** `§9.2` fixes candidate order as "deterministic transport order only,
carrying no priority or product meaning", and its duplicate-preservation rule is a provider-slice
concern that C-13 did not re-scope. `§9.3` C-11 leaves the ordered-batch idiom optional. A
single-candidate command has no deterministic Application-owned ordinal source, and inventing one
would require row counts, `MAX(sequence) + 1`, or insertion order — all prohibited. Consequence,
recorded deliberately: two admissions of the *same* canonical proposal under one Finding converge on
one record rather than being preserved as two.

**Identity and replay (C-10, C-11).** Identity derives from the anchor plus every canonical field —
contract kind/version, finding, candidate type, canonical range, and rationale. Because **every
persisted canonical semantic field participates** (Option B), a divergent payload for an existing
identity is structurally unreachable through this command. The semantic-equality guard is kept
regardless because C-10 requires it under Option B and because it is the layer that would still
hold if identity composition ever narrows — not because it is the last line of defence: a tampered
row already fails identity re-derivation in `LectureAnalysisEditCandidate.__post_init__` while
being reconstructed, before the guard is reached.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError

from .canonical_timeline_value import canonical_timeline_value
from .identities import LectureAnalysisEditCandidateId, LectureAnalysisFindingId
from .lecture_analysis_finding import (
    LectureAnalysisFinding,
    LectureAnalysisFindingError,
    LectureAnalysisFindingService,
    require_canonical_finding_id,
)
from .lecture_analysis_input_admission import AdmissionAuthorityMatch

LECTURE_ANALYSIS_EDIT_CANDIDATE_IDENTITY_PREFIX = "lecture-analysis-edit-candidate"

CANDIDATE_CONTRACT_KIND = "lecture_analysis_edit_candidate"
CANDIDATE_CONTRACT_VERSION = 1


class LectureAnalysisEditCandidateError(ValueError):
    """A candidate command that cannot proceed (malformed, unknown, or unsupported input)."""


class EditCandidateAnchorNotAdmissibleError(LectureAnalysisEditCandidateError):
    """The anchoring Finding's admission does not currently bind the current effective authority."""


class EditCandidateConflictError(LectureAnalysisEditCandidateError):
    """An existing candidate with this identity records a divergent payload."""


class EditCandidateOutcome(str, Enum):
    RECORDED = "recorded"  # a new immutable canonical candidate record was created
    REUSED = "reused"      # the identical canonical candidate already exists; no new row


# `§9.1` leaves the exact canonical key grammar to implementation "as long as it follows the
# established canonical Application-key precedent (§8.1's Finding Type)". That precedent is this
# token rule: an OPEN Application-owned vocabulary — not a closed enum, not a fixed taxonomy, and
# emphatically not `§9.2`'s three-key first-slice registry, which is a legacy provider-slice
# constraint that C-13 did not re-scope. No alias mapping, case folding, or whitespace
# normalization is applied: the token is admitted exactly as given or refused.
_CANDIDATE_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def require_canonical_candidate_type(value: str) -> str:
    """Return the value if it is a canonical Candidate Type token; otherwise refuse it."""

    if not isinstance(value, str) or not _CANDIDATE_TYPE_PATTERN.fullmatch(value):
        raise LectureAnalysisEditCandidateError(
            "edit candidate type must be a canonical Application-owned token "
            "(^[a-z][a-z0-9_]*$)"
        )
    return value


def require_rationale(value: str) -> str:
    """Rationale is canonical Candidate meaning, not display text: non-empty, stored verbatim.

    `§9.1` makes it a required canonical, provider-independent, human-reviewable text recording the
    analytical reason for this advisory proposal. It is deliberately NOT normalized (no trimming,
    case folding, or whitespace collapsing) and it participates in identity, so two proposals that
    differ only in their reason are two proposals — never silently one.
    """

    if not isinstance(value, str) or not value.strip():
        raise LectureAnalysisEditCandidateError(
            "edit candidate rationale must not be empty"
        )
    return value


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_bound(name: str, value: float) -> float:
    return canonical_timeline_value(
        value, error=LectureAnalysisEditCandidateError, subject=f"edit candidate {name}"
    )


def normalize_range(start: float, end: float) -> tuple[float, float]:
    """The released §9.1 range contract, reused verbatim: exactly one required range, finite,
    non-negative, ``start <= end``.

    A zero-duration range is structurally valid but carries no special canonical meaning, and a
    whole-recording range is merely a valid range. The range need not equal the anchoring Finding's
    optional range and is required even when the Finding has none. No media-duration validation,
    transcript-boundary alignment, Candidate-to-Finding containment check, or range reconciliation
    is applied: `§9.3` C-9 forbids adding any of them here.
    """

    canonical_start = _canonical_bound("range start", start)
    canonical_end = _canonical_bound("range end", end)
    if canonical_start > canonical_end:
        raise LectureAnalysisEditCandidateError(
            "edit candidate range start must not be after end"
        )
    return canonical_start, canonical_end


def derive_candidate_identity(
    finding_id: LectureAnalysisFindingId,
    candidate_type: str,
    range_start: float,
    range_end: float,
    rationale: str,
) -> LectureAnalysisEditCandidateId:
    """Deterministic, Application-owned candidate identity (042 §9.3 C-10).

    Derives from the exact immutable anchor plus **every** canonical field: contract kind and
    version, the Finding, the Candidate Type, the canonical range, and the rationale. No timestamp,
    randomness, rowid, path, provider identifier, DomainResult, or mutable currentness participates,
    and no ordinal exists to participate (O-1).
    """

    canonical_start, canonical_end = normalize_range(range_start, range_end)
    digest = hashlib.sha256(
        _canonical_json(
            {
                "contract": CANDIDATE_CONTRACT_KIND,
                "contract_version": CANDIDATE_CONTRACT_VERSION,
                "finding": finding_id.value,
                "candidate_type": candidate_type,
                "range_start": canonical_start,
                "range_end": canonical_end,
                "rationale": rationale,
            }
        ).encode("utf-8")
    ).hexdigest()
    return LectureAnalysisEditCandidateId(
        f"{LECTURE_ANALYSIS_EDIT_CANDIDATE_IDENTITY_PREFIX}:{digest}"
    )


def require_canonical_candidate_id(value: str) -> LectureAnalysisEditCandidateId:
    prefix = LECTURE_ANALYSIS_EDIT_CANDIDATE_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise LectureAnalysisEditCandidateError(
            "lecture analysis edit candidate identity is malformed "
            "(expected 'lecture-analysis-edit-candidate:<64 hex digest>')"
        )
    return LectureAnalysisEditCandidateId(value)


def _require_anchor_identity(value: str) -> LectureAnalysisFindingId:
    """Validate the anchor reference, reporting it as an *edit candidate* refusal.

    The released Finding-identity rule is reused verbatim, but its error is re-raised in this
    boundary's own type: a malformed anchor is a refusal of the reference supplied to this command
    (042 §9.3 C-4), never a fourth admission standing value.
    """

    try:
        return require_canonical_finding_id(value)
    except LectureAnalysisFindingError as error:
        raise LectureAnalysisEditCandidateError(str(error)) from error


@dataclass(frozen=True, slots=True)
class LectureAnalysisEditCandidate:
    """Immutable canonical Edit Candidate anchored to one current-generation Analysis Finding.

    Carries no currentness, review, or selection state (042 §9.3 C-5), no ordinal (O-1), no
    execution or DomainResult provenance (C-7), and no duplicated upstream provenance (C-8) — the
    anchor chain supplies it.
    """

    identity: LectureAnalysisEditCandidateId
    finding_id: LectureAnalysisFindingId
    candidate_type: str
    range_start: float
    range_end: float
    rationale: str
    candidate_contract_version: int = CANDIDATE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.candidate_contract_version != CANDIDATE_CONTRACT_VERSION:
            raise LectureAnalysisEditCandidateError(
                "unsupported edit candidate contract version"
            )
        require_canonical_candidate_type(self.candidate_type)
        require_rationale(self.rationale)
        start, end = normalize_range(self.range_start, self.range_end)
        object.__setattr__(self, "range_start", start)
        object.__setattr__(self, "range_end", end)
        if self.identity != derive_candidate_identity(
            self.finding_id, self.candidate_type, start, end, self.rationale
        ):
            raise LectureAnalysisEditCandidateError(
                "edit candidate identity must derive from its anchoring finding, candidate type, "
                "canonical range, and rationale"
            )


@dataclass(frozen=True, slots=True)
class EditCandidateResult:
    """One candidate command outcome: the immutable record, the outcome, and the anchor observed."""

    candidate: LectureAnalysisEditCandidate
    outcome: EditCandidateOutcome
    finding: LectureAnalysisFinding


class EditCandidateQuery(Protocol):
    def get(self, identity): ...

    def list_for_finding(self, finding_id) -> tuple: ...


class AtomicEditCandidatePersistence(Protocol):
    def persist_candidate(
        self, *, candidate: LectureAnalysisEditCandidate
    ) -> None: ...


class LectureAnalysisEditCandidateService:
    """The single canonical Edit Candidate admission path of the effective generation."""

    def __init__(
        self,
        finding_service: LectureAnalysisFindingService,
        candidate_query: EditCandidateQuery,
        persistence: AtomicEditCandidatePersistence,
    ) -> None:
        self._findings = finding_service
        self._candidates = candidate_query
        self._persistence = persistence

    # -- explicit candidate admission command ---------------------------------------------------

    def admit_edit_candidate(
        self,
        *,
        finding_id: str,
        candidate_type: str,
        range_start: float,
        range_end: float,
        rationale: str,
    ) -> EditCandidateResult:
        """Admit one provider-independent candidate against a Finding whose chain is CURRENT.

        Order (042 §9.3): validate the payload, resolve the canonical Finding, re-derive the
        standing of the admission it hangs from, derive identity, then persist atomically and
        converge on replay.
        """

        # Payload first: a malformed command never reaches the anchor or the repository.
        require_canonical_candidate_type(candidate_type)
        rationale = require_rationale(rationale)
        range_start, range_end = normalize_range(range_start, range_end)

        finding = self._require_current_chain(finding_id)

        candidate = LectureAnalysisEditCandidate(
            identity=derive_candidate_identity(
                finding.identity, candidate_type, range_start, range_end, rationale
            ),
            finding_id=finding.identity,
            candidate_type=candidate_type,
            range_start=range_start,
            range_end=range_end,
            rationale=rationale,
        )

        existing = self._candidates.get(candidate.identity)
        if existing is not None:
            return self._reuse(existing, candidate, finding)
        try:
            self._persistence.persist_candidate(candidate=candidate)
        except PersistenceIdentityCollisionError:
            # A near-concurrent identical command won the insert; converge on its record.
            resolved = self._candidates.get(candidate.identity)
            if resolved is not None:
                return self._reuse(resolved, candidate, finding)
            raise
        return EditCandidateResult(
            candidate=candidate,
            outcome=EditCandidateOutcome.RECORDED,
            finding=finding,
        )

    def _require_current_chain(self, finding_id: str) -> LectureAnalysisFinding:
        """Resolve the anchor Finding and re-derive its admission's standing (042 §9.3 C-4).

        The standing lives at the **root** of the chain — Candidate → Finding → Admission — and is
        obtained through the released GOAL-025/GOAL-023 path, never by re-resolving authority here.
        A missing or malformed reference is refused *before* standing is evaluated.
        """

        identity = _require_anchor_identity(finding_id)
        finding = self._findings.get(identity.value)
        if finding is None:
            raise LectureAnalysisEditCandidateError("unknown lecture analysis finding")
        try:
            match = self._findings.anchor_status(finding)
        except LectureAnalysisFindingError as error:
            # The Finding's own anchor is missing — a repository integrity failure, reported in
            # this boundary's error family rather than leaking the sibling's type.
            raise LectureAnalysisEditCandidateError(str(error)) from error
        if match is not AdmissionAuthorityMatch.CURRENT:
            raise EditCandidateAnchorNotAdmissibleError(
                "edit candidates may only be admitted against a finding whose analysis input "
                f"admission still binds the current effective authority (derived standing: "
                f"{match.value}); the finding and its existing candidates remain valid immutable "
                "history"
            )
        return finding

    @staticmethod
    def _reuse(
        existing: LectureAnalysisEditCandidate,
        expected: LectureAnalysisEditCandidate,
        finding: LectureAnalysisFinding,
    ) -> EditCandidateResult:
        """Converge on an identical canonical candidate; refuse a divergent payload (C-11).

        Every persisted canonical field participates in identity (Option B), so a legitimate
        divergence is structurally unreachable through this command, and a tampered row already
        fails identity re-derivation while being reconstructed — so this is not the last line of
        defence. It is kept because C-10 requires it under Option B, and because it is the check
        that would still hold if a later contract narrowed what participates in identity. Reaching
        it requires bypassing reconstruction, which is why its test injects a query stub.
        """

        if (
            existing.finding_id != expected.finding_id
            or existing.candidate_type != expected.candidate_type
            or existing.range_start != expected.range_start
            or existing.range_end != expected.range_end
            or existing.rationale != expected.rationale
            or existing.candidate_contract_version != expected.candidate_contract_version
        ):
            raise EditCandidateConflictError(
                "an existing edit candidate with this identity records a different payload "
                "(repository integrity failure); it is never overwritten"
            )
        return EditCandidateResult(
            candidate=existing, outcome=EditCandidateOutcome.REUSED, finding=finding
        )

    # -- queries (derived; never mutate history) ------------------------------------------------

    def get(self, candidate_id: str) -> LectureAnalysisEditCandidate | None:
        return self._candidates.get(require_canonical_candidate_id(candidate_id))

    def list_for_finding(
        self, finding_id: str
    ) -> tuple[LectureAnalysisEditCandidate, ...]:
        return self._candidates.list_for_finding(_require_anchor_identity(finding_id))

    def anchor_status(
        self, candidate: LectureAnalysisEditCandidate
    ) -> AdmissionAuthorityMatch:
        """Derived only: does this candidate's chain still bind the current authority?

        A candidate whose chain became superseded is NOT stale data and NOT corruption — it is valid
        immutable history (042 §9.3 C-6). Nothing is mutated by this observation, and no such state
        is ever stored on the candidate (C-5).
        """

        finding = self._findings.get(candidate.finding_id.value)
        if finding is None:
            raise LectureAnalysisEditCandidateError(
                "edit candidate anchor finding is missing (repository integrity failure)"
            )
        try:
            return self._findings.anchor_status(finding)
        except LectureAnalysisFindingError as error:
            raise LectureAnalysisEditCandidateError(str(error)) from error


__all__ = [
    "CANDIDATE_CONTRACT_KIND",
    "CANDIDATE_CONTRACT_VERSION",
    "LECTURE_ANALYSIS_EDIT_CANDIDATE_IDENTITY_PREFIX",
    "AtomicEditCandidatePersistence",
    "EditCandidateAnchorNotAdmissibleError",
    "EditCandidateConflictError",
    "EditCandidateOutcome",
    "EditCandidateQuery",
    "EditCandidateResult",
    "LectureAnalysisEditCandidate",
    "LectureAnalysisEditCandidateError",
    "LectureAnalysisEditCandidateService",
    "derive_candidate_identity",
    "normalize_range",
    "require_canonical_candidate_id",
    "require_canonical_candidate_type",
    "require_rationale",
]
