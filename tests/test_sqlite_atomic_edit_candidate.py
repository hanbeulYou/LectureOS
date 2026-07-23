import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application import (
    AnalysisFindingIdentityPlan,
    EditCandidateIdentityPlan,
    LectureAnalysisInputIdentityPlan,
    NormalizedAnalysisFinding,
    NormalizedAnalysisResult,
    NormalizedCandidateResult,
    NormalizedEditCandidate,
)
from lectureos.application.identities import (
    AnalysisFindingId,
    EditCandidateId,
    EligibleAnalysisInputId,
    TranscriptReadinessEvaluationId,
)
from lectureos.composition import (
    compose_sqlite_analysis_finding_service,
    compose_sqlite_edit_candidate_service,
    compose_sqlite_lecture_analysis_input_service,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteAnalysisFindingRepository,
    SQLiteDomainResultReferenceRepository,
    SQLiteEditCandidateCommandPersistence,
    SQLiteEditCandidateRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import SchemaFeatureUnavailableError
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")
_INPUT = EligibleAnalysisInputId("candidate-input")
_FINDING = AnalysisFindingId("candidate-finding")


def _result(*candidates):
    return NormalizedCandidateResult(
        source_timeline_id=SourceTimelineId(TIMELINE_ID), candidates=candidates
    )


def _candidate(candidate_type="review", start=0.0, end=5.0):
    return NormalizedEditCandidate(
        candidate_type=candidate_type,
        rationale="propose review of a possible non-lecture region",
        range_start=start,
        range_end=end,
    )


def _candidate_plans(*names):
    return tuple(
        EditCandidateIdentityPlan(
            candidate_id=EditCandidateId(name),
            candidate_result_id=DomainResultId(f"{name}-result"),
        )
        for name in names
    )


class SQLiteAtomicEditCandidateTests(unittest.TestCase):
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
        self._seed_finding(self.connection, self.execution, self.run_id, self.execution_id)

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def _seed_finding(self, connection, execution, run_id, execution_id):
        input_service = compose_sqlite_lecture_analysis_input_service(connection, execution)
        input_service.record_input(
            source_readiness_id=_READY,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=LectureAnalysisInputIdentityPlan(
                input_id=_INPUT,
                input_result_id=DomainResultId("candidate-input-result"),
            ),
        )
        finding_service = compose_sqlite_analysis_finding_service(connection, execution)
        finding_service.record_findings(
            source_input_id=_INPUT,
            run_id=run_id,
            unit_execution_id=execution_id,
            result=NormalizedAnalysisResult(
                source_timeline_id=SourceTimelineId(TIMELINE_ID),
                findings=(
                    NormalizedAnalysisFinding(
                        finding_type="low_educational_value",
                        evidence="an off-topic aside appears mid-lecture",
                    ),
                ),
            ),
            identities=(
                AnalysisFindingIdentityPlan(
                    finding_id=_FINDING,
                    finding_result_id=DomainResultId("candidate-finding-result"),
                ),
            ),
        )

    def _record(self, result, plans):
        service = compose_sqlite_edit_candidate_service(self.connection, self.execution)
        return service.record_candidates(
            source_finding_id=_FINDING,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=result,
            identities=plans,
        )

    def test_persists_and_reconstructs_candidates(self) -> None:
        prepared = self._record(
            _result(_candidate("review", 0.0, 10.0), _candidate("condense", 10.0, 20.0)),
            _candidate_plans("candidate-0", "candidate-1"),
        )
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteEditCandidateRepository(reopened)
            results = SQLiteDomainResultReferenceRepository(reopened)
            for item in prepared.candidates:
                self.assertEqual(repo.get(item.candidate.identity), item.candidate)
                self.assertEqual(
                    results.get(item.candidate_result.identity), item.candidate_result
                )
                # sole direct upstream is the Finding DomainResult
                self.assertEqual(
                    item.candidate_result.upstream_results,
                    (DomainResultId("candidate-finding-result"),),
                )
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = self._record(_result(_candidate()), _candidate_plans("candidate-0"))
        self.connection.close()
        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id, _, _ = _build_persisted_readiness(
                replay_connection
            )
            self._seed_finding(replay_connection, execution, run_id, execution_id)
            service = compose_sqlite_edit_candidate_service(replay_connection, execution)
            second = service.record_candidates(
                source_finding_id=_FINDING,
                run_id=run_id,
                unit_execution_id=execution_id,
                result=_result(_candidate()),
                identities=_candidate_plans("candidate-0"),
            )
            self.assertEqual(first.candidates[0].candidate, second.candidates[0].candidate)
            self.assertEqual(
                first.candidates[0].candidate_result,
                second.candidates[0].candidate_result,
            )
        finally:
            replay_connection.close()

    def test_recording_does_not_mutate_upstream_finding(self) -> None:
        finding_repo = SQLiteAnalysisFindingRepository(self.connection)
        before = finding_repo.get(_FINDING)
        self._record(_result(_candidate()), _candidate_plans("candidate-0"))
        self.assertEqual(finding_repo.get(_FINDING), before)

    def test_identity_collision_rolls_back_all_candidates(self) -> None:
        self._record(_result(_candidate()), _candidate_plans("candidate-0"))
        service = compose_sqlite_edit_candidate_service(self.connection, self.execution)
        # first candidate fresh, second collides -> neither must persist
        prepared = service.evaluate_candidates(
            source_finding_id=_FINDING,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=_result(_candidate("review", 0.0, 1.0), _candidate("condense", 1.0, 2.0)),
            identities=_candidate_plans("candidate-1", "candidate-0"),
        )
        persistence = SQLiteEditCandidateCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_edit_candidates(prepared=prepared.candidates)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM edit_candidates WHERE identity = 'candidate-1'"
            ).fetchone()[0],
            0,
        )

    def test_result_collision_rolls_back_candidate(self) -> None:
        service = compose_sqlite_edit_candidate_service(self.connection, self.execution)
        prepared = service.evaluate_candidates(
            source_finding_id=_FINDING,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=_result(_candidate()),
            identities=(
                EditCandidateIdentityPlan(
                    candidate_id=EditCandidateId("candidate-x"),
                    # reuse the Finding's DomainResult id to force a collision
                    candidate_result_id=DomainResultId("candidate-finding-result"),
                ),
            ),
        )
        persistence = SQLiteEditCandidateCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_edit_candidates(prepared=prepared.candidates)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM edit_candidates WHERE identity = 'candidate-x'"
            ).fetchone()[0],
            0,
        )

    def test_repository_rejects_pre_v26_schema(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 26):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 25)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEditCandidateRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
