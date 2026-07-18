"""Default in-memory implementation of the atomic Start persistence port."""

from .models import ProcessingRun, UnitExecution
from .repositories import ProcessingRunRepository, UnitExecutionRepository


class InMemoryAtomicStartExecutionPersistence:
    """Preserve the existing in-process write order without storage mechanics."""

    def __init__(
        self,
        executions: UnitExecutionRepository,
        runs: ProcessingRunRepository,
    ) -> None:
        self._executions = executions
        self._runs = runs

    def persist_started_execution(
        self,
        *,
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None:
        self._executions.save(execution)
        self._runs.save(run)
