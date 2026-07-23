import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.persistence import (
    PersistenceError,
    SQLITE_SCHEMA_VERSION,
    SQLiteTranscriptReviewDecisionRepository,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle

V7_TABLES = {"transcript_review_decisions"}


def create_legacy_database(path: Path, version: int) -> None:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
    if version >= 2:
        statements += sqlite_lifecycle._V2_ADDITION_STATEMENTS
    if version >= 3:
        statements += sqlite_lifecycle._V3_ADDITION_STATEMENTS
    if version >= 4:
        statements += sqlite_lifecycle._V4_ADDITION_STATEMENTS
    if version >= 5:
        statements += sqlite_lifecycle._V5_ADDITION_STATEMENTS
    if version >= 6:
        statements += sqlite_lifecycle._V6_ADDITION_STATEMENTS
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


class SQLiteSchemaVersionSevenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_fresh_database_initializes_with_v7_tables(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V7_TABLES.issubset(table_names(connection)))
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
        finally:
            connection.close()

    def test_migrates_v6_to_v7_preserving_existing_rows(self) -> None:
        create_legacy_database(self.database_path, 6)
        migrate_sqlite_database(self.database_path, 7)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertTrue(V7_TABLES.issubset(table_names(connection)))
            preserved = connection.execute(
                "SELECT purpose FROM processing_units WHERE identity = 'unit'"
            ).fetchone()
            self.assertEqual(preserved[0], "preserved")
        finally:
            connection.close()

    def test_v7_no_op_migration_is_allowed(self) -> None:
        create_legacy_database(self.database_path, 6)
        migrate_sqlite_database(self.database_path, 7)
        migrate_sqlite_database(self.database_path, 7)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                7,
            )
        finally:
            connection.close()

    def test_direct_v5_to_v7_is_rejected(self) -> None:
        create_legacy_database(self.database_path, 5)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 7)

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 26)

    def test_repository_rejects_pre_v7_schema(self) -> None:
        create_legacy_database(self.database_path, 6)
        connection = open_sqlite_database(self.database_path)
        try:
            with self.assertRaises(Exception):
                SQLiteTranscriptReviewDecisionRepository(connection)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
