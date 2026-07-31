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

V52_TABLES = {"lecture_review_authority_positions"}

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


class SQLiteSchemaVersionFiftyTwoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_schema_version_is_fifty_two(self) -> None:
        self.assertEqual(SQLITE_SCHEMA_VERSION, 52)

    def test_fresh_database_initializes_with_v52_tables(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V52_TABLES.issubset(table_names(connection)))
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
        finally:
            connection.close()

    def test_migrates_v51_to_v52_preserving_existing_rows(self) -> None:
        create_legacy_database(self.database_path, 51)
        migrate_sqlite_database(self.database_path, 52)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertTrue(V52_TABLES.issubset(table_names(connection)))
            preserved = connection.execute(
                "SELECT purpose FROM processing_units WHERE identity = 'unit'"
            ).fetchone()
            self.assertEqual(preserved[0], "preserved")
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM lecture_review_decisions"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_the_released_review_relations_are_untouched_by_the_migration(self) -> None:
        """AH-12: released rows keep their identities and columns; nothing is backfilled."""

        create_legacy_database(self.database_path, 51)
        before = {}
        connection = open_sqlite_database(self.database_path)
        try:
            for table in ("lecture_review_decisions", "lecture_approved_edit_decisions",
                          "edit_review_decisions", "approved_edit_decisions"):
                before[table] = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                    (table,),
                ).fetchone()[0]
        finally:
            connection.close()
        migrate_sqlite_database(self.database_path, 52)
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
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM lecture_review_authority_positions"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_the_history_relation_has_no_per_decision_uniqueness(self) -> None:
        """AH-6 prohibits it: several positions must be able to reference one decision."""

        connection = initialize_sqlite_database(self.database_path)
        try:
            definition = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' "
                "AND name = 'lecture_review_authority_positions'"
            ).fetchone()[0]
            self.assertIn("UNIQUE (candidate_id, actor, sequence)", definition)
            self.assertNotIn("review_decision_id TEXT NOT NULL UNIQUE", definition)
            indexes = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'index' "
                "AND tbl_name = 'lecture_review_authority_positions' AND sql IS NOT NULL"
            ).fetchall()
            for (sql,) in indexes:
                self.assertNotIn("review_decision_id", sql or "")
        finally:
            connection.close()

    def test_v52_no_op_migration_is_allowed(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        migrate_sqlite_database(self.database_path, 52)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                52,
            )
        finally:
            connection.close()

    def test_direct_v50_to_v52_is_rejected(self) -> None:
        create_legacy_database(self.database_path, 50)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 52)

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 53)

    def test_downgrade_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 51)

    def test_repository_rejects_pre_v52_schema(self) -> None:
        create_legacy_database(self.database_path, 51)
        connection = open_sqlite_database(self.database_path)
        try:
            with self.assertRaises(Exception):
                SQLiteLectureReviewRepository(connection)
        finally:
            connection.close()

    def test_every_released_version_chains_to_v52_preserving_data(self) -> None:
        for start in range(1, 52):
            with self.subTest(start=start):
                path = Path(self.temporary_directory.name) / f"chain-v{start}.sqlite3"
                create_legacy_database(path, start)
                for target in range(start + 1, 53):
                    migrate_sqlite_database(path, target)
                connection = open_sqlite_database(path)
                try:
                    self.assertEqual(
                        connection.execute(
                            "SELECT version FROM schema_metadata"
                        ).fetchone()[0],
                        52,
                    )
                    self.assertTrue(V52_TABLES.issubset(table_names(connection)))
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
