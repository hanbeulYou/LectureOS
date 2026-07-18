import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import lectureos.persistence as persistence
from lectureos.execution.identities import (
    CapabilityReference,
    ConfigurationReference,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import (
    ExecutionIntent,
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


def create_legacy_database(path: Path, version: int) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN")
    statements = list(sqlite_lifecycle._V1_TABLE_STATEMENTS)
    if version >= 2:
        statements.extend(sqlite_lifecycle._V2_ADDITION_STATEMENTS)
    for statement in statements:
        connection.execute(statement)
    connection.execute("INSERT INTO schema_metadata VALUES (1, ?)", (version,))
    connection.execute("COMMIT")
    return connection


class SQLiteAtomicExecutionStartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.run_repository = SQLiteProcessingRunRepository(self.connection)
        self.execution_repository = SQLiteUnitExecutionRepository(self.connection)
        self.persistence = SQLiteExecutionCommandPersistence(self.connection)
        self.initial_run = ProcessingRun(
            identity=ProcessingRunId("run-main"),
            intent=ExecutionIntent("Atomic start fixture"),
            working_context=WorkingContextReference("context-main"),
            configuration=ConfigurationReference("configuration-main"),
            unit_references=(ProcessingUnitId("unit-main"),),
        )
        self.execution = UnitExecution(
            identity=UnitExecutionId("execution-main"),
            run_id=self.initial_run.identity,
            unit_id=ProcessingUnitId("unit-main"),
            configuration=self.initial_run.configuration,
            capabilities=(CapabilityReference("capability-main"),),
            state=ProcessingState.RUNNING,
        )
        self.final_run = replace(
            self.initial_run,
            state=ProcessingState.RUNNING,
            unit_execution_references=(self.execution.identity,),
        )
        self.run_repository.save(self.initial_run)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def test_atomic_start_persists_final_linked_snapshots_and_restarts(self) -> None:
        self.persistence.persist_started_execution(
            execution=self.execution,
            run=self.final_run,
        )
        self.assertEqual(
            self.execution_repository.get(self.execution.identity), self.execution
        )
        self.assertEqual(self.run_repository.get(self.final_run.identity), self.final_run)

        self.connection.close()
        self.connection = open_sqlite_database(self.database_path)
        self.run_repository = SQLiteProcessingRunRepository(self.connection)
        self.execution_repository = SQLiteUnitExecutionRepository(self.connection)
        restored_execution = self.execution_repository.get(self.execution.identity)
        restored_run = self.run_repository.get(self.final_run.identity)
        self.assertEqual(restored_execution, self.execution)
        self.assertEqual(restored_run, self.final_run)
        self.assertIn(restored_execution.identity, restored_run.unit_execution_references)

    def test_unit_execution_write_failure_rolls_back_run(self) -> None:
        self.connection.execute(
            """
            CREATE TRIGGER reject_atomic_execution BEFORE INSERT ON unit_executions
            BEGIN SELECT RAISE(ABORT, 'injected execution failure'); END
            """
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_started_execution(
                execution=self.execution,
                run=self.final_run,
            )
        self._assert_initial_state()

    def test_processing_run_write_failure_rolls_back_execution(self) -> None:
        self.connection.execute(
            """
            CREATE TRIGGER reject_atomic_run BEFORE UPDATE ON processing_runs
            BEGIN SELECT RAISE(ABORT, 'injected run failure'); END
            """
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_started_execution(
                execution=self.execution,
                run=self.final_run,
            )
        self._assert_initial_state()

    def test_commit_failure_rolls_back_both_snapshots(self) -> None:
        with patch.object(
            self.persistence,
            "_commit",
            side_effect=sqlite3.OperationalError("injected commit failure"),
        ):
            with self.assertRaises(PersistenceError):
                self.persistence.persist_started_execution(
                    execution=self.execution,
                    run=self.final_run,
                )
        self._assert_initial_state()

    def test_execution_identity_collision_leaves_run_unchanged(self) -> None:
        existing = replace(self.execution, state=ProcessingState.PENDING)
        self.execution_repository.save(existing)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_started_execution(
                execution=self.execution,
                run=self.final_run,
            )
        self.assertEqual(self.execution_repository.get(existing.identity), existing)
        self.assertEqual(self.run_repository.get(self.initial_run.identity), self.initial_run)

    def test_linkage_mismatch_is_rejected_before_transaction(self) -> None:
        mismatched_execution = replace(
            self.execution, run_id=ProcessingRunId("another-run")
        )
        with self.assertRaises(ValueError):
            self.persistence.persist_started_execution(
                execution=mismatched_execution,
                run=self.final_run,
            )
        unlinked_run = replace(self.final_run, unit_execution_references=())
        with self.assertRaises(ValueError):
            self.persistence.persist_started_execution(
                execution=self.execution,
                run=unlinked_run,
            )
        self.assertFalse(self.connection.in_transaction)
        self._assert_initial_state()

    def test_non_sqlite_error_rolls_back_and_preserves_original_type(self) -> None:
        with patch(
            "lectureos.persistence.execution_commands._write_processing_run_snapshot",
            side_effect=ValueError("injected domain error"),
        ):
            with self.assertRaisesRegex(ValueError, "injected domain error"):
                self.persistence.persist_started_execution(
                    execution=self.execution,
                    run=self.final_run,
                )
        self._assert_initial_state()

    def test_composition_does_not_validate_lifecycle_or_external_unit(self) -> None:
        completed = replace(self.execution, state=ProcessingState.COMPLETED)
        self.persistence.persist_started_execution(
            execution=completed,
            run=self.final_run,
        )
        self.assertEqual(self.execution_repository.get(completed.identity), completed)

    def test_public_repository_save_remains_self_transactional(self) -> None:
        independent_execution = replace(
            self.execution,
            identity=UnitExecutionId("execution-independent"),
        )
        self.execution_repository.save(independent_execution)
        independent_run = replace(
            self.initial_run,
            state=ProcessingState.COMPLETED,
        )
        self.run_repository.save(independent_run)
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(
            self.execution_repository.get(independent_execution.identity),
            independent_execution,
        )
        self.assertEqual(self.run_repository.get(independent_run.identity), independent_run)

    def test_internal_writers_are_not_public_package_exports(self) -> None:
        self.assertNotIn("_write_processing_run_snapshot", persistence.__all__)
        self.assertNotIn("_insert_unit_execution_snapshot", persistence.__all__)
        self.assertFalse(hasattr(persistence, "_write_processing_run_snapshot"))
        self.assertFalse(hasattr(persistence, "_insert_unit_execution_snapshot"))

    def test_lower_schema_versions_are_feature_unavailable_and_unchanged(self) -> None:
        for version in (1, 2):
            path = Path(self.temporary_directory.name) / f"legacy-v{version}.sqlite3"
            connection = create_legacy_database(path, version)
            tables_before = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteExecutionCommandPersistence(connection)
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

    def test_connection_is_caller_owned_and_no_nested_transaction_is_started(self) -> None:
        self.persistence.persist_started_execution(
            execution=self.execution,
            run=self.final_run,
        )
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))

    def test_existing_caller_transaction_is_not_adopted_or_rolled_back(self) -> None:
        self.connection.execute("CREATE TABLE caller_work(value TEXT)")
        self.connection.execute("BEGIN")
        self.connection.execute("INSERT INTO caller_work VALUES ('preserved')")
        with self.assertRaises(PersistenceError):
            self.persistence.persist_started_execution(
                execution=self.execution,
                run=self.final_run,
            )
        self.assertTrue(self.connection.in_transaction)
        self.assertEqual(
            self.connection.execute("SELECT value FROM caller_work").fetchall(),
            [("preserved",)],
        )
        self.connection.execute("ROLLBACK")
        self._assert_initial_state()

    def _assert_initial_state(self) -> None:
        self.assertIsNone(self.execution_repository.get(self.execution.identity))
        self.assertEqual(self.run_repository.get(self.initial_run.identity), self.initial_run)
        self.assertFalse(self.connection.in_transaction)


if __name__ == "__main__":
    unittest.main()
