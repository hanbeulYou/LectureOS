import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.persistence import (
    PersistenceError,
    SQLITE_SCHEMA_VERSION,
    SQLiteReviewItemRepository,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle

V6_TABLES = {
    "review_candidate_references",
    "review_contexts",
    "review_context_domain_results",
    "review_context_evidence",
    "review_items",
    "transcript_review_preparations",
    "transcript_review_preparation_items",
    "transcript_review_preparation_candidates",
    "transcript_review_preparation_groups",
}


def create_v5_database(path: Path) -> None:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    statements = [
        *sqlite_lifecycle._V1_TABLE_STATEMENTS,
        *sqlite_lifecycle._V2_ADDITION_STATEMENTS,
        *sqlite_lifecycle._V3_ADDITION_STATEMENTS,
        *sqlite_lifecycle._V4_ADDITION_STATEMENTS,
        *sqlite_lifecycle._V5_ADDITION_STATEMENTS,
    ]
    connection.execute("BEGIN")
    for statement in statements:
        connection.execute(statement)
    connection.execute("INSERT INTO schema_metadata VALUES (1, 5)")
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


class SQLiteSchemaVersionSixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_fresh_database_initializes_with_v6_tables(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V6_TABLES.issubset(table_names(connection)))
            version = connection.execute(
                "SELECT version FROM schema_metadata"
            ).fetchone()[0]
            self.assertEqual(version, SQLITE_SCHEMA_VERSION)
        finally:
            connection.close()

    def test_migrates_v5_to_v6_preserving_existing_rows(self) -> None:
        create_v5_database(self.database_path)
        migrate_sqlite_database(self.database_path, 6)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertTrue(V6_TABLES.issubset(table_names(connection)))
            preserved = connection.execute(
                "SELECT purpose FROM processing_units WHERE identity = 'unit'"
            ).fetchone()
            self.assertEqual(preserved[0], "preserved")
        finally:
            connection.close()

    def test_v6_no_op_migration_is_allowed(self) -> None:
        create_v5_database(self.database_path)
        migrate_sqlite_database(self.database_path, 6)
        migrate_sqlite_database(self.database_path, 6)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                6,
            )
        finally:
            connection.close()

    def test_direct_v4_to_v6_is_rejected(self) -> None:
        connection = sqlite_lifecycle_create_v4(self.database_path)
        connection.close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 6)

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 11)

    def test_repository_rejects_pre_v6_schema(self) -> None:
        create_v5_database(self.database_path)
        connection = open_sqlite_database(self.database_path)
        try:
            with self.assertRaises(Exception):
                SQLiteReviewItemRepository(connection)
        finally:
            connection.close()


def sqlite_lifecycle_create_v4(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    statements = [
        *sqlite_lifecycle._V1_TABLE_STATEMENTS,
        *sqlite_lifecycle._V2_ADDITION_STATEMENTS,
        *sqlite_lifecycle._V3_ADDITION_STATEMENTS,
        *sqlite_lifecycle._V4_ADDITION_STATEMENTS,
    ]
    connection.execute("BEGIN")
    for statement in statements:
        connection.execute(statement)
    connection.execute("INSERT INTO schema_metadata VALUES (1, 4)")
    connection.execute("COMMIT")
    return connection


if __name__ == "__main__":
    unittest.main()
