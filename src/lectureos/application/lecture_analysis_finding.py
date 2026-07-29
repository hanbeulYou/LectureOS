"""Analysis Finding Application Foundation — effective-transcript generation (042 §8.2, GOAL-025).

The effective-transcript generation's canonical Analysis Finding contract, implementing the
Architect Decisions confirmed by `patches/PATCH-0030` (D-1…D-12). One explicit command admits one
provider-independent finding payload against exactly one immutable Lecture Analysis Input
Admission (GOAL-023) and appends one **immutable, identity-owning, provenance-bearing** canonical
record.

**No analysis happens here.** This boundary performs no analysis and does not invoke AI, implement
a provider, define prompts or models, or create a Lecture Segment, Segment Label, Edit Candidate,
or Review Item. The payload it admits is an internal Application contract, never a provider API:
it carries no provider identifier, model, prompt, token usage, transport metadata, raw provider
JSON, or internal reasoning.

**Anchor (D-2).** Every Finding anchors to exactly one `LectureAnalysisInputAdmission`, never to
the legacy `EligibleAnalysisInput`. Upstream provenance — intake, source media, corrected
revision, parent raw transcript, both observed selections, the released §19 content fingerprint —
is obtained *through* that anchor and deliberately not duplicated onto the Finding.

**Current-only standing (D-3).** A stored admission's mere existence never suffices: every command
re-derives the anchor's authority standing and admits only at `current`. A missing or malformed
admission reference is refused before standing is evaluated — it is never a fourth standing value.

**Historical semantics (D-5, D-10).** Existing Findings are never mutated or deleted when upstream
authority changes; a Finding legitimately anchored to a then-current admission stays valid
immutable history. No `current`/`stale`/`active`/`ready`/`superseded` state is stored on a Finding;
present applicability is derived externally from the anchor's standing.

**Execution-free deterministic provenance (D-6).** No `ProcessingRun`, `ProcessingUnit`,
`UnitExecution`, or RUNNING state is created or required, and none is fabricated. Following the
GOAL-023 marker-free precedent, generation provenance is the contract kind (cryptographically bound
into the identity), the recorded contract version, and the immutable admitted source (the anchor).

**Identity and replay (D-8, D-9).** Identity is Application-owned and derives from the exact
immutable anchor plus the stable canonical finding content — contract kind/version, admission
identity, finding type, evidence, and the optional single source range. Confidence and uncertainty
are *recorded facts, not identity* (the released GOAL-023 rule that authority provenance and the
content fingerprint are recorded, never identity). Re-admitting the same canonical finding
converges idempotently (REUSED, no new row); a divergent payload on an existing identity is an
explicit conflict, never an overwrite. No wall-clock, randomness, path, or rowid participates.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError

from .identities import LectureAnalysisFindingId, LectureAnalysisInputAdmissionId
from .lecture_analysis_input_admission import (
    AdmissionAuthorityMatch,
    LectureAnalysisInputAdmission,
    LectureAnalysisInputAdmissionError,
    LectureAnalysisInputAdmissionService,
    require_canonical_admission_id,
)

LECTURE_ANALYSIS_FINDING_IDENTITY_PREFIX = "lecture-analysis-finding"

FINDING_CONTRACT_KIND = "lecture_analysis_finding"
FINDING_CONTRACT_VERSION = 1

class LectureAnalysisFindingError(ValueError):
    """A finding command that cannot proceed (malformed, unknown, or unsupported input)."""


class AnalysisFindingAnchorNotAdmissibleError(LectureAnalysisFindingError):
    """The anchoring admission does not currently bind the current effective authority."""


class AnalysisFindingConflictError(LectureAnalysisFindingError):
    """An existing finding with this identity records a divergent payload."""


# The released canonical Finding Type token rule (042 §8.1, PATCH-0010), restated here rather than
# imported from the legacy module so this generation declares no source-level dependency on the
# execution-coupled one (PATCH-0030 D-1 keeps the two generations separate). This is a source
# boundary only — it does not shrink the import graph, since `persistence.errors` already loads
# the legacy modules transitively. The copies are kept honest by
# `test_canonical_finding_type_rule_agrees_across_layers`.
#
# The rule is an OPEN Application-owned vocabulary — deliberately not a closed enum, not a fixed
# taxonomy, and never derived from LI-001…LI-012 — but constrained in representation so a raw
# provider classification (free text, punctuation, scores, casing) can never be preserved as a
# canonical Finding Type. No alias mapping, case folding, or whitespace normalization is applied:
# the token is admitted exactly as given or refused.
_FINDING_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def require_canonical_finding_type(value: str) -> str:
    """Return the value if it is a canonical Finding Type token; otherwise refuse it."""

    if not isinstance(value, str) or not _FINDING_TYPE_PATTERN.fullmatch(value):
        raise LectureAnalysisFindingError(
            "analysis finding type must be a canonical Application-owned token "
            "(^[a-z][a-z0-9_]*$)"
        )
    return value


class FindingOutcome(str, Enum):
    RECORDED = "recorded"  # a new immutable canonical finding record was created
    REUSED = "reused"      # the identical canonical finding already exists; no new row


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize_confidence_component(name: str, value: float | None) -> float | None:
    """The released §8.1 confidence contract, reused verbatim: optional, real, within [0, 1].

    Nothing is computed, calibrated, prioritized, or ranked here (042 §8.1 keeps that deferred).
    """

    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise LectureAnalysisFindingError(f"analysis finding {name} must be a real number")
    if not isfinite(value) or value < 0.0 or value > 1.0:
        raise LectureAnalysisFindingError(f"analysis finding {name} must be within [0, 1]")
    return float(value)


def _normalize_source_range(
    start: float | None, end: float | None
) -> tuple[float | None, float | None]:
    """Validate the range and return it in its canonical ``float`` form.

    The released §8.1 range contract, reused verbatim: optional, at most one, both-or-neither,
    finite, non-negative, ``start <= end``.

    Coercion is load-bearing, not cosmetic. The range participates in identity through canonical
    JSON, where ``json.dumps(1)`` is ``1`` but ``json.dumps(1.0)`` is ``1.0`` — two different
    digests for one range. The column has REAL affinity, so SQLite would store ``1.0`` regardless
    and the row would re-derive an identity different from the one recorded in its own identity
    column, making it permanently unreadable and permanently flagged by repository validation in
    an insert-only table with no delete path. Normalizing here keeps one range = one identity.

    A zero-duration range is structurally valid (042 §9.1 states this explicitly for the sibling
    Candidate contract). No media-duration or transcript-boundary validation is added here: 042
    §9.2 explicitly forbids introducing such checks at an Application Foundation, and the anchor
    records no timeline extent to check against.
    """

    if (start is None) != (end is None):
        raise LectureAnalysisFindingError(
            "analysis finding source range requires both start and end"
        )
    if start is None:
        return None, None
    if not isinstance(start, (int, float)) or isinstance(start, bool):
        raise LectureAnalysisFindingError("analysis finding range start must be a real number")
    if not isinstance(end, (int, float)) or isinstance(end, bool):
        raise LectureAnalysisFindingError("analysis finding range end must be a real number")
    if not isfinite(start) or not isfinite(end):
        raise LectureAnalysisFindingError("analysis finding source range must be finite")
    if start < 0 or end < 0:
        raise LectureAnalysisFindingError(
            "analysis finding source range must not be negative"
        )
    if start > end:
        raise LectureAnalysisFindingError(
            "analysis finding range start must not be after end"
        )
    return float(start), float(end)


def _require_evidence(value: str) -> str:
    """Evidence is canonical Finding meaning, not display text: non-empty and stored verbatim.

    It is deliberately NOT normalized (no trimming, case folding, or collapsing): differing
    evidence must never converge on one Finding (042 §8.2 D-9), so the exact admitted string is
    what participates in identity.
    """

    if not isinstance(value, str) or not value.strip():
        raise LectureAnalysisFindingError("analysis finding evidence must not be empty")
    return value


def derive_finding_identity(
    admission_id: LectureAnalysisInputAdmissionId,
    finding_type: str,
    evidence: str,
    range_start: float | None,
    range_end: float | None,
) -> LectureAnalysisFindingId:
    """Deterministic, Application-owned finding identity (042 §8.2 D-8).

    Derives from the exact immutable anchor plus the stable canonical finding content only.
    Confidence and uncertainty are recorded facts, not identity — the released GOAL-023 rule that
    observed provenance and the content fingerprint never participate in identity. No timestamp,
    randomness, rowid, path, provider identifier, or mutable currentness participates.
    """

    digest = hashlib.sha256(
        _canonical_json(
            {
                "contract": FINDING_CONTRACT_KIND,
                "contract_version": FINDING_CONTRACT_VERSION,
                "admission": admission_id.value,
                "finding_type": finding_type,
                "evidence": evidence,
                "range_start": None if range_start is None else float(range_start),
                "range_end": None if range_end is None else float(range_end),
            }
        ).encode("utf-8")
    ).hexdigest()
    return LectureAnalysisFindingId(
        f"{LECTURE_ANALYSIS_FINDING_IDENTITY_PREFIX}:{digest}"
    )


def _require_anchor_identity(value: str) -> LectureAnalysisInputAdmissionId:
    """Validate the anchor reference, reporting it as a *finding* refusal.

    The released admission-identity rule is reused verbatim, but its error is re-raised in this
    boundary's own type: a malformed anchor is a refusal of the reference supplied to this
    command (042 §8.2 D-3), never a fourth admission standing value, so callers of the finding
    boundary handle exactly one error family.
    """

    try:
        return require_canonical_admission_id(value)
    except LectureAnalysisInputAdmissionError as error:
        raise LectureAnalysisFindingError(str(error)) from error


def require_canonical_finding_id(value: str) -> LectureAnalysisFindingId:
    prefix = LECTURE_ANALYSIS_FINDING_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise LectureAnalysisFindingError(
            "lecture analysis finding identity is malformed "
            "(expected 'lecture-analysis-finding:<64 hex digest>')"
        )
    return LectureAnalysisFindingId(value)


@dataclass(frozen=True, slots=True)
class LectureAnalysisFinding:
    """Immutable canonical Analysis Finding anchored to one Lecture Analysis Input Admission.

    Carries no currentness, lifecycle, review, or supersession state (042 §8.2 D-10) and no
    duplicated upstream provenance (D-2) — the anchor supplies both.
    """

    identity: LectureAnalysisFindingId
    admission_id: LectureAnalysisInputAdmissionId
    finding_type: str
    evidence: str
    confidence: float | None = None
    uncertainty: float | None = None
    range_start: float | None = None
    range_end: float | None = None
    finding_contract_version: int = FINDING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.finding_contract_version != FINDING_CONTRACT_VERSION:
            raise LectureAnalysisFindingError(
                "unsupported analysis finding contract version"
            )
        require_canonical_finding_type(self.finding_type)
        _require_evidence(self.evidence)
        object.__setattr__(
            self, "confidence", _normalize_confidence_component("confidence", self.confidence)
        )
        object.__setattr__(
            self, "uncertainty",
            _normalize_confidence_component("uncertainty", self.uncertainty),
        )
        start, end = _normalize_source_range(self.range_start, self.range_end)
        object.__setattr__(self, "range_start", start)
        object.__setattr__(self, "range_end", end)
        if self.identity != derive_finding_identity(
            self.admission_id,
            self.finding_type,
            self.evidence,
            self.range_start,
            self.range_end,
        ):
            raise LectureAnalysisFindingError(
                "analysis finding identity must derive from its anchoring admission and "
                "canonical finding content"
            )

    @property
    def has_source_range(self) -> bool:
        return self.range_start is not None


@dataclass(frozen=True, slots=True)
class FindingResult:
    """One finding command outcome: the immutable record, the outcome, and the anchor observed."""

    finding: LectureAnalysisFinding
    outcome: FindingOutcome
    admission: LectureAnalysisInputAdmission


class FindingQuery(Protocol):
    def get(self, identity): ...

    def list_for_admission(self, admission_id) -> tuple: ...


class AtomicFindingPersistence(Protocol):
    def persist_finding(self, *, finding: LectureAnalysisFinding) -> None: ...


class LectureAnalysisFindingService:
    """The single canonical Analysis Finding admission path of the effective generation."""

    def __init__(
        self,
        admission_service: LectureAnalysisInputAdmissionService,
        finding_query: FindingQuery,
        persistence: AtomicFindingPersistence,
    ) -> None:
        self._admissions = admission_service
        self._findings = finding_query
        self._persistence = persistence

    # -- explicit finding admission command ----------------------------------------------------

    def admit(
        self,
        *,
        admission_id: str,
        finding_type: str,
        evidence: str,
        confidence: float | None = None,
        uncertainty: float | None = None,
        range_start: float | None = None,
        range_end: float | None = None,
    ) -> FindingResult:
        """Admit one provider-independent finding against a CURRENT analysis input admission.

        Order (042 §8.2): validate the payload, resolve the canonical anchor, re-derive its
        standing, derive identity, then persist atomically and converge on replay.
        """

        # Payload first: a malformed command never reaches the anchor or the repository.
        require_canonical_finding_type(finding_type)
        evidence = _require_evidence(evidence)
        confidence = _normalize_confidence_component("confidence", confidence)
        uncertainty = _normalize_confidence_component("uncertainty", uncertainty)
        range_start, range_end = _normalize_source_range(range_start, range_end)

        admission = self._require_current_admission(admission_id)

        finding = LectureAnalysisFinding(
            identity=derive_finding_identity(
                admission.identity, finding_type, evidence, range_start, range_end
            ),
            admission_id=admission.identity,
            finding_type=finding_type,
            evidence=evidence,
            confidence=confidence,
            uncertainty=uncertainty,
            range_start=range_start,
            range_end=range_end,
        )

        existing = self._findings.get(finding.identity)
        if existing is not None:
            return self._reuse(existing, finding, admission)
        try:
            self._persistence.persist_finding(finding=finding)
        except PersistenceIdentityCollisionError:
            # A near-concurrent identical command won the insert; converge on its record.
            resolved = self._findings.get(finding.identity)
            if resolved is not None:
                return self._reuse(resolved, finding, admission)
            raise
        return FindingResult(
            finding=finding, outcome=FindingOutcome.RECORDED, admission=admission
        )

    def _require_current_admission(self, admission_id: str) -> LectureAnalysisInputAdmission:
        """Resolve the anchor and re-derive its standing at command time (042 §8.2 D-3).

        A missing or malformed reference is refused *before* standing is evaluated — it is a
        refusal of the reference itself, never a fourth standing value.
        """

        identity = _require_anchor_identity(admission_id)
        admission = self._admissions.get(identity.value)
        if admission is None:
            raise LectureAnalysisFindingError(
                "unknown lecture analysis input admission"
            )
        match = self._admissions.authority_match(admission)
        if match is not AdmissionAuthorityMatch.CURRENT:
            raise AnalysisFindingAnchorNotAdmissibleError(
                "analysis findings may only be admitted against an admission that still binds "
                f"the current effective authority (derived standing: {match.value}); the "
                "admission remains valid immutable history"
            )
        return admission

    @staticmethod
    def _reuse(
        existing: LectureAnalysisFinding,
        expected: LectureAnalysisFinding,
        admission: LectureAnalysisInputAdmission,
    ) -> FindingResult:
        """Converge on an identical canonical finding; refuse a divergent payload (D-9).

        Identity already pins the anchor, type, evidence, and range, so only the recorded
        non-identity facts can disagree — and a disagreement is an explicit conflict, never an
        overwrite and never a silent second row.
        """

        if (
            existing.confidence != expected.confidence
            or existing.uncertainty != expected.uncertainty
            or existing.finding_contract_version != expected.finding_contract_version
        ):
            raise AnalysisFindingConflictError(
                "an existing analysis finding with this identity records a different payload "
                "(confidence, uncertainty, or contract version); it is never overwritten"
            )
        return FindingResult(
            finding=existing, outcome=FindingOutcome.REUSED, admission=admission
        )

    # -- queries (derived; never mutate history) -----------------------------------------------

    def get(self, finding_id: str) -> LectureAnalysisFinding | None:
        return self._findings.get(require_canonical_finding_id(finding_id))

    def list_for_admission(self, admission_id: str) -> tuple[LectureAnalysisFinding, ...]:
        return self._findings.list_for_admission(_require_anchor_identity(admission_id))

    def anchor_status(self, finding: LectureAnalysisFinding) -> AdmissionAuthorityMatch:
        """Derived only: does this finding's anchor still bind the current authority?

        A finding whose anchor became superseded is NOT stale data and NOT corruption — it is
        valid immutable history (042 §8.2 D-5). Nothing is mutated by this observation, and no
        such state is ever stored on the finding (D-10).
        """

        admission = self._admissions.get(finding.admission_id.value)
        if admission is None:
            raise LectureAnalysisFindingError(
                "analysis finding anchor is missing (repository integrity failure)"
            )
        return self._admissions.authority_match(admission)


__all__ = [
    "FINDING_CONTRACT_KIND",
    "FINDING_CONTRACT_VERSION",
    "LECTURE_ANALYSIS_FINDING_IDENTITY_PREFIX",
    "AnalysisFindingAnchorNotAdmissibleError",
    "AnalysisFindingConflictError",
    "AtomicFindingPersistence",
    "FindingOutcome",
    "FindingQuery",
    "FindingResult",
    "LectureAnalysisFinding",
    "LectureAnalysisFindingError",
    "LectureAnalysisFindingService",
    "derive_finding_identity",
    "require_canonical_finding_id",
    "require_canonical_finding_type",
]
