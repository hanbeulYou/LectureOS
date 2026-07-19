"""Transport-independent application boundaries."""

from dataclasses import dataclass
from typing import Protocol

from .identities import (
    ConfigurationReference,
    DomainResultId,
    FailureId,
    InputReference,
    ProcessingRunId,
    ProcessingUnitId,
    ReviewDecisionId,
    UnitExecutionId,
    WorkingContextReference,
)
from .models import DomainResultReference, ExecutionIntent, Failure, ProcessingRun, UnitExecution


@dataclass(frozen=True, slots=True)
class RequestAccepted:
    run_id: ProcessingRunId | None = None
    unit_execution_id: UnitExecutionId | None = None


class ProcessingRequestBoundary(Protocol):
    def start_run(
        self,
        *,
        run_id: ProcessingRunId,
        intent: ExecutionIntent,
        working_context: WorkingContextReference,
        unit_ids: tuple[ProcessingUnitId, ...] = (),
        inputs: tuple[InputReference, ...] = (),
        configuration: ConfigurationReference | None = None,
    ) -> RequestAccepted: ...

    def start_unit_execution(
        self,
        *,
        execution_id: UnitExecutionId,
        run_id: ProcessingRunId,
        unit_id: ProcessingUnitId,
    ) -> RequestAccepted: ...

    def retry_unit_execution(
        self,
        *,
        execution_id: UnitExecutionId,
        failed_execution_id: UnitExecutionId,
    ) -> RequestAccepted: ...

    def request_reprocessing(
        self,
        *,
        run_id: ProcessingRunId,
        previous_run_id: ProcessingRunId,
        intent: ExecutionIntent,
        working_context: WorkingContextReference,
    ) -> RequestAccepted: ...

    def cancel_unit_execution(self, execution_id: UnitExecutionId) -> None: ...


class AtomicStartExecutionPersistence(Protocol):
    """Application-owned port for storing final Start command snapshots."""

    def persist_started_execution(
        self,
        *,
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None: ...


class AtomicFailureExecutionPersistence(Protocol):
    """Application-owned port for storing final Record Failure outputs."""

    def persist_recorded_failure(
        self,
        *,
        failure: Failure,
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None: ...


class AtomicRetryExecutionPersistence(Protocol):
    """Application-owned port for storing final Retry command snapshots."""

    def persist_retried_execution(
        self,
        *,
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None: ...


class AtomicResultExecutionPersistence(Protocol):
    """Application-owned port for storing final Record Results outputs."""

    def persist_recorded_results(
        self,
        *,
        results: tuple[DomainResultReference, ...],
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None: ...


class ExecutionQueryBoundary(Protocol):
    def get_run(self, run_id: ProcessingRunId) -> ProcessingRun | None: ...

    def get_unit_execution(self, execution_id: UnitExecutionId) -> UnitExecution | None: ...

    def get_failure(self, failure_id: FailureId) -> Failure | None: ...

    def get_result_reference(self, result_id: DomainResultId) -> DomainResultReference | None: ...


class HumanDecisionBoundary(Protocol):
    """Separate authority boundary; execution services do not implement it."""

    def get_decision(self, decision_id: ReviewDecisionId) -> object | None: ...
