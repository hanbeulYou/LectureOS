import inspect
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lectureos.execution.boundaries import AtomicFailureExecutionPersistence
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
    ExecutionOutcome,
    Failure,
    FailureCategory,
    OutcomeKind,
    ProcessingRun,
    ProcessingState,
    UnitExecution,
)
from lectureos.persistence import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SQLiteExecutionCommandPersistence,
    SQLiteFailureRepository,
    SQLiteProcessingRunRepository,
    SQLiteUnitExecutionRepository,
    SchemaFeatureUnavailableError,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import failures as failure_persistence
from lectureos.persistence import sqlite as sqlite_lifecycle


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


class SQLiteAtomicFailurePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.run_repository = SQLiteProcessingRunRepository(self.connection)
        self.execution_repository = SQLiteUnitExecutionRepository(self.connection)
        self.failure_repository = SQLiteFailureRepository(self.connection)
        self.persistence = SQLiteExecutionCommandPersistence(self.connection)

        self.initial_run = ProcessingRun(
            identity=ProcessingRunId("run-main"),
            intent=ExecutionIntent("Atomic failure fixture"),
            working_context=WorkingContextReference("context-main"),
            unit_references=(ProcessingUnitId("unit-main"),),
            unit_execution_references=(UnitExecutionId("execution-main"),),
            state=ProcessingState.RUNNING,
        )
        self.initial_execution = UnitExecution(
            identity=UnitExecutionId("execution-main"),
            run_id=self.initial_run.identity,
            unit_id=ProcessingUnitId("unit-main"),
            state=ProcessingState.RUNNING,
        )
        self.failure = Failure(
            identity=FailureId("failure-main"),
            category=FailureCategory.PROCESSING,
            run_id=self.initial_run.identity,
            unit_execution_id=self.initial_execution.identity,
            affected_inputs=(
                InputReference("input-z"),
                InputReference("input-a"),
                InputReference("input-z"),
            ),
            affected_results=(
                DomainResultId("result-z"),
                DomainResultId("result-a"),
            ),
            retryable=True,
            diagnostics=(DiagnosticId("diagnostic-z"), DiagnosticId("diagnostic-a")),
        )
        self.final_execution = replace(
            self.initial_execution,
            state=ProcessingState.FAILED,
            outcome=ExecutionOutcome(OutcomeKind.RECOVERABLE_FAILURE),
            failure_references=(FailureId("failure-existing"), self.failure.identity),
        )
        self.final_run = replace(
            self.initial_run,
            failure_references=(FailureId("failure-existing"), self.failure.identity),
        )
        self.run_repository.save(self.initial_run)
        self.execution_repository.save(self.initial_execution)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def test_atomic_failure_persists_all_records_and_survives_restart(self) -> None:
        self._persist()
        self._assert_final_state()

        self.connection.close()
        self.connection = open_sqlite_database(self.database_path)
        self.run_repository = SQLiteProcessingRunRepository(self.connection)
        self.execution_repository = SQLiteUnitExecutionRepository(self.connection)
        self.failure_repository = SQLiteFailureRepository(self.connection)
        self.assertEqual(self.failure_repository.get(self.failure.identity), self.failure)
        self.assertEqual(
            self.execution_repository.get(self.final_execution.identity),
            self.final_execution,
        )
        self.assertEqual(self.run_repository.get(self.final_run.identity), self.final_run)

    def test_lower_versions_are_feature_unavailable_without_migration_or_mutation(self) -> None:
        for version in (1, 2, 3):
            with self.subTest(version=version):
                path = Path(self.temporary_directory.name) / f"legacy-v{version}.sqlite3"
                connection = create_legacy_database(path, version)
                tables_before = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
                with self.assertRaises(SchemaFeatureUnavailableError):
                    adapter = SQLiteExecutionCommandPersistence(connection)
                    adapter.persist_recorded_failure(
                        failure=self.failure,
                        execution=self.final_execution,
                        run=self.final_run,
                    )
                self.assertEqual(
                    connection.execute("SELECT version FROM schema_metadata").fetchone(),
                    (version,),
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                    ).fetchall(),
                    tables_before,
                )
                connection.close()

    def test_failure_collision_rolls_back_both_snapshot_changes(self) -> None:
        existing = replace(self.failure, retryable=False)
        self.failure_repository.save(existing)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self._persist()
        self.assertEqual(self.failure_repository.get(existing.identity), existing)
        self._assert_initial_snapshots()

    def test_failure_child_failure_rolls_back_complete_record_set(self) -> None:
        original = failure_persistence._insert_children
        calls = 0

        def fail_after_one_child_table(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise sqlite3.IntegrityError("injected Failure child failure")
            return original(*args, **kwargs)

        with patch.object(
            failure_persistence,
            "_insert_children",
            side_effect=fail_after_one_child_table,
        ):
            with self.assertRaises(PersistenceError):
                self._persist()
        self._assert_initial_state()

    def test_unit_execution_write_failure_rolls_back_failure_and_run(self) -> None:
        with patch(
            "lectureos.persistence.execution_commands._write_unit_execution_snapshot",
            side_effect=sqlite3.OperationalError("injected execution failure"),
        ):
            with self.assertRaises(PersistenceError):
                self._persist()
        self._assert_initial_state()

    def test_processing_run_write_failure_rolls_back_failure_and_execution(self) -> None:
        with patch(
            "lectureos.persistence.execution_commands._write_processing_run_snapshot",
            side_effect=sqlite3.OperationalError("injected run failure"),
        ):
            with self.assertRaises(PersistenceError):
                self._persist()
        self._assert_initial_state()

    def test_commit_failure_rolls_back_all_three_records(self) -> None:
        with patch.object(
            self.persistence,
            "_commit",
            side_effect=sqlite3.OperationalError("injected commit failure"),
        ):
            with self.assertRaises(PersistenceError):
                self._persist()
        self._assert_initial_state()

    def test_every_linkage_mismatch_is_rejected_without_mutation(self) -> None:
        mismatches = (
            (
                replace(self.failure, unit_execution_id=UnitExecutionId("other")),
                self.final_execution,
                self.final_run,
            ),
            (
                replace(self.failure, run_id=ProcessingRunId("other")),
                self.final_execution,
                self.final_run,
            ),
            (
                self.failure,
                replace(self.final_execution, run_id=ProcessingRunId("other")),
                self.final_run,
            ),
            (
                self.failure,
                replace(self.final_execution, failure_references=()),
                self.final_run,
            ),
            (
                self.failure,
                self.final_execution,
                replace(self.final_run, failure_references=()),
            ),
        )
        for failure, execution, run in mismatches:
            with self.subTest(failure=failure, execution=execution, run=run):
                with self.assertRaises(PersistenceError):
                    self.persistence.persist_recorded_failure(
                        failure=failure,
                        execution=execution,
                        run=run,
                    )
                self._assert_initial_state()

    def test_execution_only_and_both_provenance_are_supported(self) -> None:
        execution_only = replace(self.failure, run_id=None)
        final_execution = replace(
            self.final_execution,
            failure_references=(execution_only.identity,),
        )
        final_run = replace(
            self.final_run,
            failure_references=(execution_only.identity,),
        )
        self.persistence.persist_recorded_failure(
            failure=execution_only,
            execution=final_execution,
            run=final_run,
        )
        self.assertEqual(
            self.failure_repository.get(execution_only.identity), execution_only
        )

    def test_run_only_provenance_is_rejected_by_existing_terminal_contract(self) -> None:
        run_only = replace(self.failure, unit_execution_id=None)
        with self.assertRaises(PersistenceError):
            self.persistence.persist_recorded_failure(
                failure=run_only,
                execution=self.final_execution,
                run=self.final_run,
            )
        self._assert_initial_state()

    def test_connection_is_caller_owned_and_transactions_close_on_both_paths(self) -> None:
        self._persist()
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))

        conflicting = replace(self.failure, identity=FailureId("failure-second"))
        with self.assertRaises(PersistenceError):
            self.persistence.persist_recorded_failure(
                failure=conflicting,
                execution=self.final_execution,
                run=self.final_run,
            )
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))

    def test_application_port_is_sqlite_independent_and_service_is_unchanged(self) -> None:
        self.assertTrue(
            hasattr(AtomicFailureExecutionPersistence, "persist_recorded_failure")
        )
        source = inspect.getsource(
            __import__("lectureos.execution.boundaries", fromlist=["boundaries"])
        )
        self.assertNotIn("sqlite", source.lower())

    def _persist(self) -> None:
        self.persistence.persist_recorded_failure(
            failure=self.failure,
            execution=self.final_execution,
            run=self.final_run,
        )

    def _assert_final_state(self) -> None:
        self.assertEqual(self.failure_repository.get(self.failure.identity), self.failure)
        self.assertEqual(
            self.execution_repository.get(self.final_execution.identity),
            self.final_execution,
        )
        self.assertEqual(self.run_repository.get(self.final_run.identity), self.final_run)
        self.assertFalse(self.connection.in_transaction)

    def _assert_initial_snapshots(self) -> None:
        self.assertEqual(
            self.execution_repository.get(self.initial_execution.identity),
            self.initial_execution,
        )
        self.assertEqual(
            self.run_repository.get(self.initial_run.identity), self.initial_run
        )

    def _assert_initial_state(self) -> None:
        self.assertIsNone(self.failure_repository.get(self.failure.identity))
        self._assert_initial_snapshots()
        self.assertFalse(self.connection.in_transaction)


if __name__ == "__main__":
    unittest.main()
