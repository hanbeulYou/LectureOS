import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.persistence import (
    PersistenceError,
    SQLITE_SCHEMA_VERSION,
    SQLiteTranscriptSourceIntakeRepository,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle

V31_TABLES = {"transcript_source_intakes"}

_ADDITION_BLOCKS = tuple(
    (level, getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS"))
    for level in range(2, 43)
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


class SQLiteSchemaVersionThirtyOneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_v31_remains_a_supported_version(self) -> None:
        self.assertIn(31, sqlite_lifecycle._SUPPORTED_SCHEMA_VERSIONS)
        self.assertLessEqual(31, SQLITE_SCHEMA_VERSION)

    def test_fresh_database_initializes_with_v31_tables(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V31_TABLES.issubset(table_names(connection)))
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
        finally:
            connection.close()

    def test_migrates_v30_to_v31_preserving_existing_rows(self) -> None:
        create_legacy_database(self.database_path, 30)
        migrate_sqlite_database(self.database_path, 31)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertTrue(V31_TABLES.issubset(table_names(connection)))
            preserved = connection.execute(
                "SELECT purpose FROM processing_units WHERE identity = 'unit'"
            ).fetchone()
            self.assertEqual(preserved[0], "preserved")
        finally:
            connection.close()

    def test_v31_no_op_migration_is_allowed(self) -> None:
        create_legacy_database(self.database_path, 30)
        migrate_sqlite_database(self.database_path, 31)
        migrate_sqlite_database(self.database_path, 31)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                31,
            )
        finally:
            connection.close()

    def test_direct_v29_to_v31_is_rejected(self) -> None:
        create_legacy_database(self.database_path, 29)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 31)

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 44)

    def test_repository_rejects_pre_v31_schema(self) -> None:
        create_legacy_database(self.database_path, 30)
        connection = open_sqlite_database(self.database_path)
        try:
            with self.assertRaises(Exception):
                SQLiteTranscriptSourceIntakeRepository(connection)
        finally:
            connection.close()

    def test_every_released_version_chains_to_v31_preserving_data(self) -> None:
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
                    self.assertTrue(V31_TABLES.issubset(table_names(connection)))
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
