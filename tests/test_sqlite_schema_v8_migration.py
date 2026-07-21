import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.persistence import (
    PersistenceError,
    SQLITE_SCHEMA_VERSION,
    SQLiteTranscriptApplicabilityEvaluationRepository,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle

V8_TABLES = {"transcript_applicability_evaluations"}


def create_legacy_database(path: Path, version: int) -> None:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
    for level, block in (
        (2, sqlite_lifecycle._V2_ADDITION_STATEMENTS),
        (3, sqlite_lifecycle._V3_ADDITION_STATEMENTS),
        (4, sqlite_lifecycle._V4_ADDITION_STATEMENTS),
        (5, sqlite_lifecycle._V5_ADDITION_STATEMENTS),
        (6, sqlite_lifecycle._V6_ADDITION_STATEMENTS),
        (7, sqlite_lifecycle._V7_ADDITION_STATEMENTS),
    ):
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


class SQLiteSchemaVersionEightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_fresh_database_initializes_with_v8_tables(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V8_TABLES.issubset(table_names(connection)))
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
        finally:
            connection.close()

    def test_migrates_v7_to_v8_preserving_existing_rows(self) -> None:
        create_legacy_database(self.database_path, 7)
        migrate_sqlite_database(self.database_path, 8)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertTrue(V8_TABLES.issubset(table_names(connection)))
            preserved = connection.execute(
                "SELECT purpose FROM processing_units WHERE identity = 'unit'"
            ).fetchone()
            self.assertEqual(preserved[0], "preserved")
        finally:
            connection.close()

    def test_v8_no_op_migration_is_allowed(self) -> None:
        create_legacy_database(self.database_path, 7)
        migrate_sqlite_database(self.database_path, 8)
        migrate_sqlite_database(self.database_path, 8)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                8,
            )
        finally:
            connection.close()

    def test_direct_v6_to_v8_is_rejected(self) -> None:
        create_legacy_database(self.database_path, 6)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 8)

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 12)

    def test_repository_rejects_pre_v8_schema(self) -> None:
        create_legacy_database(self.database_path, 7)
        connection = open_sqlite_database(self.database_path)
        try:
            with self.assertRaises(Exception):
                SQLiteTranscriptApplicabilityEvaluationRepository(connection)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
