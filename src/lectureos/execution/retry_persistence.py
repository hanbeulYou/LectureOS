"""Default in-memory implementation of the atomic Retry persistence port."""

from .models import ProcessingRun, UnitExecution
from .repositories import ProcessingRunRepository, UnitExecutionRepository


class InMemoryAtomicRetryExecutionPersistence:
    """Preserve in-process Retry behavior behind one command boundary."""

    def __init__(
        self,
        executions: UnitExecutionRepository,
        runs: ProcessingRunRepository,
    ) -> None:
        self._executions = executions
        self._runs = runs

    def persist_retried_execution(
        self,
        *,
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None:
        if self._executions.get(execution.identity) is not None:
            raise ValueError("unit execution identity already exists")
        self._executions.save(execution)
        self._runs.save(run)
