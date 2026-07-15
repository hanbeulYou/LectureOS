"""Execution-domain records with identities separated from runtime implementation."""

from dataclasses import dataclass
from enum import Enum

from .identities import (
    CapabilityReference,
    ConfigurationReference,
    DiagnosticId,
    DomainResultId,
    FailureId,
    InputReference,
    PluginReference,
    ProcessingRunId,
    ProcessingUnitId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)


class ProcessingState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutcomeKind(str, Enum):
    DOMAIN_RESULT_GENERATED = "domain_result_generated"
    PARTIAL_RESULT = "partial_result"
    NO_RESULT = "no_result"
    VALIDATION_FAILURE = "validation_failure"
    RECOVERABLE_FAILURE = "recoverable_failure"
    NON_RECOVERABLE_CONDITION = "non_recoverable_condition"


class FailureCategory(str, Enum):
    PREPARATION = "preparation"
    CAPABILITY = "capability"
    PROVIDER_OR_PLUGIN = "provider_or_plugin"
    PROCESSING = "processing"
    VALIDATION = "validation"
    PERSISTENCE = "persistence"
    REVIEW_BLOCKING = "review_blocking"
    EXPORT = "export"
    EXTERNAL_CONSUMER = "external_consumer"


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    purpose: str
    retry_of: UnitExecutionId | None = None
    reprocessing_of: ProcessingRunId | None = None

    def __post_init__(self) -> None:
        if not self.purpose.strip():
            raise ValueError("execution intent purpose must not be empty")
        if self.retry_of is not None and self.reprocessing_of is not None:
            raise ValueError("retry and reprocessing relationships are distinct")


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    kind: OutcomeKind
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessingUnit:
    """Reusable logical responsibility, never a run-scoped execution instance."""

    identity: ProcessingUnitId
    purpose: str
    dependencies: tuple[ProcessingUnitId, ...] = ()
    capabilities: tuple[CapabilityReference, ...] = ()
    result_kinds: tuple[str, ...] = ()
    independently_retryable: bool = True

    def __post_init__(self) -> None:
        if not self.purpose.strip():
            raise ValueError("processing unit purpose must not be empty")


@dataclass(frozen=True, slots=True)
class DomainResultReference:
    """Reference boundary for a concrete pipeline result defined elsewhere."""

    identity: DomainResultId
    kind: str
    source_media: SourceMediaId | None = None
    source_timeline: SourceTimelineId | None = None
    upstream_results: tuple[DomainResultId, ...] = ()
    revision_of: DomainResultId | None = None
    applicability: str | None = None

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("domain result kind must not be empty")


@dataclass(frozen=True, slots=True)
class Diagnostic:
    identity: DiagnosticId
    summary: str

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("diagnostic summary must not be empty")


@dataclass(frozen=True, slots=True)
class Failure:
    identity: FailureId
    category: FailureCategory
    run_id: ProcessingRunId | None = None
    unit_execution_id: UnitExecutionId | None = None
    affected_inputs: tuple[InputReference, ...] = ()
    affected_results: tuple[DomainResultId, ...] = ()
    retryable: bool = False
    reprocessing_required: bool = False
    human_action_required: bool = False
    diagnostics: tuple[DiagnosticId, ...] = ()

    def __post_init__(self) -> None:
        if self.run_id is None and self.unit_execution_id is None:
            raise ValueError("failure must reference a run or unit execution")


@dataclass(frozen=True, slots=True)
class UnitExecution:
    """A single run-scoped execution of a logical ProcessingUnit."""

    identity: UnitExecutionId
    run_id: ProcessingRunId
    unit_id: ProcessingUnitId
    input_references: tuple[InputReference, ...] = ()
    configuration: ConfigurationReference | None = None
    capabilities: tuple[CapabilityReference, ...] = ()
    plugins: tuple[PluginReference, ...] = ()
    state: ProcessingState = ProcessingState.PENDING
    outcome: ExecutionOutcome | None = None
    result_references: tuple[DomainResultId, ...] = ()
    failure_references: tuple[FailureId, ...] = ()
    diagnostic_references: tuple[DiagnosticId, ...] = ()
    retry_of: UnitExecutionId | None = None
    cancelled_from: UnitExecutionId | None = None
    recovery_of: UnitExecutionId | None = None


@dataclass(frozen=True, slots=True)
class ProcessingRun:
    """Persistent execution context that references, but does not own, results."""

    identity: ProcessingRunId
    intent: ExecutionIntent
    working_context: WorkingContextReference
    input_references: tuple[InputReference, ...] = ()
    upstream_results: tuple[DomainResultId, ...] = ()
    configuration: ConfigurationReference | None = None
    unit_references: tuple[ProcessingUnitId, ...] = ()
    unit_execution_references: tuple[UnitExecutionId, ...] = ()
    state: ProcessingState = ProcessingState.PENDING
    result_references: tuple[DomainResultId, ...] = ()
    failure_references: tuple[FailureId, ...] = ()
    reprocessing_of: ProcessingRunId | None = None
