"""Default in-memory implementation of the atomic Result persistence port."""

from .models import DomainResultReference, ProcessingRun, UnitExecution
from .repositories import (
    DomainResultReferenceRepository,
    ProcessingRunRepository,
    UnitExecutionRepository,
)


class InMemoryAtomicResultExecutionPersistence:
    """Preserve in-process Result behavior behind one command boundary."""

    def __init__(
        self,
        results: DomainResultReferenceRepository,
        executions: UnitExecutionRepository,
        runs: ProcessingRunRepository,
    ) -> None:
        self._results = results
        self._executions = executions
        self._runs = runs

    def persist_recorded_results(
        self,
        *,
        results: tuple[DomainResultReference, ...],
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None:
        for result in results:
            self._results.save(result)
        self._executions.save(execution)
        self._runs.save(run)
