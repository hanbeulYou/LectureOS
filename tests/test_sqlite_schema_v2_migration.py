import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lectureos.execution.identities import CapabilityReference, ProcessingUnitId
from lectureos.execution.models import ProcessingUnit
from lectureos.persistence import (
    PersistenceError,
    SQLITE_SCHEMA_VERSION,
    SQLiteProcessingUnitRepository,
    SchemaFeatureUnavailableError,
    UnsupportedSchemaVersionError,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle


V2_TABLES = {
    "processing_runs",
    "processing_run_inputs",
    "processing_run_upstream_results",
    "processing_run_units",
    "processing_run_unit_executions",
    "processing_run_results",
    "processing_run_failures",
}


def create_legacy_v1_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN")
    for statement in sqlite_lifecycle._V1_TABLE_STATEMENTS:
        connection.execute(statement)
    connection.execute(
        "INSERT INTO schema_metadata(singleton, version) VALUES (1, 1)"
    )
    connection.execute("COMMIT")
    return connection


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


class SQLiteSchemaVersionTwoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _unit(self) -> ProcessingUnit:
        return ProcessingUnit(
            identity=ProcessingUnitId("unit-migrate"),
            purpose="Preserve this unit",
            dependencies=(ProcessingUnitId("dep-second"), ProcessingUnitId("dep-first")),
            capabilities=(CapabilityReference("cap-second"), CapabilityReference("cap-first")),
            result_kinds=("result-second", "result-first"),
            independently_retryable=False,
        )

    def test_frozen_v1_opens_without_processing_run_tables_or_mutation(self) -> None:
        create_legacy_v1_database(self.database_path).close()
        connection = open_sqlite_database(self.database_path)
        try:
            before = table_names(connection)
            self.assertTrue(V2_TABLES.isdisjoint(before))
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone(),
                (1,),
            )
            SQLiteProcessingUnitRepository(connection)
            self.assertEqual(table_names(connection), before)
        finally:
            connection.close()

    def test_processing_unit_repository_reads_and_writes_on_v1(self) -> None:
        connection = create_legacy_v1_database(self.database_path)
        try:
            repository = SQLiteProcessingUnitRepository(connection)
            unit = self._unit()
            repository.save(unit)
            self.assertEqual(repository.get(unit.identity), unit)
        finally:
            connection.close()

    def test_malformed_v1_still_fails(self) -> None:
        connection = create_legacy_v1_database(self.database_path)
        connection.execute("DROP TABLE processing_unit_result_kinds")
        connection.close()
        with self.assertRaises(PersistenceError):
            open_sqlite_database(self.database_path)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, target_version=2)

    def test_new_initializer_contains_complete_version_two_foundation(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertEqual(SQLITE_SCHEMA_VERSION, 28)
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone(),
                (28,),
            )
            self.assertTrue(V2_TABLES.issubset(table_names(connection)))
            unit = self._unit()
            repository = SQLiteProcessingUnitRepository(connection)
            repository.save(unit)
            self.assertEqual(repository.get(unit.identity), unit)
        finally:
            connection.close()
        open_sqlite_database(self.database_path).close()

    def test_malformed_v2_child_table_fails_on_reopen(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        connection.execute("DROP TABLE processing_run_failures")
        connection.execute("CREATE TABLE processing_run_failures(wrong TEXT)")
        connection.close()
        with self.assertRaises(PersistenceError):
            open_sqlite_database(self.database_path)

    def test_valid_v1_migrates_to_v2_and_preserves_ordered_unit_data(self) -> None:
        connection = create_legacy_v1_database(self.database_path)
        unit = self._unit()
        SQLiteProcessingUnitRepository(connection).save(unit)
        connection.close()

        migrate_sqlite_database(self.database_path, target_version=2)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone(),
                (2,),
            )
            self.assertTrue(V2_TABLES.issubset(table_names(connection)))
            self.assertEqual(SQLiteProcessingUnitRepository(connection).get(unit.identity), unit)
        finally:
            connection.close()

        migrate_sqlite_database(self.database_path, target_version=2)
        reopened = open_sqlite_database(self.database_path)
        self.assertEqual(SQLiteProcessingUnitRepository(reopened).get(unit.identity), unit)
        reopened.close()

    def test_ordinary_open_and_repository_construction_do_not_migrate_v1(self) -> None:
        create_legacy_v1_database(self.database_path).close()
        connection = initialize_sqlite_database(self.database_path)
        try:
            SQLiteProcessingUnitRepository(connection)
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone(),
                (1,),
            )
            self.assertTrue(V2_TABLES.isdisjoint(table_names(connection)))
        finally:
            connection.close()
        connection = open_sqlite_database(self.database_path)
        self.assertTrue(V2_TABLES.isdisjoint(table_names(connection)))
        connection.close()

    def test_failure_after_first_v2_ddl_rolls_back_new_tables_and_preserves_v1(self) -> None:
        connection = create_legacy_v1_database(self.database_path)
        unit = self._unit()
        SQLiteProcessingUnitRepository(connection).save(unit)
        connection.execute("CREATE TABLE processing_run_inputs(conflict TEXT)")
        connection.close()

        with self.assertRaises(PersistenceError) as caught:
            migrate_sqlite_database(self.database_path, target_version=2)
        self.assertNotIsInstance(caught.exception, sqlite3.Error)

        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone(),
                (1,),
            )
            self.assertNotIn("processing_runs", table_names(connection))
            self.assertEqual(SQLiteProcessingUnitRepository(connection).get(unit.identity), unit)
        finally:
            connection.close()

    def test_marker_update_failure_rolls_back_all_v2_structures(self) -> None:
        connection = create_legacy_v1_database(self.database_path)
        connection.execute(
            """
            CREATE TRIGGER reject_schema_version_update
            BEFORE UPDATE ON schema_metadata
            BEGIN SELECT RAISE(ABORT, 'injected marker failure'); END
            """
        )
        connection.close()

        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, target_version=2)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone(),
                (1,),
            )
            self.assertTrue(V2_TABLES.isdisjoint(table_names(connection)))
        finally:
            connection.close()

    def test_final_validation_failure_rolls_back_migration(self) -> None:
        create_legacy_v1_database(self.database_path).close()
        original_validate = sqlite_lifecycle._validate_schema_shape

        def fail_v2_validation(connection: sqlite3.Connection, version: int) -> None:
            if version == 2:
                raise PersistenceError("injected final validation failure")
            original_validate(connection, version)

        with patch.object(
            sqlite_lifecycle, "_validate_schema_shape", side_effect=fail_v2_validation
        ):
            with self.assertRaises(PersistenceError):
                migrate_sqlite_database(self.database_path, target_version=2)

        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone(),
                (1,),
            )
            self.assertTrue(V2_TABLES.isdisjoint(table_names(connection)))
        finally:
            connection.close()

    def test_unknown_version_and_unsupported_target_are_rejected_without_mutation(self) -> None:
        connection = create_legacy_v1_database(self.database_path)
        connection.execute("UPDATE schema_metadata SET version = 99")
        connection.close()
        with self.assertRaises(UnsupportedSchemaVersionError):
            migrate_sqlite_database(self.database_path, target_version=2)

        self.database_path.unlink()
        create_legacy_v1_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, target_version=3)
        connection = open_sqlite_database(self.database_path)
        self.assertEqual(connection.execute("SELECT version FROM schema_metadata").fetchone(), (1,))
        connection.close()

    def test_invalid_migration_paths_are_rejected(self) -> None:
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database("relative.sqlite3")
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database("file:/tmp/lectureos.sqlite3")
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, target_version=2)

    def test_conflicting_processing_run_shape_blocks_migration(self) -> None:
        connection = create_legacy_v1_database(self.database_path)
        connection.execute("CREATE TABLE processing_runs(identity INTEGER)")
        connection.close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, target_version=2)
        connection = open_sqlite_database(self.database_path)
        self.assertEqual(connection.execute("SELECT version FROM schema_metadata").fetchone(), (1,))
        connection.close()

    def test_migration_owned_connection_is_closed_on_success_and_failure(self) -> None:
        create_legacy_v1_database(self.database_path).close()
        connections: list[sqlite3.Connection] = []
        original_connect = sqlite_lifecycle._connect

        def capture_connect(path: Path) -> sqlite3.Connection:
            connection = original_connect(path)
            connections.append(connection)
            return connection

        with patch.object(sqlite_lifecycle, "_connect", side_effect=capture_connect):
            migrate_sqlite_database(self.database_path, target_version=2)
        with self.assertRaises(sqlite3.ProgrammingError):
            connections[-1].execute("SELECT 1")

        connection = open_sqlite_database(self.database_path)
        connection.execute("UPDATE schema_metadata SET version = 99")
        connection.close()
        with patch.object(sqlite_lifecycle, "_connect", side_effect=capture_connect):
            with self.assertRaises(UnsupportedSchemaVersionError):
                migrate_sqlite_database(self.database_path)
        with self.assertRaises(sqlite3.ProgrammingError):
            connections[-1].execute("SELECT 1")

    def test_feature_unavailable_error_is_a_persistence_error(self) -> None:
        self.assertTrue(issubclass(SchemaFeatureUnavailableError, PersistenceError))

    def test_unapproved_aggregates_are_not_added(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            names = table_names(connection)
            self.assertNotIn("projects", names)
            self.assertNotIn("lectures", names)
            self.assertNotIn("source_media", names)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
