"""Provider-independent Application foundation for durable canonical Edit Candidates (042 §9.1).

The fourth Lecture Intelligence Pipeline milestone (042_LECTURE_INTELLIGENCE_PIPELINE.md §9.1, PATCH-0012).
From an already-normalized, provider-independent Edit Candidate result — admitted read-only against exactly
one canonical :class:`AnalysisFinding` (042 §8.1) — it deterministically records one or more immutable,
canonical :class:`EditCandidate` records: optional, evaluative, advisory edit proposals derived from
analysis, prepared for later Review handoff.

It performs **no candidate generation** and does **not** invoke AI, implement a provider, define prompts or
models, or create a Segment Label, Review CandidateReference, Review Item, or Approved Edit Decision. It
assigns no Review status and supports no Accept/Reject/Modify. Raw provider output, provider classifications,
provider operation names, model or prompt identifiers, token usage, and provider internal reasoning never
reach this boundary: the normalized result it admits is a provider-independent Application contract, not a
provider API. It starts no downstream capability and mutates no upstream record. Application owns Candidate
identity, admission, provenance, persistence and reconstruction. No wall-clock is read, so reconstruction and
replay are deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference, ProcessingState

from .analysis_finding import AnalysisFinding
from .identities import AnalysisFindingId, EditCandidateId

EDIT_CANDIDATE_RESULT_KIND = "edit_candidate"

# A canonical Edit Candidate Type is a stable, Application-owned key. It is deliberately NOT a fixed taxonomy
# or closed enum: any token is admissible, but its representation is constrained so a provider-native label,
# classification, or operation name can never be preserved as a canonical Candidate Type. Illustrative
# values (retain, remove, condense, review, emphasize) remain non-normative; the actual set is deferred
# (042 §9.1). This follows the §8.1 Finding Type canonical Application-key precedent.
_CANDIDATE_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def require_canonical_candidate_type(value: str) -> str:
    """Return the value if it is a canonical Candidate Type token; otherwise reject it."""

    if not isinstance(value, str) or not _CANDIDATE_TYPE_PATTERN.fullmatch(value):
        raise ValueError(
            "edit candidate type must be a canonical Application-owned token "
            "(^[a-z][a-z0-9_]*$)"
        )
    return value


def _validate_time_range(start: float, end: float) -> None:
    # Every Edit Candidate carries exactly one required, single Source Timeline Time Range (042 §9.1).
    for name, value in (("start", start), ("end", end)):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"edit candidate range {name} must be a real number")
    if not isfinite(start) or not isfinite(end):
        raise ValueError("edit candidate time range must be finite")
    if start < 0 or end < 0:
        raise ValueError("edit candidate time range must not be negative")
    if start > end:
        raise ValueError("edit candidate start must not be after end")


@dataclass(frozen=True, slots=True)
class EditCandidate:
    """Immutable, provenance-bearing canonical Edit Candidate anchored to one Analysis Finding."""

    identity: EditCandidateId
    domain_result_id: DomainResultId
    source_finding_id: AnalysisFindingId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    candidate_type: str
    rationale: str
    range_start: float
    range_end: float

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("edit candidate sequence must not be negative")
        require_canonical_candidate_type(self.candidate_type)
        if not self.rationale.strip():
            raise ValueError("edit candidate rationale must not be empty")
        _validate_time_range(self.range_start, self.range_end)


@dataclass(frozen=True, slots=True)
class NormalizedEditCandidate:
    """One provider-independent proposed candidate within a normalized Edit Candidate result."""

    candidate_type: str
    rationale: str
    range_start: float
    range_end: float

    def __post_init__(self) -> None:
        require_canonical_candidate_type(self.candidate_type)
        if not self.rationale.strip():
            raise ValueError("normalized edit candidate rationale must not be empty")
        _validate_time_range(self.range_start, self.range_end)


@dataclass(frozen=True, slots=True)
class NormalizedCandidateResult:
    """A validated, provider-independent Edit Candidate result for one Analysis Finding.

    This is an internal Application contract, never a provider API contract. It carries no candidate/DomainResult
    identity, provider identifier, provider-native label, model, prompt, token usage, transport metadata, raw
    provider JSON, confidence, uncertainty, Review state, Segment reference, or executable operation. Its
    ``source_timeline_id`` records the Source Timeline the candidate result was produced against so admission
    can verify lineage against the anchoring Analysis Finding.
    """

    source_timeline_id: SourceTimelineId
    candidates: tuple[NormalizedEditCandidate, ...]

    def __post_init__(self) -> None:
        if not self.candidates:
            raise ValueError("normalized candidate result must contain at least one candidate")


@dataclass(frozen=True, slots=True)
class EditCandidateIdentityPlan:
    """Application-owned identities for one canonical Edit Candidate."""

    candidate_id: EditCandidateId
    candidate_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedEditCandidate:
    """One immutable canonical Edit Candidate and its Domain Result; not yet persisted."""

    candidate: EditCandidate
    candidate_result: DomainResultReference


@dataclass(frozen=True, slots=True)
class PreparedEditCandidates:
    """All prepared canonical Candidates for one admission; persisted together atomically."""

    source_finding_id: AnalysisFindingId
    candidates: tuple[PreparedEditCandidate, ...]


class AnalysisFindingQuery(Protocol):
    def get(self, identity): ...


class AtomicEditCandidatePersistence(Protocol):
    def persist_edit_candidates(
        self, *, prepared: tuple[PreparedEditCandidate, ...]
    ) -> None: ...


class EditCandidateError(ValueError):
    """A structurally valid request that cannot become canonical Edit Candidate records."""


class EditCandidateApplicationService:
    """Admits a normalized Edit Candidate result and records durable canonical Edit Candidates."""

    def __init__(
        self,
        finding_query: AnalysisFindingQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicEditCandidatePersistence | None = None,
    ) -> None:
        self._findings = finding_query
        self._executions = execution_query
        self._persistence = persistence

    def record_candidates(self, **kwargs) -> PreparedEditCandidates:
        prepared = self.evaluate_candidates(**kwargs)
        if self._persistence is None:
            raise RuntimeError("edit candidate persistence is not configured")
        self._persistence.persist_edit_candidates(prepared=prepared.candidates)
        return prepared

    def evaluate_candidates(
        self,
        *,
        source_finding_id: AnalysisFindingId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        result: NormalizedCandidateResult,
        identities: tuple[EditCandidateIdentityPlan, ...],
    ) -> PreparedEditCandidates:
        # Admit the candidate basis through its canonical Analysis Finding, read only for provenance. A
        # persisted Analysis Finding is already the durable output of an ELIGIBLE Eligible Analysis Input
        # (042 §8.1), so anchoring to a canonical Finding transitively guarantees ELIGIBLE provenance; no
        # separate eligibility check is re-run here. The Finding, and everything it traces to, is never
        # mutated.
        finding = self._findings.get(source_finding_id)
        if finding is None:
            raise KeyError("unknown analysis finding")
        if not isinstance(finding, AnalysisFinding):
            raise EditCandidateError(
                "edit candidate must anchor to a canonical Analysis Finding"
            )
        self._require_running_execution(run_id, unit_execution_id)

        if result.source_timeline_id != finding.source_timeline_id:
            raise EditCandidateError(
                "normalized candidate result source timeline must match the analysis finding"
            )
        if len(identities) != len(result.candidates):
            raise EditCandidateError(
                "edit candidate identity plan count must match the normalized candidates"
            )

        prepared = tuple(
            self._prepare_one(
                finding=finding,
                run_id=run_id,
                unit_execution_id=unit_execution_id,
                normalized=normalized,
                identity=identity,
                sequence=sequence,
            )
            for sequence, (normalized, identity) in enumerate(
                zip(result.candidates, identities)
            )
        )
        return PreparedEditCandidates(
            source_finding_id=finding.identity, candidates=prepared
        )

    def _prepare_one(
        self,
        *,
        finding: AnalysisFinding,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        normalized: NormalizedEditCandidate,
        identity: EditCandidateIdentityPlan,
        sequence: int,
    ) -> PreparedEditCandidate:
        candidate = EditCandidate(
            identity=identity.candidate_id,
            domain_result_id=identity.candidate_result_id,
            source_finding_id=finding.identity,
            source_media_id=finding.source_media_id,
            source_timeline_id=finding.source_timeline_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            candidate_type=normalized.candidate_type,
            rationale=normalized.rationale,
            range_start=normalized.range_start,
            range_end=normalized.range_end,
        )
        candidate_result = DomainResultReference(
            identity=identity.candidate_result_id,
            kind=EDIT_CANDIDATE_RESULT_KIND,
            source_media=finding.source_media_id,
            source_timeline=finding.source_timeline_id,
            upstream_results=(finding.domain_result_id,),
        )
        return PreparedEditCandidate(
            candidate=candidate, candidate_result=candidate_result
        )

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise EditCandidateError("unit execution must belong to processing run")
        if execution.state is not ProcessingState.RUNNING:
            raise EditCandidateError(
                "recording edit candidates requires a running unit execution"
            )


__all__ = [
    "EDIT_CANDIDATE_RESULT_KIND",
    "AnalysisFindingQuery",
    "AtomicEditCandidatePersistence",
    "EditCandidate",
    "EditCandidateApplicationService",
    "EditCandidateError",
    "EditCandidateIdentityPlan",
    "NormalizedCandidateResult",
    "NormalizedEditCandidate",
    "PreparedEditCandidate",
    "PreparedEditCandidates",
    "require_canonical_candidate_type",
]
