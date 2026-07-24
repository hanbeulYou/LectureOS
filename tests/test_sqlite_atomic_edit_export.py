import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application import (
    AnalysisFindingIdentityPlan,
    ApprovedEditExportIdentityPlan,
    EditCandidateIdentityPlan,
    EditReviewIdentityPlan,
    LectureAnalysisInputIdentityPlan,
    NormalizedAnalysisFinding,
    NormalizedAnalysisResult,
    NormalizedCandidateResult,
    NormalizedEditCandidate,
)
from lectureos.application.identities import (
    AnalysisFindingId,
    ApprovedEditDecisionId,
    ApprovedEditExportRepresentationId,
    EditCandidateId,
    EditReviewDecisionId,
    EligibleAnalysisInputId,
    TranscriptReadinessEvaluationId,
)
from lectureos.composition import (
    compose_sqlite_analysis_finding_service,
    compose_sqlite_edit_candidate_service,
    compose_sqlite_edit_export_service,
    compose_sqlite_edit_review_service,
    compose_sqlite_lecture_analysis_input_service,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteApprovedEditDecisionRepository,
    SQLiteApprovedEditExportCommandPersistence,
    SQLiteApprovedEditExportRepresentationRepository,
    SQLiteDomainResultReferenceRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import SchemaFeatureUnavailableError
from lectureos.review.identities import HumanActorReference
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")
_INPUT = EligibleAnalysisInputId("export-input")
_FINDING = AnalysisFindingId("export-finding")
_CANDIDATE = EditCandidateId("export-candidate")
_APPROVED = ApprovedEditDecisionId("export-approved")
_ACTOR = HumanActorReference("reviewer:alice")


def _plan(name):
    return ApprovedEditExportIdentityPlan(
        representation_id=ApprovedEditExportRepresentationId(name),
        representation_result_id=DomainResultId(f"{name}-result"),
    )


class SQLiteAtomicEditExportTests(unittest.TestCase):
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
        self._seed_approved(self.connection, self.execution, self.run_id, self.execution_id)

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def _seed_approved(self, connection, execution, run_id, execution_id):
        compose_sqlite_lecture_analysis_input_service(connection, execution).record_input(
            source_readiness_id=_READY,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=LectureAnalysisInputIdentityPlan(
                input_id=_INPUT, input_result_id=DomainResultId("export-input-result")
            ),
        )
        compose_sqlite_analysis_finding_service(connection, execution).record_findings(
            source_input_id=_INPUT,
            run_id=run_id,
            unit_execution_id=execution_id,
            result=NormalizedAnalysisResult(
                source_timeline_id=SourceTimelineId(TIMELINE_ID),
                findings=(NormalizedAnalysisFinding(finding_type="low_educational_value", evidence="aside"),),
            ),
            identities=(
                AnalysisFindingIdentityPlan(
                    finding_id=_FINDING, finding_result_id=DomainResultId("export-finding-result")
                ),
            ),
        )
        compose_sqlite_edit_candidate_service(connection, execution).record_candidates(
            source_finding_id=_FINDING,
            run_id=run_id,
            unit_execution_id=execution_id,
            result=NormalizedCandidateResult(
                source_timeline_id=SourceTimelineId(TIMELINE_ID),
                candidates=(
                    NormalizedEditCandidate(
                        candidate_type="non_lecture_region", rationale="propose review",
                        range_start=0.5, range_end=1.5,
                    ),
                ),
            ),
            identities=(
                EditCandidateIdentityPlan(
                    candidate_id=_CANDIDATE, candidate_result_id=DomainResultId("export-candidate-result")
                ),
            ),
        )
        compose_sqlite_edit_review_service(connection, execution).record_decision(
            source_candidate_id=_CANDIDATE,
            run_id=run_id,
            unit_execution_id=execution_id,
            decision_kind="accept",
            actor=_ACTOR,
            identities=EditReviewIdentityPlan(
                decision_id=EditReviewDecisionId("export-review"),
                decision_result_id=DomainResultId("export-review-result"),
                approved_id=_APPROVED,
                approved_result_id=DomainResultId("export-approved-result"),
            ),
        )

    def _service(self):
        return compose_sqlite_edit_export_service(self.connection, self.execution)

    def _record(self, plan):
        return self._service().record_representation(
            source_approved_decision_id=_APPROVED,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=plan,
        )

    def test_persists_and_reconstructs(self) -> None:
        prepared = self._record(_plan("rep-a"))
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteApprovedEditExportRepresentationRepository(reopened)
            results = SQLiteDomainResultReferenceRepository(reopened)
            self.assertEqual(repo.get(prepared.representation.identity), prepared.representation)
            self.assertEqual(
                results.get(prepared.representation_result.identity), prepared.representation_result
            )
            self.assertEqual(
                prepared.representation_result.upstream_results,
                (DomainResultId("export-approved-result"),),
            )
        finally:
            reopened.close()

    def test_multiple_representations_for_one_decision(self) -> None:
        self._record(_plan("rep-a"))
        self._record(_plan("rep-b"))
        repo = SQLiteApprovedEditExportRepresentationRepository(self.connection)
        self.assertEqual(repo.count_for_approved_decision(_APPROVED), 2)

    def test_recording_does_not_mutate_approved_decision(self) -> None:
        approved_repo = SQLiteApprovedEditDecisionRepository(self.connection)
        before = approved_repo.get(_APPROVED)
        self._record(_plan("rep-a"))
        self.assertEqual(approved_repo.get(_APPROVED), before)

    def test_identity_collision_rolls_back(self) -> None:
        self._record(_plan("rep-a"))
        service = self._service()
        prepared = service.evaluate_representation(
            source_approved_decision_id=_APPROVED,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=ApprovedEditExportIdentityPlan(
                representation_id=ApprovedEditExportRepresentationId("rep-a"),  # collides
                representation_result_id=DomainResultId("rep-a2-result"),
            ),
        )
        persistence = SQLiteApprovedEditExportCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_export_representation(prepared=prepared)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM domain_result_references WHERE identity = 'rep-a2-result'"
            ).fetchone()[0], 0
        )

    def test_result_collision_rolls_back(self) -> None:
        service = self._service()
        prepared = service.evaluate_representation(
            source_approved_decision_id=_APPROVED,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=ApprovedEditExportIdentityPlan(
                representation_id=ApprovedEditExportRepresentationId("rep-x"),
                # reuse the approved decision's DomainResult id to force a collision
                representation_result_id=DomainResultId("export-approved-result"),
            ),
        )
        persistence = SQLiteApprovedEditExportCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_export_representation(prepared=prepared)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM approved_edit_export_representations WHERE identity = 'rep-x'"
            ).fetchone()[0], 0
        )

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = self._record(_plan("rep-a"))
        self.connection.close()
        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id, _, _ = _build_persisted_readiness(replay)
            self.connection, self.execution, self.run_id, self.execution_id = (
                replay, execution, run_id, execution_id,
            )
            self._seed_approved(replay, execution, run_id, execution_id)
            second = compose_sqlite_edit_export_service(replay, execution).record_representation(
                source_approved_decision_id=_APPROVED,
                run_id=run_id,
                unit_execution_id=execution_id,
                identities=_plan("rep-a"),
            )
            self.assertEqual(first.representation, second.representation)
        finally:
            replay.close()

    def test_repository_rejects_pre_v28_schema(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 29):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 27)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteApprovedEditExportRepresentationRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
