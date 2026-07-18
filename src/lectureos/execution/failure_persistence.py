"""Default in-memory implementation of the atomic Failure persistence port."""

from .models import Failure, ProcessingRun, UnitExecution
from .repositories import (
    FailureRepository,
    ProcessingRunRepository,
    UnitExecutionRepository,
)


class InMemoryAtomicFailureExecutionPersistence:
    """Preserve in-process behavior behind one Application command boundary."""

    def __init__(
        self,
        failures: FailureRepository,
        executions: UnitExecutionRepository,
        runs: ProcessingRunRepository,
    ) -> None:
        self._failures = failures
        self._executions = executions
        self._runs = runs

    def persist_recorded_failure(
        self,
        *,
        failure: Failure,
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None:
        self._failures.save(failure)
        self._executions.save(execution)
        self._runs.save(run)
