import tempfile
import unittest
from pathlib import Path

from lectureos.application import SubtitleValidationIdentityPlan
from lectureos.application.identities import (
    SubtitleTimeRevisionId,
    SubtitleValidationId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_structural_validation_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleTimeRevisionRepository,
    SQLiteSubtitleValidationCommandPersistence,
    SQLiteSubtitleValidationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)

try:  # importable both under discovery and as tests.<module>
    from tests.test_sqlite_atomic_subtitle_time import (
        _build_persisted_reading,
        _record_timing,
    )
except ImportError:  # pragma: no cover - invocation-style fallback
    from test_sqlite_atomic_subtitle_time import (
        _build_persisted_reading,
        _record_timing,
    )

_TIME_ID = SubtitleTimeRevisionId("time-0")


def _validation_plan(name="validation-0") -> SubtitleValidationIdentityPlan:
    return SubtitleValidationIdentityPlan(
        validation_id=SubtitleValidationId(name),
        validation_result_id=DomainResultId(f"{name}-result"),
    )


def _record_validation(connection, execution, run_id, execution_id, name="validation-0"):
    service = compose_sqlite_subtitle_structural_validation_service(connection, execution)
    return service.record_validation(
        source_time_revision_id=_TIME_ID,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_validation_plan(name),
    )


def _build_persisted_time(connection):
    execution, run_id, execution_id = _build_persisted_reading(connection)
    _record_timing(connection, execution, run_id, execution_id)
    return execution, run_id, execution_id


class SQLiteAtomicSubtitleValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.execution, self.run_id, self.execution_id = _build_persisted_time(
            self.connection
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_and_reconstructs_validation(self) -> None:
        prepared = _record_validation(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        # the clean pipeline time revision is structurally valid with no findings
        self.assertTrue(prepared.validation.structural_valid)
        self.assertEqual(prepared.findings, ())
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteSubtitleValidationRepository(reopened)
            validation = repo.get(prepared.validation.identity)
            self.assertEqual(validation, prepared.validation)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.validation_result.identity
            )
            self.assertEqual(result, prepared.validation_result)
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = _record_validation(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.connection.close()

        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id = _build_persisted_time(replay_connection)
            second = _record_validation(replay_connection, execution, run_id, execution_id)
            self.assertEqual(first.validation, second.validation)
            self.assertEqual(first.findings, second.findings)
            self.assertEqual(first.validation_result, second.validation_result)
            replayed = SQLiteSubtitleValidationRepository(replay_connection).get(
                first.validation.identity
            )
            self.assertEqual(replayed, first.validation)
        finally:
            replay_connection.close()

    def test_repeated_validation_does_not_mutate_upstream_time_revision(self) -> None:
        time_repo = SQLiteSubtitleTimeRevisionRepository(self.connection)
        before = time_repo.get(_TIME_ID)
        _record_validation(self.connection, self.execution, self.run_id, self.execution_id, "v-a")
        _record_validation(self.connection, self.execution, self.run_id, self.execution_id, "v-b")
        after = time_repo.get(_TIME_ID)
        self.assertEqual(before, after)
        count = self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_validations"
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_repeated_persist_is_rejected_and_atomic(self) -> None:
        prepared = _record_validation(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        persistence = SQLiteSubtitleValidationCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_validation(
                validation=prepared.validation,
                findings=prepared.findings,
                validation_result=prepared.validation_result,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_validations"
            ).fetchone()[0],
            1,
        )

    def test_result_collision_rolls_back_validation(self) -> None:
        service = compose_sqlite_subtitle_structural_validation_service(
            self.connection, self.execution
        )
        prepared = service.validate_timing(
            source_time_revision_id=_TIME_ID,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=SubtitleValidationIdentityPlan(
                validation_id=SubtitleValidationId("validation-x"),
                # Reuse an existing DomainResult identity to force a collision.
                validation_result_id=DomainResultId("time-0-result"),
            ),
        )
        persistence = SQLiteSubtitleValidationCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_validation(
                validation=prepared.validation,
                findings=prepared.findings,
                validation_result=prepared.validation_result,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_validations"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
