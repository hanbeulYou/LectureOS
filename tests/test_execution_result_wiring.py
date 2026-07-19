import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lectureos.composition import compose_sqlite_execution_service
from lectureos.execution import InMemoryAtomicResultExecutionPersistence
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    ProcessingUnitId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import (
    DomainResultReference,
    ExecutionIntent,
    OutcomeKind,
    ProcessingRun,
    ProcessingState,
    ProcessingUnit,
    UnitExecution,
)
from lectureos.execution.repositories import InMemoryRepository
from lectureos.execution.service import ExecutionService
from lectureos.persistence import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
    SQLiteDomainResultReferenceRepository,
    SQLiteProcessingRunRepository,
    SQLiteUnitExecutionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)


class RecordingRepository(InMemoryRepository):
    def __init__(self, name: str = "repository", events: list | None = None) -> None:
        super().__init__()
        self.name = name
        self.events = events
        self.save_calls = []

    def save(self, record) -> None:
        self.save_calls.append(record)
        if self.events is not None:
            self.events.append((self.name, record))
        super().save(record)


class RecordingAtomicResultPersistence:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls = []
        self.error = error

    def persist_recorded_results(self, *, results, execution, run) -> None:
        self.calls.append((results, execution, run))
        if self.error is not None:
            raise self.error


class ExecutionServiceResultWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runs = RecordingRepository()
        self.units = RecordingRepository()
        self.executions = RecordingRepository()
        self.results_repository = RecordingRepository()
        self.atomic_result = RecordingAtomicResultPersistence()
        self.service = ExecutionService(
            runs=self.runs,
            units=self.units,
            executions=self.executions,
            results=self.results_repository,
            atomic_result_persistence=self.atomic_result,
        )
        self.run = ProcessingRun(
            identity=ProcessingRunId("run-main"),
            intent=ExecutionIntent("Result wiring fixture"),
            working_context=WorkingContextReference("context-main"),
            unit_references=(ProcessingUnitId("unit-main"),),
            unit_execution_references=(UnitExecutionId("execution-main"),),
            state=ProcessingState.RUNNING,
            result_references=(DomainResultId("result-existing"),),
        )
        self.execution = UnitExecution(
            identity=UnitExecutionId("execution-main"),
            run_id=self.run.identity,
            unit_id=ProcessingUnitId("unit-main"),
            state=ProcessingState.RUNNING,
            result_references=(DomainResultId("result-existing"),),
        )
        self.results = (
            DomainResultReference(
                identity=DomainResultId("result-z"),
                kind="transcript",
                source_media=SourceMediaId("media-main"),
                upstream_results=(DomainResultId("upstream-z"),),
            ),
            DomainResultReference(
                identity=DomainResultId("result-a"),
                kind="subtitle",
                source_timeline=SourceTimelineId("timeline-main"),
                applicability="final",
            ),
        )
        self.runs.save(self.run)
        self.executions.save(self.execution)
        self.runs.save_calls.clear()
        self.executions.save_calls.clear()
        self.results_repository.save_calls.clear()

    def test_service_computes_final_records_and_invokes_atomic_port_once(self) -> None:
        returned = self.service.record_results(self.execution.identity, self.results)
        self.assertIsNone(returned)
        self.assertEqual(len(self.atomic_result.calls), 1)
        results, execution, run = self.atomic_result.calls[0]
        result_ids = tuple(result.identity for result in self.results)
        self.assertIs(results, self.results)
        self.assertEqual(execution.identity, self.execution.identity)
        self.assertEqual(execution.run_id, self.execution.run_id)
        self.assertEqual(execution.unit_id, self.execution.unit_id)
        self.assertEqual(execution.state, ProcessingState.COMPLETED)
        self.assertEqual(execution.outcome.kind, OutcomeKind.DOMAIN_RESULT_GENERATED)
        self.assertEqual(
            execution.result_references,
            self.execution.result_references + result_ids,
        )
        self.assertEqual(run.identity, self.run.identity)
        self.assertEqual(
            run.result_references,
            self.run.result_references + result_ids,
        )
        self.assertEqual(self.results_repository.save_calls, [])
        self.assertEqual(self.executions.save_calls, [])
        self.assertEqual(self.runs.save_calls, [])

    def test_partial_outcome_and_every_result_field_are_preserved(self) -> None:
        self.service.record_results(self.execution.identity, self.results, partial=True)
        results, execution, _ = self.atomic_result.calls[0]
        self.assertEqual(execution.outcome.kind, OutcomeKind.PARTIAL_RESULT)
        self.assertIs(results, self.results)
        self.assertEqual(results[0].source_media, SourceMediaId("media-main"))
        self.assertEqual(results[0].upstream_results, (DomainResultId("upstream-z"),))
        self.assertEqual(results[1].source_timeline, SourceTimelineId("timeline-main"))
        self.assertEqual(results[1].applicability, "final")

    def test_every_validation_error_precedes_atomic_persistence(self) -> None:
        existing = self.results[0]
        cases = []
        cases.append((replace(self.execution, state=ProcessingState.COMPLETED), self.results))
        cases.append((self.execution, ()))
        cases.append((self.execution, (self.results[0], self.results[0])))
        for execution, results in cases:
            with self.subTest(execution=execution, results=results):
                self.executions.save(execution)
                self.executions.save_calls.clear()
                with self.assertRaises(ValueError):
                    self.service.record_results(execution.identity, results)
                self.assertEqual(self.atomic_result.calls, [])
                self.assertEqual(self.results_repository.save_calls, [])
                self.assertEqual(self.executions.save_calls, [])
                self.assertEqual(self.runs.save_calls, [])
                self.executions.save(self.execution)
                self.executions.save_calls.clear()
        self.results_repository.save(existing)
        self.results_repository.save_calls.clear()
        with self.assertRaises(ValueError):
            self.service.record_results(self.execution.identity, self.results)
        self.assertEqual(self.atomic_result.calls, [])
        self.assertEqual(self.results_repository.save_calls, [])

    def test_each_persistence_error_propagates_without_fallback_writes(self) -> None:
        errors = (
            PersistenceError("injected persistence failure"),
            PersistenceIdentityCollisionError("injected collision"),
            SchemaFeatureUnavailableError("injected feature gate"),
        )
        for error in errors:
            with self.subTest(error=error):
                atomic = RecordingAtomicResultPersistence(error)
                service = ExecutionService(
                    runs=self.runs,
                    units=self.units,
                    executions=self.executions,
                    results=self.results_repository,
                    atomic_result_persistence=atomic,
                )
                with self.assertRaises(type(error)):
                    service.record_results(self.execution.identity, self.results)
                self.assertEqual(len(atomic.calls), 1)
                self.assertEqual(self.results_repository.save_calls, [])
                self.assertEqual(self.executions.save_calls, [])
                self.assertEqual(self.runs.save_calls, [])
                self.assertEqual(self.executions.get(self.execution.identity), self.execution)
                self.assertEqual(self.runs.get(self.run.identity), self.run)

    def test_default_in_memory_adapter_preserves_write_order(self) -> None:
        events = []
        results = RecordingRepository("result", events)
        executions = RecordingRepository("execution", events)
        runs = RecordingRepository("run", events)
        adapter = InMemoryAtomicResultExecutionPersistence(results, executions, runs)
        adapter.persist_recorded_results(
            results=self.results,
            execution=self.execution,
            run=self.run,
        )
        self.assertEqual(
            [name for name, _ in events],
            ["result", "result", "execution", "run"],
        )


class SQLiteExecutionServiceResultIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.service = compose_sqlite_execution_service(self.connection)
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("unit-main"),
            purpose="Terminal Result integration fixture",
        )
        self.run_id = ProcessingRunId("run-main")
        self.execution_id = UnitExecutionId("execution-main")
        self.service.register_unit(self.unit)
        self.service.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("Terminal Result integration"),
            working_context=WorkingContextReference("context-main"),
            unit_ids=(self.unit.identity,),
        )
        self.service.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit.identity,
        )
        self.initial_execution = self.service.get_unit_execution(self.execution_id)
        self.initial_run = self.service.get_run(self.run_id)
        self.results = (
            DomainResultReference(
                DomainResultId("result-z"),
                "transcript",
                upstream_results=(DomainResultId("upstream-z"),),
            ),
            DomainResultReference(DomainResultId("result-a"), "subtitle"),
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def test_public_service_durably_records_results_and_restarts(self) -> None:
        self.service.record_results(self.execution_id, self.results)
        expected_execution = self.service.get_unit_execution(self.execution_id)
        expected_run = self.service.get_run(self.run_id)
        for result in self.results:
            self.assertEqual(self.service.get_result_reference(result.identity), result)
        self.assertEqual(expected_execution.state, ProcessingState.COMPLETED)
        self.assertEqual(
            expected_execution.result_references,
            tuple(result.identity for result in self.results),
        )
        self.assertEqual(expected_run.result_references, expected_execution.result_references)

        self.connection.close()
        self.connection = open_sqlite_database(self.database_path)
        results_repository = SQLiteDomainResultReferenceRepository(self.connection)
        executions = SQLiteUnitExecutionRepository(self.connection)
        runs = SQLiteProcessingRunRepository(self.connection)
        for result in self.results:
            self.assertEqual(results_repository.get(result.identity), result)
        self.assertEqual(executions.get(self.execution_id), expected_execution)
        self.assertEqual(runs.get(self.run_id), expected_run)

    def test_service_write_and_commit_failures_roll_back_complete_command(self) -> None:
        failures = (
            patch(
                "lectureos.persistence.execution_commands._write_processing_run_snapshot",
                side_effect=sqlite3.OperationalError("injected run failure"),
            ),
            patch(
                "lectureos.persistence.execution_commands.SQLiteExecutionCommandPersistence._commit",
                side_effect=sqlite3.OperationalError("injected commit failure"),
            ),
        )
        for injected_failure in failures:
            with self.subTest(injected_failure=injected_failure):
                with injected_failure:
                    with self.assertRaises(PersistenceError):
                        self.service.record_results(self.execution_id, self.results)
                self._assert_original_state()

    def _assert_original_state(self) -> None:
        repository = SQLiteDomainResultReferenceRepository(self.connection)
        for result in self.results:
            self.assertIsNone(repository.get(result.identity))
        self.assertEqual(
            SQLiteUnitExecutionRepository(self.connection).get(self.execution_id),
            self.initial_execution,
        )
        self.assertEqual(
            SQLiteProcessingRunRepository(self.connection).get(self.run_id),
            self.initial_run,
        )
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))


if __name__ == "__main__":
    unittest.main()
