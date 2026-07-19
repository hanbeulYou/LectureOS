import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lectureos.execution.identities import (
    CapabilityReference,
    ConfigurationReference,
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
    OutcomeKind,
    ProcessingRun,
    ProcessingState,
    ProcessingUnit,
)
from lectureos.persistence import (
    PersistenceError,
    SQLiteProcessingRunRepository,
    SQLiteProcessingUnitRepository,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle


V3_TABLES = {
    "unit_executions",
    "unit_execution_inputs",
    "unit_execution_capabilities",
    "unit_execution_plugins",
    "unit_execution_results",
    "unit_execution_failures",
    "unit_execution_diagnostics",
}


def create_legacy_database(path: Path, version: int) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN")
    statements = list(sqlite_lifecycle._V1_TABLE_STATEMENTS)
    if version == 2:
        statements.extend(sqlite_lifecycle._V2_ADDITION_STATEMENTS)
    for statement in statements:
        connection.execute(statement)
    connection.execute("INSERT INTO schema_metadata VALUES (1, ?)", (version,))
    connection.execute("COMMIT")
    return connection


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


class SQLiteSchemaVersionThreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _unit(self) -> ProcessingUnit:
        return ProcessingUnit(
            identity=ProcessingUnitId("unit-v3"),
            purpose="Preserved unit",
            dependencies=(ProcessingUnitId("dep-b"), ProcessingUnitId("dep-a")),
            capabilities=(CapabilityReference("cap-b"), CapabilityReference("cap-a")),
            result_kinds=("kind-b", "kind-a"),
            independently_retryable=False,
        )

    def _run(self) -> ProcessingRun:
        return ProcessingRun(
            identity=ProcessingRunId("run-v3"),
            intent=ExecutionIntent(
                "Preserved run", reprocessing_of=ProcessingRunId("intent-source")
            ),
            working_context=WorkingContextReference("context-v3"),
            input_references=(InputReference("input-b"), InputReference("input-a")),
            upstream_results=(DomainResultId("upstream-b"), DomainResultId("upstream-a")),
            configuration=ConfigurationReference("configuration-v3"),
            unit_references=(ProcessingUnitId("unit-b"), ProcessingUnitId("unit-a")),
            unit_execution_references=(
                UnitExecutionId("execution-b"),
                UnitExecutionId("execution-a"),
            ),
            state=ProcessingState.RUNNING,
            result_references=(DomainResultId("result-b"), DomainResultId("result-a")),
            failure_references=(FailureId("failure-b"), FailureId("failure-a")),
            reprocessing_of=ProcessingRunId("lineage-source"),
        )

    def _populate_v2(self) -> tuple[ProcessingUnit, ProcessingRun]:
        connection = create_legacy_database(self.database_path, 2)
        unit = self._unit()
        run = self._run()
        SQLiteProcessingUnitRepository(connection).save(unit)
        SQLiteProcessingRunRepository(connection).save(run)
        connection.close()
        return unit, run

    def _assert_preserved(
        self, connection: sqlite3.Connection, unit: ProcessingUnit, run: ProcessingRun
    ) -> None:
        self.assertEqual(SQLiteProcessingUnitRepository(connection).get(unit.identity), unit)
        self.assertEqual(SQLiteProcessingRunRepository(connection).get(run.identity), run)

    def test_frozen_v1_and_v2_open_without_later_schema_requirements(self) -> None:
        v1_path = Path(self.temporary_directory.name) / "legacy-v1.sqlite3"
        create_legacy_database(v1_path, 1).close()
        v1 = open_sqlite_database(v1_path)
        self.assertTrue(V3_TABLES.isdisjoint(table_names(v1)))
        self.assertNotIn("processing_runs", table_names(v1))
        v1.close()

        create_legacy_database(self.database_path, 2).close()
        v2 = open_sqlite_database(self.database_path)
        self.assertIn("processing_runs", table_names(v2))
        self.assertTrue(V3_TABLES.isdisjoint(table_names(v2)))
        v2.close()

    def test_malformed_frozen_v1_and_v2_still_fail(self) -> None:
        v1_path = Path(self.temporary_directory.name) / "malformed-v1.sqlite3"
        v1 = create_legacy_database(v1_path, 1)
        v1.execute("DROP TABLE processing_unit_capabilities")
        v1.close()
        with self.assertRaises(PersistenceError):
            open_sqlite_database(v1_path)

        v2 = create_legacy_database(self.database_path, 2)
        v2.execute("DROP TABLE processing_run_results")
        v2.close()
        with self.assertRaises(PersistenceError):
            open_sqlite_database(self.database_path)

    def test_new_initializer_includes_complete_v3_and_existing_repositories_work(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone(),
                (5,),
            )
            self.assertTrue(V3_TABLES.issubset(table_names(connection)))
            unit = self._unit()
            run = self._run()
            SQLiteProcessingUnitRepository(connection).save(unit)
            SQLiteProcessingRunRepository(connection).save(run)
            self._assert_preserved(connection, unit, run)
        finally:
            connection.close()
        open_sqlite_database(self.database_path).close()

    def test_new_v3_initialization_is_transactional_on_commit_failure(self) -> None:
        with patch.object(
            sqlite_lifecycle,
            "_commit",
            side_effect=sqlite3.OperationalError("injected initialization commit failure"),
        ):
            with self.assertRaises(PersistenceError):
                initialize_sqlite_database(self.database_path)
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(table_names(connection), set())
        finally:
            connection.close()

    def test_v2_migrates_to_v3_preserving_all_existing_data_without_backfill(self) -> None:
        unit, run = self._populate_v2()
        migrate_sqlite_database(self.database_path, target_version=3)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone(),
                (3,),
            )
            self.assertTrue(V3_TABLES.issubset(table_names(connection)))
            self._assert_preserved(connection, unit, run)
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM unit_executions").fetchone(),
                (0,),
            )
        finally:
            connection.close()
        migrate_sqlite_database(self.database_path, target_version=3)
        open_sqlite_database(self.database_path).close()

    def test_open_and_repository_construction_do_not_migrate_v2(self) -> None:
        self._populate_v2()
        connection = open_sqlite_database(self.database_path)
        try:
            SQLiteProcessingUnitRepository(connection)
            SQLiteProcessingRunRepository(connection)
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone(),
                (2,),
            )
            self.assertTrue(V3_TABLES.isdisjoint(table_names(connection)))
        finally:
            connection.close()

    def test_target_three_rejects_v1_but_explicit_sequential_migration_works(self) -> None:
        create_legacy_database(self.database_path, 1).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, target_version=3)
        connection = open_sqlite_database(self.database_path)
        self.assertEqual(connection.execute("SELECT version FROM schema_metadata").fetchone(), (1,))
        connection.close()

        migrate_sqlite_database(self.database_path, target_version=2)
        migrate_sqlite_database(self.database_path, target_version=3)
        connection = open_sqlite_database(self.database_path)
        self.assertEqual(connection.execute("SELECT version FROM schema_metadata").fetchone(), (3,))
        connection.close()

    def test_failure_after_first_v3_ddl_rolls_back_and_preserves_v2(self) -> None:
        unit, run = self._populate_v2()
        connection = open_sqlite_database(self.database_path)
        connection.execute("CREATE TABLE unit_execution_inputs(conflict TEXT)")
        connection.close()
        with self.assertRaises(PersistenceError) as caught:
            migrate_sqlite_database(self.database_path, target_version=3)
        self.assertNotIsInstance(caught.exception, sqlite3.Error)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT version FROM schema_metadata").fetchone(), (2,))
            self.assertNotIn("unit_executions", table_names(connection))
            self._assert_preserved(connection, unit, run)
        finally:
            connection.close()

    def test_conflicting_parent_or_child_shape_blocks_migration(self) -> None:
        for table_name in ("unit_executions", "unit_execution_capabilities"):
            with self.subTest(table=table_name):
                path = Path(self.temporary_directory.name) / f"{table_name}.sqlite3"
                connection = create_legacy_database(path, 2)
                connection.execute(f"CREATE TABLE {table_name}(wrong TEXT)")
                connection.close()
                with self.assertRaises(PersistenceError):
                    migrate_sqlite_database(path, target_version=3)
                reopened = open_sqlite_database(path)
                self.assertEqual(
                    reopened.execute("SELECT version FROM schema_metadata").fetchone(),
                    (2,),
                )
                reopened.close()

    def test_marker_update_failure_rolls_back_and_preserves_v2_data(self) -> None:
        unit, run = self._populate_v2()
        connection = open_sqlite_database(self.database_path)
        connection.execute(
            """
            CREATE TRIGGER reject_v3_marker BEFORE UPDATE ON schema_metadata
            BEGIN SELECT RAISE(ABORT, 'injected marker failure'); END
            """
        )
        connection.close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, target_version=3)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT version FROM schema_metadata").fetchone(), (2,))
            self.assertTrue(V3_TABLES.isdisjoint(table_names(connection)))
            self._assert_preserved(connection, unit, run)
        finally:
            connection.close()

    def test_final_validation_failure_rolls_back_v3(self) -> None:
        unit, run = self._populate_v2()
        original_validate = sqlite_lifecycle._validate_schema_shape

        def fail_v3(connection: sqlite3.Connection, version: int) -> None:
            if version == 3:
                raise PersistenceError("injected v3 validation failure")
            original_validate(connection, version)

        with patch.object(sqlite_lifecycle, "_validate_schema_shape", side_effect=fail_v3):
            with self.assertRaises(PersistenceError):
                migrate_sqlite_database(self.database_path, target_version=3)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT version FROM schema_metadata").fetchone(), (2,))
            self.assertTrue(V3_TABLES.isdisjoint(table_names(connection)))
            self._assert_preserved(connection, unit, run)
        finally:
            connection.close()

    def test_commit_failure_rolls_back_v3_and_closes_owned_connection(self) -> None:
        unit, run = self._populate_v2()
        captured: list[sqlite3.Connection] = []
        original_connect = sqlite_lifecycle._connect

        def capture(path: Path) -> sqlite3.Connection:
            connection = original_connect(path)
            captured.append(connection)
            return connection

        with patch.object(sqlite_lifecycle, "_connect", side_effect=capture), patch.object(
            sqlite_lifecycle,
            "_commit",
            side_effect=sqlite3.OperationalError("injected commit failure"),
        ):
            with self.assertRaises(PersistenceError):
                migrate_sqlite_database(self.database_path, target_version=3)
        with self.assertRaises(sqlite3.ProgrammingError):
            captured[-1].execute("SELECT 1")
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT version FROM schema_metadata").fetchone(), (2,))
            self.assertTrue(V3_TABLES.isdisjoint(table_names(connection)))
            self._assert_preserved(connection, unit, run)
        finally:
            connection.close()

    def test_unit_execution_parent_representation_constraints(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        base = ("execution", "run", "unit", None)
        try:
            connection.execute(
                "INSERT INTO unit_executions(identity, processing_run_id, processing_unit_id, configuration, state) VALUES (?, ?, ?, ?, ?)",
                (*base, ProcessingState.PENDING.value),
            )
            connection.execute("DELETE FROM unit_executions")
            for state in ProcessingState:
                connection.execute(
                    "INSERT INTO unit_executions(identity, processing_run_id, processing_unit_id, state) VALUES (?, ?, ?, ?)",
                    (f"execution-{state.value}", "opaque-run", "opaque-unit", state.value),
                )
            for outcome in OutcomeKind:
                connection.execute(
                    "INSERT INTO unit_executions(identity, processing_run_id, processing_unit_id, state, outcome_kind) VALUES (?, ?, ?, ?, ?)",
                    (f"outcome-{outcome.value}", "run", "unit", "running", outcome.value),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO unit_executions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("bad-state", "run", "unit", None, "unknown", None, None, None, None, None),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO unit_executions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("bad-outcome", "run", "unit", None, "running", "unknown", None, None, None, None),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO unit_executions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("detail-only", "run", "unit", None, "running", None, "detail", None, None, None),
                )
            connection.execute(
                "INSERT INTO unit_executions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("completed-no-outcome", "run", "unit", None, "completed", None, None, None, None, None),
            )
            connection.execute(
                "INSERT INTO unit_executions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("running-outcome", "run", "unit", None, "running", "no_result", None, None, None, None),
            )
        finally:
            connection.close()

    def test_child_constraints_and_external_reference_policy(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertEqual(connection.execute("PRAGMA foreign_key_list(unit_executions)").fetchall(), [])
            connection.execute(
                "INSERT INTO unit_executions(identity, processing_run_id, processing_unit_id, state) VALUES ('execution', 'missing-run', 'missing-unit', 'running')"
            )
            connection.execute(
                "INSERT INTO unit_execution_inputs VALUES ('execution', 0, 'input-b')"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO unit_execution_inputs VALUES ('execution', -1, 'input-a')"
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO unit_execution_inputs VALUES ('missing', 0, 'input-a')"
                )
            for table in V3_TABLES - {"unit_executions"}:
                foreign_keys = connection.execute(
                    f"PRAGMA foreign_key_list({table})"
                ).fetchall()
                self.assertEqual(len(foreign_keys), 1)
                self.assertEqual(foreign_keys[0][2], "unit_executions")
        finally:
            connection.close()

    def test_boundary_adds_no_unapproved_aggregates(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            names = table_names(connection)
            self.assertNotIn("projects", names)
            self.assertNotIn("lectures", names)
            self.assertNotIn("source_media", names)
            self.assertNotIn("domain_results", names)
            self.assertNotIn("diagnostics", names)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
