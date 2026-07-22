import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.persistence import (
    PersistenceError,
    SQLITE_SCHEMA_VERSION,
    SQLiteSubtitleApprovedDocumentRepository,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle

V20_TABLES = {
    "subtitle_approved_documents",
    "subtitle_approved_units",
    "subtitle_approved_unit_lines",
}

_ADDITION_BLOCKS = tuple(
    (level, getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS"))
    for level in range(2, 21)
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


class SQLiteSchemaVersionTwentyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_v20_remains_a_supported_version(self) -> None:
        self.assertIn(20, sqlite_lifecycle._SUPPORTED_SCHEMA_VERSIONS)
        self.assertLessEqual(20, SQLITE_SCHEMA_VERSION)

    def test_fresh_database_initializes_with_v20_tables(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V20_TABLES.issubset(table_names(connection)))
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
        finally:
            connection.close()

    def test_migrates_v19_to_v20_preserving_existing_rows(self) -> None:
        create_legacy_database(self.database_path, 19)
        migrate_sqlite_database(self.database_path, 20)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertTrue(V20_TABLES.issubset(table_names(connection)))
            preserved = connection.execute(
                "SELECT purpose FROM processing_units WHERE identity = 'unit'"
            ).fetchone()
            self.assertEqual(preserved[0], "preserved")
        finally:
            connection.close()

    def test_v20_no_op_migration_is_allowed(self) -> None:
        create_legacy_database(self.database_path, 19)
        migrate_sqlite_database(self.database_path, 20)
        migrate_sqlite_database(self.database_path, 20)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                20,
            )
        finally:
            connection.close()

    def test_direct_v18_to_v20_is_rejected(self) -> None:
        create_legacy_database(self.database_path, 18)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 20)

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 22)

    def test_repository_rejects_pre_v20_schema(self) -> None:
        create_legacy_database(self.database_path, 19)
        connection = open_sqlite_database(self.database_path)
        try:
            with self.assertRaises(Exception):
                SQLiteSubtitleApprovedDocumentRepository(connection)
        finally:
            connection.close()

    def test_every_released_version_chains_to_v20_preserving_data(self) -> None:
        # Migration compatibility: every released schema version reaches v20 through the
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
                    self.assertTrue(V20_TABLES.issubset(table_names(connection)))
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
