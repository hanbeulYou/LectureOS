"""v52 → v53 migration for the Edit Export Assembly (044 §23 EA-10, GOAL-030).

Strictly additive: two new relations, every released row preserved, and no released relation — this
generation's Review family or the legacy `edit_export_*` family — altered in any way.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.persistence import (
    PersistenceError,
    SQLITE_SCHEMA_VERSION,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle
from lectureos.persistence.errors import SchemaFeatureUnavailableError
from lectureos.persistence.lecture_edit_export_assembly import (
    SQLiteEditExportAssemblyRepository,
)

V53_TABLES = {
    "lecture_edit_export_assemblies",
    "lecture_edit_export_assembly_members",
}

# Relations this migration must leave byte-identical: this generation's released Review family and
# the legacy execution-coupled Export family, which EA-10 keeps out of reuse entirely.
_UNTOUCHED = (
    "lecture_review_decisions",
    "lecture_approved_edit_decisions",
    "lecture_review_authority_positions",
    "approved_edit_export_representations",
    "edit_export_assemblies",
    "edit_export_assembly_members",
)

_ADDITION_BLOCKS = tuple(
    (level, getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS"))
    for level in range(2, 54)
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
    connection.execute("INSERT INTO processing_units VALUES ('unit', 'preserved', 1)")
    connection.execute("COMMIT")
    connection.close()


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


class SQLiteSchemaVersionFiftyThreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_schema_version_is_fifty_three(self) -> None:
        self.assertEqual(SQLITE_SCHEMA_VERSION, 53)

    def test_fresh_database_initializes_with_v53_tables(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V53_TABLES.issubset(table_names(connection)))
        finally:
            connection.close()

    def test_migrates_v52_to_v53_preserving_existing_rows(self) -> None:
        create_legacy_database(self.database_path, 52)
        migrate_sqlite_database(self.database_path, 53)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertTrue(V53_TABLES.issubset(table_names(connection)))
            self.assertEqual(
                connection.execute(
                    "SELECT purpose FROM processing_units WHERE identity = 'unit'"
                ).fetchone()[0],
                "preserved",
            )
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                53,
            )
        finally:
            connection.close()

    def test_released_relations_are_byte_identical_across_the_step(self) -> None:
        """EA-10: no backfill, no dual-write, no reinterpretation of a released relation."""

        create_legacy_database(self.database_path, 52)
        before = {}
        connection = open_sqlite_database(self.database_path)
        try:
            for table in _UNTOUCHED:
                before[table] = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                    (table,),
                ).fetchone()[0]
        finally:
            connection.close()
        migrate_sqlite_database(self.database_path, 53)
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
            for table in V53_TABLES:
                self.assertEqual(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0
                )
        finally:
            connection.close()

    def test_the_assembly_relations_carry_no_execution_or_result_provenance(self) -> None:
        """EA-8: there is no Domain Result, run, execution, ordinal, or wall clock to store."""

        connection = initialize_sqlite_database(self.database_path)
        try:
            for table in V53_TABLES:
                columns = {
                    row[1]
                    for row in connection.execute(
                        f"PRAGMA table_info({table})"
                    ).fetchall()
                }
                for forbidden in (
                    "domain_result_id",
                    "processing_run_id",
                    "unit_execution_id",
                    "sequence",
                    "created_at",
                    "recorded_at",
                    "status",
                    "is_current",
                    "selected",
                ):
                    self.assertNotIn(forbidden, columns, f"{table}.{forbidden}")
        finally:
            connection.close()

    def test_membership_uniqueness_is_per_assembly(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            definition = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' "
                "AND name = 'lecture_edit_export_assembly_members'"
            ).fetchone()[0]
            self.assertIn("PRIMARY KEY (assembly_id, ordinal)", definition)
            self.assertIn(
                "UNIQUE (assembly_id, approved_edit_decision_id)", definition
            )
            # An approved edit may belong to several assemblies over time — membership is derived
            # and total, so a later assembly legitimately gathers it again.
            self.assertNotIn("approved_edit_decision_id TEXT NOT NULL UNIQUE", definition)
        finally:
            connection.close()

    def test_v53_no_op_migration_is_allowed(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        migrate_sqlite_database(self.database_path, 53)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                53,
            )
        finally:
            connection.close()

    def test_direct_v51_to_v53_is_rejected(self) -> None:
        create_legacy_database(self.database_path, 51)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 53)

    def test_downgrade_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 52)

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 54)

    def test_repository_rejects_pre_v53_schema(self) -> None:
        create_legacy_database(self.database_path, 52)
        connection = open_sqlite_database(self.database_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEditExportAssemblyRepository(connection)
        finally:
            connection.close()

    def test_every_released_version_chains_to_v53_preserving_data(self) -> None:
        for start in range(1, 53):
            with self.subTest(start=start):
                path = Path(self.temporary_directory.name) / f"chain-v{start}.sqlite3"
                create_legacy_database(path, start)
                for target in range(start + 1, 54):
                    migrate_sqlite_database(path, target)
                connection = open_sqlite_database(path)
                try:
                    self.assertEqual(
                        connection.execute(
                            "SELECT version FROM schema_metadata"
                        ).fetchone()[0],
                        53,
                    )
                    self.assertTrue(V53_TABLES.issubset(table_names(connection)))
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
