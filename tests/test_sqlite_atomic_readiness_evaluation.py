import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from lectureos.application import (
    ApplicabilityEvaluationIdentityPlan,
    CurrentSelectionIdentityPlan,
    ReadinessEvaluationIdentityPlan,
    ReadinessOutcome,
    ReviewDecisionIdentityPlan,
    ReviewPreparationIdentityPlan,
    ReviewPreparationTargetIdentityPlan,
)
from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
    TranscriptReviewPreparationId,
)
from lectureos.composition import (
    compose_sqlite_execution_service,
    compose_sqlite_transcript_applicability_evaluation_service,
    compose_sqlite_transcript_current_selection_service,
    compose_sqlite_transcript_readiness_evaluation_service,
    compose_sqlite_transcript_review_decision_service,
    compose_sqlite_transcript_review_preparation_service,
    compose_sqlite_transcript_service,
)
from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    ProcessingUnitId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import ExecutionIntent, ProcessingUnit
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteReadinessEvaluationCommandPersistence,
    SQLiteTranscriptCurrentSelectionRepository,
    SQLiteTranscriptReadinessEvaluationRepository,
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
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import (
    CorrectedTranscriptRevision,
    CorrectionCandidate,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)

WHEN = datetime(2026, 7, 22, 19, 0, tzinfo=timezone.utc)


def _build_persisted_selection(connection):
    run_id = ProcessingRunId("run")
    execution_id = UnitExecutionId("execution")
    media_id = SourceMediaId("media")
    timeline_id = SourceTimelineId("timeline")
    capability = CapabilityReference("transcript.correction")
    execution = compose_sqlite_execution_service(connection)
    unit_id = ProcessingUnitId("unit")
    execution.register_unit(
        ProcessingUnit(identity=unit_id, purpose="ready", capabilities=(capability,))
    )
    execution.start_run(
        run_id=run_id,
        intent=ExecutionIntent("ready"),
        working_context=WorkingContextReference("context"),
        unit_ids=(unit_id,),
    )
    execution.start_unit_execution(
        execution_id=execution_id, run_id=run_id, unit_id=unit_id
    )
    transcripts = compose_sqlite_transcript_service(connection, execution)
    provider = ProviderTranscriptResult(
        identity=ProviderTranscriptResultId("provider"),
        source_media_id=media_id,
        source_timeline_id=timeline_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        capability=CapabilityReference("speech.transcription"),
        provider_reference="provider:model",
        original_content="source",
    )
    raw = RawTranscript(
        identity=TranscriptId("raw"),
        domain_result_id=DomainResultId("raw-result"),
        source_media_id=media_id,
        source_timeline_id=timeline_id,
        provider_result_id=provider.identity,
        run_id=run_id,
        unit_execution_id=execution_id,
        segment_ids=(TranscriptSegmentId("segment-0"),),
    )
    segment = TranscriptSegment(
        identity=raw.segment_ids[0],
        transcript_id=raw.identity,
        source_timeline_id=timeline_id,
        text="one",
        source_order=0,
        start=0.0,
        end=1.0,
    )
    transcripts.register_provider_result(provider)
    transcripts.create_raw_transcript(raw, (segment,))
    transcripts.create_correction_candidate(
        CorrectionCandidate(
            identity=CorrectionCandidateId("candidate-0"),
            domain_result_id=DomainResultId("candidate-result-0"),
            transcript_id=raw.identity,
            segment_id=segment.identity,
            proposed_text="corrected",
            rationale="recognition",
            run_id=run_id,
            unit_execution_id=execution_id,
        )
    )
    revision = CorrectedTranscriptRevision(
        identity=TranscriptRevisionId("revision"),
        transcript_id=raw.identity,
        domain_result_id=DomainResultId("revision-result"),
        run_id=run_id,
        unit_execution_id=execution_id,
        segment_ids=raw.segment_ids,
        parent_raw_transcript_id=raw.identity,
        correction_candidate_ids=(CorrectionCandidateId("candidate-0"),),
    )
    transcripts.create_corrected_revision(revision, (segment,))
    preparation_service = compose_sqlite_transcript_review_preparation_service(
        connection, execution
    )
    preparation_service.generate_review(
        revision_id=revision.identity,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=ReviewPreparationIdentityPlan(
            preparation_id=TranscriptReviewPreparationId("prep"),
            preparation_result_id=DomainResultId("prep-result"),
            context_id=ReviewContextId("context"),
            targets=(
                ReviewPreparationTargetIdentityPlan(
                    candidate_reference_id=CandidateReferenceId("candidate-0"),
                    review_item_id=ReviewItemId("item-0"),
                ),
            ),
        ),
    )
    decision_service = compose_sqlite_transcript_review_decision_service(
        connection, execution
    )
    decision_service.record_decision(
        preparation_id=TranscriptReviewPreparationId("prep"),
        review_item_id=ReviewItemId("item-0"),
        reviewer=HumanActorReference("reviewer"),
        kind=DecisionKind.ACCEPT,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=ReviewDecisionIdentityPlan(
            decision_id=TranscriptReviewDecisionId("decision-0"),
            decision_result_id=DomainResultId("decision-result-0"),
            decided_at=WHEN,
        ),
    )
    applicability_service = compose_sqlite_transcript_applicability_evaluation_service(
        connection, execution
    )
    applicability_service.record_evaluation(
        source_decision_id=TranscriptReviewDecisionId("decision-0"),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=ApplicabilityEvaluationIdentityPlan(
            evaluation_id=TranscriptApplicabilityEvaluationId("evaluation-0"),
            evaluation_result_id=DomainResultId("evaluation-result-0"),
        ),
    )
    selection_service = compose_sqlite_transcript_current_selection_service(
        connection, execution
    )
    selection_service.record_selection(
        source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation-0"),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=CurrentSelectionIdentityPlan(
            selection_id=TranscriptCurrentSelectionId("selection-0"),
            selection_result_id=DomainResultId("selection-result-0"),
        ),
    )
    return execution, run_id, execution_id


