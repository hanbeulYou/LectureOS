"""Minimal execution application service without transport or runtime assumptions."""

from dataclasses import replace

from .boundaries import (
    AtomicFailureExecutionPersistence,
    AtomicStartExecutionPersistence,
    RequestAccepted,
)
from .identities import (
    ConfigurationReference,
    DomainResultId,
    FailureId,
    InputReference,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
    WorkingContextReference,
)
from .models import (
    DomainResultReference,
    ExecutionIntent,
    ExecutionOutcome,
    Failure,
    OutcomeKind,
    ProcessingRun,
    ProcessingState,
    ProcessingUnit,
    UnitExecution,
)
from .repositories import (
    DomainResultReferenceRepository,
    FailureRepository,
    InMemoryRepository,
    ProcessingRunRepository,
    ProcessingUnitRepository,
    UnitExecutionRepository,
)
from .start_persistence import InMemoryAtomicStartExecutionPersistence
from .failure_persistence import InMemoryAtomicFailureExecutionPersistence


class ExecutionService:
    def __init__(
        self,
        *,
        runs: ProcessingRunRepository | None = None,
        units: ProcessingUnitRepository | None = None,
        executions: UnitExecutionRepository | None = None,
        results: DomainResultReferenceRepository | None = None,
        failures: FailureRepository | None = None,
        atomic_start_persistence: AtomicStartExecutionPersistence | None = None,
        atomic_failure_persistence: AtomicFailureExecutionPersistence | None = None,
    ) -> None:
        self.runs = runs if runs is not None else InMemoryRepository()
        self.units = units if units is not None else InMemoryRepository()
        self.executions = executions if executions is not None else InMemoryRepository()
        self.results = results if results is not None else InMemoryRepository()
        self.failures = failures if failures is not None else InMemoryRepository()
        self._atomic_start_persistence = (
            atomic_start_persistence
            if atomic_start_persistence is not None
            else InMemoryAtomicStartExecutionPersistence(
                self.executions,
                self.runs,
            )
        )
        self._atomic_failure_persistence = (
            atomic_failure_persistence
            if atomic_failure_persistence is not None
            else InMemoryAtomicFailureExecutionPersistence(
                self.failures,
                self.executions,
                self.runs,
            )
        )

    def register_unit(self, unit: ProcessingUnit) -> None:
        self.units.save(unit)

    def start_run(
        self,
        *,
        run_id: ProcessingRunId,
        intent: ExecutionIntent,
        working_context: WorkingContextReference,
        unit_ids: tuple[ProcessingUnitId, ...] = (),
        inputs: tuple[InputReference, ...] = (),
        configuration: ConfigurationReference | None = None,
    ) -> RequestAccepted:
        if self.runs.get(run_id) is not None:
            raise ValueError("processing run identity already exists")
        for unit_id in unit_ids:
            self._require_unit(unit_id)
        run = ProcessingRun(
            identity=run_id,
            intent=intent,
            working_context=working_context,
            unit_references=unit_ids,
            input_references=inputs,
            configuration=configuration,
        )
        self.runs.save(run)
        return RequestAccepted(run_id=run_id)

    def start_unit_execution(
        self,
        *,
        execution_id: UnitExecutionId,
        run_id: ProcessingRunId,
        unit_id: ProcessingUnitId,
    ) -> RequestAccepted:
        if self.executions.get(execution_id) is not None:
            raise ValueError("unit execution identity already exists")
        run = self._require_run(run_id)
        unit = self._require_unit(unit_id)
        execution = UnitExecution(
            identity=execution_id,
            run_id=run_id,
            unit_id=unit_id,
            configuration=run.configuration,
            capabilities=unit.capabilities,
            state=ProcessingState.RUNNING,
        )
        updated_run = replace(
            run,
            state=ProcessingState.RUNNING,
            unit_execution_references=run.unit_execution_references + (execution_id,),
        )
        self._atomic_start_persistence.persist_started_execution(
            execution=execution,
            run=updated_run,
        )
        return RequestAccepted(run_id=run_id, unit_execution_id=execution_id)

    def record_results(
        self,
        execution_id: UnitExecutionId,
        results: tuple[DomainResultReference, ...],
        *,
        partial: bool = False,
    ) -> None:
        execution = self._require_execution(execution_id)
        self._require_running(execution, "record results")
        if not results:
            raise ValueError("at least one domain result is required")
        result_ids = tuple(result.identity for result in results)
        if len(set(result_ids)) != len(result_ids):
            raise ValueError("domain result identities must be unique")
        if any(self.results.get(result_id) is not None for result_id in result_ids):
            raise ValueError("domain result identity already exists")
        run = self._require_run(execution.run_id)
        for result in results:
            self.results.save(result)
        outcome_kind = OutcomeKind.PARTIAL_RESULT if partial else OutcomeKind.DOMAIN_RESULT_GENERATED
        self.executions.save(
            replace(
                execution,
                state=ProcessingState.COMPLETED,
                outcome=ExecutionOutcome(outcome_kind),
                result_references=execution.result_references + result_ids,
            )
        )
        self.runs.save(replace(run, result_references=run.result_references + result_ids))

    def record_failure(self, execution_id: UnitExecutionId, failure: Failure) -> None:
        execution = self._require_execution(execution_id)
        self._require_running(execution, "record failure")
        if failure.unit_execution_id != execution_id:
            raise ValueError("failure must reference the affected unit execution")
        if failure.run_id is not None and failure.run_id != execution.run_id:
            raise ValueError("failure run must match the affected unit execution")
        if self.failures.get(failure.identity) is not None:
            raise ValueError("failure identity already exists")
        run = self._require_run(execution.run_id)
        outcome = (
            OutcomeKind.RECOVERABLE_FAILURE
            if failure.retryable
            else OutcomeKind.NON_RECOVERABLE_CONDITION
        )
        failed_execution = replace(
            execution,
            state=ProcessingState.FAILED,
            outcome=ExecutionOutcome(outcome),
            failure_references=execution.failure_references + (failure.identity,),
        )
        updated_run = replace(
            run,
            failure_references=run.failure_references + (failure.identity,),
        )
        self._atomic_failure_persistence.persist_recorded_failure(
            failure=failure,
            execution=failed_execution,
            run=updated_run,
        )

    def retry_unit_execution(
        self,
        *,
        execution_id: UnitExecutionId,
        failed_execution_id: UnitExecutionId,
    ) -> RequestAccepted:
        previous = self._require_execution(failed_execution_id)
        if previous.state is not ProcessingState.FAILED:
            raise ValueError("only a failed unit execution can be retried")
        if not previous.failure_references:
            raise ValueError("failed unit execution has no failure record")
        failures = tuple(self.failures.get(failure_id) for failure_id in previous.failure_references)
        if not any(failure is not None and failure.retryable for failure in failures):
            raise ValueError("failed unit execution has no retryable failure")
        accepted = self.start_unit_execution(
            execution_id=execution_id,
            run_id=previous.run_id,
            unit_id=previous.unit_id,
        )
        created = self._require_execution(execution_id)
        self.executions.save(replace(created, retry_of=failed_execution_id))
        return accepted

    def request_reprocessing(
        self,
        *,
        run_id: ProcessingRunId,
        previous_run_id: ProcessingRunId,
        intent: ExecutionIntent,
        working_context: WorkingContextReference,
    ) -> RequestAccepted:
        self._require_run(previous_run_id)
        accepted = self.start_run(
            run_id=run_id,
            intent=intent,
            working_context=working_context,
        )
        created = self._require_run(run_id)
        self.runs.save(replace(created, reprocessing_of=previous_run_id))
        return accepted

    def cancel_unit_execution(self, execution_id: UnitExecutionId) -> None:
        execution = self._require_execution(execution_id)
        self._require_running(execution, "cancel")
        self.executions.save(replace(execution, state=ProcessingState.CANCELLED))

    def get_run(self, run_id: ProcessingRunId) -> ProcessingRun | None:
        return self.runs.get(run_id)

    def get_unit_execution(self, execution_id: UnitExecutionId) -> UnitExecution | None:
        return self.executions.get(execution_id)

    def get_failure(self, failure_id: FailureId) -> Failure | None:
        return self.failures.get(failure_id)

    def get_result_reference(self, result_id: DomainResultId) -> DomainResultReference | None:
        return self.results.get(result_id)

    def _require_run(self, run_id: ProcessingRunId) -> ProcessingRun:
        run = self.runs.get(run_id)
        if run is None:
            raise KeyError(f"unknown processing run: {run_id.value}")
        return run

    def _require_unit(self, unit_id: ProcessingUnitId) -> ProcessingUnit:
        unit = self.units.get(unit_id)
        if unit is None:
            raise KeyError(f"unknown processing unit: {unit_id.value}")
        return unit

    def _require_execution(self, execution_id: UnitExecutionId) -> UnitExecution:
        execution = self.executions.get(execution_id)
        if execution is None:
            raise KeyError(f"unknown unit execution: {execution_id.value}")
        return execution

    @staticmethod
    def _require_running(execution: UnitExecution, action: str) -> None:
        if execution.state is not ProcessingState.RUNNING:
            raise ValueError(
                f"cannot {action} for unit execution in {execution.state.value} state"
            )
