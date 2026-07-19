import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lectureos.execution.identities import (
    DomainResultId,
    SourceMediaId,
    SourceTimelineId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.persistence import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
    SQLiteDomainResultReferenceRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import domain_results as result_persistence
from lectureos.persistence import sqlite as sqlite_lifecycle


def create_legacy_database(path: Path, version: int) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN")
    statements = list(sqlite_lifecycle._V1_TABLE_STATEMENTS)
    if version >= 2:
        statements.extend(sqlite_lifecycle._V2_ADDITION_STATEMENTS)
    if version >= 3:
        statements.extend(sqlite_lifecycle._V3_ADDITION_STATEMENTS)
    for statement in statements:
        connection.execute(statement)
    connection.execute("INSERT INTO schema_metadata VALUES (1, ?)", (version,))
    connection.execute("COMMIT")
    return connection


class SQLiteDomainResultReferenceRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.repository = SQLiteDomainResultReferenceRepository(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def _result(self, identity: str = "result-main") -> DomainResultReference:
        return DomainResultReference(
            identity=DomainResultId(identity),
            kind="transcript.reviewed",
            source_media=SourceMediaId("media-main"),
            source_timeline=SourceTimelineId("timeline-main"),
            upstream_results=(
                DomainResultId("result-z"),
                DomainResultId("result-a"),
                DomainResultId("result-z"),
            ),
            revision_of=DomainResultId("result-previous"),
            applicability="lecture-segment",
        )

    def test_v4_supports_repository_and_lower_versions_are_unavailable_without_mutation(
        self,
    ) -> None:
        self.assertIsNone(self.repository.get(DomainResultId("missing")))
        for version in (1, 2, 3):
            with self.subTest(version=version):
                path = Path(self.temporary_directory.name) / f"legacy-v{version}.sqlite3"
                connection = create_legacy_database(path, version)
                tables_before = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
                with self.assertRaises(SchemaFeatureUnavailableError):
                    SQLiteDomainResultReferenceRepository(connection)
                self.assertEqual(
                    connection.execute("SELECT version FROM schema_metadata").fetchone(),
                    (version,),
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                    ).fetchall(),
                    tables_before,
                )
                connection.close()

    def test_missing_v4_schema_is_rejected_and_not_repaired(self) -> None:
        self.connection.execute("DROP TABLE domain_result_upstream_results")
        with self.assertRaises(PersistenceError):
            SQLiteDomainResultReferenceRepository(self.connection)
        self.assertIsNone(
            self.connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE name = 'domain_result_upstream_results'"
            ).fetchone()
        )

    def test_complete_result_round_trips_with_exact_types_order_and_duplicates(self) -> None:
        expected = self._result()
        self.repository.save(expected)
        restored = self.repository.get(expected.identity)
        self.assertEqual(restored, expected)
        self.assertIs(type(restored.identity), DomainResultId)
        self.assertIs(type(restored.source_media), SourceMediaId)
        self.assertIs(type(restored.source_timeline), SourceTimelineId)
        self.assertIs(type(restored.revision_of), DomainResultId)
        self.assertTrue(
            all(type(item) is DomainResultId for item in restored.upstream_results)
        )
        rows = self.connection.execute(
            """
            SELECT ordinal, upstream_domain_result_id
            FROM domain_result_upstream_results
            WHERE domain_result_id = ? ORDER BY ordinal
            """,
            (expected.identity.value,),
        ).fetchall()
        self.assertEqual(rows, [(0, "result-z"), (1, "result-a"), (2, "result-z")])

    def test_nullable_fields_and_empty_upstream_tuple_round_trip(self) -> None:
        expected = DomainResultReference(
            identity=DomainResultId("result-minimal"),
            kind="artifact",
        )
        self.repository.save(expected)
        self.assertEqual(self.repository.get(expected.identity), expected)
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM domain_result_upstream_results "
                "WHERE domain_result_id = ?",
                (expected.identity.value,),
            ).fetchone(),
            (0,),
        )

    def test_blank_kind_is_rejected_by_domain_and_schema(self) -> None:
        with self.assertRaises(ValueError):
            DomainResultReference(DomainResultId("result-domain-blank"), "  ")
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO domain_result_references(identity, kind)
                VALUES ('result-schema-blank', '  ')
                """
            )

    def test_duplicate_identity_is_never_idempotent_and_never_overwrites(self) -> None:
        original = self._result()
        self.repository.save(original)
        changed_parent = DomainResultReference(
            identity=original.identity,
            kind="subtitle",
        )
        changed_children = DomainResultReference(
            identity=original.identity,
            kind=original.kind,
            upstream_results=(DomainResultId("changed"),),
        )
        for duplicate in (original, changed_parent, changed_children):
            with self.assertRaises(PersistenceIdentityCollisionError):
                self.repository.save(duplicate)
            self.assertEqual(self.repository.get(original.identity), original)

    def test_child_failure_rolls_back_parent_and_preserves_unrelated_record(self) -> None:
        existing = self._result("result-existing")
        attempted = self._result("result-attempted")
        self.repository.save(existing)
        with patch.object(
            result_persistence,
            "_insert_upstream_results",
            side_effect=sqlite3.IntegrityError("injected child failure"),
        ):
            with self.assertRaises(PersistenceError):
                self.repository.save(attempted)
        self.assertIsNone(self.repository.get(attempted.identity))
        self.assertEqual(self.repository.get(existing.identity), existing)
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM domain_result_upstream_results "
                "WHERE domain_result_id = ?",
                (attempted.identity.value,),
            ).fetchone(),
            (0,),
        )

    def test_malformed_upstream_ordinal_gap_is_reported_as_corruption(self) -> None:
        expected = self._result()
        self.repository.save(expected)
        self.connection.execute(
            "DELETE FROM domain_result_upstream_results "
            "WHERE domain_result_id = ? AND ordinal = 1",
            (expected.identity.value,),
        )
        with self.assertRaisesRegex(PersistenceError, "ordering is corrupt"):
            self.repository.get(expected.identity)

    def test_record_survives_restart_and_connection_remains_caller_owned(self) -> None:
        expected = self._result()
        self.repository.save(expected)
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))
        self.connection.close()
        self.connection = open_sqlite_database(self.database_path)
        restarted = SQLiteDomainResultReferenceRepository(self.connection)
        self.assertEqual(restarted.get(expected.identity), expected)

    def test_public_api_remains_minimal(self) -> None:
        self.assertTrue(callable(self.repository.save))
        self.assertTrue(callable(self.repository.get))
        for speculative_method in ("update", "delete", "all", "history", "find_by_kind"):
            self.assertFalse(hasattr(self.repository, speculative_method))


if __name__ == "__main__":
    unittest.main()
