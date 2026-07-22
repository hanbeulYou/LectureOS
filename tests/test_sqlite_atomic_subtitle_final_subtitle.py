import tempfile
import unittest
from pathlib import Path

from lectureos.application import (
    SubtitleFinalOutcome,
    SubtitleFinalSubtitleIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleDecisionRevisionId,
    SubtitleFinalSubtitleId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_final_subtitle_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleDecisionRevisionRepository,
    SQLiteSubtitleFinalSubtitleCommandPersistence,
    SQLiteSubtitleFinalSubtitleRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)

try:  # importable both under discovery and as tests.<module>
    from tests.test_sqlite_atomic_subtitle_decision_application import (
        _ACCEPT_DECISION,
        _MODIFY_DECISION,
        _apply as _apply_decision,
        _build_persisted_decisions,
    )
except ImportError:  # pragma: no cover - invocation-style fallback
    from test_sqlite_atomic_subtitle_decision_application import (
        _ACCEPT_DECISION,
        _MODIFY_DECISION,
        _apply as _apply_decision,
        _build_persisted_decisions,
    )

_ACCEPT_REVISION = SubtitleDecisionRevisionId("revision-accept")
_MODIFY_REVISION = SubtitleDecisionRevisionId("revision-modify")


def _final_plan(name):
    return SubtitleFinalSubtitleIdentityPlan(
        final_id=SubtitleFinalSubtitleId(name),
        final_result_id=DomainResultId(f"{name}-result"),
    )


def _select(connection, execution, run_id, execution_id, revision_id, name):
    service = compose_sqlite_subtitle_final_subtitle_service(connection, execution)
    return service.record_final(
        source_decision_revision_id=revision_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_final_plan(name),
    )


def _build_persisted_revisions(connection):
    execution, run_id, execution_id = _build_persisted_decisions(connection)
    _apply_decision(
        connection, execution, run_id, execution_id, _ACCEPT_DECISION, "revision-accept"
    )
    _apply_decision(
        connection, execution, run_id, execution_id, _MODIFY_DECISION, "revision-modify"
    )
    return execution, run_id, execution_id


class SQLiteAtomicSubtitleFinalSubtitleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.execution, self.run_id, self.execution_id = _build_persisted_revisions(
            self.connection
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_and_reconstructs_final_subtitle(self) -> None:
        prepared = _select(
            self.connection, self.execution, self.run_id, self.execution_id,
            _ACCEPT_REVISION, "final-accept",
        )
        self.assertIs(prepared.final.final_outcome, SubtitleFinalOutcome.FINAL)
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            final = SQLiteSubtitleFinalSubtitleRepository(reopened).get(
                prepared.final.identity
            )
            self.assertEqual(final, prepared.final)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.final_result.identity
            )
            self.assertEqual(result, prepared.final_result)
        finally:
            reopened.close()

    def test_modify_final_round_trips_applied_text(self) -> None:
        prepared = _select(
            self.connection, self.execution, self.run_id, self.execution_id,
            _MODIFY_REVISION, "final-modify",
        )
        self.assertIs(prepared.final.final_outcome, SubtitleFinalOutcome.FINAL)
        self.assertEqual(prepared.final.applied_text, "corrected line")
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            final = SQLiteSubtitleFinalSubtitleRepository(reopened).get(
                prepared.final.identity
            )
            self.assertEqual(final.applied_text, "corrected line")
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = _select(
            self.connection, self.execution, self.run_id, self.execution_id,
            _ACCEPT_REVISION, "final-accept",
        )
        self.connection.close()

        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id = _build_persisted_revisions(replay_connection)
            second = _select(
                replay_connection, execution, run_id, execution_id,
                _ACCEPT_REVISION, "final-accept",
            )
            self.assertEqual(first.final, second.final)
            self.assertEqual(first.final_result, second.final_result)
        finally:
            replay_connection.close()

    def test_repeated_selection_does_not_mutate_upstream_revision(self) -> None:
        revision_repo = SQLiteSubtitleDecisionRevisionRepository(self.connection)
        before = revision_repo.get(_ACCEPT_REVISION)
        _select(self.connection, self.execution, self.run_id, self.execution_id, _ACCEPT_REVISION, "f-a")
        _select(self.connection, self.execution, self.run_id, self.execution_id, _MODIFY_REVISION, "f-b")
        after = revision_repo.get(_ACCEPT_REVISION)
        self.assertEqual(before, after)
        count = self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_final_subtitles"
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_result_collision_rolls_back_final(self) -> None:
        service = compose_sqlite_subtitle_final_subtitle_service(
            self.connection, self.execution
        )
        prepared = service.select_final(
            source_decision_revision_id=_ACCEPT_REVISION,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=SubtitleFinalSubtitleIdentityPlan(
                final_id=SubtitleFinalSubtitleId("final-x"),
                # Reuse an existing DomainResult identity to force a collision.
                final_result_id=DomainResultId("revision-accept-result"),
            ),
        )
        persistence = SQLiteSubtitleFinalSubtitleCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_final_subtitle(
                final=prepared.final,
                final_result=prepared.final_result,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_final_subtitles"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
