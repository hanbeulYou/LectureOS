"""Provider-independent Application contract for Subtitle Structural Validation.

The fifth Subtitle Pipeline stage (041_SUBTITLE_PIPELINE.md §4.5, §9). From a canonical
`SubtitleTimeRevision` and its ordered timed units, it deterministically diagnoses the subtitle
revision's structural correctness and produces one immutable Validation Result plus a collection of
immutable Findings traceable to affected timed units.

Validation diagnoses only. It records structural defects (provenance integrity, timeline
traceability, unresolved timing, ordering, overlap) and a derived ``structural_valid`` verdict
(= no blocking finding); it modifies nothing, creates no Review Item, adjudicates no uncertainty,
approves nothing, and applies no numeric quality threshold. Diagnosis is entirely deterministic and
provider-free.

Each finding carries a stable ``rule`` identifier independent of its human-readable ``description``:
the rule identifier is the finding's stable rule identity that downstream layers consume, while the
description is explanatory text only and is not part of the rule identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)

from .identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleTranscriptIntakeId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from .subtitle_time_representation import SubtitleTimeRevision, SubtitleTimingStatus

SUBTITLE_VALIDATION_RESULT_KIND = "subtitle_validation"


class SubtitleValidationCategory(str, Enum):
    PROVENANCE_INTEGRITY = "provenance_integrity"
    TIMELINE_TRACEABILITY = "timeline_traceability"
    UNRESOLVED_TIMING = "unresolved_timing"
    ORDERING = "ordering"
    OVERLAP = "overlap"


# Stable rule identifiers — the deterministic rule identity that produced a finding. Downstream
# layers consume these rather than parsing descriptions; they remain stable across wording changes.
RULE_PROVENANCE_READING_REVISION_MISSING = "provenance.reading_revision_missing"
RULE_PROVENANCE_READING_UNIT_MISSING = "provenance.reading_unit_missing"
RULE_PROVENANCE_COVERAGE_MISMATCH = "provenance.coverage_mismatch"
RULE_TIMELINE_MISMATCH = "traceability.timeline_mismatch"
RULE_UNRESOLVED_TIMING = "timing.unresolved"
RULE_ORDERING_NON_MONOTONIC = "ordering.non_monotonic"
RULE_OVERLAP_ADJACENT = "overlap.adjacent"


@dataclass(frozen=True, slots=True)
class SubtitleValidationFinding:
    """One immutable structural finding: a stable rule plus an explanatory description."""

    identity: SubtitleValidationFindingId
    validation_id: SubtitleValidationId
    rule: str
    category: SubtitleValidationCategory
    blocking: bool
    description: str
    target_timed_unit_id: SubtitleTimedUnitId | None = None

    def __post_init__(self) -> None:
        if not self.rule.strip():
            raise ValueError("subtitle validation finding rule must not be empty")
        if not self.description.strip():
            raise ValueError("subtitle validation finding description must not be empty")


@dataclass(frozen=True, slots=True)
class SubtitleValidation:
    """Immutable structural validation result diagnosing one canonical Subtitle Time Revision."""

    identity: SubtitleValidationId
    domain_result_id: DomainResultId
    source_time_revision_id: SubtitleTimeRevisionId
    source_reading_revision_id: SubtitleReadingRevisionId
    source_candidate_id: SubtitleCandidateId
    source_intake_id: SubtitleTranscriptIntakeId
    source_readiness_id: TranscriptReadinessEvaluationId
    source_selection_id: TranscriptCurrentSelectionId
    source_applicability_id: TranscriptApplicabilityEvaluationId
    source_decision_id: TranscriptReviewDecisionId
    review_item_id: ReviewItemId
    candidate_reference_id: CandidateReferenceId
    source_transcript_id: TranscriptId
    source_revision_id: TranscriptRevisionId
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    source_transcript_validation_id: TranscriptValidationId
    structural_valid: bool
    provenance_complete: bool
    timeline_traceable: bool
    ordering_consistent: bool
    time_consistent: bool
    finding_ids: tuple[SubtitleValidationFindingId, ...]
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    sequence: int
    reason: str
    previous_validation_id: SubtitleValidationId | None = None

    def __post_init__(self) -> None:
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("subtitle validation finding ids must be unique")
        if self.sequence < 0:
            raise ValueError("subtitle validation sequence must not be negative")
        if not self.reason.strip():
            raise ValueError("subtitle validation reason must not be empty")
        if self.previous_validation_id is not None and self.sequence == 0:
            raise ValueError(
                "first subtitle validation must not reference a previous validation"
            )


@dataclass(frozen=True, slots=True)
class SubtitleValidationIdentityPlan:
    """Application-owned validation identities for one diagnosis.

    Only the validation and its Result identity are caller-owned; because the finding count is
    defect-dependent, finding identities are deterministically derived from the validation identity
    plus their ordinal (see ``finding_identity``).
    """

    validation_id: SubtitleValidationId
    validation_result_id: DomainResultId


def finding_identity(
    validation_id: SubtitleValidationId, ordinal: int
) -> SubtitleValidationFindingId:
    """Deterministic finding identity derived from the caller-owned validation identity + ordinal."""

    if ordinal < 0:
        raise ValueError("finding ordinal must not be negative")
    return SubtitleValidationFindingId(f"{validation_id.value}::finding::{ordinal}")


@dataclass(frozen=True, slots=True)
class _FindingSpec:
    rule: str
    category: SubtitleValidationCategory
    blocking: bool
    description: str
    target_timed_unit_id: SubtitleTimedUnitId | None


def diagnose_time_revision(time_revision, timed_units, reading_revision):
    """Deterministic, threshold-free structural diagnosis. Returns ordered finding specs.

    Runs the five structural checks in fixed order (provenance, timeline traceability, unresolved
    timing, ordering, overlap). Modifies nothing; applies no numeric quality threshold.
    """

    specs: list[_FindingSpec] = []

    # 1. Provenance integrity (§9.4): resolve the reading revision and verify unit coverage.
    if reading_revision is None:
        specs.append(
            _FindingSpec(
                RULE_PROVENANCE_READING_REVISION_MISSING,
                SubtitleValidationCategory.PROVENANCE_INTEGRITY,
                True,
                "source reading revision could not be resolved",
                None,
            )
        )
    else:
        reading_unit_ids = set(reading_revision.unit_ids)
        for unit in timed_units:
            if unit.source_reading_unit_id not in reading_unit_ids:
                specs.append(
                    _FindingSpec(
                        RULE_PROVENANCE_READING_UNIT_MISSING,
                        SubtitleValidationCategory.PROVENANCE_INTEGRITY,
                        True,
                        "timed unit references a reading unit absent from the source reading revision",
                        unit.identity,
                    )
                )
        referenced = sorted(u.source_reading_unit_id.value for u in timed_units)
        expected = sorted(u.value for u in reading_revision.unit_ids)
        if referenced != expected:
            specs.append(
                _FindingSpec(
                    RULE_PROVENANCE_COVERAGE_MISMATCH,
                    SubtitleValidationCategory.PROVENANCE_INTEGRITY,
                    True,
                    "timed units do not cover the reading revision units exactly",
                    None,
                )
            )

    # 2. Timeline traceability (§9.2): anchored units must share the revision source timeline.
    for unit in timed_units:
        if (
            unit.timing_status is SubtitleTimingStatus.ANCHORED
            and unit.source_timeline_id != time_revision.source_timeline_id
        ):
            specs.append(
                _FindingSpec(
                    RULE_TIMELINE_MISMATCH,
                    SubtitleValidationCategory.TIMELINE_TRACEABILITY,
                    True,
                    "anchored timed unit timeline is not traceable to the revision source timeline",
                    unit.identity,
                )
            )

    # 3. Unresolved timing (§9.2): an unresolved timed unit is a structural defect.
    for unit in timed_units:
        if unit.timing_status is SubtitleTimingStatus.UNRESOLVED:
            specs.append(
                _FindingSpec(
                    RULE_UNRESOLVED_TIMING,
                    SubtitleValidationCategory.UNRESOLVED_TIMING,
                    True,
                    "timed unit has unresolved timing",
                    unit.identity,
                )
            )

    anchored = [
        unit
        for unit in timed_units
        if unit.timing_status is SubtitleTimingStatus.ANCHORED
    ]

    # 4. Ordering (§9.3): anchored start times must not decrease along display order.
    previous_start = None
    for unit in anchored:
        if previous_start is not None and unit.start < previous_start:
            specs.append(
                _FindingSpec(
                    RULE_ORDERING_NON_MONOTONIC,
                    SubtitleValidationCategory.ORDERING,
                    True,
                    "anchored timed unit start precedes an earlier displayed unit",
                    unit.identity,
                )
            )
        previous_start = unit.start

    # 5. Overlap (§9.2): consecutive anchored units on one timeline must not overlap.
    for earlier, later in zip(anchored, anchored[1:]):
        if (
            earlier.source_timeline_id == later.source_timeline_id
            and earlier.end > later.start
        ):
            specs.append(
                _FindingSpec(
                    RULE_OVERLAP_ADJACENT,
                    SubtitleValidationCategory.OVERLAP,
                    True,
                    "anchored timed unit overlaps the following displayed unit",
                    later.identity,
                )
            )

    return specs


@dataclass(frozen=True, slots=True)
class PreparedSubtitleValidation:
    """Immutable canonical validation result + ordered findings; not yet persisted."""

    validation: SubtitleValidation
    findings: tuple[SubtitleValidationFinding, ...]
    validation_result: DomainResultReference


class SubtitleTimeRevisionQuery(Protocol):
    def get(self, identity): ...

    def get_unit(self, identity): ...


class SubtitleReadingRevisionQuery(Protocol):
    def get(self, identity): ...


class AtomicSubtitleValidationPersistence(Protocol):
    def persist_subtitle_validation(
        self,
        *,
        validation: SubtitleValidation,
        findings: tuple[SubtitleValidationFinding, ...],
        validation_result: DomainResultReference,
    ) -> None: ...


class SubtitleStructuralValidationError(ValueError):
    """A structurally valid request that cannot become a canonical validation record."""


class SubtitleStructuralValidationService:
    """Deterministically diagnoses a subtitle time revision into a validation result + findings."""

    def __init__(
        self,
        time_query: SubtitleTimeRevisionQuery,
        reading_query: SubtitleReadingRevisionQuery,
        execution_query: ExecutionQueryBoundary,
        persistence: AtomicSubtitleValidationPersistence | None = None,
    ) -> None:
        self._times = time_query
        self._readings = reading_query
        self._executions = execution_query
        self._persistence = persistence

    def record_validation(self, **kwargs) -> PreparedSubtitleValidation:
        prepared = self.validate_timing(**kwargs)
        if self._persistence is None:
            raise RuntimeError("subtitle validation persistence is not configured")
        self._persistence.persist_subtitle_validation(
            validation=prepared.validation,
            findings=prepared.findings,
            validation_result=prepared.validation_result,
        )
        return prepared

    def validate_timing(
        self,
        *,
        source_time_revision_id: SubtitleTimeRevisionId,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        identities: SubtitleValidationIdentityPlan,
        sequence: int = 0,
        previous_validation_id: SubtitleValidationId | None = None,
        reason: str | None = None,
    ) -> PreparedSubtitleValidation:
        time = self._times.get(source_time_revision_id)
        if time is None:
            raise KeyError("unknown subtitle time revision")
        if not isinstance(time, SubtitleTimeRevision):
            raise SubtitleStructuralValidationError(
                "subtitle validation must derive from a canonical Subtitle Time Revision"
            )
        self._require_running_execution(run_id, unit_execution_id)

        timed_units = tuple(
            self._require_timed_unit(unit_id) for unit_id in time.timed_unit_ids
        )
        reading = self._readings.get(time.source_reading_revision_id)

        specs = diagnose_time_revision(time, timed_units, reading)
        vid = identities.validation_id
        findings = tuple(
            SubtitleValidationFinding(
                identity=finding_identity(vid, ordinal),
                validation_id=vid,
                rule=spec.rule,
                category=spec.category,
                blocking=spec.blocking,
                description=spec.description,
                target_timed_unit_id=spec.target_timed_unit_id,
            )
            for ordinal, spec in enumerate(specs)
        )
        categories = {finding.category for finding in findings}
        structural_valid = not any(finding.blocking for finding in findings)
        provenance_complete = (
            SubtitleValidationCategory.PROVENANCE_INTEGRITY not in categories
        )
        timeline_traceable = (
            SubtitleValidationCategory.TIMELINE_TRACEABILITY not in categories
            and SubtitleValidationCategory.UNRESOLVED_TIMING not in categories
        )
        ordering_consistent = SubtitleValidationCategory.ORDERING not in categories
        time_consistent = SubtitleValidationCategory.OVERLAP not in categories

        resolved_reason = (
            reason
            if reason is not None
            else _default_reason(len(findings), structural_valid)
        )
        validation = SubtitleValidation(
            identity=vid,
            domain_result_id=identities.validation_result_id,
            source_time_revision_id=time.identity,
            source_reading_revision_id=time.source_reading_revision_id,
            source_candidate_id=time.source_candidate_id,
            source_intake_id=time.source_intake_id,
            source_readiness_id=time.source_readiness_id,
            source_selection_id=time.source_selection_id,
            source_applicability_id=time.source_applicability_id,
            source_decision_id=time.source_decision_id,
            review_item_id=time.review_item_id,
            candidate_reference_id=time.candidate_reference_id,
            source_transcript_id=time.source_transcript_id,
            source_revision_id=time.source_revision_id,
            source_media_id=time.source_media_id,
            source_timeline_id=time.source_timeline_id,
            source_transcript_validation_id=time.validation_id,
            structural_valid=structural_valid,
            provenance_complete=provenance_complete,
            timeline_traceable=timeline_traceable,
            ordering_consistent=ordering_consistent,
            time_consistent=time_consistent,
            finding_ids=tuple(finding.identity for finding in findings),
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            sequence=sequence,
            reason=resolved_reason,
            previous_validation_id=previous_validation_id,
        )
        validation_result = DomainResultReference(
            identity=identities.validation_result_id,
            kind=SUBTITLE_VALIDATION_RESULT_KIND,
            source_media=time.source_media_id,
            source_timeline=time.source_timeline_id,
            upstream_results=(time.domain_result_id,),
        )
        return PreparedSubtitleValidation(
            validation=validation, findings=findings, validation_result=validation_result
        )

    def _require_timed_unit(self, unit_id: SubtitleTimedUnitId):
        unit = self._times.get_unit(unit_id)
        if unit is None:
            raise KeyError("unknown subtitle timed unit")
        return unit

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise SubtitleStructuralValidationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise SubtitleStructuralValidationError(
                "recording subtitle validation requires a running unit execution"
            )


def _default_reason(finding_count: int, structural_valid: bool) -> str:
    verdict = "structurally valid" if structural_valid else "structurally invalid"
    return (
        f"structural validation of the time revision: {verdict} with {finding_count} "
        "finding(s)"
    )


__all__ = [
    "RULE_ORDERING_NON_MONOTONIC",
    "RULE_OVERLAP_ADJACENT",
    "RULE_PROVENANCE_COVERAGE_MISMATCH",
    "RULE_PROVENANCE_READING_REVISION_MISSING",
    "RULE_PROVENANCE_READING_UNIT_MISSING",
    "RULE_TIMELINE_MISMATCH",
    "RULE_UNRESOLVED_TIMING",
    "SUBTITLE_VALIDATION_RESULT_KIND",
    "AtomicSubtitleValidationPersistence",
    "PreparedSubtitleValidation",
    "SubtitleReadingRevisionQuery",
    "SubtitleStructuralValidationError",
    "SubtitleStructuralValidationService",
    "SubtitleTimeRevisionQuery",
    "SubtitleValidation",
    "SubtitleValidationCategory",
    "SubtitleValidationFinding",
    "SubtitleValidationIdentityPlan",
    "diagnose_time_revision",
    "finding_identity",
]
