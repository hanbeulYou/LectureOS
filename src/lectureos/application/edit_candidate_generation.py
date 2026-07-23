"""Provider-neutral generation orchestration for the Edit Candidate Application Foundation (042 §9.2).

The first Concrete Edit Candidate Generation Provider milestone (PATCH-0013). This module owns the
**provider-generation product semantics** that sit above the completed Edit Candidate Application Foundation
(§9.1): a provider-neutral generation Port, provider-neutral request/proposal models, an Application/
generation-owned first-slice Candidate Type registry, explicit zero/one/many and partial-success generation
outcomes, bounded located transcript-context construction, and the mapping of valid provider-neutral
proposals into the existing ``NormalizedCandidateResult`` for admission.

It changes nothing in §9.1: the canonical Edit Candidate record, its open-key Candidate Type field, the
required Time Range, admission, and the empty-batch rejection are inherited unchanged. The concrete adapter
(a separate module) invokes the external provider; this layer never sees provider-native output. No
wall-clock or randomness is read here, so replay through a deterministic fake Port is exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Callable, Protocol

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import (
    ProcessingRunId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import ProcessingState
from lectureos.persistence.errors import PersistenceError
from lectureos.transcript.boundaries import TranscriptQueryBoundary

from .analysis_finding import AnalysisFinding
from .edit_candidate import (
    EditCandidateApplicationService,
    EditCandidateIdentityPlan,
    NormalizedCandidateResult,
    NormalizedEditCandidate,
    PreparedEditCandidates,
)
from .identities import AnalysisFindingId
from .lecture_analysis_input import EligibleAnalysisInput

# The Application/generation-owned closed first-slice Candidate Type registry (042 §9.2). It is deliberately
# closed for this generation milestone and additively extensible only through a later approved product
# decision. It is a generation/admission constraint layered above §9.1's open-key canonical field, NOT a
# global closed enum: the canonical Edit Candidate record still accepts any structurally valid Application-
# owned open key. The registry is owned here, not by the adapter or the prompt.
EDIT_CANDIDATE_TYPE_REGISTRY: frozenset[str] = frozenset(
    {"non_lecture_region", "redundant_restatement", "delivery_concern"}
)


def is_registry_candidate_type(value: object) -> bool:
    """True iff the value is an approved first-slice provider-generation Candidate Type key."""

    return isinstance(value, str) and value in EDIT_CANDIDATE_TYPE_REGISTRY


@dataclass(frozen=True, slots=True)
class GenerationTranscriptSegment:
    """One bounded corrected-transcript segment exposed as provider-neutral context (no identity)."""

    text: str
    source_order: int
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class EditCandidateGenerationRequest:
    """Immutable provider-neutral generation context; never a provider-specific payload.

    Carries only the approved first-slice input (042 §9.2): canonical Finding Type/evidence, the located
    Finding range, a bounded located transcript context with canonical timing, the allowed Candidate Type
    keys, and the bounded context window. It carries no canonical identity, provider metadata, media, or
    file path.
    """

    finding_type: str
    finding_evidence: str
    finding_range_start: float
    finding_range_end: float
    source_timeline_id: SourceTimelineId
    context_segments: tuple[GenerationTranscriptSegment, ...]
    context_window_start: float
    context_window_end: float
    allowed_candidate_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeneratedProposal:
    """A provider-neutral proposed Edit Candidate; not yet validated or canonical."""

    candidate_type: str
    rationale: str
    range_start: float
    range_end: float
    source_index: int | None = None


class EditCandidateGenerationFailure(RuntimeError):
    """Base: the generation capability could not produce a usable response."""


class EditCandidateProviderFailure(EditCandidateGenerationFailure):
    """External provider transport/service/refusal failure."""


class EditCandidateMalformedOutputError(EditCandidateGenerationFailure):
    """The provider returned a structurally malformed top-level response."""


class EditCandidateGenerationPort(Protocol):
    def generate_candidates(
        self, request: EditCandidateGenerationRequest
    ) -> tuple[GeneratedProposal, ...]: ...


class EditCandidateGenerationError(ValueError):
    """A structurally invalid generation request that cannot proceed."""


class GenerationOutcomeKind(str, Enum):
    ALL_VALID = "all_valid"
    NO_CANDIDATE = "no_candidate"
    PARTIAL_SUCCESS = "partial_success"
    PROVIDER_FAILURE = "provider_failure"
    MALFORMED_OUTPUT = "malformed_output"
    NORMALIZATION_FAILURE = "normalization_failure"
    ADMISSION_FAILURE = "admission_failure"


@dataclass(frozen=True, slots=True)
class RejectedProposal:
    """A bounded diagnostic for a provider proposal rejected before admission (never persisted)."""

    source_index: int
    failure_category: str
    reason: str


@dataclass(frozen=True, slots=True)
class EditCandidateGenerationOutcome:
    """The explicit generation-layer outcome; distinct from the canonical admission result."""

    kind: GenerationOutcomeKind
    admitted: PreparedEditCandidates | None = None
    rejected: tuple[RejectedProposal, ...] = ()
    failure_reason: str | None = None


IdentityPlanner = Callable[[int], tuple[EditCandidateIdentityPlan, ...]]


class EditCandidateGenerationService:
    """Orchestrates one provider invocation per Analysis Finding into the existing admission service."""

    def __init__(
        self,
        finding_query,
        input_query,
        transcript_query: TranscriptQueryBoundary,
        execution_query: ExecutionQueryBoundary,
        generation: EditCandidateGenerationPort,
        admission: EditCandidateApplicationService,
        *,
        context_window_seconds: float,
    ) -> None:
        if not isfinite(context_window_seconds) or context_window_seconds < 0:
            raise ValueError("context window seconds must be finite and non-negative")
        self._findings = finding_query
        self._inputs = input_query
        self._transcripts = transcript_query
        self._executions = execution_query
        self._generation = generation
        self._admission = admission
        self._context_window_seconds = context_window_seconds

    def generate(
        self,
        *,
        source_finding_id: AnalysisFindingId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identity_planner: IdentityPlanner,
    ) -> EditCandidateGenerationOutcome:
        # Preconditions (raise): the Finding must be canonical and the execution must be running. All
        # upstream records are read only.
        finding = self._findings.get(source_finding_id)
        if finding is None:
            raise KeyError("unknown analysis finding")
        if not isinstance(finding, AnalysisFinding):
            raise EditCandidateGenerationError(
                "edit candidate generation requires a canonical Analysis Finding"
            )
        self._require_running_execution(run_id, unit_execution_id)

        window = self._context_window(finding)
        if window is None:
            # No usable located transcript context: no provider call, no admission.
            return EditCandidateGenerationOutcome(kind=GenerationOutcomeKind.NO_CANDIDATE)
        window_start, window_end, context_segments = window
        if not context_segments:
            return EditCandidateGenerationOutcome(kind=GenerationOutcomeKind.NO_CANDIDATE)

        request = EditCandidateGenerationRequest(
            finding_type=finding.finding_type,
            finding_evidence=finding.evidence,
            finding_range_start=finding.range_start,
            finding_range_end=finding.range_end,
            source_timeline_id=finding.source_timeline_id,
            context_segments=context_segments,
            context_window_start=window_start,
            context_window_end=window_end,
            allowed_candidate_types=tuple(sorted(EDIT_CANDIDATE_TYPE_REGISTRY)),
        )

        try:
            proposals = self._generation.generate_candidates(request)
        except EditCandidateMalformedOutputError as error:
            return EditCandidateGenerationOutcome(
                kind=GenerationOutcomeKind.MALFORMED_OUTPUT, failure_reason=str(error)
            )
        except EditCandidateProviderFailure as error:
            return EditCandidateGenerationOutcome(
                kind=GenerationOutcomeKind.PROVIDER_FAILURE, failure_reason=str(error)
            )
        if not isinstance(proposals, tuple):
            return EditCandidateGenerationOutcome(
                kind=GenerationOutcomeKind.MALFORMED_OUTPUT,
                failure_reason="generation port must return an immutable proposal tuple",
            )
        if not proposals:
            return EditCandidateGenerationOutcome(kind=GenerationOutcomeKind.NO_CANDIDATE)

        valid: list[NormalizedEditCandidate] = []
        rejected: list[RejectedProposal] = []
        for index, proposal in enumerate(proposals):
            reason = self._reject_reason(proposal, window_start, window_end)
            if reason is None:
                valid.append(
                    NormalizedEditCandidate(
                        candidate_type=proposal.candidate_type,
                        rationale=proposal.rationale,
                        range_start=float(proposal.range_start),
                        range_end=float(proposal.range_end),
                    )
                )
            else:
                category, detail = reason
                rejected.append(
                    RejectedProposal(
                        source_index=index, failure_category=category, reason=detail
                    )
                )

        if not valid:
            return EditCandidateGenerationOutcome(
                kind=GenerationOutcomeKind.NORMALIZATION_FAILURE,
                rejected=tuple(rejected),
                failure_reason="no provider proposal passed generation validation",
            )

        identities = identity_planner(len(valid))
        if len(identities) != len(valid):
            raise EditCandidateGenerationError(
                "identity plan count must match the valid proposal count"
            )
        result = NormalizedCandidateResult(
            source_timeline_id=finding.source_timeline_id, candidates=tuple(valid)
        )
        try:
            admitted = self._admission.record_candidates(
                source_finding_id=finding.identity,
                run_id=run_id,
                unit_execution_id=unit_execution_id,
                result=result,
                identities=identities,
            )
        except PersistenceError as error:
            return EditCandidateGenerationOutcome(
                kind=GenerationOutcomeKind.ADMISSION_FAILURE,
                rejected=tuple(rejected),
                failure_reason=str(error),
            )
        kind = (
            GenerationOutcomeKind.PARTIAL_SUCCESS
            if rejected
            else GenerationOutcomeKind.ALL_VALID
        )
        return EditCandidateGenerationOutcome(
            kind=kind, admitted=admitted, rejected=tuple(rejected)
        )

    def _reject_reason(
        self, proposal: object, window_start: float, window_end: float
    ) -> tuple[str, str] | None:
        if not isinstance(proposal, GeneratedProposal):
            return ("malformed_proposal", "proposal is not a provider-neutral proposal")
        if not is_registry_candidate_type(proposal.candidate_type):
            return (
                "unknown_candidate_type",
                "candidate type is not an approved first-slice registry key",
            )
        if not isinstance(proposal.rationale, str) or not proposal.rationale.strip():
            return ("blank_rationale", "rationale must be non-empty text")
        start, end = proposal.range_start, proposal.range_end
        for value in (start, end):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return ("invalid_range", "range bounds must be real numbers")
        if not isfinite(start) or not isfinite(end):
            return ("invalid_range", "range bounds must be finite")
        if start < 0 or end < 0 or start > end:
            return ("invalid_range", "range must be non-negative with start <= end")
        if start < window_start or end > window_end:
            return (
                "range_out_of_context",
                "range must lie within the supplied bounded context window",
            )
        return None

    def _context_window(
        self, finding: AnalysisFinding
    ) -> tuple[float, float, tuple[GenerationTranscriptSegment, ...]] | None:
        if finding.range_start is None or finding.range_end is None:
            return None
        window_start = max(0.0, finding.range_start - self._context_window_seconds)
        window_end = finding.range_end + self._context_window_seconds
        eligible_input = self._require_input(finding.source_input_id)
        revision = self._transcripts.get_corrected_revision(
            eligible_input.source_revision_id
        )
        if revision is None:
            raise KeyError("unknown corrected transcript revision")
        selected: list[GenerationTranscriptSegment] = []
        for segment_id in revision.segment_ids:
            segment = self._transcripts.get_segment(segment_id)
            if segment is None:
                raise KeyError("unknown corrected transcript segment")
            if segment.start is None or segment.end is None:
                continue
            if segment.end < window_start or segment.start > window_end:
                continue
            selected.append(
                GenerationTranscriptSegment(
                    text=segment.text,
                    source_order=segment.source_order,
                    start=segment.start,
                    end=segment.end,
                )
            )
        selected.sort(key=lambda item: item.source_order)
        return window_start, window_end, tuple(selected)

    def _require_input(self, input_id) -> EligibleAnalysisInput:
        eligible_input = self._inputs.get(input_id)
        if eligible_input is None:
            raise KeyError("unknown eligible analysis input")
        if not isinstance(eligible_input, EligibleAnalysisInput):
            raise EditCandidateGenerationError(
                "analysis finding must trace to a canonical Eligible Analysis Input"
            )
        return eligible_input

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise EditCandidateGenerationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise EditCandidateGenerationError(
                "edit candidate generation requires a running unit execution"
            )


__all__ = [
    "EDIT_CANDIDATE_TYPE_REGISTRY",
    "EditCandidateGenerationError",
    "EditCandidateGenerationFailure",
    "EditCandidateGenerationOutcome",
    "EditCandidateGenerationPort",
    "EditCandidateGenerationRequest",
    "EditCandidateGenerationService",
    "EditCandidateMalformedOutputError",
    "EditCandidateProviderFailure",
    "GeneratedProposal",
    "GenerationOutcomeKind",
    "GenerationTranscriptSegment",
    "IdentityPlanner",
    "RejectedProposal",
    "is_registry_candidate_type",
]
