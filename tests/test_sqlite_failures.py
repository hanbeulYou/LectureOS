import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lectureos.execution.identities import (
    DiagnosticId,
    DomainResultId,
    FailureId,
    InputReference,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import Failure, FailureCategory
from lectureos.persistence import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SQLiteFailureRepository,
    SchemaFeatureUnavailableError,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import failures as failure_persistence
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


class SQLiteFailureRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.repository = SQLiteFailureRepository(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def _failure(self, identity: str = "failure-main") -> Failure:
        return Failure(
            identity=FailureId(identity),
            category=FailureCategory.PROCESSING,
            run_id=ProcessingRunId("run-main"),
            unit_execution_id=UnitExecutionId("execution-main"),
            affected_inputs=(
                InputReference("input-z"),
                InputReference("input-a"),
                InputReference("input-z"),
            ),
            affected_results=(
                DomainResultId("result-z"),
                DomainResultId("result-a"),
                DomainResultId("result-z"),
            ),
            retryable=True,
            reprocessing_required=False,
            human_action_required=True,
            diagnostics=(
                DiagnosticId("diagnostic-z"),
                DiagnosticId("diagnostic-a"),
                DiagnosticId("diagnostic-z"),
            ),
        )

    def test_v4_supports_repository_and_lower_versions_are_unavailable_without_mutation(
        self,
    ) -> None:
        self.assertIsNone(self.repository.get(FailureId("missing")))
        for version in (1, 2, 3):
            with self.subTest(version=version):
                path = Path(self.temporary_directory.name) / f"legacy-v{version}.sqlite3"
                connection = create_legacy_database(path, version)
                tables_before = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
                with self.assertRaises(SchemaFeatureUnavailableError):
                    SQLiteFailureRepository(connection)
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
        self.connection.execute("DROP TABLE failure_diagnostics")
        with self.assertRaises(PersistenceError):
            SQLiteFailureRepository(self.connection)
        self.assertIsNone(
            self.connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'failure_diagnostics'"
            ).fetchone()
        )

    def test_complete_failure_round_trips_with_exact_types_order_and_duplicates(self) -> None:
        expected = self._failure()
        self.repository.save(expected)
        restored = self.repository.get(expected.identity)
        self.assertEqual(restored, expected)
        self.assertIs(type(restored.identity), FailureId)
        self.assertIs(type(restored.category), FailureCategory)
        self.assertIs(type(restored.run_id), ProcessingRunId)
        self.assertIs(type(restored.unit_execution_id), UnitExecutionId)
        self.assertTrue(all(type(item) is InputReference for item in restored.affected_inputs))
        self.assertTrue(all(type(item) is DomainResultId for item in restored.affected_results))
        self.assertTrue(all(type(item) is DiagnosticId for item in restored.diagnostics))

    def test_nullable_provenance_and_empty_children_round_trip(self) -> None:
        variants = (
            Failure(
                FailureId("failure-run"),
                FailureCategory.PREPARATION,
                run_id=ProcessingRunId("run"),
            ),
            Failure(
                FailureId("failure-execution"),
                FailureCategory.CAPABILITY,
                unit_execution_id=UnitExecutionId("execution"),
            ),
            Failure(
                FailureId("failure-both"),
                FailureCategory.EXPORT,
                run_id=ProcessingRunId("run"),
                unit_execution_id=UnitExecutionId("execution"),
            ),
        )
        for expected in variants:
            with self.subTest(identity=expected.identity.value):
                self.repository.save(expected)
                self.assertEqual(self.repository.get(expected.identity), expected)
                counts = tuple(
                    self.connection.execute(
                        f"SELECT count(*) FROM {table} WHERE failure_id = ?",
                        (expected.identity.value,),
                    ).fetchone()[0]
                    for table in (
                        "failure_affected_inputs",
                        "failure_affected_results",
                        "failure_diagnostics",
                    )
                )
                self.assertEqual(counts, (0, 0, 0))

    def test_every_category_and_boolean_combinations_round_trip_exactly(self) -> None:
        boolean_combinations = (
            (False, False, False),
            (True, False, False),
            (False, True, False),
            (False, False, True),
            (True, True, True),
        )
        for index, category in enumerate(FailureCategory):
            flags = boolean_combinations[index % len(boolean_combinations)]
            expected = Failure(
                identity=FailureId(f"failure-category-{index}"),
                category=category,
                run_id=ProcessingRunId("run-category"),
                retryable=flags[0],
                reprocessing_required=flags[1],
                human_action_required=flags[2],
            )
            self.repository.save(expected)
            self.assertEqual(self.repository.get(expected.identity), expected)
            stored = self.connection.execute(
                """
                SELECT category, retryable, reprocessing_required, human_action_required
                FROM failures WHERE identity = ?
                """,
                (expected.identity.value,),
            ).fetchone()
            self.assertEqual(stored, (category.value, *(int(flag) for flag in flags)))

    def test_child_rows_use_zero_based_ordinals_and_normalized_tables(self) -> None:
        expected = self._failure()
        self.repository.save(expected)
        for table, column, values in (
            ("failure_affected_inputs", "input_reference", ("input-z", "input-a", "input-z")),
            ("failure_affected_results", "domain_result_id", ("result-z", "result-a", "result-z")),
            (
                "failure_diagnostics",
                "diagnostic_id",
                ("diagnostic-z", "diagnostic-a", "diagnostic-z"),
            ),
        ):
            with self.subTest(table=table):
                rows = self.connection.execute(
                    f"SELECT ordinal, {column} FROM {table} WHERE failure_id = ? ORDER BY ordinal",
                    (expected.identity.value,),
                ).fetchall()
                self.assertEqual(rows, list(enumerate(values)))

    def test_duplicate_identity_is_never_idempotent_and_never_overwrites(self) -> None:
        original = self._failure()
        self.repository.save(original)
        changed_parent = Failure(
            identity=original.identity,
            category=FailureCategory.VALIDATION,
            run_id=original.run_id,
        )
        changed_children = Failure(
            identity=original.identity,
            category=original.category,
            run_id=original.run_id,
            affected_inputs=(InputReference("changed"),),
        )
        for duplicate in (original, changed_parent, changed_children):
            with self.assertRaises(PersistenceIdentityCollisionError):
                self.repository.save(duplicate)
            self.assertEqual(self.repository.get(original.identity), original)

    def test_child_failure_rolls_back_parent_and_preserves_unrelated_record(self) -> None:
        existing = self._failure("failure-existing")
        attempted = self._failure("failure-attempted")
        self.repository.save(existing)
        with patch.object(
            failure_persistence,
            "_insert_children",
            side_effect=sqlite3.IntegrityError("injected child failure"),
        ):
            with self.assertRaises(PersistenceError):
                self.repository.save(attempted)
        self.assertIsNone(self.repository.get(attempted.identity))
        self.assertEqual(self.repository.get(existing.identity), existing)
        for table in (
            "failure_affected_inputs",
            "failure_affected_results",
            "failure_diagnostics",
        ):
            self.assertEqual(
                self.connection.execute(
                    f"SELECT count(*) FROM {table} WHERE failure_id = ?",
                    (attempted.identity.value,),
                ).fetchone(),
                (0,),
            )

    def test_record_survives_connection_restart_and_connection_is_caller_owned(self) -> None:
        expected = self._failure()
        self.repository.save(expected)
        self.connection.close()
        self.connection = open_sqlite_database(self.database_path)
        self.repository = SQLiteFailureRepository(self.connection)
        self.assertEqual(self.repository.get(expected.identity), expected)
        self.repository.get(expected.identity)
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))

    def test_corrupt_boolean_or_child_ordinal_is_not_normalized(self) -> None:
        self.connection.execute("PRAGMA ignore_check_constraints = ON")
        self.connection.execute(
            """
            INSERT INTO failures(
                identity, category, processing_run_id, unit_execution_id,
                retryable, reprocessing_required, human_action_required
            ) VALUES ('failure-corrupt-boolean', 'processing', 'run', NULL, 2, 0, 0)
            """
        )
        self.connection.execute("PRAGMA ignore_check_constraints = OFF")
        with self.assertRaises(PersistenceError):
            self.repository.get(FailureId("failure-corrupt-boolean"))

        self.connection.execute(
            """
            INSERT INTO failures VALUES ('failure-gap', 'processing', 'run', NULL, 0, 0, 0)
            """
        )
        self.connection.execute(
            "INSERT INTO failure_diagnostics VALUES ('failure-gap', 1, 'diagnostic')"
        )
        with self.assertRaises(PersistenceError):
            self.repository.get(FailureId("failure-gap"))

    def test_only_protocol_methods_are_added(self) -> None:
        self.assertTrue(callable(self.repository.get))
        self.assertTrue(callable(self.repository.save))
        for method in ("all", "update", "delete", "upsert", "history"):
            self.assertFalse(hasattr(self.repository, method))


if __name__ == "__main__":
    unittest.main()
