import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lectureos.persistence import (
    PersistenceError,
    SQLITE_SCHEMA_VERSION,
    UnsupportedSchemaVersionError,
    initialize_sqlite_database,
    migrate_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle


V5_TABLES = {
    "provider_transcript_results",
    "provider_transcript_result_diagnostics",
    "transcript_segments",
    "raw_transcripts",
    "raw_transcript_segments",
    "correction_candidates",
    "correction_candidate_evidence",
    "corrected_transcript_revisions",
    "corrected_transcript_revision_segments",
    "corrected_transcript_revision_candidates",
}


def create_legacy_database(path: Path, version: int) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    statements = list(sqlite_lifecycle._V1_TABLE_STATEMENTS)
    if version >= 2:
        statements.extend(sqlite_lifecycle._V2_ADDITION_STATEMENTS)
    if version >= 3:
        statements.extend(sqlite_lifecycle._V3_ADDITION_STATEMENTS)
    if version >= 4:
        statements.extend(sqlite_lifecycle._V4_ADDITION_STATEMENTS)
    connection.execute("BEGIN")
    for statement in statements:
        connection.execute(statement)
    connection.execute("INSERT INTO schema_metadata VALUES (1, ?)", (version,))
    connection.execute("COMMIT")
    return connection


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


class SQLiteSchemaVersionFiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _v4_with_data(self, path: Path | None = None) -> None:
        connection = create_legacy_database(path or self.database_path, 4)
        connection.execute(
            "INSERT INTO processing_units VALUES ('unit', 'preserved', 1)"
        )
        connection.execute(
            "INSERT INTO domain_result_references(identity, kind) VALUES ('result', 'raw_transcript')"
        )
        connection.execute(
            "INSERT INTO domain_result_upstream_results VALUES ('result', 0, 'upstream')"
        )
        connection.execute(
            "INSERT INTO failures VALUES ('failure', 'processing', 'run', NULL, 1, 0, 0)"
        )
        connection.execute(
            "INSERT INTO failure_diagnostics VALUES ('failure', 0, 'diagnostic')"
        )
        connection.close()

    def _assert_v4_data(self, connection: sqlite3.Connection) -> None:
        self.assertEqual(
            connection.execute("SELECT * FROM processing_units").fetchall(),
            [("unit", "preserved", 1)],
        )
        self.assertEqual(
            connection.execute(
                "SELECT identity, kind FROM domain_result_references"
            ).fetchall(),
            [("result", "raw_transcript")],
        )
        self.assertEqual(
            connection.execute(
                "SELECT * FROM domain_result_upstream_results"
            ).fetchall(),
            [("result", 0, "upstream")],
        )
        self.assertEqual(
            connection.execute("SELECT identity FROM failures").fetchall(),
            [("failure",)],
        )
        self.assertEqual(
            connection.execute("SELECT * FROM failure_diagnostics").fetchall(),
            [("failure", 0, "diagnostic")],
        )

    def test_new_database_initializes_directly_as_complete_v5(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertEqual(SQLITE_SCHEMA_VERSION, 22)
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone(),
                (22,),
            )
            self.assertTrue(V5_TABLES.issubset(table_names(connection)))
            self.assertEqual(sqlite_lifecycle.validate_sqlite_connection(connection), 22)
        finally:
            connection.close()
        open_sqlite_database(self.database_path).close()

    def test_frozen_v1_through_v4_open_without_v5_or_mutation(self) -> None:
        for version in (1, 2, 3, 4):
            with self.subTest(version=version):
                path = Path(self.temporary_directory.name) / f"v{version}.sqlite3"
                connection = create_legacy_database(path, version)
                before = table_names(connection)
                connection.close()
                reopened = open_sqlite_database(path)
                self.assertEqual(table_names(reopened), before)
                self.assertTrue(V5_TABLES.isdisjoint(before))
                self.assertEqual(
                    reopened.execute("SELECT version FROM schema_metadata").fetchone(),
                    (version,),
                )
                reopened.close()

    def test_v4_migrates_to_v5_preserving_data_without_backfill(self) -> None:
        self._v4_with_data()
        migrate_sqlite_database(self.database_path, target_version=5)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone(),
                (5,),
            )
            self.assertTrue(V5_TABLES.issubset(table_names(connection)))
            self._assert_v4_data(connection)
            for table in (
                "provider_transcript_results",
                "transcript_segments",
                "raw_transcripts",
                "correction_candidates",
                "corrected_transcript_revisions",
            ):
                self.assertEqual(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone(),
                    (0,),
                )
        finally:
            connection.close()

    def test_latest_to_latest_is_validated_no_op(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        connection.execute(
            """INSERT INTO provider_transcript_results VALUES (
            'provider', 'media', 'timeline', 'run', 'execution', 'speech',
            'provider-ref', 'content', NULL, NULL, 0
            )"""
        )
        before = table_names(connection)
        connection.close()
        migrate_sqlite_database(self.database_path, target_version=SQLITE_SCHEMA_VERSION)
        reopened = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(table_names(reopened), before)
            self.assertEqual(
                reopened.execute(
                    "SELECT identity FROM provider_transcript_results"
                ).fetchall(),
                [("provider",)],
            )
        finally:
            reopened.close()

    def test_direct_lower_paths_downgrade_and_unknown_marker_are_rejected(self) -> None:
        for version in (1, 2, 3):
            path = Path(self.temporary_directory.name) / f"reject-v{version}.sqlite3"
            connection = create_legacy_database(path, version)
            before = table_names(connection)
            connection.close()
            with self.assertRaises(PersistenceError):
                migrate_sqlite_database(path, target_version=5)
            reopened = open_sqlite_database(path)
            self.assertEqual(table_names(reopened), before)
            self.assertEqual(
                reopened.execute("SELECT version FROM schema_metadata").fetchone(),
                (version,),
            )
            reopened.close()

        connection = initialize_sqlite_database(self.database_path)
        connection.close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, target_version=4)
        connection = open_sqlite_database(self.database_path)
        connection.execute("UPDATE schema_metadata SET version = 99")
        connection.close()
        with self.assertRaises(UnsupportedSchemaVersionError):
            migrate_sqlite_database(self.database_path, target_version=5)

    def test_v5_ddl_conflicts_roll_back_to_v4(self) -> None:
        for conflict in ("provider_transcript_results", "correction_candidates"):
            with self.subTest(conflict=conflict):
                path = Path(self.temporary_directory.name) / f"conflict-{conflict}.sqlite3"
                self._v4_with_data(path)
                connection = open_sqlite_database(path)
                connection.execute(f"CREATE TABLE {conflict}(wrong TEXT)")
                connection.close()
                with self.assertRaises(PersistenceError):
                    migrate_sqlite_database(path, target_version=5)
                reopened = open_sqlite_database(path)
                try:
                    self.assertEqual(
                        reopened.execute("SELECT version FROM schema_metadata").fetchone(),
                        (4,),
                    )
                    self.assertTrue(
                        (V5_TABLES - {conflict}).isdisjoint(table_names(reopened))
                    )
                    self._assert_v4_data(reopened)
                finally:
                    reopened.close()

    def test_marker_validation_and_commit_failures_roll_back_to_v4(self) -> None:
        for scenario in ("marker", "validation", "commit"):
            with self.subTest(scenario=scenario):
                path = Path(self.temporary_directory.name) / f"{scenario}.sqlite3"
                self._v4_with_data(path)
                if scenario == "marker":
                    connection = open_sqlite_database(path)
                    connection.execute(
                        """CREATE TRIGGER reject_v5_marker BEFORE UPDATE ON schema_metadata
                        BEGIN SELECT RAISE(ABORT, 'injected marker failure'); END"""
                    )
                    connection.close()
                    context = patch.object(
                        sqlite_lifecycle, "_commit", wraps=sqlite_lifecycle._commit
                    )
                elif scenario == "validation":
                    original = sqlite_lifecycle._validate_schema_shape

                    def validate(connection, version):
                        if version == 5:
                            raise PersistenceError("injected v5 validation failure")
                        return original(connection, version)

                    context = patch.object(
                        sqlite_lifecycle,
                        "_validate_schema_shape",
                        side_effect=validate,
                    )
                else:
                    context = patch.object(
                        sqlite_lifecycle,
                        "_commit",
                        side_effect=sqlite3.OperationalError(
                            "injected commit failure"
                        ),
                    )
                with context:
                    with self.assertRaises(PersistenceError):
                        migrate_sqlite_database(path, target_version=5)
                reopened = open_sqlite_database(path)
                try:
                    self.assertEqual(
                        reopened.execute("SELECT version FROM schema_metadata").fetchone(),
                        (4,),
                    )
                    self.assertTrue(V5_TABLES.isdisjoint(table_names(reopened)))
                    self._assert_v4_data(reopened)
                finally:
                    reopened.close()

    def test_v5_required_tables_columns_and_foreign_keys_are_validated(self) -> None:
        for table in V5_TABLES:
            with self.subTest(table=table):
                path = Path(self.temporary_directory.name) / f"missing-{table}.sqlite3"
                connection = initialize_sqlite_database(path)
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute(f"DROP TABLE {table}")
                connection.close()
                with self.assertRaises(PersistenceError):
                    open_sqlite_database(path)

        connection = initialize_sqlite_database(self.database_path)
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DROP TABLE raw_transcript_segments")
        connection.execute(
            """CREATE TABLE raw_transcript_segments (
            raw_transcript_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
            transcript_segment_id TEXT NOT NULL,
            PRIMARY KEY (raw_transcript_id, ordinal)
            )"""
        )
        connection.close()
        with self.assertRaises(PersistenceError):
            open_sqlite_database(self.database_path)

    def test_v5_constraints_order_cascade_and_external_reference_policy(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            provider_insert = "INSERT INTO provider_transcript_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    provider_insert,
                    ("blank", "media", "timeline", "run", "execution", "cap", "  ", "", None, None, 0),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    provider_insert,
                    ("normalized", "media", "timeline", "run", "execution", "cap", "provider", "", None, None, 1),
                )
            connection.execute(
                provider_insert,
                ("provider", "missing-media", "missing-timeline", "missing-run", "missing-execution", "cap", "provider", "", "missing-plugin", None, 0),
            )
            connection.execute(
                "INSERT INTO provider_transcript_result_diagnostics VALUES ('provider', 0, 'same')"
            )
            connection.execute(
                "INSERT INTO provider_transcript_result_diagnostics VALUES ('provider', 1, 'same')"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO provider_transcript_result_diagnostics VALUES ('provider', -1, 'bad')"
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO provider_transcript_result_diagnostics VALUES ('provider', 1, 'duplicate')"
                )

            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO transcript_segments(identity, transcript_id, source_order, start, end) VALUES ('bad', 'raw', 0, 1, 2)"
                )
            connection.execute(
                "INSERT INTO transcript_segments(identity, transcript_id, text, source_order) VALUES ('segment', 'missing-transcript', '', 0)"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO corrected_transcript_revisions(identity, transcript_id, domain_result_id, processing_run_id, unit_execution_id, applicability) VALUES ('revision', 'raw', 'result', 'run', 'execution', 'undetermined')"
                )
            self.assertEqual(
                connection.execute(
                    "PRAGMA foreign_key_list(provider_transcript_results)"
                ).fetchall(),
                [],
            )
            self.assertEqual(
                connection.execute("PRAGMA foreign_key_list(transcript_segments)").fetchall(),
                [],
            )
            connection.execute(
                "DELETE FROM provider_transcript_results WHERE identity = 'provider'"
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM provider_transcript_result_diagnostics"
                ).fetchone(),
                (0,),
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
