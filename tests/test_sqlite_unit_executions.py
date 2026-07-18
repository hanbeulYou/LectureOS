import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lectureos.execution.identities import (
    CapabilityReference,
    ConfigurationReference,
    DiagnosticId,
    DomainResultId,
    FailureId,
    InputReference,
    PluginReference,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
)
from lectureos.execution.models import (
    ExecutionOutcome,
    OutcomeKind,
    ProcessingState,
    UnitExecution,
)
from lectureos.persistence import (
    PersistenceError,
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


class SQLiteUnitExecutionRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.repository = SQLiteUnitExecutionRepository(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def _initial(self, identity: str = "execution-main") -> UnitExecution:
        return UnitExecution(
            identity=UnitExecutionId(identity),
            run_id=ProcessingRunId("run-initial"),
            unit_id=ProcessingUnitId("unit-initial"),
            input_references=(InputReference("input-b"), InputReference("input-a")),
            configuration=ConfigurationReference("configuration-initial"),
            capabilities=(CapabilityReference("capability-b"), CapabilityReference("capability-a")),
            plugins=(PluginReference("plugin-b"), PluginReference("plugin-a")),
            state=ProcessingState.RUNNING,
            outcome=ExecutionOutcome(OutcomeKind.PARTIAL_RESULT, "partial detail"),
            result_references=(DomainResultId("result-b"), DomainResultId("result-a")),
            failure_references=(FailureId("failure-b"), FailureId("failure-a")),
            diagnostic_references=(DiagnosticId("diagnostic-b"), DiagnosticId("diagnostic-a")),
            retry_of=UnitExecutionId("execution-retry-source"),
            cancelled_from=UnitExecutionId("execution-cancel-source"),
            recovery_of=UnitExecutionId("execution-recovery-source"),
        )

    def _later(self, identity: str = "execution-main") -> UnitExecution:
        return UnitExecution(
            identity=UnitExecutionId(identity),
            run_id=ProcessingRunId("run-later"),
            unit_id=ProcessingUnitId("unit-later"),
            input_references=(InputReference("input-c"),),
            configuration=None,
            capabilities=(CapabilityReference("capability-c"),),
            plugins=(),
            state=ProcessingState.COMPLETED,
            outcome=ExecutionOutcome(OutcomeKind.DOMAIN_RESULT_GENERATED, "complete"),
            result_references=(DomainResultId("result-c"),),
            failure_references=(),
            diagnostic_references=(DiagnosticId("diagnostic-c"),),
            retry_of=None,
            cancelled_from=None,
            recovery_of=None,
        )

    def test_v3_supports_repository_and_lower_versions_are_unavailable_without_mutation(self) -> None:
        self.assertIsNone(self.repository.get(UnitExecutionId("missing")))
        for version in (1, 2):
            path = Path(self.temporary_directory.name) / f"legacy-v{version}.sqlite3"
            connection = create_legacy_database(path, version)
            tables_before = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteUnitExecutionRepository(connection)
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

    def test_missing_v3_schema_is_rejected_and_not_repaired(self) -> None:
        self.connection.execute("DROP TABLE unit_execution_diagnostics")
        with self.assertRaises(PersistenceError):
            SQLiteUnitExecutionRepository(self.connection)
        self.assertIsNone(
            self.connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'unit_execution_diagnostics'"
            ).fetchone()
        )

    def test_complete_snapshot_round_trips_with_exact_types_and_order(self) -> None:
        expected = self._initial()
        self.repository.save(expected)
        restored = self.repository.get(expected.identity)
        self.assertEqual(restored, expected)
        self.assertIs(type(restored.identity), UnitExecutionId)
        self.assertIs(type(restored.run_id), ProcessingRunId)
        self.assertIs(type(restored.unit_id), ProcessingUnitId)
        self.assertIs(type(restored.configuration), ConfigurationReference)
        self.assertIs(type(restored.outcome), ExecutionOutcome)
        self.assertIs(type(restored.outcome.kind), OutcomeKind)

    def test_none_and_empty_values_round_trip_distinctly(self) -> None:
        expected = UnitExecution(
            identity=UnitExecutionId("execution-empty"),
            run_id=ProcessingRunId("run-empty"),
            unit_id=ProcessingUnitId("unit-empty"),
        )
        self.repository.save(expected)
        self.assertEqual(self.repository.get(expected.identity), expected)
        row = self.connection.execute(
            "SELECT configuration, outcome_kind, outcome_detail FROM unit_executions WHERE identity = ?",
            (expected.identity.value,),
        ).fetchone()
        self.assertEqual(row, (None, None, None))

    def test_every_outcome_kind_and_detail_round_trips(self) -> None:
        for index, kind in enumerate(OutcomeKind):
            expected = UnitExecution(
                identity=UnitExecutionId(f"execution-outcome-{index}"),
                run_id=ProcessingRunId("run-outcome"),
                unit_id=ProcessingUnitId("unit-outcome"),
                outcome=ExecutionOutcome(kind, None if index % 2 else f"detail-{index}"),
            )
            self.repository.save(expected)
            self.assertEqual(self.repository.get(expected.identity), expected)

    def test_restart_restores_equal_typed_snapshot(self) -> None:
        expected = self._initial()
        self.repository.save(expected)
        self.connection.close()
        self.connection = open_sqlite_database(self.database_path)
        self.repository = SQLiteUnitExecutionRepository(self.connection)
        self.assertEqual(self.repository.get(expected.identity), expected)

    def test_same_identity_atomically_replaces_the_complete_snapshot(self) -> None:
        initial = self._initial()
        later = self._later()
        self.repository.save(initial)
        self.repository.save(later)
        self.repository.save(later)
        self.assertEqual(self.repository.get(initial.identity), later)
        self.assertEqual(self.repository.all(), (later,))
        self.assertFalse(hasattr(self.repository, "history"))
        self.assertFalse(hasattr(self.repository, "delete"))
        self.assertFalse(hasattr(self.repository, "update"))

    def test_all_is_deterministic_by_first_identity_insertion(self) -> None:
        first = self._initial("execution-first")
        second = self._initial("execution-second")
        self.repository.save(first)
        self.repository.save(second)
        self.repository.save(self._later("execution-first"))
        self.assertEqual(
            tuple(item.identity for item in self.repository.all()),
            (first.identity, second.identity),
        )

    def test_failure_in_each_child_table_rolls_back_new_snapshot(self) -> None:
        for table, _ in (
            ("unit_execution_inputs", "input_reference"),
            ("unit_execution_capabilities", "capability"),
            ("unit_execution_plugins", "plugin_reference"),
            ("unit_execution_results", "domain_result_id"),
            ("unit_execution_failures", "failure_id"),
            ("unit_execution_diagnostics", "diagnostic_id"),
        ):
            trigger = f"fail_{table}"
            self.connection.execute(
                f"CREATE TRIGGER {trigger} BEFORE INSERT ON {table} BEGIN SELECT RAISE(ABORT, 'injected'); END"
            )
            record = self._initial(f"execution-{table}")
            with self.assertRaises(PersistenceError) as raised:
                self.repository.save(record)
            self.assertNotIsInstance(raised.exception.__cause__, type(None))
            self.connection.execute(f"DROP TRIGGER {trigger}")
            self.assertIsNone(self.repository.get(record.identity))

    def test_failed_replacement_preserves_parent_and_all_previous_children(self) -> None:
        initial = self._initial()
        self.repository.save(initial)
        self.connection.execute(
            """CREATE TRIGGER fail_second_result BEFORE INSERT ON unit_execution_results
               WHEN NEW.ordinal = 0 BEGIN SELECT RAISE(ABORT, 'injected'); END"""
        )
        with self.assertRaises(PersistenceError):
            self.repository.save(self._later())
        self.assertEqual(self.repository.get(initial.identity), initial)

    def test_parent_insert_and_update_failures_rollback(self) -> None:
        self.connection.execute(
            "CREATE TRIGGER fail_parent_insert BEFORE INSERT ON unit_executions BEGIN SELECT RAISE(ABORT, 'injected'); END"
        )
        with self.assertRaises(PersistenceError):
            self.repository.save(self._initial())
        self.assertIsNone(self.repository.get(UnitExecutionId("execution-main")))
        self.connection.execute("DROP TRIGGER fail_parent_insert")
        initial = self._initial()
        self.repository.save(initial)
        self.connection.execute(
            "CREATE TRIGGER fail_parent_update BEFORE UPDATE ON unit_executions BEGIN SELECT RAISE(ABORT, 'injected'); END"
        )
        with self.assertRaises(PersistenceError):
            self.repository.save(self._later())
        self.assertEqual(self.repository.get(initial.identity), initial)

    def test_commit_failure_rolls_back_and_does_not_return_success(self) -> None:
        initial = self._initial()
        self.repository.save(initial)
        with patch.object(
            self.repository, "_commit", side_effect=sqlite3.OperationalError("commit failed")
        ):
            with self.assertRaises(PersistenceError):
                self.repository.save(self._later())
        self.assertEqual(self.repository.get(initial.identity), initial)

    def test_corrupt_enums_identities_and_ordinals_fail_explicitly(self) -> None:
        expected = self._initial()
        self.repository.save(expected)
        self.connection.execute("PRAGMA ignore_check_constraints = ON")
        self.connection.execute(
            "UPDATE unit_executions SET state = 'unknown' WHERE identity = ?",
            (expected.identity.value,),
        )
        with self.assertRaises(ValueError):
            self.repository.get(expected.identity)
        self.connection.execute(
            "UPDATE unit_executions SET state = ?, processing_run_id = '' WHERE identity = ?",
            (ProcessingState.RUNNING.value, expected.identity.value),
        )
        with self.assertRaises(ValueError):
            self.repository.get(expected.identity)
        self.connection.execute(
            "UPDATE unit_executions SET processing_run_id = ? WHERE identity = ?",
            ("run-initial", expected.identity.value),
        )
        self.connection.execute(
            "DELETE FROM unit_execution_inputs WHERE unit_execution_id = ? AND ordinal = 0",
            (expected.identity.value,),
        )
        with self.assertRaises(PersistenceError):
            self.repository.get(expected.identity)

    def test_corrupt_outcome_kind_fails_as_domain_value(self) -> None:
        expected = self._initial()
        self.repository.save(expected)
        self.connection.execute("PRAGMA ignore_check_constraints = ON")
        self.connection.execute(
            "UPDATE unit_executions SET outcome_kind = 'unknown' WHERE identity = ?",
            (expected.identity.value,),
        )
        with self.assertRaises(ValueError):
            self.repository.get(expected.identity)

    def test_schema_constraints_reject_negative_ordinals_and_detail_without_kind(self) -> None:
        expected = self._initial()
        self.repository.save(expected)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO unit_execution_inputs VALUES (?, -1, 'input')",
                (expected.identity.value,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """INSERT INTO unit_executions(
                       identity, processing_run_id, processing_unit_id, state, outcome_detail
                   ) VALUES ('bad-outcome', 'run', 'unit', 'running', 'detail')"""
            )

    def test_external_references_need_not_exist_and_connection_remains_caller_owned(self) -> None:
        expected = self._initial()
        self.repository.save(expected)
        self.assertEqual(self.repository.get(expected.identity), expected)
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))


if __name__ == "__main__":
    unittest.main()
