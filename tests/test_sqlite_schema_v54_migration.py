"""v53 → v54 migration for the Human Timing Correction sibling relations (040 §17, PATCH-0047 TC-19/TC-20).

Strictly additive: three new relations, every released row preserved, and no released relation
altered in any way — in particular the released text-correction family, whose
`correction_candidates.proposed_text TEXT NOT NULL` and K-2 no-op rule are exactly why a sibling was
needed. Also asserts what TC-20 forbids: no backfill and no inference over legacy records.
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
from lectureos.persistence.timing_correction_candidate import (
    SQLiteTimingCorrectionCandidateRepository,
)
from lectureos.persistence.timing_correction_candidate_decision import (
    SQLiteTimingCorrectionDecisionRepository,
)
from lectureos.persistence.timing_correction_revision_generation import (
    SQLiteTimingCorrectionGenerationRepository,
)

# `tests/` is not a package, so a single-module invocation does not put it on sys.path the way
# discovery does; this keeps both `unittest discover` and `unittest tests.<module>` working.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

V54_TABLES = {
    "timing_correction_candidates",
    "timing_correction_candidate_decisions",
    "timing_correction_revision_generations",
}

# The released correction family this migration must leave byte-identical, plus the revision and
# selection relations a timing correction reuses rather than extends.
_UNTOUCHED = (
    "correction_candidates",
    "correction_candidate_evidence",
    "correction_candidate_admissions",
    "correction_candidate_decisions",
    "corrected_revision_generations",
    "corrected_revision_selections",
    "corrected_transcript_revisions",
    "corrected_transcript_revision_segments",
    "corrected_transcript_revision_candidates",
    "transcript_segments",
    "raw_transcripts",
    "provider_transcript_results",
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


class SQLiteSchemaVersionFiftyFourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_v54_remains_a_supported_released_version(self) -> None:
        # v54 is no longer the latest; it must stay reachable and supported (superseded, not removed).
        self.assertLessEqual(54, SQLITE_SCHEMA_VERSION)
        self.assertIn(54, sqlite_lifecycle._SUPPORTED_SCHEMA_VERSIONS)

    def test_fresh_database_initializes_with_v54_tables(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            self.assertTrue(V54_TABLES.issubset(table_names(connection)))
        finally:
            connection.close()

    def test_migrates_v53_to_v54_preserving_existing_rows(self) -> None:
        create_legacy_database(self.database_path, 53)
        migrate_sqlite_database(self.database_path, 54)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertTrue(V54_TABLES.issubset(table_names(connection)))
            self.assertEqual(
                connection.execute(
                    "SELECT purpose FROM processing_units WHERE identity = 'unit'"
                ).fetchone()[0],
                "preserved",
            )
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                54,
            )
        finally:
            connection.close()

    def test_released_relations_are_byte_identical_across_the_step(self) -> None:
        """TC-19/TC-20: no released column widened, made nullable, or reinterpreted."""

        create_legacy_database(self.database_path, 53)
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
        migrate_sqlite_database(self.database_path, 54)
        connection = open_sqlite_database(self.database_path)
        try:
            for table, sql in before.items():
                self.assertEqual(
                    connection.execute(
                        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (table,),
                    ).fetchone()[0],
                    sql,
                    f"{table} must be byte-identical across the step",
                )
            for table in V54_TABLES:
                self.assertEqual(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                    0,
                    "TC-20 forbids any backfill",
                )
        finally:
            connection.close()

    def test_proposed_text_stays_not_null(self) -> None:
        """The reason a sibling exists: making this column nullable is not an additive change."""

        create_legacy_database(self.database_path, 53)
        migrate_sqlite_database(self.database_path, 54)
        connection = open_sqlite_database(self.database_path)
        try:
            columns = {
                row[1]: row[3]
                for row in connection.execute("PRAGMA table_info(correction_candidates)")
            }
            self.assertEqual(columns["proposed_text"], 1)
        finally:
            connection.close()

    def test_existing_text_correction_rows_survive_the_step_unchanged(self) -> None:
        from lectureos.application.correction_candidate_admission import (
            build_correction_candidate_input,
        )
        from lectureos.composition import (
            compose_sqlite_correction_candidate_admission_service,
            compose_sqlite_correction_candidate_decision_service,
            compose_sqlite_corrected_revision_generation_service,
        )

        # Build a full text-correction lineage on a v54 database, then compare the released rows
        # before and after re-running the migration entry point (a no-op at the same version).
        from timing_correction_fixture import TimingCorrectionFixture

        fixture = TimingCorrectionFixture(self.temporary_directory.name)
        self.addCleanup(fixture.close)
        candidate = compose_sqlite_correction_candidate_admission_service(
            fixture.connection
        ).admit(
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
        compose_sqlite_correction_candidate_decision_service(fixture.connection).decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        compose_sqlite_corrected_revision_generation_service(fixture.connection).generate(
            candidate_id=candidate.identity.value
        )

        def _snapshot(connection):
            return {
                table: connection.execute(
                    f"SELECT * FROM {table} ORDER BY 1"
                ).fetchall()
                for table in (
                    "correction_candidates",
                    "correction_candidate_admissions",
                    "correction_candidate_decisions",
                    "corrected_revision_generations",
                    "corrected_transcript_revisions",
                    "transcript_segments",
                )
            }

        before = _snapshot(fixture.connection)
        fixture.connection.close()
        migrate_sqlite_database(
            fixture.database_path, SQLITE_SCHEMA_VERSION
        )  # no-op at the current version
        connection = open_sqlite_database(fixture.database_path)
        try:
            self.assertEqual(before, _snapshot(connection))
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM timing_correction_candidates"
                ).fetchone()[0],
                0,
                "a text-only repository gains no timing rows and is not 'timing corrected'",
            )
        finally:
            connection.close()

    def test_repositories_reject_a_pre_v54_schema(self) -> None:
        create_legacy_database(self.database_path, 53)
        connection = open_sqlite_database(self.database_path)
        try:
            for repository in (
                SQLiteTimingCorrectionCandidateRepository,
                SQLiteTimingCorrectionDecisionRepository,
                SQLiteTimingCorrectionGenerationRepository,
            ):
                with self.subTest(repository=repository.__name__):
                    with self.assertRaises(SchemaFeatureUnavailableError):
                        repository(connection)
        finally:
            connection.close()

    def test_v54_no_op_migration_is_allowed(self) -> None:
        create_legacy_database(self.database_path, 53)
        migrate_sqlite_database(self.database_path, 54)
        migrate_sqlite_database(self.database_path, 54)
        connection = open_sqlite_database(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
                54,
            )
        finally:
            connection.close()

    def test_direct_skip_migration_is_rejected(self) -> None:
        create_legacy_database(self.database_path, 52)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 54)

    def test_downgrade_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 53)
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, 54)

    def test_unsupported_target_is_rejected(self) -> None:
        initialize_sqlite_database(self.database_path).close()
        with self.assertRaises(PersistenceError):
            migrate_sqlite_database(self.database_path, SQLITE_SCHEMA_VERSION + 1)

    def test_every_released_version_chains_to_v54_preserving_data(self) -> None:
        # Migration compatibility: every released schema version reaches v54 through the supported
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
                        SQLITE_SCHEMA_VERSION,
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT purpose FROM processing_units WHERE identity = 'unit'"
                        ).fetchone()[0],
                        "preserved",
                    )
                    self.assertTrue(V54_TABLES.issubset(table_names(connection)))
                finally:
                    connection.close()

    def test_new_relations_enforce_their_structural_constraints(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        try:
            # end must be after start, and a snapshot must be a valid interval.
            for values, label in (
                ((5.0, 5.0), "proposed_end must exceed proposed_start"),
                ((5.0, 4.0), "an inverted proposal is refused"),
            ):
                with self.subTest(label=label):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(
                            """
                            INSERT INTO timing_correction_candidates VALUES
                            (?, 'intake', 'raw', 'segment', 'author', 'ref',
                             0.0, 1.0, ?, ?, 'why', ?)
                            """,
                            ("id", values[0], values[1], "0" * 64),
                        )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO timing_correction_candidate_decisions VALUES
                    ('d', 'c', 'modify', 'r', 0, NULL, NULL, ?)
                    """,
                    ("0" * 64,),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO timing_correction_revision_generations VALUES
                    ('g', 'rev', 'c', 'd', 'raw', 'same', 'same', ?)
                    """,
                    ("0" * 64,),
                )
        finally:
            connection.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
