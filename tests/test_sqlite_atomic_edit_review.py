import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application import (
    AnalysisFindingIdentityPlan,
    EditCandidateIdentityPlan,
    EditReviewIdentityPlan,
    LectureAnalysisInputIdentityPlan,
    NormalizedAnalysisFinding,
    NormalizedAnalysisResult,
    NormalizedCandidateResult,
    NormalizedEditCandidate,
    NormalizedModification,
)
from lectureos.application.identities import (
    AnalysisFindingId,
    ApprovedEditDecisionId,
    EditCandidateId,
    EditReviewDecisionId,
    EligibleAnalysisInputId,
    TranscriptReadinessEvaluationId,
)
from lectureos.composition import (
    compose_sqlite_analysis_finding_service,
    compose_sqlite_edit_candidate_service,
    compose_sqlite_edit_review_service,
    compose_sqlite_lecture_analysis_input_service,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteApprovedEditDecisionRepository,
    SQLiteDomainResultReferenceRepository,
    SQLiteEditCandidateRepository,
    SQLiteEditReviewCommandPersistence,
    SQLiteEditReviewDecisionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import SchemaFeatureUnavailableError
from lectureos.review.identities import HumanActorReference
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")
_INPUT = EligibleAnalysisInputId("review-input")
_FINDING = AnalysisFindingId("review-finding")
_CANDIDATE = EditCandidateId("review-candidate")
_ACTOR = HumanActorReference("reviewer:alice")


def _plan(name="d", *, approved=True):
    return EditReviewIdentityPlan(
        decision_id=EditReviewDecisionId(f"decision-{name}"),
        decision_result_id=DomainResultId(f"decision-{name}-result"),
        approved_id=ApprovedEditDecisionId(f"approved-{name}") if approved else None,
        approved_result_id=DomainResultId(f"approved-{name}-result") if approved else None,
    )


class SQLiteAtomicEditReviewTests(unittest.TestCase):
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
        self._seed_candidate()

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def _seed_candidate(self):
        input_service = compose_sqlite_lecture_analysis_input_service(
            self.connection, self.execution
        )
        input_service.record_input(
            source_readiness_id=_READY,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=LectureAnalysisInputIdentityPlan(
                input_id=_INPUT,
                input_result_id=DomainResultId("review-input-result"),
            ),
        )
        finding_service = compose_sqlite_analysis_finding_service(
            self.connection, self.execution
        )
        finding_service.record_findings(
            source_input_id=_INPUT,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=NormalizedAnalysisResult(
                source_timeline_id=SourceTimelineId(TIMELINE_ID),
                findings=(
                    NormalizedAnalysisFinding(
                        finding_type="low_educational_value",
                        evidence="an off-topic aside",
                    ),
                ),
            ),
            identities=(
                AnalysisFindingIdentityPlan(
                    finding_id=_FINDING,
                    finding_result_id=DomainResultId("review-finding-result"),
                ),
            ),
        )
        candidate_service = compose_sqlite_edit_candidate_service(
            self.connection, self.execution
        )
        candidate_service.record_candidates(
            source_finding_id=_FINDING,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=NormalizedCandidateResult(
                source_timeline_id=SourceTimelineId(TIMELINE_ID),
                candidates=(
                    NormalizedEditCandidate(
                        candidate_type="non_lecture_region",
                        rationale="propose review",
                        range_start=0.5,
                        range_end=1.5,
                    ),
                ),
            ),
            identities=(
                EditCandidateIdentityPlan(
                    candidate_id=_CANDIDATE,
                    candidate_result_id=DomainResultId("review-candidate-result"),
                ),
            ),
        )

    def _service(self):
        return compose_sqlite_edit_review_service(self.connection, self.execution)

    def _record(self, decision_kind, plan, modification=None):
        return self._service().record_decision(
            source_candidate_id=_CANDIDATE,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            decision_kind=decision_kind,
            actor=_ACTOR,
            identities=plan,
            modification=modification,
        )

    def test_accept_persists_decision_and_approved(self) -> None:
        prepared = self._record("accept", _plan("a"))
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            decisions = SQLiteEditReviewDecisionRepository(reopened)
            approvals = SQLiteApprovedEditDecisionRepository(reopened)
            results = SQLiteDomainResultReferenceRepository(reopened)
            self.assertEqual(decisions.get(prepared.decision.identity), prepared.decision)
            self.assertEqual(approvals.get(prepared.approved.identity), prepared.approved)
            self.assertEqual(
                approvals.get_for_decision(prepared.decision.identity), prepared.approved
            )
            self.assertEqual(
                results.get(prepared.decision_result.identity), prepared.decision_result
            )
            self.assertEqual(
                results.get(prepared.approved_result.identity), prepared.approved_result
            )
        finally:
            reopened.close()

    def test_reject_persists_only_decision(self) -> None:
        prepared = self._record("reject", _plan("r", approved=False))
        self.assertIsNone(prepared.approved)
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            decisions = SQLiteEditReviewDecisionRepository(reopened)
            approvals = SQLiteApprovedEditDecisionRepository(reopened)
            self.assertEqual(decisions.get(prepared.decision.identity), prepared.decision)
            self.assertIsNone(approvals.get_for_decision(prepared.decision.identity))
            self.assertEqual(
                reopened.execute("SELECT COUNT(*) FROM approved_edit_decisions").fetchone()[0], 0
            )
        finally:
            reopened.close()

    def test_recording_does_not_mutate_candidate(self) -> None:
        candidate_repo = SQLiteEditCandidateRepository(self.connection)
        before = candidate_repo.get(_CANDIDATE)
        self._record("modify", _plan("m"), NormalizedModification(
            approved_range_start=0.75, approved_range_end=1.25,
            approved_candidate_type="condense_repetition", approved_rationale="ok",
        ))
        self.assertEqual(candidate_repo.get(_CANDIDATE), before)

    def test_decision_identity_collision_rolls_back_all(self) -> None:
        self._record("accept", _plan("a"))
        service = self._service()
        # a fresh approved plan but a colliding decision identity -> nothing persists
        prepared = service.evaluate_decision(
            source_candidate_id=_CANDIDATE,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            decision_kind="accept",
            actor=_ACTOR,
            identities=EditReviewIdentityPlan(
                decision_id=EditReviewDecisionId("decision-a"),  # collides
                decision_result_id=DomainResultId("decision-a2-result"),
                approved_id=ApprovedEditDecisionId("approved-a2"),
                approved_result_id=DomainResultId("approved-a2-result"),
            ),
        )
        persistence = SQLiteEditReviewCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_edit_review(prepared=prepared)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM approved_edit_decisions WHERE identity = 'approved-a2'"
            ).fetchone()[0], 0
        )

    def test_approved_identity_collision_rolls_back_decision(self) -> None:
        self._record("accept", _plan("a"))
        service = self._service()
        prepared = service.evaluate_decision(
            source_candidate_id=_CANDIDATE,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            decision_kind="accept",
            actor=_ACTOR,
            identities=EditReviewIdentityPlan(
                decision_id=EditReviewDecisionId("decision-b"),
                decision_result_id=DomainResultId("decision-b-result"),
                approved_id=ApprovedEditDecisionId("approved-a"),  # collides
                approved_result_id=DomainResultId("approved-b-result"),
            ),
        )
        persistence = SQLiteEditReviewCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_edit_review(prepared=prepared)
        # the fresh decision must not remain
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM edit_review_decisions WHERE identity = 'decision-b'"
            ).fetchone()[0], 0
        )

    def test_result_collision_rolls_back(self) -> None:
        service = self._service()
        prepared = service.evaluate_decision(
            source_candidate_id=_CANDIDATE,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            decision_kind="accept",
            actor=_ACTOR,
            identities=EditReviewIdentityPlan(
                decision_id=EditReviewDecisionId("decision-x"),
                # reuse the candidate's DomainResult id to force a collision
                decision_result_id=DomainResultId("review-candidate-result"),
                approved_id=ApprovedEditDecisionId("approved-x"),
                approved_result_id=DomainResultId("approved-x-result"),
            ),
        )
        persistence = SQLiteEditReviewCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_edit_review(prepared=prepared)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM edit_review_decisions WHERE identity = 'decision-x'"
            ).fetchone()[0], 0
        )

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = self._record("accept", _plan("a"))
        self.connection.close()
        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id, _, _ = _build_persisted_readiness(replay)
            self.connection = replay  # reuse seeding helper on the replay connection
            self.execution, self.run_id, self.execution_id = execution, run_id, execution_id
            self._seed_candidate()
            second = compose_sqlite_edit_review_service(replay, execution).record_decision(
                source_candidate_id=_CANDIDATE,
                run_id=run_id,
                unit_execution_id=execution_id,
                decision_kind="accept",
                actor=_ACTOR,
                identities=_plan("a"),
            )
            self.assertEqual(first.decision, second.decision)
            self.assertEqual(first.approved, second.approved)
        finally:
            replay.close()

    def test_repository_rejects_pre_v27_schema(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 27):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 26)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEditReviewDecisionRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
