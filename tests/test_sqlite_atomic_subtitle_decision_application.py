import tempfile
import unittest
from pathlib import Path

from lectureos.application import (
    SubtitleAppliedOutcome,
    SubtitleDecisionRevisionIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleDecisionRevisionId,
    SubtitleReviewDecisionId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_decision_application_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleDecisionRevisionCommandPersistence,
    SQLiteSubtitleDecisionRevisionRepository,
    SQLiteSubtitleReviewDecisionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.models import DecisionKind

try:  # importable both under discovery and as tests.<module>
    from tests.test_sqlite_atomic_subtitle_review_decision import (
        _build_persisted_preparation,
        _record_decision,
    )
except ImportError:  # pragma: no cover - invocation-style fallback
    from test_sqlite_atomic_subtitle_review_decision import (
        _build_persisted_preparation,
        _record_decision,
    )

_ACCEPT_DECISION = SubtitleReviewDecisionId("decision-accept")
_MODIFY_DECISION = SubtitleReviewDecisionId("decision-modify")


def _revision_plan(name):
    return SubtitleDecisionRevisionIdentityPlan(
        revision_id=SubtitleDecisionRevisionId(name),
        revision_result_id=DomainResultId(f"{name}-result"),
    )


def _apply(connection, execution, run_id, execution_id, decision_id, name):
    service = compose_sqlite_subtitle_decision_application_service(connection, execution)
    return service.record_application(
        source_review_decision_id=decision_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_revision_plan(name),
    )


def _build_persisted_decisions(connection):
    execution, run_id, execution_id, items = _build_persisted_preparation(connection)
    _record_decision(
        connection, execution, run_id, execution_id, items[0].identity,
        name="decision-accept", kind=DecisionKind.ACCEPT,
    )
    _record_decision(
        connection, execution, run_id, execution_id, items[1].identity,
        name="decision-modify", kind=DecisionKind.MODIFY, modified_text="corrected line",
    )
    return execution, run_id, execution_id


class SQLiteAtomicSubtitleDecisionApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.execution, self.run_id, self.execution_id = _build_persisted_decisions(
            self.connection
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_and_reconstructs_accepted_revision(self) -> None:
        prepared = _apply(
            self.connection, self.execution, self.run_id, self.execution_id,
            _ACCEPT_DECISION, "revision-accept",
        )
        self.assertIs(prepared.revision.outcome, SubtitleAppliedOutcome.ACCEPTED)
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            revision = SQLiteSubtitleDecisionRevisionRepository(reopened).get(
                prepared.revision.identity
            )
            self.assertEqual(revision, prepared.revision)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.revision_result.identity
            )
            self.assertEqual(result, prepared.revision_result)
        finally:
            reopened.close()

    def test_modify_application_round_trips_applied_text(self) -> None:
        prepared = _apply(
            self.connection, self.execution, self.run_id, self.execution_id,
            _MODIFY_DECISION, "revision-modify",
        )
        self.assertIs(prepared.revision.outcome, SubtitleAppliedOutcome.MODIFIED)
        self.assertEqual(prepared.revision.applied_text, "corrected line")
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            revision = SQLiteSubtitleDecisionRevisionRepository(reopened).get(
                prepared.revision.identity
            )
            self.assertEqual(revision.applied_text, "corrected line")
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = _apply(
            self.connection, self.execution, self.run_id, self.execution_id,
            _ACCEPT_DECISION, "revision-accept",
        )
        self.connection.close()

        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id = _build_persisted_decisions(replay_connection)
            second = _apply(
                replay_connection, execution, run_id, execution_id,
                _ACCEPT_DECISION, "revision-accept",
            )
            self.assertEqual(first.revision, second.revision)
            self.assertEqual(first.revision_result, second.revision_result)
        finally:
            replay_connection.close()

    def test_repeated_application_does_not_mutate_upstream_decision(self) -> None:
        decision_repo = SQLiteSubtitleReviewDecisionRepository(self.connection)
        before = decision_repo.get(_ACCEPT_DECISION)
        _apply(self.connection, self.execution, self.run_id, self.execution_id, _ACCEPT_DECISION, "r-a")
        _apply(self.connection, self.execution, self.run_id, self.execution_id, _MODIFY_DECISION, "r-b")
        after = decision_repo.get(_ACCEPT_DECISION)
        self.assertEqual(before, after)
        count = self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_decision_revisions"
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_result_collision_rolls_back_revision(self) -> None:
        service = compose_sqlite_subtitle_decision_application_service(
            self.connection, self.execution
        )
        prepared = service.apply_decision(
            source_review_decision_id=_ACCEPT_DECISION,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=SubtitleDecisionRevisionIdentityPlan(
                revision_id=SubtitleDecisionRevisionId("revision-x"),
                # Reuse an existing DomainResult identity to force a collision.
                revision_result_id=DomainResultId("decision-accept-result"),
            ),
        )
        persistence = SQLiteSubtitleDecisionRevisionCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_decision_revision(
                revision=prepared.revision,
                revision_result=prepared.revision_result,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_decision_revisions"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
