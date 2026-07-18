import inspect
import tempfile
import unittest
from pathlib import Path

import lectureos.execution.service as execution_service_module
from lectureos.composition import compose_sqlite_atomic_start_execution_service
from lectureos.execution.boundaries import AtomicStartExecutionPersistence
from lectureos.execution.identities import (
    CapabilityReference,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import (
    ExecutionIntent,
    ProcessingRun,
    ProcessingState,
    ProcessingUnit,
    UnitExecution,
)
from lectureos.execution.repositories import InMemoryRepository
from lectureos.execution.service import ExecutionService
from lectureos.execution.start_persistence import (
    InMemoryAtomicStartExecutionPersistence,
)
from lectureos.persistence import (
    PersistenceError,
    SQLiteProcessingRunRepository,
    SQLiteUnitExecutionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)


class RecordingRepository(InMemoryRepository):
    def __init__(self, name: str, log: list[str] | None = None) -> None:
        super().__init__()
        self.name = name
        self.log = log
        self.save_count = 0

    def save(self, record: object) -> None:
        self.save_count += 1
        if self.log is not None:
            self.log.append(self.name)
        super().save(record)


class RecordingAtomicStartPersistence:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[UnitExecution, ProcessingRun]] = []
        self.error = error

    def persist_started_execution(
        self,
        *,
        execution: UnitExecution,
        run: ProcessingRun,
    ) -> None:
        self.calls.append((execution, run))
        if self.error is not None:
            raise self.error


class ExecutionServiceAtomicStartWiringTests(unittest.TestCase):
    def _dependencies(self):
        runs = RecordingRepository("runs")
        units = RecordingRepository("units")
        executions = RecordingRepository("executions")
        return runs, units, executions

    def _seed_run_and_unit(
        self,
        runs: RecordingRepository,
        units: RecordingRepository,
    ) -> tuple[ProcessingRun, ProcessingUnit]:
        unit = ProcessingUnit(
            identity=ProcessingUnitId("unit-main"),
            purpose="Atomic Start unit",
            capabilities=(CapabilityReference("capability-main"),),
        )
        run = ProcessingRun(
            identity=ProcessingRunId("run-main"),
            intent=ExecutionIntent("Atomic Start run"),
            working_context=WorkingContextReference("context-main"),
            unit_references=(unit.identity,),
        )
        units.save(unit)
        runs.save(run)
        runs.save_count = 0
        units.save_count = 0
        return run, unit

    def test_service_computes_final_snapshots_and_calls_port_exactly_once(self) -> None:
        runs, units, executions = self._dependencies()
        run, unit = self._seed_run_and_unit(runs, units)
        atomic_start = RecordingAtomicStartPersistence()
        service = ExecutionService(
            runs=runs,
            units=units,
            executions=executions,
            atomic_start_persistence=atomic_start,
        )

        accepted = service.start_unit_execution(
            execution_id=UnitExecutionId("execution-main"),
            run_id=run.identity,
            unit_id=unit.identity,
        )

        self.assertEqual(accepted.run_id, run.identity)
        self.assertEqual(accepted.unit_execution_id, UnitExecutionId("execution-main"))
        self.assertEqual(len(atomic_start.calls), 1)
        execution, updated_run = atomic_start.calls[0]
        self.assertEqual(execution.run_id, run.identity)
        self.assertEqual(execution.unit_id, unit.identity)
        self.assertEqual(execution.capabilities, unit.capabilities)
        self.assertEqual(execution.state, ProcessingState.RUNNING)
        self.assertEqual(updated_run.state, ProcessingState.RUNNING)
        self.assertEqual(
            updated_run.unit_execution_references,
            (execution.identity,),
        )
        self.assertEqual(executions.save_count, 0)
        self.assertEqual(runs.save_count, 0)

    def test_persistence_failure_propagates_without_success_or_direct_saves(self) -> None:
        runs, units, executions = self._dependencies()
        run, unit = self._seed_run_and_unit(runs, units)
        expected = PersistenceError("injected persistence failure")
        atomic_start = RecordingAtomicStartPersistence(expected)
        service = ExecutionService(
            runs=runs,
            units=units,
            executions=executions,
            atomic_start_persistence=atomic_start,
        )

        with self.assertRaises(PersistenceError) as raised:
            service.start_unit_execution(
                execution_id=UnitExecutionId("execution-main"),
                run_id=run.identity,
                unit_id=unit.identity,
            )
        self.assertIs(raised.exception, expected)
        self.assertEqual(len(atomic_start.calls), 1)
        self.assertEqual(executions.save_count, 0)
        self.assertEqual(runs.save_count, 0)
        self.assertIsNone(executions.get(UnitExecutionId("execution-main")))
        self.assertEqual(runs.get(run.identity), run)

    def test_service_has_no_sqlite_dependency(self) -> None:
        source = inspect.getsource(execution_service_module)
        self.assertNotIn("sqlite", source.lower())
        self.assertNotIn("lectureos.persistence", source)

    def test_atomic_start_port_is_structurally_implemented(self) -> None:
        self.assertTrue(hasattr(AtomicStartExecutionPersistence, "persist_started_execution"))
        adapter = InMemoryAtomicStartExecutionPersistence(
            InMemoryRepository(),
            InMemoryRepository(),
        )
        self.assertTrue(callable(adapter.persist_started_execution))


