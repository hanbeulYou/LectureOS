import inspect
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lectureos.execution.boundaries import AtomicRetryExecutionPersistence
from lectureos.execution.identities import (
    CapabilityReference,
    FailureId,
    InputReference,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import (
    ExecutionIntent,
    ExecutionOutcome,
    OutcomeKind,
    ProcessingRun,
    ProcessingState,
    UnitExecution,
)
from lectureos.persistence import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SQLiteExecutionCommandPersistence,
    SQLiteProcessingRunRepository,
    SQLiteUnitExecutionRepository,
    SchemaFeatureUnavailableError,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle
from lectureos.persistence import unit_executions as unit_execution_persistence


def create_legacy_database(path: Path, version: int) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN")
    statements = list(sqlite_lifecycle._V1_TABLE_STATEMENTS)
    if version >= 2:
        statements.extend(sqlite_lifecycle._V2_ADDITION_STATEMENTS)
    if version >= 3:
        statements.extend(sqlite_lifecycle._V3_ADDITION_STATEMENTS)
    for statement in statements:
        connection.execute(statement)
    connection.execute("INSERT INTO schema_metadata VALUES (1, ?)", (version,))
    connection.execute("COMMIT")
    return connection


class SQLiteAtomicRetryPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.run_repository = SQLiteProcessingRunRepository(self.connection)
        self.execution_repository = SQLiteUnitExecutionRepository(self.connection)
        self.persistence = SQLiteExecutionCommandPersistence(self.connection)

        self.source = UnitExecution(
            identity=UnitExecutionId("execution-source"),
            run_id=ProcessingRunId("run-main"),
            unit_id=ProcessingUnitId("unit-main"),
            state=ProcessingState.FAILED,
            outcome=ExecutionOutcome(OutcomeKind.RECOVERABLE_FAILURE),
            failure_references=(FailureId("failure-retryable"),),
        )
        self.initial_run = ProcessingRun(
            identity=self.source.run_id,
            intent=ExecutionIntent("Atomic Retry fixture"),
            working_context=WorkingContextReference("context-main"),
            unit_references=(self.source.unit_id,),
            unit_execution_references=(
                UnitExecutionId("execution-z"),
                self.source.identity,
                UnitExecutionId("execution-a"),
            ),
            state=ProcessingState.RUNNING,
        )
        self.retry = UnitExecution(
            identity=UnitExecutionId("execution-retry"),
            run_id=self.initial_run.identity,
            unit_id=self.source.unit_id,
            input_references=(InputReference("input-z"), InputReference("input-a")),
            capabilities=(CapabilityReference("capability-retry"),),
            state=ProcessingState.RUNNING,
            retry_of=self.source.identity,
        )
        self.final_run = replace(
            self.initial_run,
            unit_execution_references=(
                *self.initial_run.unit_execution_references,
                self.retry.identity,
            ),
        )
        self.execution_repository.save(self.source)
        self.run_repository.save(self.initial_run)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def test_atomic_retry_persists_target_and_run_and_survives_restart(self) -> None:
        self._persist()
        self._assert_final_state()

        self.connection.close()
        self.connection = open_sqlite_database(self.database_path)
        executions = SQLiteUnitExecutionRepository(self.connection)
        runs = SQLiteProcessingRunRepository(self.connection)
        self.assertEqual(executions.get(self.source.identity), self.source)
        self.assertEqual(executions.get(self.retry.identity), self.retry)
        self.assertEqual(runs.get(self.final_run.identity), self.final_run)

    def test_schema_v3_and_v4_support_retry_while_v1_and_v2_do_not_mutate(self) -> None:
        for version in (1, 2, 3):
            with self.subTest(version=version):
                path = Path(self.temporary_directory.name) / f"legacy-v{version}.sqlite3"
                connection = create_legacy_database(path, version)
                tables_before = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
                if version < 3:
                    with self.assertRaises(SchemaFeatureUnavailableError):
                        SQLiteExecutionCommandPersistence(connection)
                else:
                    adapter = SQLiteExecutionCommandPersistence(connection)
                    run_repository = SQLiteProcessingRunRepository(connection)
                    source_repository = SQLiteUnitExecutionRepository(connection)
                    source_repository.save(self.source)
                    run_repository.save(self.initial_run)
                    adapter.persist_retried_execution(
                        execution=self.retry,
                        run=self.final_run,
                    )
                    self.assertEqual(source_repository.get(self.retry.identity), self.retry)
                self.assertEqual(
                    connection.execute("SELECT version FROM schema_metadata").fetchone(),
                    (version,),
                )
                if version < 3:
                    self.assertEqual(
                        connection.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                        ).fetchall(),
                        tables_before,
                    )
                connection.close()

    def test_target_identity_collision_preserves_every_existing_record(self) -> None:
        existing_target = replace(self.retry, state=ProcessingState.PENDING)
        self.execution_repository.save(existing_target)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self._persist()
        self.assertEqual(
            self.execution_repository.get(existing_target.identity), existing_target
        )
        self._assert_original_state()

    def test_partial_execution_child_failure_rolls_back_everything(self) -> None:
        original = unit_execution_persistence._insert_unit_execution_children
        calls = 0

        def fail_after_one_child_table(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise sqlite3.IntegrityError("injected execution child failure")
            return original(*args, **kwargs)

        with patch.object(
            unit_execution_persistence,
            "_insert_unit_execution_children",
            side_effect=fail_after_one_child_table,
        ):
            with self.assertRaises(PersistenceError):
                self._persist()
        self._assert_initial_state()

    def test_processing_run_write_failure_rolls_back_new_execution(self) -> None:
        with patch(
            "lectureos.persistence.execution_commands._write_processing_run_snapshot",
            side_effect=sqlite3.OperationalError("injected run failure"),
        ):
            with self.assertRaises(PersistenceError):
                self._persist()
        self._assert_initial_state()

    def test_commit_failure_rolls_back_and_connection_remains_reusable(self) -> None:
        with patch.object(
            self.persistence,
            "_commit",
            side_effect=sqlite3.OperationalError("injected commit failure"),
        ):
            with self.assertRaises(PersistenceError):
                self._persist()
        self._assert_initial_state()
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))

    def test_every_retry_linkage_mismatch_rolls_back_without_mutation(self) -> None:
        mismatches = (
            (
                replace(self.retry, run_id=ProcessingRunId("other-run")),
                self.final_run,
            ),
            (
                replace(self.retry, retry_of=None),
                self.final_run,
            ),
            (
                self.retry,
                replace(self.final_run, unit_execution_references=()),
            ),
            (
                self.retry,
                replace(
                    self.final_run,
                    unit_execution_references=(self.retry.identity, self.retry.identity),
                ),
            ),
        )
        for execution, run in mismatches:
            with self.subTest(execution=execution, run=run):
                with self.assertRaises(PersistenceError):
                    self.persistence.persist_retried_execution(
                        execution=execution,
                        run=run,
                    )
                self._assert_initial_state()

    def test_missing_run_uses_existing_processing_run_save_as_create_semantics(self) -> None:
        missing_run = replace(
            self.final_run,
            identity=ProcessingRunId("run-new"),
            unit_execution_references=(self.retry.identity,),
        )
        retry = replace(self.retry, run_id=missing_run.identity)
        self.persistence.persist_retried_execution(execution=retry, run=missing_run)
        self.assertEqual(self.execution_repository.get(retry.identity), retry)
        self.assertEqual(self.run_repository.get(missing_run.identity), missing_run)
        self.assertEqual(self.execution_repository.get(self.source.identity), self.source)

    def test_port_is_sqlite_independent(self) -> None:
        self.assertTrue(
            hasattr(AtomicRetryExecutionPersistence, "persist_retried_execution")
        )
        boundary_source = inspect.getsource(
            __import__("lectureos.execution.boundaries", fromlist=["boundaries"])
        )
        self.assertNotIn("sqlite", boundary_source.lower())

    def test_success_and_failure_leave_no_transaction_and_connection_open(self) -> None:
        self._persist()
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))

    def _persist(self) -> None:
        self.persistence.persist_retried_execution(
            execution=self.retry,
            run=self.final_run,
        )

    def _assert_final_state(self) -> None:
        self.assertEqual(self.execution_repository.get(self.source.identity), self.source)
        self.assertEqual(self.execution_repository.get(self.retry.identity), self.retry)
        self.assertEqual(self.run_repository.get(self.final_run.identity), self.final_run)
        self.assertFalse(self.connection.in_transaction)

    def _assert_original_state(self) -> None:
        self.assertEqual(self.execution_repository.get(self.source.identity), self.source)
        self.assertEqual(self.run_repository.get(self.initial_run.identity), self.initial_run)
        self.assertFalse(self.connection.in_transaction)

    def _assert_initial_state(self) -> None:
        self.assertIsNone(self.execution_repository.get(self.retry.identity))
        self._assert_original_state()


if __name__ == "__main__":
    unittest.main()
