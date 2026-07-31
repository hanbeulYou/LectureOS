import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.persistence import (
    PersistenceError,
    SQLITE_SCHEMA_VERSION,
    SQLiteLectureReviewRepository,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle

V51_TABLES = {"lecture_review_decisions", "lecture_approved_edit_decisions"}

_ADDITION_BLOCKS = tuple(
    (level, getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS"))
    for level in range(2, 53)
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


class SQLiteSchemaVersionFiftyOneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_v51_remains_a_supported_version(self) -> None:
        self.assertIn(51, sqlite_lifecycle._SUPPORTED_SCHEMA_VERSIONS)
        self.assertLessEqual(51, SQLITE_SCHEMA_VERSION)

    def test_fresh_database_initializes_with_v51_tables(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V51_TABLES.issubset(table_names(connection)))
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
        finally:
            connection.close()

    def test_migrates_v50_to_v51_preserving_existing_rows(self) -> None:
        create_legacy_database(self.database_path, 50)
        migrate_sqlite_database(self.database_path, 51)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertTrue(V51_TABLES.issubset(table_names(connection)))
            preserved = connection.execute(
                "SELECT purpose FROM processing_units WHERE identity = 'unit'"
            ).fetchone()
            self.assertEqual(preserved[0], "preserved")
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM lecture_analysis_edit_candidates"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_legacy_review_relations_are_untouched_by_the_migration(self) -> None:
        """R-12: the legacy generation's relations and rows are neither reused nor rewritten."""

        create_legacy_database(self.database_path, 50)
        before = {}
        connection = open_sqlite_database(self.database_path)
        try:
            for table in ("edit_review_decisions", "approved_edit_decisions"):
                before[table] = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                    (table,),
                ).fetchone()[0]
        finally:
            connection.close()
        migrate_sqlite_database(self.database_path, 51)
        connection = open_sqlite_database(self.database_path)
        try:
            for table, sql in before.items():
                self.assertEqual(
                    connection.execute(
                        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (table,),
                    ).fetchone()[0],
                    sql,
                )
        finally:
            connection.close()

    def test_v51_no_op_migration_is_allowed(self) -> None:
        create_legacy_database(self.database_path, 50)
        migrate_sqlite_database(self.database_path, 51)
        migrate_sqlite_database(self.database_path, 51)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                51,
            )
        finally:
            connection.close()

    def test_direct_v49_to_v51_is_rejected(self) -> None:
        create_legacy_database(self.database_path, 49)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 51)

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 54)

    def test_downgrade_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 50)

    def test_repository_rejects_pre_v51_schema(self) -> None:
        create_legacy_database(self.database_path, 50)
        connection = open_sqlite_database(self.database_path)
        try:
            with self.assertRaises(Exception):
                SQLiteLectureReviewRepository(connection)
        finally:
            connection.close()

    def test_every_released_version_chains_to_v51_preserving_data(self) -> None:
        for start in range(1, 51):
            with self.subTest(start=start):
                path = Path(self.temporary_directory.name) / f"chain-v{start}.sqlite3"
                create_legacy_database(path, start)
                for target in range(start + 1, 52):
                    migrate_sqlite_database(path, target)
                connection = open_sqlite_database(path)
                try:
                    self.assertEqual(
                        connection.execute(
                            "SELECT version FROM schema_metadata"
                        ).fetchone()[0],
                        51,
                    )
                    self.assertTrue(V51_TABLES.issubset(table_names(connection)))
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
