import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application import (
    AnalysisFindingIdentityPlan,
    LectureAnalysisInputIdentityPlan,
    NormalizedAnalysisFinding,
    NormalizedAnalysisResult,
)
from lectureos.application.identities import (
    AnalysisFindingId,
    EligibleAnalysisInputId,
    TranscriptReadinessEvaluationId,
)
from lectureos.composition import (
    compose_sqlite_analysis_finding_service,
    compose_sqlite_lecture_analysis_input_service,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteAnalysisFindingCommandPersistence,
    SQLiteAnalysisFindingRepository,
    SQLiteDomainResultReferenceRepository,
    SQLiteEligibleAnalysisInputRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import SchemaFeatureUnavailableError
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")
_INPUT = EligibleAnalysisInputId("analysis-input")


def _result(*findings):
    return NormalizedAnalysisResult(
        source_timeline_id=SourceTimelineId(TIMELINE_ID), findings=findings
    )


def _finding(finding_type="terminology_drift", **overrides):
    base = dict(finding_type=finding_type, evidence="evidence rationale")
    base.update(overrides)
    return NormalizedAnalysisFinding(**base)


def _finding_plans(*names):
    return tuple(
        AnalysisFindingIdentityPlan(
            finding_id=AnalysisFindingId(name),
            finding_result_id=DomainResultId(f"{name}-result"),
        )
        for name in names
    )


class SQLiteAtomicAnalysisFindingTests(unittest.TestCase):
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
        input_service = compose_sqlite_lecture_analysis_input_service(
            self.connection, self.execution
        )
        input_service.record_input(
            source_readiness_id=_READY,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=LectureAnalysisInputIdentityPlan(
                input_id=_INPUT,
                input_result_id=DomainResultId("analysis-input-result"),
            ),
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def _record(self, result, plans):
        service = compose_sqlite_analysis_finding_service(self.connection, self.execution)
        return service.record_findings(
            source_input_id=_INPUT,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=result,
            identities=plans,
        )

    def test_persists_and_reconstructs_findings(self) -> None:
        prepared = self._record(
            _result(_finding("terminology_drift"), _finding("missing_definition")),
            _finding_plans("finding-0", "finding-1"),
        )
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteAnalysisFindingRepository(reopened)
            results = SQLiteDomainResultReferenceRepository(reopened)
            for item in prepared.findings:
                self.assertEqual(repo.get(item.finding.identity), item.finding)
                self.assertEqual(
                    results.get(item.finding_result.identity), item.finding_result
                )
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = self._record(_result(_finding()), _finding_plans("finding-0"))
        self.connection.close()
        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id, _, _ = _build_persisted_readiness(
                replay_connection
            )
            input_service = compose_sqlite_lecture_analysis_input_service(
                replay_connection, execution
            )
            input_service.record_input(
                source_readiness_id=_READY,
                run_id=run_id,
                unit_execution_id=execution_id,
                identities=LectureAnalysisInputIdentityPlan(
                    input_id=_INPUT,
                    input_result_id=DomainResultId("analysis-input-result"),
                ),
            )
            service = compose_sqlite_analysis_finding_service(replay_connection, execution)
            second = service.record_findings(
                source_input_id=_INPUT,
                run_id=run_id,
                unit_execution_id=execution_id,
                result=_result(_finding()),
                identities=_finding_plans("finding-0"),
            )
            self.assertEqual(first.findings[0].finding, second.findings[0].finding)
            self.assertEqual(
                first.findings[0].finding_result, second.findings[0].finding_result
            )
        finally:
            replay_connection.close()

    def test_recording_does_not_mutate_upstream_input(self) -> None:
        input_repo = SQLiteEligibleAnalysisInputRepository(self.connection)
        before = input_repo.get(_INPUT)
        self._record(_result(_finding()), _finding_plans("finding-0"))
        self.assertEqual(input_repo.get(_INPUT), before)

    def test_identity_collision_rolls_back_all_findings(self) -> None:
        self._record(_result(_finding()), _finding_plans("finding-0"))
        # A second admission whose first finding is fresh but second collides must persist neither.
        service = compose_sqlite_analysis_finding_service(self.connection, self.execution)
        prepared = service.evaluate_findings(
            source_input_id=_INPUT,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=_result(_finding("a"), _finding("b")),
            identities=_finding_plans("finding-1", "finding-0"),
        )
        persistence = SQLiteAnalysisFindingCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_analysis_findings(prepared=prepared.findings)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM analysis_findings WHERE identity = 'finding-1'"
            ).fetchone()[0],
            0,
        )

    def test_result_collision_rolls_back_finding(self) -> None:
        service = compose_sqlite_analysis_finding_service(self.connection, self.execution)
        prepared = service.evaluate_findings(
            source_input_id=_INPUT,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=_result(_finding()),
            identities=(
                AnalysisFindingIdentityPlan(
                    finding_id=AnalysisFindingId("finding-x"),
                    # reuse the eligible input's DomainResult id to force a collision
                    finding_result_id=DomainResultId("analysis-input-result"),
                ),
            ),
        )
        persistence = SQLiteAnalysisFindingCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_analysis_findings(prepared=prepared.findings)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM analysis_findings WHERE identity = 'finding-x'"
            ).fetchone()[0],
            0,
        )

    def test_repository_rejects_pre_v24_schema(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 24):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 23)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteAnalysisFindingRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
