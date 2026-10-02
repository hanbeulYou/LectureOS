"""v55 → v56 migration for the same-source composition relation (040 §19, PATCH-0050).

Strictly additive: one new relation, every released row preserved, and no released relation altered
in any way. The decisive property TX-21/TX-22 and Canonical Invariant 16 require is that existing
text-only and timing-only sibling revisions are left exactly where they are — no composition row is
ever back-filled for them, and the released singleton and aggregate relations keep their columns and
rows. A composition exists only when a person explicitly requests one.
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
from lectureos.persistence.same_source_composition_generation import (
    SQLiteSameSourceCompositionCommandPersistence,
    SQLiteSameSourceCompositionRepository,
)
from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.timing_correction_candidate_admission import (
    build_timing_correction_candidate_input,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_timing_correction_candidate_admission_service,
    compose_sqlite_timing_correction_decision_service,
    compose_sqlite_timing_correction_revision_generation_service,
)

# `tests/` is not a package, so a single-module invocation does not put it on sys.path the way
# discovery does; this keeps both `unittest discover` and `unittest tests.<module>` working.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import temporary_fixture  # noqa: E402
from test_sqlite_schema_v55_migration import (  # noqa: E402
    create_legacy_database,
    schema_differences,
    snapshot_at,
    table_names,
    table_sql,
)

V56_TABLES = {"same_source_composition_generations"}

# The released families this migration must leave untouched — including the v54/v55 timing family,
# whose singleton and aggregate relations stay the canonical representation of their generations.
_UNTOUCHED = (
    "timing_correction_revision_aggregate_generations",
    "timing_correction_revision_generation_members",
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

_EQUIVALENCE_START_VERSIONS = (1, 37, 54, 55)


class SQLiteSchemaVersionFiftySixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_schema_version_is_fifty_six(self) -> None:
        self.assertEqual(SQLITE_SCHEMA_VERSION, 56)
        self.assertIn(56, sqlite_lifecycle._SUPPORTED_SCHEMA_VERSIONS)
        self.assertIn(55, sqlite_lifecycle._SUPPORTED_SCHEMA_VERSIONS)

    def test_fresh_database_initializes_with_v56_table(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V56_TABLES.issubset(table_names(connection)))
        finally:
            connection.close()

    def test_migrates_v55_to_v56_preserving_existing_rows(self) -> None:
        create_legacy_database(self.database_path, 55)
        migrate_sqlite_database(self.database_path, 56)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0], 56
            )
            self.assertEqual(
                connection.execute("SELECT * FROM processing_units").fetchall(),
                [("unit", "preserved", 1)],
            )
            self.assertTrue(V56_TABLES.issubset(table_names(connection)))
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM same_source_composition_generations"
                ).fetchone()[0],
                0,
                "the migration never back-fills a composition",
            )
        finally:
            connection.close()

    def test_released_relations_keep_their_exact_definition(self) -> None:
        create_legacy_database(self.database_path, 55)
        before = {}
        connection = open_sqlite_database(self.database_path)
        try:
            for table in _UNTOUCHED:
                before[table] = table_sql(connection, table)
        finally:
            connection.close()
        migrate_sqlite_database(self.database_path, 56)
        connection = open_sqlite_database(self.database_path)
        try:
            for table in _UNTOUCHED:
                self.assertEqual(before[table], table_sql(connection, table), table)
        finally:
            connection.close()

    def test_existing_sibling_revisions_survive_without_composition_backfill(self) -> None:
        # The decisive compatibility property: a text-only and a timing-only sibling revision on
        # one segment keep their identities and rows, and no composition is derived or written for
        # them (Canonical Invariant 16).
        directory, fixture = temporary_fixture()
        self.addCleanup(directory.cleanup)
        connection = fixture.connection
        text = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=fixture.intake_id,
            candidate=build_correction_candidate_input(
                {
                    "raw_transcript_id": fixture.raw_transcript_id,
                    "segment_id": fixture.target.identity.value,
                    "candidate_ref": "c1",
                    "source_type": "manual",
                    "source_reference": "human:editor-1",
                    "proposed_text": "둘째 문장입니다",
                    "source_text_snapshot": fixture.target.text,
                    "rationale": "표현 교정",
                }
            ),
        ).candidate
        compose_sqlite_correction_candidate_decision_service(connection).decide(
            candidate_id=text.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        timing = compose_sqlite_timing_correction_candidate_admission_service(connection).admit(
            intake_id=fixture.intake_id,
            candidate=build_timing_correction_candidate_input(fixture.proposal()),
        ).candidate
        compose_sqlite_timing_correction_decision_service(connection).decide(
            candidate_id=timing.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        text_revision = compose_sqlite_corrected_revision_generation_service(connection).generate(
            candidate_id=text.identity.value
        ).revision
        timing_revision = compose_sqlite_timing_correction_revision_generation_service(
            connection
        ).generate(candidate_id=timing.identity.value).revision

        def snapshot(conn):
            return {
                table: conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
                for table in (
                    "correction_candidates",
                    "correction_candidate_decisions",
                    "corrected_revision_generations",
                    "timing_correction_candidates",
                    "timing_correction_candidate_decisions",
                    "timing_correction_revision_generations",
                    "corrected_transcript_revisions",
                    "corrected_transcript_revision_segments",
                    "transcript_segments",
                )
            }

        before = snapshot(connection)
        connection.close()
        migrate_sqlite_database(fixture.database_path, SQLITE_SCHEMA_VERSION)  # no-op
        reopened = open_sqlite_database(fixture.database_path)
        try:
            self.assertEqual(before, snapshot(reopened))
            self.assertEqual(
                reopened.execute(
                    "SELECT COUNT(*) FROM same_source_composition_generations"
                ).fetchone()[0],
                0,
                "sibling revisions are correct history, never auto-composed",
            )
            self.assertIsNotNone(
                reopened.execute(
                    "SELECT 1 FROM corrected_transcript_revisions WHERE identity = ?",
                    (text_revision.identity.value,),
                ).fetchone()
            )
            self.assertIsNotNone(
                reopened.execute(
                    "SELECT 1 FROM corrected_transcript_revisions WHERE identity = ?",
                    (timing_revision.identity.value,),
                ).fetchone()
            )
        finally:
            reopened.close()

    def test_composition_persistence_is_unavailable_below_v56(self) -> None:
        create_legacy_database(self.database_path, 55)
        connection = open_sqlite_database(self.database_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteSameSourceCompositionCommandPersistence(
                    connection
                ).persist_same_source_composition(
                    generation=None, revision=None, replacement_segment=None, result=None
                )
            # The reader degrades to "no composition" rather than failing on an older schema.
            self.assertEqual(
                SQLiteSameSourceCompositionRepository(connection).generations_for_text_candidate(
                    type("Id", (), {"value": "correction-candidate:" + "0" * 64})()
                ),
                (),
            )
        finally:
            connection.close()

    def test_downgrade_and_direct_skip_are_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 55)
        create_legacy_database(Path(self.temporary_directory.name) / "skip.sqlite3", 54)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(Path(self.temporary_directory.name) / "skip.sqlite3", 56)

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, SQLITE_SCHEMA_VERSION + 1)

    def test_every_released_version_chains_to_v56_preserving_data(self) -> None:
        for start in range(1, SQLITE_SCHEMA_VERSION):
            with self.subTest(start=start):
                path = Path(self.temporary_directory.name) / f"chain-v{start}.sqlite3"
                create_legacy_database(path, start)
                for target in range(start + 1, SQLITE_SCHEMA_VERSION + 1):
                    migrate_sqlite_database(path, target)
                connection = open_sqlite_database(path)
                try:
                    self.assertEqual(
                        connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    self.assertTrue(V56_TABLES.issubset(table_names(connection)))
                    self.assertEqual(
                        connection.execute("SELECT * FROM processing_units").fetchall(),
                        [("unit", "preserved", 1)],
                    )
                finally:
                    connection.close()

    def test_migrated_schema_is_equivalent_to_fresh_initialization(self) -> None:
        # Two independently built databases: one migrated through the chain, one fresh at v56.
        fresh_path = Path(self.temporary_directory.name) / "fresh.sqlite3"
        initialize_sqlite_database(fresh_path).close()
        fresh = snapshot_at(fresh_path)
        self.assertEqual(fresh["version"], 56)
        self.assertTrue(V56_TABLES.issubset(fresh["tables"]))
        for start in _EQUIVALENCE_START_VERSIONS:
            with self.subTest(start=start):
                migrated_path = Path(self.temporary_directory.name) / f"migrated-v{start}.sqlite3"
                create_legacy_database(migrated_path, start)
                for target in range(start + 1, SQLITE_SCHEMA_VERSION + 1):
                    migrate_sqlite_database(migrated_path, target)
                migrated = snapshot_at(migrated_path)
                self.assertEqual(migrated["version"], 56)
                self.assertEqual(schema_differences(migrated, fresh), [])
                self.assertEqual(migrated, fresh)

    def test_schema_equivalence_detects_a_composition_index_on_one_side_only(self) -> None:
        # Negative control on the new relation: the comparison must fail on a real mismatch.
        fresh_path = Path(self.temporary_directory.name) / "fresh.sqlite3"
        initialize_sqlite_database(fresh_path).close()
        migrated_path = Path(self.temporary_directory.name) / "migrated.sqlite3"
        create_legacy_database(migrated_path, 55)
        migrate_sqlite_database(migrated_path, 56)
        self.assertEqual(schema_differences(snapshot_at(migrated_path), snapshot_at(fresh_path)), [])
        probe = sqlite3.connect(migrated_path)
        probe.execute(
            "CREATE INDEX probe_only_in_migrated "
            "ON same_source_composition_generations(replaced_segment_id)"
        )
        probe.commit()
        probe.close()
        differences = schema_differences(snapshot_at(migrated_path), snapshot_at(fresh_path))
        self.assertTrue(
            any("probe_only_in_migrated" in line and "only in migrated" in line for line in differences),
            differences,
        )

    def test_migration_failure_rolls_back_to_the_previous_version(self) -> None:
        create_legacy_database(self.database_path, 55)
        connection = sqlite3.connect(self.database_path, isolation_level=None)
        connection.execute(
            "CREATE TABLE same_source_composition_generations (blocked INTEGER)"
        )
        connection.close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 56)
        connection = sqlite3.connect(self.database_path, isolation_level=None)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                55,
                "a failed migration leaves the released version untouched",
            )
        finally:
            connection.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
