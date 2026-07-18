import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lectureos.composition import compose_sqlite_atomic_failure_execution_service
from lectureos.execution.identities import (
    DiagnosticId,
    DomainResultId,
    FailureId,
    InputReference,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import (
    ExecutionIntent,
    Failure,
    FailureCategory,
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
    SQLiteFailureRepository,
    SQLiteProcessingRunRepository,
    SQLiteUnitExecutionRepository,
    SchemaFeatureUnavailableError,
    initialize_sqlite_database,
    open_sqlite_database,
)


class RecordingRepository(InMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.save_calls = []

    def save(self, record) -> None:
        self.save_calls.append(record)
        super().save(record)


class RecordingAtomicFailurePersistence:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls = []
        self.error = error

    def persist_recorded_failure(self, *, failure, execution, run) -> None:
        self.calls.append((failure, execution, run))
        if self.error is not None:
            raise self.error


class ExecutionServiceFailureWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runs = RecordingRepository()
        self.units = RecordingRepository()
        self.executions = RecordingRepository()
        self.failures = RecordingRepository()
        self.atomic_failure = RecordingAtomicFailurePersistence()
        self.service = ExecutionService(
            runs=self.runs,
            units=self.units,
            executions=self.executions,
            failures=self.failures,
            atomic_failure_persistence=self.atomic_failure,
        )
        self.run = ProcessingRun(
            identity=ProcessingRunId("run-main"),
            intent=ExecutionIntent("Failure wiring fixture"),
            working_context=WorkingContextReference("context-main"),
            unit_references=(ProcessingUnitId("unit-main"),),
            unit_execution_references=(UnitExecutionId("execution-main"),),
            state=ProcessingState.RUNNING,
            failure_references=(FailureId("failure-existing"),),
        )
        self.execution = UnitExecution(
            identity=UnitExecutionId("execution-main"),
            run_id=self.run.identity,
            unit_id=ProcessingUnitId("unit-main"),
            state=ProcessingState.RUNNING,
            result_references=(DomainResultId("result-existing"),),
            failure_references=(FailureId("failure-existing"),),
        )
        self.failure = Failure(
            identity=FailureId("failure-new"),
            category=FailureCategory.PROVIDER_OR_PLUGIN,
            run_id=self.run.identity,
            unit_execution_id=self.execution.identity,
            affected_inputs=(InputReference("input-b"), InputReference("input-a")),
            affected_results=(DomainResultId("result-b"), DomainResultId("result-a")),
            retryable=True,
            reprocessing_required=True,
            human_action_required=False,
            diagnostics=(DiagnosticId("diagnostic-b"), DiagnosticId("diagnostic-a")),
        )
        self.runs.save(self.run)
        self.executions.save(self.execution)
        self.runs.save_calls.clear()
        self.executions.save_calls.clear()
        self.failures.save_calls.clear()

    def test_service_computes_final_records_and_invokes_atomic_port_once(self) -> None:
        result = self.service.record_failure(self.execution.identity, self.failure)
        self.assertIsNone(result)
        self.assertEqual(len(self.atomic_failure.calls), 1)
        failure, execution, run = self.atomic_failure.calls[0]
        self.assertEqual(failure, self.failure)
        self.assertEqual(execution.identity, self.execution.identity)
        self.assertEqual(execution.run_id, self.execution.run_id)
        self.assertEqual(execution.unit_id, self.execution.unit_id)
        self.assertEqual(execution.result_references, self.execution.result_references)
        self.assertEqual(execution.state, ProcessingState.FAILED)
        self.assertEqual(execution.outcome.kind, OutcomeKind.RECOVERABLE_FAILURE)
        self.assertEqual(
            execution.failure_references,
            self.execution.failure_references + (self.failure.identity,),
        )
        self.assertEqual(
            run.failure_references,
            self.run.failure_references + (self.failure.identity,),
        )
        self.assertEqual(run.state, self.run.state)
        self.assertEqual(self.failures.save_calls, [])
        self.assertEqual(self.executions.save_calls, [])
        self.assertEqual(self.runs.save_calls, [])

    def test_failure_fields_are_forwarded_without_reconstruction(self) -> None:
        self.service.record_failure(self.execution.identity, self.failure)
        supplied = self.atomic_failure.calls[0][0]
        self.assertIs(supplied, self.failure)
        self.assertEqual(supplied.category, FailureCategory.PROVIDER_OR_PLUGIN)
        self.assertEqual(supplied.run_id, self.run.identity)
        self.assertEqual(supplied.unit_execution_id, self.execution.identity)
        self.assertEqual(supplied.affected_inputs, self.failure.affected_inputs)
        self.assertEqual(supplied.affected_results, self.failure.affected_results)
        self.assertIs(supplied.retryable, True)
        self.assertIs(supplied.reprocessing_required, True)
        self.assertIs(supplied.human_action_required, False)
        self.assertEqual(supplied.diagnostics, self.failure.diagnostics)

    def test_non_retryable_failure_preserves_existing_outcome_rule(self) -> None:
        failure = replace(self.failure, retryable=False)
        self.service.record_failure(self.execution.identity, failure)
        supplied_execution = self.atomic_failure.calls[0][1]
        self.assertEqual(
            supplied_execution.outcome.kind,
            OutcomeKind.NON_RECOVERABLE_CONDITION,
        )

    def test_lifecycle_and_provenance_errors_precede_atomic_persistence(self) -> None:
        invalid_cases = (
            (
                replace(self.execution, state=ProcessingState.COMPLETED),
                self.failure,
            ),
            (
                replace(self.execution, state=ProcessingState.FAILED),
                self.failure,
            ),
            (
                self.execution,
                replace(
                    self.failure,
                    unit_execution_id=UnitExecutionId("another-execution"),
                ),
            ),
            (
                self.execution,
                replace(self.failure, run_id=ProcessingRunId("another-run")),
            ),
        )
        for execution, failure in invalid_cases:
            with self.subTest(execution=execution, failure=failure):
                self.executions.save(execution)
                self.executions.save_calls.clear()
                with self.assertRaises(ValueError):
                    self.service.record_failure(execution.identity, failure)
                self.assertEqual(self.atomic_failure.calls, [])
                self.assertEqual(self.failures.save_calls, [])
                self.assertEqual(self.executions.save_calls, [])
                self.assertEqual(self.runs.save_calls, [])
                self.executions.save(self.execution)
                self.executions.save_calls.clear()

    def test_each_persistence_error_propagates_without_fallback_writes(self) -> None:
        errors = (
            PersistenceError("injected persistence failure"),
            PersistenceIdentityCollisionError("injected collision"),
            SchemaFeatureUnavailableError("injected feature gate"),
        )
        for error in errors:
            with self.subTest(error=error):
                atomic = RecordingAtomicFailurePersistence(error)
                service = ExecutionService(
                    runs=self.runs,
                    units=self.units,
                    executions=self.executions,
                    failures=self.failures,
                    atomic_failure_persistence=atomic,
                )
                with self.assertRaises(type(error)):
                    service.record_failure(self.execution.identity, self.failure)
                self.assertEqual(len(atomic.calls), 1)
                self.assertEqual(self.failures.save_calls, [])
                self.assertEqual(self.executions.save_calls, [])
                self.assertEqual(self.runs.save_calls, [])
                self.assertEqual(self.executions.get(self.execution.identity), self.execution)
                self.assertEqual(self.runs.get(self.run.identity), self.run)


class SQLiteExecutionServiceFailureIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.service = compose_sqlite_atomic_failure_execution_service(self.connection)
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("unit-main"),
            purpose="Terminal failure integration fixture",
        )
        self.run_id = ProcessingRunId("run-main")
        self.execution_id = UnitExecutionId("execution-main")
        self.service.register_unit(self.unit)
        self.service.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("Terminal failure integration"),
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
        self.failure = Failure(
            identity=FailureId("failure-main"),
            category=FailureCategory.PROCESSING,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            affected_inputs=(InputReference("input-b"), InputReference("input-a")),
            retryable=True,
            diagnostics=(DiagnosticId("diagnostic-main"),),
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def test_public_service_durably_records_terminal_failure_and_restarts(self) -> None:
        self.service.record_failure(self.execution_id, self.failure)
        expected_execution = self.service.get_unit_execution(self.execution_id)
        expected_run = self.service.get_run(self.run_id)
        self.assertEqual(self.service.get_failure(self.failure.identity), self.failure)
        self.assertEqual(expected_execution.state, ProcessingState.FAILED)
        self.assertEqual(expected_execution.failure_references, (self.failure.identity,))
        self.assertEqual(expected_run.failure_references, (self.failure.identity,))

        self.connection.close()
        self.connection = open_sqlite_database(self.database_path)
        failures = SQLiteFailureRepository(self.connection)
        executions = SQLiteUnitExecutionRepository(self.connection)
        runs = SQLiteProcessingRunRepository(self.connection)
        self.assertEqual(failures.get(self.failure.identity), self.failure)
        self.assertEqual(executions.get(self.execution_id), expected_execution)
        self.assertEqual(runs.get(self.run_id), expected_run)

    def test_service_write_failure_rolls_back_all_terminal_records(self) -> None:
        with patch(
            "lectureos.persistence.execution_commands._write_processing_run_snapshot",
            side_effect=sqlite3.OperationalError("injected run failure"),
        ):
            with self.assertRaises(PersistenceError):
                self.service.record_failure(self.execution_id, self.failure)
        self._assert_original_state()
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))

    def test_service_failure_collision_propagates_without_snapshot_changes(self) -> None:
        SQLiteFailureRepository(self.connection).save(self.failure)
        with self.assertRaises(ValueError):
            self.service.record_failure(self.execution_id, self.failure)
        self.assertEqual(
            SQLiteFailureRepository(self.connection).get(self.failure.identity),
            self.failure,
        )
        self.assertEqual(
            SQLiteUnitExecutionRepository(self.connection).get(self.execution_id),
            self.initial_execution,
        )
        self.assertEqual(
            SQLiteProcessingRunRepository(self.connection).get(self.run_id),
            self.initial_run,
        )

    def _assert_original_state(self) -> None:
        self.assertIsNone(
            SQLiteFailureRepository(self.connection).get(self.failure.identity)
        )
        self.assertEqual(
            SQLiteUnitExecutionRepository(self.connection).get(self.execution_id),
            self.initial_execution,
        )
        self.assertEqual(
            SQLiteProcessingRunRepository(self.connection).get(self.run_id),
            self.initial_run,
        )
        self.assertFalse(self.connection.in_transaction)


if __name__ == "__main__":
    unittest.main()
