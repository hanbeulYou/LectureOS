import tempfile
import unittest
from pathlib import Path

from lectureos.application import LectureAnalysisEligibility
from lectureos.application.identities import EligibleAnalysisInputId
from lectureos.composition import compose_sqlite_lecture_analysis_input_service
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteEligibleAnalysisInputCommandPersistence,
    SQLiteEligibleAnalysisInputRepository,
    SQLiteTranscriptReadinessEvaluationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)

from lectureos.application import LectureAnalysisInputIdentityPlan
from lectureos.application.identities import TranscriptReadinessEvaluationId
from lectureos.subtitle_intake_acceptance import _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")


def _plan(name="input"):
    return LectureAnalysisInputIdentityPlan(
        input_id=EligibleAnalysisInputId(name),
        input_result_id=DomainResultId(f"{name}-result"),
    )


class SQLiteAtomicLectureAnalysisInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        (
            self.execution,
            self.run_id,
            self.execution_id,
            _revision,
            _raw,
        ) = _build_persisted_readiness(self.connection)

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def _record(self, name="input"):
        service = compose_sqlite_lecture_analysis_input_service(
            self.connection, self.execution
        )
        return service.record_input(
            source_readiness_id=_READY,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=_plan(name),
        )

    def test_persists_and_reconstructs_eligible_input(self) -> None:
        prepared = self._record()
        self.assertIs(
            prepared.eligible_input.eligibility, LectureAnalysisEligibility.ELIGIBLE
        )
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteEligibleAnalysisInputRepository(reopened)
            self.assertEqual(
                repo.get(prepared.eligible_input.identity), prepared.eligible_input
            )
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.input_result.identity
            )
            self.assertEqual(result, prepared.input_result)
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = self._record()
        self.connection.close()
        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id, _, _ = _build_persisted_readiness(
                replay_connection
            )
            service = compose_sqlite_lecture_analysis_input_service(
                replay_connection, execution
            )
            second = service.record_input(
                source_readiness_id=_READY,
                run_id=run_id,
                unit_execution_id=execution_id,
                identities=_plan(),
            )
            self.assertEqual(first.eligible_input, second.eligible_input)
            self.assertEqual(first.input_result, second.input_result)
        finally:
            replay_connection.close()

    def test_repeated_recording_does_not_mutate_upstream_readiness(self) -> None:
        readiness_repo = SQLiteTranscriptReadinessEvaluationRepository(self.connection)
        before = readiness_repo.get(_READY)
        self._record("input-a")
        self._record("input-b")
        after = readiness_repo.get(_READY)
        self.assertEqual(before, after)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM eligible_analysis_inputs"
            ).fetchone()[0],
            2,
        )

    def test_result_collision_rolls_back_input(self) -> None:
        service = compose_sqlite_lecture_analysis_input_service(
            self.connection, self.execution
        )
        prepared = service.evaluate_input(
            source_readiness_id=_READY,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=LectureAnalysisInputIdentityPlan(
                input_id=EligibleAnalysisInputId("input-x"),
                # reuse the READY readiness's DomainResult id to force a collision
                input_result_id=DomainResultId("rdy-int-accept-result"),
            ),
        )
        persistence = SQLiteEligibleAnalysisInputCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_eligible_analysis_input(
                eligible_input=prepared.eligible_input,
                input_result=prepared.input_result,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM eligible_analysis_inputs WHERE identity = 'input-x'"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
