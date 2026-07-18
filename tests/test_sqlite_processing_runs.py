import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lectureos.execution.identities import (
    ConfigurationReference,
    DomainResultId,
    FailureId,
    InputReference,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import ExecutionIntent, ProcessingRun, ProcessingState
from lectureos.persistence import (
    PersistenceError,
    SQLiteProcessingRunRepository,
    SchemaFeatureUnavailableError,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle


def create_legacy_v1_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN")
    for statement in sqlite_lifecycle._V1_TABLE_STATEMENTS:
        connection.execute(statement)
    connection.execute("INSERT INTO schema_metadata VALUES (1, 1)")
    connection.execute("COMMIT")
    return connection


class SQLiteProcessingRunRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.repository = SQLiteProcessingRunRepository(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def _initial_run(self, identity: str = "run-main") -> ProcessingRun:
        return ProcessingRun(
            identity=ProcessingRunId(identity),
            intent=ExecutionIntent(
                purpose="Initial transcript processing",
                retry_of=UnitExecutionId("execution-earlier"),
            ),
            working_context=WorkingContextReference("context-primary"),
            input_references=(InputReference("input-b"), InputReference("input-a")),
            upstream_results=(DomainResultId("upstream-b"), DomainResultId("upstream-a")),
            configuration=ConfigurationReference("configuration-initial"),
            unit_references=(ProcessingUnitId("unit-b"), ProcessingUnitId("unit-a")),
            unit_execution_references=(
                UnitExecutionId("execution-b"),
                UnitExecutionId("execution-a"),
            ),
            state=ProcessingState.RUNNING,
            result_references=(DomainResultId("result-b"), DomainResultId("result-a")),
            failure_references=(FailureId("failure-b"), FailureId("failure-a")),
            reprocessing_of=None,
        )

    def _later_run(self, identity: str = "run-main") -> ProcessingRun:
        return ProcessingRun(
            identity=ProcessingRunId(identity),
            intent=ExecutionIntent(
                purpose="Later completed processing",
                reprocessing_of=ProcessingRunId("run-intent-source"),
            ),
            working_context=WorkingContextReference("context-later"),
            input_references=(InputReference("input-c"),),
            upstream_results=(
                DomainResultId("upstream-c"),
                DomainResultId("upstream-b"),
                DomainResultId("upstream-a"),
            ),
            configuration=None,
            unit_references=(ProcessingUnitId("unit-c"),),
            unit_execution_references=(
                UnitExecutionId("execution-c"),
                UnitExecutionId("execution-b"),
            ),
            state=ProcessingState.COMPLETED,
            result_references=(DomainResultId("result-c"),),
            failure_references=(),
            reprocessing_of=ProcessingRunId("run-lineage-source"),
        )

    def test_version_two_supports_repository_and_version_one_is_unavailable(self) -> None:
        self.assertIsNone(self.repository.get(ProcessingRunId("missing")))

        self.connection.close()
        self.database_path.unlink()
        legacy = create_legacy_v1_database(self.database_path)
        tables_before = legacy.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
        with self.assertRaises(SchemaFeatureUnavailableError):
            SQLiteProcessingRunRepository(legacy)
        self.assertEqual(
            legacy.execute("SELECT version FROM schema_metadata").fetchone(), (1,)
        )
        self.assertEqual(
            legacy.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall(),
            tables_before,
        )
        self.connection = legacy

    def test_missing_or_malformed_v2_schema_is_not_repaired(self) -> None:
        self.connection.execute("DROP TABLE processing_run_failures")
        with self.assertRaises(PersistenceError):
            SQLiteProcessingRunRepository(self.connection)
        self.assertNotIn(
            "processing_run_failures",
            {
                row[0]
                for row in self.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            },
        )

    def test_complete_snapshot_round_trips_with_exact_types_and_order(self) -> None:
        expected = self._initial_run()
        self.repository.save(expected)
        restored = self.repository.get(expected.identity)
        self.assertEqual(restored, expected)
        self.assertIs(type(restored.identity), ProcessingRunId)
        self.assertIs(type(restored.intent), ExecutionIntent)
        self.assertIs(type(restored.intent.retry_of), UnitExecutionId)
        self.assertIs(type(restored.working_context), WorkingContextReference)
        self.assertIs(type(restored.configuration), ConfigurationReference)
        self.assertIs(type(restored.state), ProcessingState)
        self.assertEqual(restored.input_references, expected.input_references)
        self.assertEqual(restored.upstream_results, expected.upstream_results)
        self.assertEqual(restored.unit_references, expected.unit_references)
        self.assertEqual(
            restored.unit_execution_references, expected.unit_execution_references
        )
        self.assertEqual(restored.result_references, expected.result_references)
        self.assertEqual(restored.failure_references, expected.failure_references)

    def test_empty_tuples_and_optional_none_values_round_trip(self) -> None:
        expected = ProcessingRun(
            identity=ProcessingRunId("run-empty"),
            intent=ExecutionIntent("Empty references"),
            working_context=WorkingContextReference("context-empty"),
        )
        self.repository.save(expected)
        restored = self.repository.get(expected.identity)
        self.assertEqual(restored, expected)
        self.assertIsNone(restored.intent.retry_of)
        self.assertIsNone(restored.intent.reprocessing_of)
        self.assertIsNone(restored.configuration)
        self.assertIsNone(restored.reprocessing_of)

    def test_snapshot_survives_connection_restart(self) -> None:
        expected = self._initial_run()
        self.repository.save(expected)
        self.connection.close()
        self.connection = open_sqlite_database(self.database_path)
        self.repository = SQLiteProcessingRunRepository(self.connection)
        restored = self.repository.get(expected.identity)
        self.assertEqual(restored, expected)
        self.assertIs(type(restored.identity), ProcessingRunId)
        self.assertEqual(restored.input_references, expected.input_references)

    def test_same_identity_atomically_replaces_complete_snapshot(self) -> None:
        initial = self._initial_run()
        later = self._later_run()
        self.repository.save(initial)
        self.repository.save(later)
        self.repository.save(later)

        self.assertEqual(self.repository.get(initial.identity), later)
        self.assertEqual(self.repository.all(), (later,))
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM processing_runs WHERE identity = ?",
                (initial.identity.value,),
            ).fetchone(),
            (1,),
        )
        names = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertFalse(any("history" in name for name in names))
        self.assertFalse(hasattr(self.repository, "history"))

    def test_all_returns_each_current_snapshot_once_in_insertion_order(self) -> None:
        first = self._initial_run("run-z")
        second = self._initial_run("run-a")
        self.repository.save(first)
        self.repository.save(second)
        self.repository.save(self._later_run("run-z"))
        self.assertEqual(
            self.repository.all(), (self._later_run("run-z"), second)
        )

    def test_parent_insert_failure_leaves_no_run(self) -> None:
        self.connection.execute(
            """
            CREATE TRIGGER reject_run_insert BEFORE INSERT ON processing_runs
            BEGIN SELECT RAISE(ABORT, 'injected parent failure'); END
            """
        )
        with self.assertRaises(PersistenceError) as caught:
            self.repository.save(self._initial_run())
        self.assertNotIsInstance(caught.exception, sqlite3.Error)
        self.assertEqual(self.repository.all(), ())

    def test_child_failure_for_new_run_rolls_back_parent_and_children(self) -> None:
        self.connection.execute(
            """
            CREATE TRIGGER reject_new_input BEFORE INSERT ON processing_run_inputs
            BEGIN SELECT RAISE(ABORT, 'injected child failure'); END
            """
        )
        with self.assertRaises(PersistenceError):
            self.repository.save(self._initial_run())
        self.assertEqual(self.repository.all(), ())
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM processing_run_inputs").fetchone(),
            (0,),
        )

    def test_replacement_child_failure_preserves_previous_complete_snapshot(self) -> None:
        initial = self._initial_run()
        self.repository.save(initial)
        self.connection.execute(
            """
            CREATE TRIGGER reject_replacement_input
            BEFORE INSERT ON processing_run_inputs
            BEGIN SELECT RAISE(ABORT, 'injected replacement failure'); END
            """
        )
        with self.assertRaises(PersistenceError):
            self.repository.save(self._later_run())
        self.assertEqual(self.repository.get(initial.identity), initial)

    def test_failure_after_some_new_children_preserves_previous_snapshot(self) -> None:
        initial = self._initial_run()
        self.repository.save(initial)
        self.connection.execute(
            """
            CREATE TRIGGER reject_second_upstream
            BEFORE INSERT ON processing_run_upstream_results
            WHEN NEW.ordinal = 1
            BEGIN SELECT RAISE(ABORT, 'injected later child failure'); END
            """
        )
        with self.assertRaises(PersistenceError):
            self.repository.save(self._later_run())
        self.assertEqual(self.repository.get(initial.identity), initial)

    def test_parent_update_failure_preserves_previous_snapshot(self) -> None:
        initial = self._initial_run()
        self.repository.save(initial)
        self.connection.execute(
            """
            CREATE TRIGGER reject_run_update BEFORE UPDATE ON processing_runs
            BEGIN SELECT RAISE(ABORT, 'injected update failure'); END
            """
        )
        with self.assertRaises(PersistenceError):
            self.repository.save(self._later_run())
        self.assertEqual(self.repository.get(initial.identity), initial)

    def test_commit_failure_rolls_back_and_does_not_return_success(self) -> None:
        initial = self._initial_run()
        self.repository.save(initial)
        with patch.object(
            self.repository,
            "_commit",
            side_effect=sqlite3.OperationalError("injected commit failure"),
        ):
            with self.assertRaises(PersistenceError):
                self.repository.save(self._later_run())
        self.assertEqual(self.repository.get(initial.identity), initial)

    def test_unknown_state_and_malformed_domain_values_fail_explicitly(self) -> None:
        run = self._initial_run()
        self.repository.save(run)
        self.connection.execute("PRAGMA ignore_check_constraints = ON")
        self.connection.execute(
            "UPDATE processing_runs SET state = 'unknown' WHERE identity = ?",
            (run.identity.value,),
        )
        self.connection.execute("PRAGMA ignore_check_constraints = OFF")
        with self.assertRaises(ValueError):
            self.repository.get(run.identity)

        self.connection.execute("PRAGMA ignore_check_constraints = ON")
        self.connection.execute(
            "UPDATE processing_runs SET state = 'running', intent_purpose = '  ' WHERE identity = ?",
            (run.identity.value,),
        )
        self.connection.execute("PRAGMA ignore_check_constraints = OFF")
        with self.assertRaises(ValueError):
            self.repository.get(run.identity)

    def test_malformed_reference_and_empty_optional_are_domain_errors(self) -> None:
        run = self._initial_run()
        self.repository.save(run)
        self.connection.execute(
            "UPDATE processing_runs SET configuration = '' WHERE identity = ?",
            (run.identity.value,),
        )
        with self.assertRaises(ValueError):
            self.repository.get(run.identity)
        self.connection.execute(
            "UPDATE processing_runs SET configuration = NULL WHERE identity = ?",
            (run.identity.value,),
        )
        self.connection.execute(
            """
            UPDATE processing_run_inputs SET input_reference = ' '
            WHERE processing_run_id = ? AND ordinal = 0
            """,
            (run.identity.value,),
        )
        with self.assertRaises(ValueError):
            self.repository.get(run.identity)

    def test_ordinal_gap_is_detected_and_duplicate_is_schema_rejected(self) -> None:
        run = self._initial_run()
        self.repository.save(run)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO processing_run_inputs VALUES (?, 0, ?)",
                (run.identity.value, "duplicate"),
            )
        self.connection.execute(
            "DELETE FROM processing_run_inputs WHERE processing_run_id = ? AND ordinal = 0",
            (run.identity.value,),
        )
        with self.assertRaises(PersistenceError):
            self.repository.get(run.identity)

    def test_repository_keeps_connection_caller_owned_and_has_protocol_only(self) -> None:
        self.repository.save(self._initial_run())
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))
        self.assertFalse(hasattr(self.repository, "update"))
        self.assertFalse(hasattr(self.repository, "delete"))
        self.assertFalse(hasattr(self.repository, "insert"))
        self.assertFalse(hasattr(self.repository, "replace"))


if __name__ == "__main__":
    unittest.main()
