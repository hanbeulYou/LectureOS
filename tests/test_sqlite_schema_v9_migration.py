import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.persistence import (
    PersistenceError,
    SQLITE_SCHEMA_VERSION,
    SQLiteTranscriptCurrentSelectionRepository,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle

V9_TABLES = {"transcript_current_selections"}

_ADDITION_BLOCKS = (
    (2, sqlite_lifecycle._V2_ADDITION_STATEMENTS),
    (3, sqlite_lifecycle._V3_ADDITION_STATEMENTS),
    (4, sqlite_lifecycle._V4_ADDITION_STATEMENTS),
    (5, sqlite_lifecycle._V5_ADDITION_STATEMENTS),
    (6, sqlite_lifecycle._V6_ADDITION_STATEMENTS),
    (7, sqlite_lifecycle._V7_ADDITION_STATEMENTS),
    (8, sqlite_lifecycle._V8_ADDITION_STATEMENTS),
    (9, sqlite_lifecycle._V9_ADDITION_STATEMENTS),
    (10, sqlite_lifecycle._V10_ADDITION_STATEMENTS),
    (11, sqlite_lifecycle._V11_ADDITION_STATEMENTS),
    (12, sqlite_lifecycle._V12_ADDITION_STATEMENTS),
    (13, sqlite_lifecycle._V13_ADDITION_STATEMENTS),
    (14, sqlite_lifecycle._V14_ADDITION_STATEMENTS),
    (15, sqlite_lifecycle._V15_ADDITION_STATEMENTS),
    (16, sqlite_lifecycle._V16_ADDITION_STATEMENTS),
    (17, sqlite_lifecycle._V17_ADDITION_STATEMENTS),
    (18, sqlite_lifecycle._V18_ADDITION_STATEMENTS),
    (19, sqlite_lifecycle._V19_ADDITION_STATEMENTS),
    (20, sqlite_lifecycle._V20_ADDITION_STATEMENTS),
    (21, sqlite_lifecycle._V21_ADDITION_STATEMENTS),
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


class SQLiteSchemaVersionNineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_fresh_database_initializes_with_v9_tables(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V9_TABLES.issubset(table_names(connection)))
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
        finally:
            connection.close()

    def test_migrates_v8_to_v9_preserving_existing_rows(self) -> None:
        create_legacy_database(self.database_path, 8)
        migrate_sqlite_database(self.database_path, 9)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertTrue(V9_TABLES.issubset(table_names(connection)))
            preserved = connection.execute(
                "SELECT purpose FROM processing_units WHERE identity = 'unit'"
            ).fetchone()
            self.assertEqual(preserved[0], "preserved")
        finally:
            connection.close()

    def test_v9_no_op_migration_is_allowed(self) -> None:
        create_legacy_database(self.database_path, 8)
        migrate_sqlite_database(self.database_path, 9)
        migrate_sqlite_database(self.database_path, 9)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                9,
            )
        finally:
            connection.close()

    def test_direct_v7_to_v9_is_rejected(self) -> None:
        create_legacy_database(self.database_path, 7)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 9)

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 23)

    def test_repository_rejects_pre_v9_schema(self) -> None:
        create_legacy_database(self.database_path, 8)
        connection = open_sqlite_database(self.database_path)
        try:
            with self.assertRaises(Exception):
                SQLiteTranscriptCurrentSelectionRepository(connection)
        finally:
            connection.close()

    def test_every_released_version_chains_to_v9_preserving_data(self) -> None:
        # Migration compatibility: each released schema version reaches v9 through the
        # supported single-step chain, preserving existing rows.
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
                    self.assertTrue(V9_TABLES.issubset(table_names(connection)))
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