def _readiness_plan(name="readiness-0") -> ReadinessEvaluationIdentityPlan:
    from lectureos.transcript.identities import TranscriptValidationId

    return ReadinessEvaluationIdentityPlan(
        readiness_id=TranscriptReadinessEvaluationId(name),
        readiness_result_id=DomainResultId(f"{name}-result"),
        validation_id=TranscriptValidationId(f"{name}-validation"),
    )


def _record_readiness(connection, execution, run_id, execution_id, name="readiness-0"):
    service = compose_sqlite_transcript_readiness_evaluation_service(connection, execution)
    return service.record_readiness(
        source_selection_id=TranscriptCurrentSelectionId("selection-0"),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_readiness_plan(name),
    )


class SQLiteAtomicReadinessEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.execution, self.run_id, self.execution_id = _build_persisted_selection(
            self.connection
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_and_reconstructs_after_restart(self) -> None:
        prepared = _record_readiness(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.assertIs(prepared.readiness.outcome, ReadinessOutcome.READY)
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            readiness = SQLiteTranscriptReadinessEvaluationRepository(reopened).get(
                prepared.readiness.identity
            )
            self.assertEqual(readiness, prepared.readiness)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.readiness_result.identity
            )
            self.assertEqual(result, prepared.readiness_result)
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = _record_readiness(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.connection.close()

        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id = _build_persisted_selection(
                replay_connection
            )
            second = _record_readiness(replay_connection, execution, run_id, execution_id)
            self.assertEqual(first.readiness, second.readiness)
            self.assertEqual(first.readiness_result, second.readiness_result)
            replayed = SQLiteTranscriptReadinessEvaluationRepository(
                replay_connection
            ).get(first.readiness.identity)
            self.assertEqual(replayed, first.readiness)
        finally:
            replay_connection.close()

    def test_repeated_evaluation_does_not_mutate_upstream_selection(self) -> None:
        selection_repo = SQLiteTranscriptCurrentSelectionRepository(self.connection)
        before = selection_repo.get(TranscriptCurrentSelectionId("selection-0"))
        _record_readiness(
            self.connection, self.execution, self.run_id, self.execution_id, "r-a"
        )
        _record_readiness(
            self.connection, self.execution, self.run_id, self.execution_id, "r-b"
        )
        after = selection_repo.get(TranscriptCurrentSelectionId("selection-0"))
        self.assertEqual(before, after)
        readiness_count = self.connection.execute(
            "SELECT COUNT(*) FROM transcript_readiness_evaluations"
        ).fetchone()[0]
        self.assertEqual(readiness_count, 2)

    def test_repeated_persist_is_rejected_and_atomic(self) -> None:
        prepared = _record_readiness(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        persistence = SQLiteReadinessEvaluationCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_readiness_evaluation(
                readiness=prepared.readiness,
                readiness_result=prepared.readiness_result,
            )
        count = self.connection.execute(
            "SELECT COUNT(*) FROM transcript_readiness_evaluations"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_result_collision_rolls_back_readiness(self) -> None:
        service = compose_sqlite_transcript_readiness_evaluation_service(
            self.connection, self.execution
        )
        from lectureos.transcript.identities import TranscriptValidationId

        prepared = service.evaluate_readiness(
            source_selection_id=TranscriptCurrentSelectionId("selection-0"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=ReadinessEvaluationIdentityPlan(
                readiness_id=TranscriptReadinessEvaluationId("readiness-x"),
                # Reuse an existing DomainResult identity to force a collision.
                readiness_result_id=DomainResultId("selection-result-0"),
                validation_id=TranscriptValidationId("readiness-x-validation"),
            ),
        )
        persistence = SQLiteReadinessEvaluationCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_readiness_evaluation(
                readiness=prepared.readiness,
                readiness_result=prepared.readiness_result,
            )
        count = self.connection.execute(
            "SELECT COUNT(*) FROM transcript_readiness_evaluations"
        ).fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
