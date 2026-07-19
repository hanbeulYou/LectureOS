import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lectureos.composition import compose_sqlite_execution_service
from lectureos.execution.identities import (
    FailureId,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import (
    ExecutionIntent,
    ExecutionOutcome,
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
from lectureos.persistence import sqlite as sqlite_lifecycle


class RecordingRepository(InMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.save_calls = []

    def save(self, record) -> None:
        self.save_calls.append(record)
        super().save(record)


class RecordingAtomicRetryPersistence:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls = []
        self.error = error

    def persist_retried_execution(self, *, execution, run) -> None:
        self.calls.append((execution, run))
        if self.error is not None:
            raise self.error


class ExecutionServiceRetryWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runs = RecordingRepository()
        self.units = RecordingRepository()
        self.executions = RecordingRepository()
        self.failures = RecordingRepository()
        self.atomic_retry = RecordingAtomicRetryPersistence()
        self.service = ExecutionService(
            runs=self.runs,
            units=self.units,
            executions=self.executions,
            failures=self.failures,
            atomic_retry_persistence=self.atomic_retry,
        )
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("unit-main"),
            purpose="Retry wiring fixture",
            independently_retryable=False,
        )
        self.run = ProcessingRun(
            identity=ProcessingRunId("run-main"),
            intent=ExecutionIntent("Retry wiring fixture"),
            working_context=WorkingContextReference("context-main"),
            unit_references=(self.unit.identity,),
            unit_execution_references=(
                UnitExecutionId("execution-z"),
                UnitExecutionId("execution-source"),
                UnitExecutionId("execution-a"),
            ),
            state=ProcessingState.FAILED,
        )
        self.source = UnitExecution(
            identity=UnitExecutionId("execution-source"),
            run_id=self.run.identity,
            unit_id=self.unit.identity,
            state=ProcessingState.FAILED,
            outcome=ExecutionOutcome(OutcomeKind.RECOVERABLE_FAILURE),
            failure_references=(
                FailureId("failure-missing"),
                FailureId("failure-non-retryable"),
                FailureId("failure-retryable"),
            ),
        )
        self.non_retryable = Failure(
            identity=FailureId("failure-non-retryable"),
            category=FailureCategory.PROCESSING,
            unit_execution_id=self.source.identity,
            retryable=False,
        )
        self.retryable = Failure(
            identity=FailureId("failure-retryable"),
            category=FailureCategory.PROCESSING,
            unit_execution_id=self.source.identity,
            retryable=True,
            reprocessing_required=True,
            human_action_required=True,
        )
        self.units.save(self.unit)
        self.runs.save(self.run)
        self.executions.save(self.source)
        self.failures.save(self.non_retryable)
        self.failures.save(self.retryable)
        self._clear_save_calls()

    def test_partial_failure_resolution_computes_final_records_and_calls_once(self) -> None:
        target_id = UnitExecutionId("execution-retry")
        accepted = self.service.retry_unit_execution(
            execution_id=target_id,
            failed_execution_id=self.source.identity,
        )
        self.assertEqual(accepted.run_id, self.run.identity)
        self.assertEqual(accepted.unit_execution_id, target_id)
        self.assertEqual(len(self.atomic_retry.calls), 1)
        execution, run = self.atomic_retry.calls[0]
        self.assertEqual(execution.identity, target_id)
        self.assertEqual(execution.run_id, self.run.identity)
        self.assertEqual(execution.unit_id, self.unit.identity)
        self.assertEqual(execution.configuration, self.run.configuration)
        self.assertEqual(execution.capabilities, self.unit.capabilities)
        self.assertEqual(execution.state, ProcessingState.RUNNING)
        self.assertIsNone(execution.outcome)
        self.assertEqual(execution.result_references, ())
        self.assertEqual(execution.failure_references, ())
        self.assertEqual(execution.retry_of, self.source.identity)
        self.assertEqual(
            run.unit_execution_references,
            self.run.unit_execution_references + (target_id,),
        )
        self.assertEqual(run.state, ProcessingState.RUNNING)
        self.assertEqual(self.executions.get(self.source.identity), self.source)
        self._assert_no_independent_saves()

    def test_retry_authority_ignores_unapproved_fields_and_unit_flag(self) -> None:
        self.service.retry_unit_execution(
            execution_id=UnitExecutionId("execution-retry"),
            failed_execution_id=self.source.identity,
        )
        self.assertEqual(len(self.atomic_retry.calls), 1)

    def test_invalid_authority_cases_never_invoke_atomic_persistence(self) -> None:
        cases = (
            replace(self.source, state=ProcessingState.RUNNING),
            replace(self.source, failure_references=()),
            replace(
                self.source,
                failure_references=(FailureId("failure-missing"),),
            ),
            replace(
                self.source,
                failure_references=(self.non_retryable.identity,),
            ),
        )
        for source in cases:
            with self.subTest(source=source):
                self.executions.save(source)
                self.executions.save_calls.clear()
                with self.assertRaises(ValueError):
                    self.service.retry_unit_execution(
                        execution_id=UnitExecutionId("execution-retry"),
                        failed_execution_id=source.identity,
                    )
                self.assertEqual(self.atomic_retry.calls, [])
                self._assert_no_independent_saves()
        with self.assertRaises(KeyError):
            self.service.retry_unit_execution(
                execution_id=UnitExecutionId("execution-retry"),
                failed_execution_id=UnitExecutionId("execution-missing"),
            )
        self.assertEqual(self.atomic_retry.calls, [])

    def test_target_collision_precheck_precedes_atomic_persistence(self) -> None:
        target = replace(
            self.source,
            identity=UnitExecutionId("execution-retry"),
            retry_of=self.source.identity,
        )
        self.executions.save(target)
        self.executions.save_calls.clear()
        with self.assertRaisesRegex(ValueError, "identity already exists"):
            self.service.retry_unit_execution(
                execution_id=target.identity,
                failed_execution_id=self.source.identity,
            )
        self.assertEqual(self.atomic_retry.calls, [])
        self.assertEqual(self.executions.get(target.identity), target)
        self.assertEqual(self.runs.get(self.run.identity), self.run)

    def test_persistence_errors_propagate_without_fallback_or_source_mutation(self) -> None:
        errors = (
            PersistenceError("injected persistence failure"),
            PersistenceIdentityCollisionError("injected collision"),
            SchemaFeatureUnavailableError("injected feature gate"),
        )
        for error in errors:
            with self.subTest(error=error):
                atomic = RecordingAtomicRetryPersistence(error)
                service = ExecutionService(
                    runs=self.runs,
                    units=self.units,
                    executions=self.executions,
                    failures=self.failures,
                    atomic_retry_persistence=atomic,
                )
                with self.assertRaises(type(error)):
                    service.retry_unit_execution(
                        execution_id=UnitExecutionId("execution-retry"),
                        failed_execution_id=self.source.identity,
                    )
                self.assertEqual(len(atomic.calls), 1)
                self.assertEqual(self.executions.get(self.source.identity), self.source)
                self.assertIsNone(
                    self.executions.get(UnitExecutionId("execution-retry"))
                )
                self.assertEqual(self.runs.get(self.run.identity), self.run)
                self._assert_no_independent_saves()

    def _clear_save_calls(self) -> None:
        for repository in (self.runs, self.units, self.executions, self.failures):
            repository.save_calls.clear()

    def _assert_no_independent_saves(self) -> None:
        self.assertEqual(self.runs.save_calls, [])
        self.assertEqual(self.executions.save_calls, [])
        self.assertEqual(self.failures.save_calls, [])


class SQLiteExecutionServiceRetryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.service = compose_sqlite_execution_service(self.connection)
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("unit-main"),
            purpose="Durable Retry fixture",
            independently_retryable=False,
        )
        self.run_id = ProcessingRunId("run-main")
        self.source_id = UnitExecutionId("execution-source")
        self.target_id = UnitExecutionId("execution-retry")
        self.service.register_unit(self.unit)
        self.service.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("Durable Retry fixture"),
            working_context=WorkingContextReference("context-main"),
            unit_ids=(self.unit.identity,),
        )
        self.service.start_unit_execution(
            execution_id=self.source_id,
            run_id=self.run_id,
            unit_id=self.unit.identity,
        )
        self.failure = Failure(
            identity=FailureId("failure-retryable"),
            category=FailureCategory.PROCESSING,
            run_id=self.run_id,
            unit_execution_id=self.source_id,
            retryable=True,
        )
        self.service.record_failure(self.source_id, self.failure)
        self.source = self.service.get_unit_execution(self.source_id)
        self.run_before_retry = self.service.get_run(self.run_id)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def test_public_service_durably_retries_and_restarts(self) -> None:
        accepted = self.service.retry_unit_execution(
            execution_id=self.target_id,
            failed_execution_id=self.source_id,
        )
        self.assertEqual(accepted.unit_execution_id, self.target_id)
        target = self.service.get_unit_execution(self.target_id)
        run = self.service.get_run(self.run_id)
        self.assertEqual(target.retry_of, self.source_id)
        self.assertEqual(target.state, ProcessingState.RUNNING)
        self.assertEqual(run.unit_execution_references[-1], self.target_id)
        self.assertEqual(run.unit_execution_references.count(self.target_id), 1)
        self.assertEqual(self.service.get_unit_execution(self.source_id), self.source)
        self.assertEqual(self.service.get_failure(self.failure.identity), self.failure)

        self.connection.close()
        self.connection = open_sqlite_database(self.database_path)
        executions = SQLiteUnitExecutionRepository(self.connection)
        runs = SQLiteProcessingRunRepository(self.connection)
        failures = SQLiteFailureRepository(self.connection)
        self.assertEqual(executions.get(self.source_id), self.source)
        self.assertEqual(executions.get(self.target_id), target)
        self.assertEqual(runs.get(self.run_id), run)
        self.assertEqual(failures.get(self.failure.identity), self.failure)

    def test_partial_durable_failure_resolution_still_allows_retry(self) -> None:
        non_retryable = replace(
            self.failure,
            identity=FailureId("failure-non-retryable"),
            retryable=False,
        )
        SQLiteFailureRepository(self.connection).save(non_retryable)
        execution_repository = SQLiteUnitExecutionRepository(self.connection)
        source = replace(
            self.source,
            failure_references=(
                FailureId("failure-missing"),
                non_retryable.identity,
                self.failure.identity,
            ),
        )
        execution_repository.save(source)
        self.service.retry_unit_execution(
            execution_id=self.target_id,
            failed_execution_id=self.source_id,
        )
        self.assertEqual(
            self.service.get_unit_execution(self.target_id).retry_of,
            self.source_id,
        )

    def test_non_retryable_failure_denies_retry_without_writes(self) -> None:
        non_retryable = replace(self.failure, retryable=False)
        failure_repository = SQLiteFailureRepository(self.connection)
        self.connection.execute(
            "DELETE FROM failures WHERE identity = ?",
            (self.failure.identity.value,),
        )
        failure_repository.save(non_retryable)
        with self.assertRaisesRegex(ValueError, "no retryable failure"):
            self.service.retry_unit_execution(
                execution_id=self.target_id,
                failed_execution_id=self.source_id,
            )
        self.assertIsNone(self.service.get_unit_execution(self.target_id))
        self.assertEqual(self.service.get_run(self.run_id), self.run_before_retry)

    def test_atomic_write_failure_through_service_rolls_back(self) -> None:
        with patch(
            "lectureos.persistence.execution_commands._write_processing_run_snapshot",
            side_effect=sqlite3.OperationalError("injected Retry run failure"),
        ):
            with self.assertRaises(PersistenceError):
                self.service.retry_unit_execution(
                    execution_id=self.target_id,
                    failed_execution_id=self.source_id,
                )
        self.assertIsNone(self.service.get_unit_execution(self.target_id))
        self.assertEqual(self.service.get_unit_execution(self.source_id), self.source)
        self.assertEqual(self.service.get_run(self.run_id), self.run_before_retry)
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))

    def test_target_collision_precheck_preserves_source_and_run(self) -> None:
        target = replace(
            self.source,
            identity=self.target_id,
            retry_of=self.source_id,
        )
        SQLiteUnitExecutionRepository(self.connection).save(target)
        with self.assertRaisesRegex(ValueError, "identity already exists"):
            self.service.retry_unit_execution(
                execution_id=self.target_id,
                failed_execution_id=self.source_id,
            )
        self.assertEqual(self.service.get_unit_execution(self.target_id), target)
        self.assertEqual(self.service.get_unit_execution(self.source_id), self.source)
        self.assertEqual(self.service.get_run(self.run_id), self.run_before_retry)


def create_version_three_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN")
    for statement in (
        *sqlite_lifecycle._V1_TABLE_STATEMENTS,
        *sqlite_lifecycle._V2_ADDITION_STATEMENTS,
        *sqlite_lifecycle._V3_ADDITION_STATEMENTS,
    ):
        connection.execute(statement)
    connection.execute("INSERT INTO schema_metadata VALUES (1, 3)")
    connection.execute("COMMIT")
    return connection


class SQLiteRetryCompositionVersionTests(unittest.TestCase):
    def test_full_retry_service_requires_v4_failure_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "legacy-v3.sqlite3"
            connection = create_version_three_database(path)
            try:
                with self.assertRaises(SchemaFeatureUnavailableError):
                    compose_sqlite_execution_service(connection)
                self.assertEqual(
                    connection.execute("SELECT version FROM schema_metadata").fetchone(),
                    (3,),
                )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