class InMemoryAtomicStartPersistenceTests(unittest.TestCase):
    def test_adapter_preserves_execution_then_run_write_order(self) -> None:
        log: list[str] = []
        executions = RecordingRepository("executions", log)
        runs = RecordingRepository("runs", log)
        adapter = InMemoryAtomicStartExecutionPersistence(executions, runs)
        execution = UnitExecution(
            identity=UnitExecutionId("execution-main"),
            run_id=ProcessingRunId("run-main"),
            unit_id=ProcessingUnitId("unit-main"),
            state=ProcessingState.RUNNING,
        )
        run = ProcessingRun(
            identity=execution.run_id,
            intent=ExecutionIntent("In-memory adapter"),
            working_context=WorkingContextReference("context-main"),
            state=ProcessingState.RUNNING,
            unit_execution_references=(execution.identity,),
        )

        adapter.persist_started_execution(execution=execution, run=run)

        self.assertEqual(log, ["executions", "runs"])
        self.assertEqual(executions.get(execution.identity), execution)
        self.assertEqual(runs.get(run.identity), run)

    def test_default_service_preserves_existing_in_memory_behavior(self) -> None:
        service = ExecutionService()
        unit = ProcessingUnit(ProcessingUnitId("unit-main"), "Default adapter")
        service.register_unit(unit)
        run_id = ProcessingRunId("run-main")
        service.start_run(
            run_id=run_id,
            intent=ExecutionIntent("Default adapter"),
            working_context=WorkingContextReference("context-main"),
            unit_ids=(unit.identity,),
        )
        execution_id = UnitExecutionId("execution-main")

        service.start_unit_execution(
            execution_id=execution_id,
            run_id=run_id,
            unit_id=unit.identity,
        )

        self.assertEqual(
            service.get_unit_execution(execution_id).state,
            ProcessingState.RUNNING,
        )
        self.assertEqual(
            service.get_run(run_id).unit_execution_references,
            (execution_id,),
        )


class SQLiteAtomicStartCompositionTests(unittest.TestCase):
    def test_composition_shares_one_connection_and_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "lectureos.sqlite3"
            connection = initialize_sqlite_database(database_path)
            service = compose_sqlite_atomic_start_execution_service(connection)
            unit = ProcessingUnit(
                identity=ProcessingUnitId("unit-main"),
                purpose="SQLite composed unit",
                capabilities=(CapabilityReference("capability-main"),),
            )
            service.register_unit(unit)
            run_id = ProcessingRunId("run-main")
            service.start_run(
                run_id=run_id,
                intent=ExecutionIntent("SQLite composed run"),
                working_context=WorkingContextReference("context-main"),
                unit_ids=(unit.identity,),
            )
            execution_id = UnitExecutionId("execution-main")
            service.start_unit_execution(
                execution_id=execution_id,
                run_id=run_id,
                unit_id=unit.identity,
            )
            expected_execution = service.get_unit_execution(execution_id)
            expected_run = service.get_run(run_id)
            self.assertIsNotNone(expected_execution)
            self.assertIn(execution_id, expected_run.unit_execution_references)
            self.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))
            connection.close()

            reopened = open_sqlite_database(database_path)
            try:
                self.assertEqual(
                    SQLiteUnitExecutionRepository(reopened).get(execution_id),
                    expected_execution,
                )
                self.assertEqual(
                    SQLiteProcessingRunRepository(reopened).get(run_id),
                    expected_run,
                )
            finally:
                reopened.close()


if __name__ == "__main__":
    unittest.main()
