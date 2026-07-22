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
    WorkingContextReference,
)
from lectureos.execution.models import (
    ExecutionIntent,
    ExecutionOutcome,
    FailureCategory,
    OutcomeKind,
    ProcessingRun,
    ProcessingState,
    ProcessingUnit,
    UnitExecution,
)
from lectureos.persistence import (
    PersistenceError,
    SQLITE_SCHEMA_VERSION,
    SQLiteProcessingRunRepository,
    SQLiteProcessingUnitRepository,
    SQLiteUnitExecutionRepository,
    UnsupportedSchemaVersionError,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle


V4_TABLES = {
    "domain_result_references",
    "domain_result_upstream_results",
    "failures",
    "failure_affected_inputs",
    "failure_affected_results",
    "failure_diagnostics",
}


def create_legacy_database(path: Path, version: int) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN")
    statements = list(sqlite_lifecycle._V1_TABLE_STATEMENTS)
    if version >= 2:
        statements.extend(sqlite_lifecycle._V2_ADDITION_STATEMENTS)
    if version >= 3:
        statements.extend(sqlite_lifecycle._V3_ADDITION_STATEMENTS)
    if version >= 4:
        statements.extend(sqlite_lifecycle._V4_ADDITION_STATEMENTS)
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


class SQLiteSchemaVersionFourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def _unit() -> ProcessingUnit:
        return ProcessingUnit(
            identity=ProcessingUnitId("unit-v4"),
            purpose="Preserved v4 unit",
            dependencies=(ProcessingUnitId("dependency-b"), ProcessingUnitId("dependency-a")),
            capabilities=(CapabilityReference("capability-b"), CapabilityReference("capability-a")),
            result_kinds=("kind-b", "kind-a"),
            independently_retryable=False,
        )

    @staticmethod
    def _run() -> ProcessingRun:
        return ProcessingRun(
            identity=ProcessingRunId("run-v4"),
            intent=ExecutionIntent("Preserved v4 run"),
            working_context=WorkingContextReference("context-v4"),
            input_references=(InputReference("run-input-b"), InputReference("run-input-a")),
            upstream_results=(DomainResultId("upstream-b"), DomainResultId("upstream-a")),
            configuration=ConfigurationReference("configuration-v4"),
            unit_references=(ProcessingUnitId("unit-b"), ProcessingUnitId("unit-a")),
            unit_execution_references=(UnitExecutionId("execution-v4"),),
            state=ProcessingState.RUNNING,
            result_references=(DomainResultId("result-b"), DomainResultId("result-a")),
            failure_references=(FailureId("failure-b"), FailureId("failure-a")),
        )

    @staticmethod
    def _execution() -> UnitExecution:
        return UnitExecution(
            identity=UnitExecutionId("execution-v4"),
            run_id=ProcessingRunId("run-v4"),
            unit_id=ProcessingUnitId("unit-v4"),
            input_references=(InputReference("execution-input-b"), InputReference("execution-input-a")),
            configuration=ConfigurationReference("configuration-v4"),
            capabilities=(CapabilityReference("capability-b"), CapabilityReference("capability-a")),
            plugins=(PluginReference("plugin-b"), PluginReference("plugin-a")),
            state=ProcessingState.COMPLETED,
            outcome=ExecutionOutcome(OutcomeKind.PARTIAL_RESULT, "preserved"),
            result_references=(DomainResultId("result-b"), DomainResultId("result-a")),
            failure_references=(FailureId("failure-b"), FailureId("failure-a")),
            diagnostic_references=(DiagnosticId("diagnostic-b"), DiagnosticId("diagnostic-a")),
        )

    def _populate_v3(self):
        connection = create_legacy_database(self.database_path, 3)
        unit = self._unit()
        run = self._run()
        execution = self._execution()
        SQLiteProcessingUnitRepository(connection).save(unit)
        SQLiteProcessingRunRepository(connection).save(run)
        SQLiteUnitExecutionRepository(connection).save(execution)
        connection.close()
        return unit, run, execution

    def _assert_old_data(self, connection, unit, run, execution) -> None:
        self.assertEqual(SQLiteProcessingUnitRepository(connection).get(unit.identity), unit)
        self.assertEqual(SQLiteProcessingRunRepository(connection).get(run.identity), run)
        self.assertEqual(SQLiteUnitExecutionRepository(connection).get(execution.identity), execution)

    def test_new_database_includes_complete_frozen_v4(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertEqual(SQLITE_SCHEMA_VERSION, 13)
            self.assertEqual(connection.execute("SELECT version FROM schema_metadata").fetchone(), (13,))
            self.assertTrue(V4_TABLES.issubset(table_names(connection)))
            self.assertEqual(sqlite_lifecycle.validate_sqlite_connection(connection), 13)
        finally:
            connection.close()
        open_sqlite_database(self.database_path).close()

    def test_frozen_v1_v2_and_v3_open_without_v4_or_mutation(self) -> None:
        for version in (1, 2, 3):
            with self.subTest(version=version):
                path = Path(self.temporary_directory.name) / f"v{version}.sqlite3"
                connection = create_legacy_database(path, version)
                before = table_names(connection)
                connection.close()
                reopened = open_sqlite_database(path)
                self.assertEqual(reopened.execute("SELECT version FROM schema_metadata").fetchone(), (version,))
                self.assertEqual(table_names(reopened), before)
                self.assertTrue(V4_TABLES.isdisjoint(before))
                reopened.close()

    def test_v3_migrates_to_v4_preserving_complete_existing_snapshots(self) -> None:
        unit, run, execution = self._populate_v3()
        migrate_sqlite_database(self.database_path, target_version=4)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT version FROM schema_metadata").fetchone(), (4,))
            self.assertTrue(V4_TABLES.issubset(table_names(connection)))
            self._assert_old_data(connection, unit, run, execution)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM domain_result_references").fetchone(), (0,))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM failures").fetchone(), (0,))
        finally:
            connection.close()

    def test_v4_to_v4_is_validated_no_op(self) -> None:
        connection = create_legacy_database(self.database_path, 4)
        connection.execute(
            "INSERT INTO domain_result_references(identity, kind) VALUES ('result', 'kind')"
        )
        before = table_names(connection)
        connection.close()
        migrate_sqlite_database(self.database_path, target_version=4)
        reopened = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(table_names(reopened), before)
            self.assertEqual(reopened.execute("SELECT identity, kind FROM domain_result_references").fetchall(), [("result", "kind")])
        finally:
            reopened.close()

    def test_direct_lower_version_paths_downgrade_and_unknown_marker_are_rejected(self) -> None:
        for version in (1, 2):
            path = Path(self.temporary_directory.name) / f"reject-v{version}.sqlite3"
            connection = create_legacy_database(path, version)
            before = table_names(connection)
            connection.close()
            with self.assertRaises(PersistenceError):
                migrate_sqlite_database(path, target_version=4)
            reopened = open_sqlite_database(path)
            self.assertEqual(table_names(reopened), before)
            self.assertEqual(reopened.execute("SELECT version FROM schema_metadata").fetchone(), (version,))
            reopened.close()

        connection = initialize_sqlite_database(self.database_path)
        connection.close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, target_version=3)
        connection = open_sqlite_database(self.database_path)
        connection.execute("UPDATE schema_metadata SET version = 99")
        connection.close()
        with self.assertRaises(UnsupportedSchemaVersionError):
            migrate_sqlite_database(self.database_path, target_version=4)

    def test_conflicts_during_result_or_failure_ddl_roll_back_to_v3(self) -> None:
        for conflict in ("domain_result_upstream_results", "failures"):
            with self.subTest(conflict=conflict):
                path = Path(self.temporary_directory.name) / f"conflict-{conflict}.sqlite3"
                connection = create_legacy_database(path, 3)
                connection.execute(f"CREATE TABLE {conflict}(wrong TEXT)")
                connection.close()
                with self.assertRaises(PersistenceError):
                    migrate_sqlite_database(path, target_version=4)
                reopened = open_sqlite_database(path)
                self.assertEqual(reopened.execute("SELECT version FROM schema_metadata").fetchone(), (3,))
                created = V4_TABLES - {conflict}
                self.assertTrue(created.isdisjoint(table_names(reopened)))
                reopened.close()

    def test_marker_validation_and_commit_failures_roll_back_and_preserve_data(self) -> None:
        scenarios = ("marker", "validation", "commit")
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                path = Path(self.temporary_directory.name) / f"{scenario}.sqlite3"
                self.database_path = path
                unit, run, execution = self._populate_v3()
                if scenario == "marker":
                    connection = open_sqlite_database(path)
                    connection.execute(
                        """CREATE TRIGGER reject_v4_marker BEFORE UPDATE ON schema_metadata
                        BEGIN SELECT RAISE(ABORT, 'injected marker failure'); END"""
                    )
                    connection.close()
                    context = patch.object(sqlite_lifecycle, "_commit", wraps=sqlite_lifecycle._commit)
                elif scenario == "validation":
                    original = sqlite_lifecycle._validate_schema_shape

                    def validate(connection, version):
                        if version == 4:
                            raise PersistenceError("injected v4 validation failure")
                        return original(connection, version)

                    context = patch.object(sqlite_lifecycle, "_validate_schema_shape", side_effect=validate)
                else:
                    context = patch.object(
                        sqlite_lifecycle,
                        "_commit",
                        side_effect=sqlite3.OperationalError("injected commit failure"),
                    )
                with context:
                    with self.assertRaises(PersistenceError):
                        migrate_sqlite_database(path, target_version=4)
                reopened = open_sqlite_database(path)
                try:
                    self.assertEqual(reopened.execute("SELECT version FROM schema_metadata").fetchone(), (3,))
                    self.assertTrue(V4_TABLES.isdisjoint(table_names(reopened)))
                    self._assert_old_data(reopened, unit, run, execution)
                finally:
                    reopened.close()

    def test_v4_required_tables_and_columns_are_strictly_validated(self) -> None:
        for table in V4_TABLES:
            with self.subTest(table=table):
                path = Path(self.temporary_directory.name) / f"missing-{table}.sqlite3"
                connection = initialize_sqlite_database(path)
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute(f"DROP TABLE {table}")
                connection.close()
                with self.assertRaises(PersistenceError):
                    open_sqlite_database(path)

        path = Path(self.temporary_directory.name) / "malformed.sqlite3"
        connection = initialize_sqlite_database(path)
        connection.execute("DROP TABLE failure_diagnostics")
        connection.execute("CREATE TABLE failure_diagnostics(wrong TEXT)")
        connection.close()
        with self.assertRaises(PersistenceError):
            open_sqlite_database(path)

    def test_v4_owned_child_foreign_keys_are_strictly_validated(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DROP TABLE failure_diagnostics")
        connection.execute(
            """CREATE TABLE failure_diagnostics (
            failure_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
            diagnostic_id TEXT NOT NULL,
            PRIMARY KEY (failure_id, ordinal)
            )"""
        )
        connection.close()
        with self.assertRaises(PersistenceError):
            open_sqlite_database(self.database_path)

    def test_domain_result_constraints_order_and_external_reference_policy(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO domain_result_references(identity, kind) VALUES ('blank', '   ')")
            connection.execute(
                """INSERT INTO domain_result_references(
                identity, kind, source_media_id, source_timeline_id, revision_of, applicability
                ) VALUES ('result', 'subtitle', 'missing-media', 'missing-timeline', 'missing-result', '')"""
            )
            connection.execute("INSERT INTO domain_result_upstream_results VALUES ('result', 0, 'same')")
            connection.execute("INSERT INTO domain_result_upstream_results VALUES ('result', 1, 'same')")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO domain_result_upstream_results VALUES ('result', -1, 'bad')")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO domain_result_upstream_results VALUES ('result', 1, 'duplicate-position')")
            self.assertEqual(connection.execute("PRAGMA foreign_key_list(domain_result_references)").fetchall(), [])
            connection.execute("DELETE FROM domain_result_references WHERE identity = 'result'")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM domain_result_upstream_results").fetchone(), (0,))
        finally:
            connection.close()

    def test_failure_constraints_children_cascade_and_external_references(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            base = "INSERT INTO failures VALUES (?, ?, ?, ?, ?, ?, ?)"
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(base, ("bad-category", "unknown", "run", None, 0, 0, 0))
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(base, ("bad-boolean", "processing", "run", None, 2, 0, 0))
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(base, ("missing-provenance", "processing", None, None, 0, 0, 0))
            for category in FailureCategory:
                connection.execute(
                    base,
                    (f"failure-{category.value}", category.value, "opaque-run", None, 1, 0, 0),
                )
            connection.execute("INSERT INTO failure_affected_inputs VALUES ('failure-processing', 0, 'input')")
            connection.execute("INSERT INTO failure_affected_results VALUES ('failure-processing', 0, 'missing-result')")
            connection.execute("INSERT INTO failure_diagnostics VALUES ('failure-processing', 0, 'missing-diagnostic')")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO failure_affected_inputs VALUES ('failure-processing', -1, 'bad')")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO failure_affected_inputs VALUES ('failure-processing', 0, 'duplicate')")
            self.assertEqual(connection.execute("PRAGMA foreign_key_list(failures)").fetchall(), [])
            connection.execute("DELETE FROM failures WHERE identity = 'failure-processing'")
            for table in ("failure_affected_inputs", "failure_affected_results", "failure_diagnostics"):
                self.assertEqual(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone(), (0,))
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
