import inspect
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lectureos.execution.boundaries import AtomicResultExecutionPersistence
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    ProcessingUnitId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import (
    DomainResultReference,
    ExecutionIntent,
    ExecutionOutcome,
    OutcomeKind,
    ProcessingRun,
    ProcessingState,
    UnitExecution,
)
from lectureos.persistence import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
    SQLiteDomainResultReferenceRepository,
    SQLiteExecutionCommandPersistence,
    SQLiteProcessingRunRepository,
    SQLiteUnitExecutionRepository,
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


class SQLiteAtomicResultPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.runs = SQLiteProcessingRunRepository(self.connection)
        self.executions = SQLiteUnitExecutionRepository(self.connection)
        self.results_repository = SQLiteDomainResultReferenceRepository(self.connection)
        self.persistence = SQLiteExecutionCommandPersistence(self.connection)

        self.initial_run = ProcessingRun(
            identity=ProcessingRunId("run-main"),
            intent=ExecutionIntent("Atomic Result fixture"),
            working_context=WorkingContextReference("context-main"),
            unit_references=(ProcessingUnitId("unit-main"),),
            unit_execution_references=(UnitExecutionId("execution-main"),),
            state=ProcessingState.RUNNING,
            result_references=(DomainResultId("result-existing"),),
        )
        self.initial_execution = UnitExecution(
            identity=UnitExecutionId("execution-main"),
            run_id=self.initial_run.identity,
            unit_id=ProcessingUnitId("unit-main"),
            state=ProcessingState.RUNNING,
            result_references=(DomainResultId("result-existing"),),
        )
        self.results = (
            DomainResultReference(
                identity=DomainResultId("result-z"),
                kind="transcript",
                source_media=SourceMediaId("media-main"),
                upstream_results=(
                    DomainResultId("upstream-b"),
                    DomainResultId("upstream-a"),
                    DomainResultId("upstream-b"),
                ),
            ),
            DomainResultReference(
                identity=DomainResultId("result-a"),
                kind="subtitle",
                source_timeline=SourceTimelineId("timeline-main"),
                revision_of=DomainResultId("result-previous"),
                applicability="final",
            ),
            DomainResultReference(
                identity=DomainResultId("result-m"),
                kind="artifact",
            ),
        )
        result_ids = tuple(result.identity for result in self.results)
        self.final_execution = replace(
            self.initial_execution,
            state=ProcessingState.COMPLETED,
            outcome=ExecutionOutcome(OutcomeKind.DOMAIN_RESULT_GENERATED),
            result_references=self.initial_execution.result_references + result_ids,
        )
        self.final_run = replace(
            self.initial_run,
            result_references=self.initial_run.result_references + result_ids,
        )
        self.runs.save(self.initial_run)
        self.executions.save(self.initial_execution)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def _persist(
        self,
        *,
        results: tuple[DomainResultReference, ...] | None = None,
        execution: UnitExecution | None = None,
        run: ProcessingRun | None = None,
    ) -> None:
        self.persistence.persist_recorded_results(
            results=self.results if results is None else results,
            execution=self.final_execution if execution is None else execution,
            run=self.final_run if run is None else run,
        )

    def _assert_initial_state(self) -> None:
        for result in self.results:
            self.assertIsNone(self.results_repository.get(result.identity))
        self.assertEqual(
            self.executions.get(self.initial_execution.identity),
            self.initial_execution,
        )
        self.assertEqual(self.runs.get(self.initial_run.identity), self.initial_run)
        self.assertFalse(self.connection.in_transaction)
        self.assertEqual(self.connection.execute("SELECT 1").fetchone(), (1,))

    def test_multiple_results_and_final_snapshots_persist_and_survive_restart(self) -> None:
        self._persist()
        for result in self.results:
            self.assertEqual(self.results_repository.get(result.identity), result)
        self.assertEqual(
            self.executions.get(self.final_execution.identity), self.final_execution
        )
        self.assertEqual(self.runs.get(self.final_run.identity), self.final_run)

        self.connection.close()
        self.connection = open_sqlite_database(self.database_path)
        restarted_results = SQLiteDomainResultReferenceRepository(self.connection)
        restarted_executions = SQLiteUnitExecutionRepository(self.connection)
        restarted_runs = SQLiteProcessingRunRepository(self.connection)
        for result in self.results:
            self.assertEqual(restarted_results.get(result.identity), result)
        self.assertEqual(
            restarted_executions.get(self.final_execution.identity),
            self.final_execution,
        )
        self.assertEqual(restarted_runs.get(self.final_run.identity), self.final_run)

    def test_v1_through_v3_are_unavailable_without_migration_or_mutation(self) -> None:
        for version in (1, 2, 3):
            with self.subTest(version=version):
                path = Path(self.temporary_directory.name) / f"legacy-v{version}.sqlite3"
                connection = create_legacy_database(path, version)
                tables_before = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
                with self.assertRaises(SchemaFeatureUnavailableError):
                    adapter = SQLiteExecutionCommandPersistence(connection)
                    adapter.persist_recorded_results(
                        results=self.results,
                        execution=self.final_execution,
                        run=self.final_run,
                    )
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

    def test_first_middle_and_last_result_collisions_roll_back_everything(self) -> None:
        for index in range(len(self.results)):
            with self.subTest(index=index):
                self.results_repository.save(self.results[index])
                with self.assertRaises(PersistenceIdentityCollisionError):
                    self._persist()
                self.assertEqual(
                    self.results_repository.get(self.results[index].identity),
                    self.results[index],
                )
                self.assertEqual(
                    self.executions.get(self.initial_execution.identity),
                    self.initial_execution,
                )
                self.assertEqual(self.runs.get(self.initial_run.identity), self.initial_run)
                self.connection.execute(
                    "DELETE FROM domain_result_references WHERE identity = ?",
                    (self.results[index].identity.value,),
                )

    def test_result_child_failure_rolls_back_complete_record_set(self) -> None:
        original = result_persistence._insert_upstream_results
        calls = 0

        def fail_on_second_result(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise sqlite3.IntegrityError("injected Result child failure")
            return original(*args, **kwargs)

        with patch.object(
            result_persistence,
            "_insert_upstream_results",
            side_effect=fail_on_second_result,
        ):
            with self.assertRaises(PersistenceError):
                self._persist()
        self._assert_initial_state()

    def test_execution_write_failure_rolls_back_results_and_run(self) -> None:
        with patch(
            "lectureos.persistence.execution_commands._write_unit_execution_snapshot",
            side_effect=sqlite3.OperationalError("injected execution failure"),
        ):
            with self.assertRaises(PersistenceError):
                self._persist()
        self._assert_initial_state()

    def test_run_write_failure_rolls_back_results_and_execution(self) -> None:
        with patch(
            "lectureos.persistence.execution_commands._write_processing_run_snapshot",
            side_effect=sqlite3.OperationalError("injected run failure"),
        ):
            with self.assertRaises(PersistenceError):
                self._persist()
        self._assert_initial_state()

    def test_commit_failure_rolls_back_everything_and_connection_is_reusable(self) -> None:
        with patch.object(
            self.persistence,
            "_commit",
            side_effect=sqlite3.OperationalError("injected commit failure"),
        ):
            with self.assertRaises(PersistenceError):
                self._persist()
        self._assert_initial_state()

    def test_every_linkage_mismatch_rolls_back_without_mutation(self) -> None:
        duplicate_results = (self.results[0], self.results[0])
        mismatches = (
            ((), self.final_execution, self.final_run),
            (duplicate_results, self.final_execution, self.final_run),
            (
                self.results,
                replace(self.final_execution, run_id=ProcessingRunId("other")),
                self.final_run,
            ),
            (
                self.results,
                replace(
                    self.final_execution,
                    result_references=(DomainResultId("wrong"),),
                ),
                self.final_run,
            ),
            (
                self.results,
                self.final_execution,
                replace(self.final_run, result_references=(DomainResultId("wrong"),)),
            ),
        )
        for results, execution, run in mismatches:
            with self.subTest(results=results, execution=execution, run=run):
                with self.assertRaises(PersistenceError):
                    self._persist(results=results, execution=execution, run=run)
                self._assert_initial_state()

    def test_port_is_sqlite_independent_and_service_is_not_wired(self) -> None:
        self.assertTrue(
            hasattr(AtomicResultExecutionPersistence, "persist_recorded_results")
        )
        boundary_source = inspect.getsource(
            __import__("lectureos.execution.boundaries", fromlist=["boundaries"])
        )
        service_source = inspect.getsource(
            __import__("lectureos.execution.service", fromlist=["service"])
        )
        self.assertNotIn("sqlite", boundary_source.lower())
        self.assertNotIn("AtomicResultExecutionPersistence", service_source)

    def test_internal_writers_do_not_own_transactions_or_call_public_saves(self) -> None:
        command_source = inspect.getsource(
            SQLiteExecutionCommandPersistence.persist_recorded_results
        )
        result_writer_source = inspect.getsource(
            result_persistence._insert_domain_result_reference_record
        )
        self.assertIn("BEGIN IMMEDIATE", command_source)
        self.assertNotIn(".save(", command_source)
        for statement in ("BEGIN", "COMMIT", "ROLLBACK"):
            self.assertNotIn(statement, result_writer_source)


if __name__ == "__main__":
    unittest.main()
