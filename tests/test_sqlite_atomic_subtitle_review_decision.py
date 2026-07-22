import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from lectureos.application import (
    SubtitleReviewDecisionIdentityPlan,
    SubtitleReviewPreparationIdentityPlan,
    SubtitleReviewTargetIdentityPlan,
    SubtitleTimingStatus,
    SubtitleValidationIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleValidationId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_review_decision_service,
    compose_sqlite_subtitle_review_preparation_service,
    compose_sqlite_subtitle_structural_validation_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteReviewItemRepository,
    SQLiteSubtitleReviewDecisionCommandPersistence,
    SQLiteSubtitleReviewDecisionRepository,
    SQLiteSubtitleReviewPreparationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.identities import (
    CandidateReferenceId,
    HumanActorReference,
    ReviewContextId,
    ReviewItemId,
)
from lectureos.review.models import DecisionKind
from lectureos.subtitle_reading_acceptance import (
    _build_persisted_candidate,
    _compose_reading,
)
from lectureos.subtitle_validation_acceptance import _persist_defective_time

WHEN = datetime(2026, 7, 22, 21, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 7, 22, 21, 5, tzinfo=timezone.utc)
_PREP_ID = SubtitleReviewPreparationId("prep-0")


def _prep_plan(count):
    return SubtitleReviewPreparationIdentityPlan(
        preparation_id=_PREP_ID,
        preparation_result_id=DomainResultId("prep-0-result"),
        context_id=ReviewContextId("prep-0-context"),
        targets=tuple(
            SubtitleReviewTargetIdentityPlan(
                candidate_reference_id=CandidateReferenceId(f"prep-0-ref-{i}"),
                review_item_id=ReviewItemId(f"prep-0-item-{i}"),
            )
            for i in range(count)
        ),
    )


def _build_persisted_preparation(connection):
    """candidate → reading → defective time → validation (with findings) → review preparation."""

    execution, run_id, execution_id, candidate = _build_persisted_candidate(connection)
    reading = _compose_reading(connection, execution, run_id, execution_id)
    units = reading.revision.unit_ids
    disorder_time_id = _persist_defective_time(
        connection,
        reading.revision,
        candidate,
        "time-disorder",
        [
            (units[0], SubtitleTimingStatus.ANCHORED, 5.0, 6.0),
            (units[1], SubtitleTimingStatus.ANCHORED, 0.0, 1.0),
        ],
    )
    validation = compose_sqlite_subtitle_structural_validation_service(
        connection, execution
    ).record_validation(
        source_time_revision_id=disorder_time_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=SubtitleValidationIdentityPlan(
            validation_id=SubtitleValidationId("validation-0"),
            validation_result_id=DomainResultId("validation-0-result"),
        ),
    )
    prep = compose_sqlite_subtitle_review_preparation_service(
        connection, execution
    ).generate_review(
        source_validation_id=SubtitleValidationId("validation-0"),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_prep_plan(len(validation.findings)),
    )
    return execution, run_id, execution_id, tuple(prep.review_items)


def _decision_plan(name, when=WHEN):
    return SubtitleReviewDecisionIdentityPlan(
        decision_id=SubtitleReviewDecisionId(name),
        decision_result_id=DomainResultId(f"{name}-result"),
        decided_at=when,
    )


def _record_decision(
    connection, execution, run_id, execution_id, item_id, name="decision-0",
    kind=DecisionKind.ACCEPT, **overrides,
):
    service = compose_sqlite_subtitle_review_decision_service(connection, execution)
    base = dict(
        preparation_id=_PREP_ID,
        review_item_id=item_id,
        reviewer=HumanActorReference("reviewer"),
        kind=kind,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_decision_plan(name),
    )
    base.update(overrides)
    return service.record_decision(**base)


class SQLiteAtomicSubtitleReviewDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.execution, self.run_id, self.execution_id, self.items = (
            _build_persisted_preparation(self.connection)
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_and_reconstructs_decision(self) -> None:
        prepared = _record_decision(
            self.connection, self.execution, self.run_id, self.execution_id,
            self.items[0].identity,
        )
        self.assertIs(prepared.decision.kind, DecisionKind.ACCEPT)
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            decision = SQLiteSubtitleReviewDecisionRepository(reopened).get(
                prepared.decision.identity
            )
            self.assertEqual(decision, prepared.decision)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.decision_result.identity
            )
            self.assertEqual(result, prepared.decision_result)
        finally:
            reopened.close()

    def test_modify_decision_round_trips(self) -> None:
        prepared = _record_decision(
            self.connection, self.execution, self.run_id, self.execution_id,
            self.items[0].identity, name="decision-modify",
            kind=DecisionKind.MODIFY, modified_text="corrected line",
        )
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            decision = SQLiteSubtitleReviewDecisionRepository(reopened).get(
                prepared.decision.identity
            )
            self.assertEqual(decision.modified_text, "corrected line")
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = _record_decision(
            self.connection, self.execution, self.run_id, self.execution_id,
            self.items[0].identity,
        )
        self.connection.close()

        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id, items = _build_persisted_preparation(
                replay_connection
            )
            second = _record_decision(
                replay_connection, execution, run_id, execution_id, items[0].identity
            )
            self.assertEqual(first.decision, second.decision)
            self.assertEqual(first.decision_result, second.decision_result)
        finally:
            replay_connection.close()

    def test_repeated_recording_does_not_mutate_upstream(self) -> None:
        prep_repo = SQLiteSubtitleReviewPreparationRepository(self.connection)
        item_repo = SQLiteReviewItemRepository(self.connection)
        prep_before = prep_repo.get(_PREP_ID)
        item_before = item_repo.get(self.items[0].identity)
        _record_decision(
            self.connection, self.execution, self.run_id, self.execution_id,
            self.items[0].identity, "d-a",
        )
        _record_decision(
            self.connection, self.execution, self.run_id, self.execution_id,
            self.items[1].identity, "d-b",
        )
        self.assertEqual(prep_repo.get(_PREP_ID), prep_before)
        self.assertEqual(item_repo.get(self.items[0].identity), item_before)
        count = self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_review_decisions"
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_result_collision_rolls_back_decision(self) -> None:
        service = compose_sqlite_subtitle_review_decision_service(
            self.connection, self.execution
        )
        prepared = service.prepare_decision(
            preparation_id=_PREP_ID,
            review_item_id=self.items[0].identity,
            reviewer=HumanActorReference("reviewer"),
            kind=DecisionKind.ACCEPT,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=SubtitleReviewDecisionIdentityPlan(
                decision_id=SubtitleReviewDecisionId("decision-x"),
                # Reuse an existing DomainResult identity to force a collision.
                decision_result_id=DomainResultId("prep-0-result"),
                decided_at=WHEN,
            ),
        )
        persistence = SQLiteSubtitleReviewDecisionCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_review_decision(
                decision=prepared.decision,
                decision_result=prepared.decision_result,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_review_decisions"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
