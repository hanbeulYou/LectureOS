"""Provider-independent Application foundation for durable canonical Analysis Findings (042 §8.1).

The second Lecture Intelligence Pipeline milestone (042_LECTURE_INTELLIGENCE_PIPELINE.md §8.1, PATCH-0010).
From an already-normalized, provider-independent analysis result — admitted read-only against exactly one
``ELIGIBLE`` :class:`EligibleAnalysisInput` (042 §5.1) — it deterministically records one or more immutable,
canonical :class:`AnalysisFinding` records: the durable analysis boundary that later Lecture Intelligence
stages build on.

It performs **no analysis** and does **not** invoke AI, implement a provider, define prompts or models, or
create a Lecture Segment, Segment Label, Edit Candidate, or Review Item. Raw provider output, provider
classifications, model or prompt identifiers, token usage, transport metadata, and provider internal
reasoning never reach this boundary: the normalized result it admits is a provider-independent Application
contract, not a provider API. It starts no downstream capability and mutates no upstream record. Application
owns Finding identity, admission, provenance, persistence and reconstruction. No wall-clock is read, so
reconstruction and replay are deterministic.
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

from .identities import AnalysisFindingId, EligibleAnalysisInputId
from .lecture_analysis_input import EligibleAnalysisInput, LectureAnalysisEligibility

ANALYSIS_FINDING_RESULT_KIND = "analysis_finding"

# A canonical Finding Type is a stable, Application-owned classification token. It is deliberately NOT a
# fixed taxonomy or closed enum: any token is admissible, but its representation is constrained so a raw
# provider classification (free text, punctuation, scores, casing) can never be preserved as a canonical
# Finding Type. Calibrating the actual set of Finding Types is deferred (042 §8.1).
_FINDING_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def require_canonical_finding_type(value: str) -> str:
    """Return the value if it is a canonical Finding Type token; otherwise reject it."""

    if not isinstance(value, str) or not _FINDING_TYPE_PATTERN.fullmatch(value):
        raise ValueError(
            "analysis finding type must be a canonical Application-owned token "
            "(^[a-z][a-z0-9_]*$)"
        )
    return value


def _validate_confidence_component(name: str, value: float | None) -> None:
    if value is None:
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"analysis finding {name} must be a real number")
    if not isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError(f"analysis finding {name} must be within [0, 1]")


def _validate_time_range(start: float | None, end: float | None) -> None:
    if (start is None) != (end is None):
        raise ValueError("analysis finding time range requires both start and end")
    if start is None:
        return
    if not isfinite(start) or not isfinite(end):
        raise ValueError("analysis finding time range must be finite")
    if start < 0 or end < 0:
        raise ValueError("analysis finding time range must not be negative")
    if start > end:
        raise ValueError("analysis finding start must not be after end")


@dataclass(frozen=True, slots=True)
class AnalysisFinding:
    """Immutable, provenance-bearing canonical Analysis Finding anchored to one Eligible Analysis Input."""

    identity: AnalysisFindingId
    domain_result_id: DomainResultId
    source_input_id: EligibleAnalysisInputId
    finding_type: str
    evidence: str
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    confidence: float | None = None
    uncertainty: float | None = None
    range_start: float | None = None
    range_end: float | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("analysis finding sequence must not be negative")
        require_canonical_finding_type(self.finding_type)
        if not self.evidence.strip():
            raise ValueError("analysis finding evidence must not be empty")
        _validate_confidence_component("confidence", self.confidence)
        _validate_confidence_component("uncertainty", self.uncertainty)
        _validate_time_range(self.range_start, self.range_end)


@dataclass(frozen=True, slots=True)
class NormalizedAnalysisFinding:
    """One provider-independent proposed finding within a normalized analysis result."""

    finding_type: str
    evidence: str
    confidence: float | None = None
    uncertainty: float | None = None
    range_start: float | None = None
    range_end: float | None = None

    def __post_init__(self) -> None:
        require_canonical_finding_type(self.finding_type)
        if not self.evidence.strip():
            raise ValueError("normalized analysis finding evidence must not be empty")
        _validate_confidence_component("confidence", self.confidence)
        _validate_confidence_component("uncertainty", self.uncertainty)
        _validate_time_range(self.range_start, self.range_end)


@dataclass(frozen=True, slots=True)
class NormalizedAnalysisResult:
    """A validated, provider-independent analysis result for one Eligible Analysis Input.

    This is an internal Application contract, never a provider API contract. It carries no provider
    identifier, model, prompt, token usage, transport metadata, raw provider JSON, or internal reasoning.
    Its ``source_timeline_id`` records the Source Timeline the analysis was performed against so admission
    can verify lineage against the anchoring Eligible Analysis Input.
    """

    source_timeline_id: SourceTimelineId
    findings: tuple[NormalizedAnalysisFinding, ...]

    def __post_init__(self) -> None:
        if not self.findings:
            raise ValueError("normalized analysis result must contain at least one finding")


@dataclass(frozen=True, slots=True)
class AnalysisFindingIdentityPlan:
    """Application-owned identities for one canonical Analysis Finding."""

    finding_id: AnalysisFindingId
    finding_result_id: DomainResultId


@dataclass(frozen=True, slots=True)
class PreparedAnalysisFinding:
    """One immutable canonical Analysis Finding and its Domain Result; not yet persisted."""

    finding: AnalysisFinding
    finding_result: DomainResultReference


@dataclass(frozen=True, slots=True)
class PreparedAnalysisFindings:
    """All prepared canonical Findings for one admission; persisted together atomically."""

    source_input_id: EligibleAnalysisInputId
    findings: tuple[PreparedAnalysisFinding, ...]


class EligibleAnalysisInputQuery(Protocol):
    def get(self, identity): ...


class AtomicAnalysisFindingPersistence(Protocol):
    def persist_analysis_findings(
        self, *, prepared: tuple[PreparedAnalysisFinding, ...]
    ) -> None: ...


class AnalysisFindingError(ValueError):
    """A structurally valid request that cannot become canonical Analysis Finding records."""


class AnalysisFindingApplicationService:
    """Admits a normalized analysis result and records durable canonical Analysis Findings."""

    def __init__(
        self,
        input_query: EligibleAnalysisInputQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicAnalysisFindingPersistence | None = None,
    ) -> None:
        self._inputs = input_query
        self._executions = execution_query
        self._persistence = persistence

    def record_findings(self, **kwargs) -> PreparedAnalysisFindings:
        prepared = self.evaluate_findings(**kwargs)
        if self._persistence is None:
            raise RuntimeError("analysis finding persistence is not configured")
        self._persistence.persist_analysis_findings(prepared=prepared.findings)
        return prepared

    def evaluate_findings(
        self,
        *,
        source_input_id: EligibleAnalysisInputId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        result: NormalizedAnalysisResult,
        identities: tuple[AnalysisFindingIdentityPlan, ...],
    ) -> PreparedAnalysisFindings:
        # Admit the analysis basis through its canonical Eligible Analysis Input, read only for provenance.
        eligible_input = self._inputs.get(source_input_id)
        if eligible_input is None:
            raise KeyError("unknown eligible analysis input")
        if not isinstance(eligible_input, EligibleAnalysisInput):
            raise AnalysisFindingError(
                "analysis finding must anchor to a canonical Eligible Analysis Input"
            )
        if eligible_input.eligibility is not LectureAnalysisEligibility.ELIGIBLE:
            raise AnalysisFindingError(
                "analysis finding requires an ELIGIBLE eligible analysis input"
            )
        self._require_running_execution(run_id, unit_execution_id)

        if result.source_timeline_id != eligible_input.source_timeline_id:
            raise AnalysisFindingError(
                "normalized analysis result source timeline must match the eligible analysis input"
            )
        if len(identities) != len(result.findings):
            raise AnalysisFindingError(
                "analysis finding identity plan count must match the normalized findings"
            )

        prepared = tuple(
            self._prepare_one(
                eligible_input=eligible_input,
                run_id=run_id,
                unit_execution_id=unit_execution_id,
                normalized=normalized,
                identity=identity,
                sequence=sequence,
            )
            for sequence, (normalized, identity) in enumerate(
                zip(result.findings, identities)
            )
        )
        return PreparedAnalysisFindings(
            source_input_id=eligible_input.identity, findings=prepared
        )

    def _prepare_one(
        self,
        *,
        eligible_input: EligibleAnalysisInput,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        normalized: NormalizedAnalysisFinding,
        identity: AnalysisFindingIdentityPlan,
        sequence: int,
    ) -> PreparedAnalysisFinding:
        finding = AnalysisFinding(
            identity=identity.finding_id,
            domain_result_id=identity.finding_result_id,
            source_input_id=eligible_input.identity,
            finding_type=normalized.finding_type,
            evidence=normalized.evidence,
            source_media_id=eligible_input.source_media_id,
            source_timeline_id=eligible_input.source_timeline_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            confidence=normalized.confidence,
            uncertainty=normalized.uncertainty,
            range_start=normalized.range_start,
            range_end=normalized.range_end,
        )
        finding_result = DomainResultReference(
            identity=identity.finding_result_id,
            kind=ANALYSIS_FINDING_RESULT_KIND,
            source_media=eligible_input.source_media_id,
            source_timeline=eligible_input.source_timeline_id,
            upstream_results=(eligible_input.domain_result_id,),
        )
        return PreparedAnalysisFinding(finding=finding, finding_result=finding_result)

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise AnalysisFindingError("unit execution must belong to processing run")
        if execution.state is not ProcessingState.RUNNING:
            raise AnalysisFindingError(
                "recording analysis findings requires a running unit execution"
            )


__all__ = [
    "ANALYSIS_FINDING_RESULT_KIND",
    "AnalysisFinding",
    "AnalysisFindingApplicationService",
    "AnalysisFindingError",
    "AnalysisFindingIdentityPlan",
    "AtomicAnalysisFindingPersistence",
    "NormalizedAnalysisFinding",
    "NormalizedAnalysisResult",
    "PreparedAnalysisFinding",
    "PreparedAnalysisFindings",
    "require_canonical_finding_type",
]
