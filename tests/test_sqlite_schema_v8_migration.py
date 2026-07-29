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
    (22, sqlite_lifecycle._V22_ADDITION_STATEMENTS),
    (23, sqlite_lifecycle._V23_ADDITION_STATEMENTS),
    (24, sqlite_lifecycle._V24_ADDITION_STATEMENTS),
    (25, sqlite_lifecycle._V25_ADDITION_STATEMENTS),
    (26, sqlite_lifecycle._V26_ADDITION_STATEMENTS),
    (27, sqlite_lifecycle._V27_ADDITION_STATEMENTS),
    (28, sqlite_lifecycle._V28_ADDITION_STATEMENTS),
    (29, sqlite_lifecycle._V29_ADDITION_STATEMENTS),
    (30, sqlite_lifecycle._V30_ADDITION_STATEMENTS),
    (31, sqlite_lifecycle._V31_ADDITION_STATEMENTS),
    (32, sqlite_lifecycle._V32_ADDITION_STATEMENTS),
    (33, sqlite_lifecycle._V33_ADDITION_STATEMENTS),
    (34, sqlite_lifecycle._V34_ADDITION_STATEMENTS),
    (35, sqlite_lifecycle._V35_ADDITION_STATEMENTS),
    (36, sqlite_lifecycle._V36_ADDITION_STATEMENTS),
    (37, sqlite_lifecycle._V37_ADDITION_STATEMENTS),
    (38, sqlite_lifecycle._V38_ADDITION_STATEMENTS),
    (39, sqlite_lifecycle._V39_ADDITION_STATEMENTS),
    (40, sqlite_lifecycle._V40_ADDITION_STATEMENTS),
    (41, sqlite_lifecycle._V41_ADDITION_STATEMENTS),
    (42, sqlite_lifecycle._V42_ADDITION_STATEMENTS),
    (43, sqlite_lifecycle._V43_ADDITION_STATEMENTS),
    (44, sqlite_lifecycle._V44_ADDITION_STATEMENTS),
    (45, sqlite_lifecycle._V45_ADDITION_STATEMENTS),
    (46, sqlite_lifecycle._V46_ADDITION_STATEMENTS),
    (47, sqlite_lifecycle._V47_ADDITION_STATEMENTS),
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
            migrate_sqlite_database(self.database_path, 49)

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
