import tempfile
import unittest
from pathlib import Path

from lectureos.application import SubtitleReviewPreparationIdentityPlan
from lectureos.application.identities import (
    SubtitleReviewPreparationId,
    SubtitleValidationId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_review_preparation_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleReviewPreparationRepository,
    SQLiteSubtitleValidationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.identities import ReviewContextId

try:  # importable both under discovery and as tests.<module>
    from tests.test_sqlite_atomic_subtitle_validation import (
        _build_persisted_time,
        _record_validation,
    )
except ImportError:  # pragma: no cover - invocation-style fallback
    from test_sqlite_atomic_subtitle_validation import (
        _build_persisted_time,
        _record_validation,
    )

_VALIDATION_ID = SubtitleValidationId("validation-0")


def _prep_plan(name="prep-0") -> SubtitleReviewPreparationIdentityPlan:
    # The clean pipeline validation has no findings, so the preparation is empty (no targets).
    return SubtitleReviewPreparationIdentityPlan(
        preparation_id=SubtitleReviewPreparationId(name),
        preparation_result_id=DomainResultId(f"{name}-result"),
        context_id=ReviewContextId(f"{name}-context"),
        targets=(),
    )


def _record_prep(connection, execution, run_id, execution_id, name="prep-0"):
    service = compose_sqlite_subtitle_review_preparation_service(connection, execution)
    return service.generate_review(
        source_validation_id=_VALIDATION_ID,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_prep_plan(name),
    )


def _build_persisted_validation(connection):
    execution, run_id, execution_id = _build_persisted_time(connection)
    _record_validation(connection, execution, run_id, execution_id)
    return execution, run_id, execution_id


class SQLiteAtomicSubtitleReviewPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.execution, self.run_id, self.execution_id = _build_persisted_validation(
            self.connection
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_and_reconstructs_empty_preparation(self) -> None:
        prepared = _record_prep(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        # the clean pipeline validation is structurally valid → empty preparation
        self.assertEqual(prepared.preparation.item_count, 0)
        self.assertEqual(prepared.review_items, ())
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteSubtitleReviewPreparationRepository(reopened)
            preparation = repo.get(prepared.preparation.identity)
            self.assertEqual(preparation, prepared.preparation)
            self.assertEqual(preparation.item_links, ())
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.preparation_result.identity
            )
            self.assertEqual(result, prepared.preparation_result)
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = _record_prep(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.connection.close()

        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id = _build_persisted_validation(replay_connection)
            second = _record_prep(replay_connection, execution, run_id, execution_id)
            self.assertEqual(first.preparation, second.preparation)
            self.assertEqual(first.preparation_result, second.preparation_result)
            replayed = SQLiteSubtitleReviewPreparationRepository(replay_connection).get(
                first.preparation.identity
            )
            self.assertEqual(replayed, first.preparation)
        finally:
            replay_connection.close()

    def test_repeated_preparation_does_not_mutate_upstream_validation(self) -> None:
        validation_repo = SQLiteSubtitleValidationRepository(self.connection)
        before = validation_repo.get(_VALIDATION_ID)
        _record_prep(self.connection, self.execution, self.run_id, self.execution_id, "p-a")
        _record_prep(self.connection, self.execution, self.run_id, self.execution_id, "p-b")
        after = validation_repo.get(_VALIDATION_ID)
        self.assertEqual(before, after)
        count = self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_review_preparations"
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_repeated_persist_is_rejected_and_atomic(self) -> None:
        prepared = _record_prep(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        from lectureos.persistence import (
            SQLiteSubtitleReviewPreparationCommandPersistence,
        )

        persistence = SQLiteSubtitleReviewPreparationCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_review_preparation(
                preparation=prepared.preparation,
                preparation_result=prepared.preparation_result,
                context=prepared.context,
                candidate_references=prepared.candidate_references,
                review_items=prepared.review_items,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_review_preparations"
            ).fetchone()[0],
            1,
        )

    def test_result_collision_rolls_back_preparation(self) -> None:
        service = compose_sqlite_subtitle_review_preparation_service(
            self.connection, self.execution
        )
        prepared = service.prepare_review(
            source_validation_id=_VALIDATION_ID,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=SubtitleReviewPreparationIdentityPlan(
                preparation_id=SubtitleReviewPreparationId("prep-x"),
                # Reuse an existing DomainResult identity to force a collision.
                preparation_result_id=DomainResultId("validation-0-result"),
                context_id=ReviewContextId("prep-x-context"),
                targets=(),
            ),
        )
        from lectureos.persistence import (
            SQLiteSubtitleReviewPreparationCommandPersistence,
        )

        persistence = SQLiteSubtitleReviewPreparationCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_review_preparation(
                preparation=prepared.preparation,
                preparation_result=prepared.preparation_result,
                context=prepared.context,
                candidate_references=prepared.candidate_references,
                review_items=prepared.review_items,
            )
        for table in ("subtitle_review_preparations", "review_contexts"):
            self.assertEqual(
                self.connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE identity LIKE 'prep-x%'"
                ).fetchone()[0],
                0,
                table,
            )


if __name__ == "__main__":
    unittest.main()
