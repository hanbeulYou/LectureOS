import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.persistence import (
    PersistenceError,
    SQLITE_SCHEMA_VERSION,
    SQLiteSubtitleValidationRepository,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle

V15_TABLES = {"subtitle_validations", "subtitle_validation_findings"}

_ADDITION_BLOCKS = tuple(
    (level, getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS"))
    for level in range(2, 29)
)


def create_legacy_database(path: Path, version: int) -> None:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
    for level, block in _ADDITION_BLOCKS:
        if version >= level:
            statements += block
    connection.execute("BEGIN")
    for statement in statements:
        connection.execute(statement)
    connection.execute("INSERT INTO schema_metadata VALUES (1, ?)", (version,))
    connection.execute(
        "INSERT INTO processing_units VALUES ('unit', 'preserved', 1)"
    )
    connection.execute("COMMIT")
    connection.close()


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


class SQLiteSchemaVersionFifteenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_v15_remains_a_supported_version(self) -> None:
        self.assertIn(15, sqlite_lifecycle._SUPPORTED_SCHEMA_VERSIONS)
        self.assertGreaterEqual(SQLITE_SCHEMA_VERSION, 15)

    def test_fresh_database_initializes_with_v15_tables(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V15_TABLES.issubset(table_names(connection)))
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
        finally:
            connection.close()

    def test_migrates_v14_to_v15_preserving_existing_rows(self) -> None:
        create_legacy_database(self.database_path, 14)
        migrate_sqlite_database(self.database_path, 15)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertTrue(V15_TABLES.issubset(table_names(connection)))
            preserved = connection.execute(
                "SELECT purpose FROM processing_units WHERE identity = 'unit'"
            ).fetchone()
            self.assertEqual(preserved[0], "preserved")
        finally:
            connection.close()

    def test_v15_no_op_migration_is_allowed(self) -> None:
        create_legacy_database(self.database_path, 14)
        migrate_sqlite_database(self.database_path, 15)
        migrate_sqlite_database(self.database_path, 15)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                15,
            )
        finally:
            connection.close()

    def test_direct_v13_to_v15_is_rejected(self) -> None:
        create_legacy_database(self.database_path, 13)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 15)

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 30)

    def test_repository_rejects_pre_v15_schema(self) -> None:
        create_legacy_database(self.database_path, 14)
        connection = open_sqlite_database(self.database_path)
        try:
            with self.assertRaises(Exception):
                SQLiteSubtitleValidationRepository(connection)
        finally:
            connection.close()

    def test_every_released_version_chains_to_v15_preserving_data(self) -> None:
        # Migration compatibility: every released schema version reaches v15 through the
        # supported single-step chain, preserving existing rows and meaning.
        for start in range(1, SQLITE_SCHEMA_VERSION):
            with self.subTest(start=start):
                path = Path(self.temporary_directory.name) / f"chain-v{start}.sqlite3"
                create_legacy_database(path, start)
                for target in range(start + 1, SQLITE_SCHEMA_VERSION + 1):
                    migrate_sqlite_database(path, target)
                connection = open_sqlite_database(path)
                try:
                    self.assertEqual(
                        connection.execute(
                            "SELECT version FROM schema_metadata"
                        ).fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    self.assertTrue(V15_TABLES.issubset(table_names(connection)))
                    self.assertEqual(
                        connection.execute(
                            "SELECT purpose FROM processing_units WHERE identity = 'unit'"
                        ).fetchone()[0],
                        "preserved",
                    )
                finally:
                    connection.close()


if __name__ == "__main__":
    unittest.main()
