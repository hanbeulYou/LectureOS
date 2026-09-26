"""v54 → v55 migration for the multi-candidate timing generation relations (040 §19, PATCH-0049).

Strictly additive: two new relations, every released row preserved, and no released relation altered
in any way. The decisive property MG-21 requires is that a released **single-candidate** timing
generation is left exactly where it is — `timing_correction_revision_generations` keeps its columns
and its rows, and no member row is back-filled for it. A legacy singleton is *derived* as a
one-member generation at read time instead.
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
from lectureos.application.timing_correction_candidate_admission import (
    build_timing_correction_candidate_input,
)
from lectureos.composition import (
    compose_sqlite_timing_correction_candidate_admission_service,
    compose_sqlite_timing_correction_decision_service,
    compose_sqlite_timing_correction_revision_generation_service,
)
from lectureos.persistence.timing_correction_revision_generation import (
    SQLiteTimingCorrectionGenerationCommandPersistence,
)

# `tests/` is not a package, so a single-module invocation does not put it on sys.path the way
# discovery does; this keeps both `unittest discover` and `unittest tests.<module>` working.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import temporary_fixture  # noqa: E402

V55_TABLES = {
    "timing_correction_revision_aggregate_generations",
    "timing_correction_revision_generation_members",
}

# The released families this migration must leave untouched — including the v54 timing family whose
# singleton relation MG-21 keeps as the canonical representation of a one-member generation.
_UNTOUCHED = (
    "timing_correction_candidates",
    "timing_correction_candidate_decisions",
    "timing_correction_revision_generations",
    "correction_candidates",
    "correction_candidate_admissions",
    "correction_candidate_decisions",
    "corrected_revision_generations",
    "corrected_revision_selections",
    "corrected_transcript_revisions",
    "corrected_transcript_revision_segments",
    "corrected_transcript_revision_candidates",
    "transcript_segments",
    "raw_transcripts",
)

_ADDITION_BLOCKS = tuple(
    (level, getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS"))
    for level in range(2, SQLITE_SCHEMA_VERSION + 1)
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


def table_sql(connection: sqlite3.Connection, table: str) -> str:
    return connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()[0]


class SQLiteSchemaVersionFiftyFiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_schema_version_is_fifty_five(self) -> None:
        self.assertEqual(SQLITE_SCHEMA_VERSION, 55)
        self.assertIn(55, sqlite_lifecycle._SUPPORTED_SCHEMA_VERSIONS)

    def test_fresh_database_initializes_with_v55_tables(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V55_TABLES.issubset(table_names(connection)))
        finally:
            connection.close()

    def test_migrates_v54_to_v55_preserving_existing_rows(self) -> None:
        create_legacy_database(self.database_path, 54)
        migrate_sqlite_database(self.database_path, 55)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                55,
            )
            self.assertEqual(
                connection.execute("SELECT * FROM processing_units").fetchall(),
                [("unit", "preserved", 1)],
            )
            self.assertTrue(V55_TABLES.issubset(table_names(connection)))
        finally:
            connection.close()

    def test_released_relations_keep_their_exact_definition(self) -> None:
        create_legacy_database(self.database_path, 54)
        before = {}
        connection = open_sqlite_database(self.database_path)
        try:
            for table in _UNTOUCHED:
                before[table] = table_sql(connection, table)
        finally:
            connection.close()
        migrate_sqlite_database(self.database_path, 55)
        connection = open_sqlite_database(self.database_path)
        try:
            for table in _UNTOUCHED:
                self.assertEqual(before[table], table_sql(connection, table), table)
        finally:
            connection.close()

    def test_a_released_singleton_generation_survives_without_member_backfill(self) -> None:
        # The decisive legacy-compatibility property: a v54 single-candidate generation keeps its
        # identity and its row, and the migration writes no member row for it (MG-21).
        directory, fixture = temporary_fixture()
        self.addCleanup(directory.cleanup)
        candidate = compose_sqlite_timing_correction_candidate_admission_service(
            fixture.connection
        ).admit(
            intake_id=fixture.intake_id,
            candidate=build_timing_correction_candidate_input(fixture.proposal()),
        ).candidate
        compose_sqlite_timing_correction_decision_service(fixture.connection).decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        generated = compose_sqlite_timing_correction_revision_generation_service(
            fixture.connection
        ).generate(candidate_id=candidate.identity.value)

        def snapshot(connection):
            return {
                table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
                for table in (
                    "timing_correction_candidates",
                    "timing_correction_candidate_decisions",
                    "timing_correction_revision_generations",
                    "corrected_transcript_revisions",
                    "corrected_transcript_revision_segments",
                    "transcript_segments",
                )
            }

        before = snapshot(fixture.connection)
        fixture.connection.close()
        migrate_sqlite_database(fixture.database_path, SQLITE_SCHEMA_VERSION)  # no-op
        connection = open_sqlite_database(fixture.database_path)
        try:
            self.assertEqual(before, snapshot(connection))
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM timing_correction_revision_generation_members"
                ).fetchone()[0],
                0,
                "a legacy singleton is derived as a one-member generation, never back-filled",
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM timing_correction_revision_aggregate_generations"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT identity FROM timing_correction_revision_generations"
                ).fetchone()[0],
                generated.generation.identity.value,
            )
        finally:
            connection.close()

    def test_aggregate_persistence_is_unavailable_below_v55(self) -> None:
        create_legacy_database(self.database_path, 54)
        connection = open_sqlite_database(self.database_path)
        try:
            persistence = SQLiteTimingCorrectionGenerationCommandPersistence(connection)
            with self.assertRaises(SchemaFeatureUnavailableError):
                persistence.persist_timing_correction_aggregate_generation(
                    generation=None, revision=None, replacement_segments=(), result=None
                )
        finally:
            connection.close()

    def test_downgrade_and_direct_skip_are_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 54)
        create_legacy_database(
            Path(self.temporary_directory.name) / "skip.sqlite3", 53
        )
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(
                Path(self.temporary_directory.name) / "skip.sqlite3", 55
            )

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, SQLITE_SCHEMA_VERSION + 1)

    def test_every_released_version_chains_to_v55_preserving_data(self) -> None:
        # Migration compatibility: every released schema version reaches v55 through the supported
        # single-step chain, with no row rewritten and no meaning mutated.
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
                        55,
                    )
                    self.assertTrue(V55_TABLES.issubset(table_names(connection)))
                    self.assertEqual(
                        connection.execute("SELECT * FROM processing_units").fetchall(),
                        [("unit", "preserved", 1)],
                    )
                finally:
                    connection.close()

    def test_migration_failure_rolls_back_to_the_previous_version(self) -> None:
        create_legacy_database(self.database_path, 54)
        connection = sqlite3.connect(self.database_path, isolation_level=None)
        connection.execute(
            "CREATE TABLE timing_correction_revision_generation_members (blocked INTEGER)"
        )
        connection.close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 55)
        connection = sqlite3.connect(self.database_path, isolation_level=None)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                54,
                "a failed migration leaves the released version untouched",
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' "
                    "AND name = 'timing_correction_revision_aggregate_generations'"
                ).fetchone()[0],
                0,
                "no partial addition survives a failed migration",
            )
        finally:
            connection.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
