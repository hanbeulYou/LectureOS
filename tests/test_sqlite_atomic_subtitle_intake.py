import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from lectureos.application import (
    ApplicabilityEvaluationIdentityPlan,
    CurrentSelectionIdentityPlan,
    ReadinessEvaluationIdentityPlan,
    ReviewDecisionIdentityPlan,
    ReviewPreparationIdentityPlan,
    ReviewPreparationTargetIdentityPlan,
    SubtitleIntakeIdentityPlan,
    SubtitleIntakeOutcome,
)
from lectureos.application.identities import (
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
    TranscriptReviewPreparationId,
)
from lectureos.composition import (
    compose_sqlite_execution_service,
    compose_sqlite_subtitle_transcript_intake_service,
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
    SQLiteSubtitleIntakeCommandPersistence,
    SQLiteTranscriptReadinessEvaluationRepository,
    SQLiteSubtitleTranscriptIntakeRepository,
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
    TranscriptValidationId,
)
from lectureos.transcript.models import (
    CorrectedTranscriptRevision,
    CorrectionCandidate,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)

WHEN = datetime(2026, 7, 22, 21, 0, tzinfo=timezone.utc)


def _build_persisted_readiness(connection):
    run_id = ProcessingRunId("run")
    execution_id = UnitExecutionId("execution")
    media_id = SourceMediaId("media")
    timeline_id = SourceTimelineId("timeline")
    capability = CapabilityReference("transcript.correction")
    execution = compose_sqlite_execution_service(connection)
    unit_id = ProcessingUnitId("unit")
    execution.register_unit(
        ProcessingUnit(identity=unit_id, purpose="intake", capabilities=(capability,))
    )
    execution.start_run(
        run_id=run_id,
        intent=ExecutionIntent("intake"),
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
    preparation = compose_sqlite_transcript_review_preparation_service(connection, execution)
    preparation.generate_review(
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
    decisions = compose_sqlite_transcript_review_decision_service(connection, execution)
    decisions.record_decision(
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
    applicability = compose_sqlite_transcript_applicability_evaluation_service(
        connection, execution
    )
    applicability.record_evaluation(
        source_decision_id=TranscriptReviewDecisionId("decision-0"),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=ApplicabilityEvaluationIdentityPlan(
            evaluation_id=TranscriptApplicabilityEvaluationId("evaluation-0"),
            evaluation_result_id=DomainResultId("evaluation-result-0"),
        ),
    )
    selection = compose_sqlite_transcript_current_selection_service(connection, execution)
    selection.record_selection(
        source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation-0"),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=CurrentSelectionIdentityPlan(
            selection_id=TranscriptCurrentSelectionId("selection-0"),
            selection_result_id=DomainResultId("selection-result-0"),
        ),
    )
    readiness = compose_sqlite_transcript_readiness_evaluation_service(connection, execution)
    readiness.record_readiness(
        source_selection_id=TranscriptCurrentSelectionId("selection-0"),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=ReadinessEvaluationIdentityPlan(
            readiness_id=TranscriptReadinessEvaluationId("readiness-0"),
            readiness_result_id=DomainResultId("readiness-result-0"),
            validation_id=TranscriptValidationId("readiness-validation"),
        ),
    )
    return execution, run_id, execution_id


def _intake_plan(name="intake-0") -> SubtitleIntakeIdentityPlan:
    return SubtitleIntakeIdentityPlan(
        intake_id=SubtitleTranscriptIntakeId(name),
        intake_result_id=DomainResultId(f"{name}-result"),
    )


def _record_intake(connection, execution, run_id, execution_id, name="intake-0"):
    service = compose_sqlite_subtitle_transcript_intake_service(connection, execution)
    return service.record_intake(
        source_readiness_id=TranscriptReadinessEvaluationId("readiness-0"),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_intake_plan(name),
    )


class SQLiteAtomicSubtitleIntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.execution, self.run_id, self.execution_id = _build_persisted_readiness(
            self.connection
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_and_reconstructs_after_restart(self) -> None:
        prepared = _record_intake(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.assertIs(prepared.intake.outcome, SubtitleIntakeOutcome.ELIGIBLE)
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            intake = SQLiteSubtitleTranscriptIntakeRepository(reopened).get(
                prepared.intake.identity
            )
            self.assertEqual(intake, prepared.intake)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.intake_result.identity
            )
            self.assertEqual(result, prepared.intake_result)
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = _record_intake(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.connection.close()

        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id = _build_persisted_readiness(replay_connection)
            second = _record_intake(replay_connection, execution, run_id, execution_id)
            self.assertEqual(first.intake, second.intake)
            self.assertEqual(first.intake_result, second.intake_result)
            replayed = SQLiteSubtitleTranscriptIntakeRepository(replay_connection).get(
                first.intake.identity
            )
            self.assertEqual(replayed, first.intake)
        finally:
            replay_connection.close()

    def test_repeated_evaluation_does_not_mutate_upstream_readiness(self) -> None:
        readiness_repo = SQLiteTranscriptReadinessEvaluationRepository(self.connection)
        before = readiness_repo.get(TranscriptReadinessEvaluationId("readiness-0"))
        _record_intake(self.connection, self.execution, self.run_id, self.execution_id, "i-a")
        _record_intake(self.connection, self.execution, self.run_id, self.execution_id, "i-b")
        after = readiness_repo.get(TranscriptReadinessEvaluationId("readiness-0"))
        self.assertEqual(before, after)
        count = self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_transcript_intakes"
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_repeated_persist_is_rejected_and_atomic(self) -> None:
        prepared = _record_intake(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        persistence = SQLiteSubtitleIntakeCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_intake(
                intake=prepared.intake, intake_result=prepared.intake_result
            )
        count = self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_transcript_intakes"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_result_collision_rolls_back_intake(self) -> None:
        service = compose_sqlite_subtitle_transcript_intake_service(
            self.connection, self.execution
        )
        prepared = service.evaluate_intake(
            source_readiness_id=TranscriptReadinessEvaluationId("readiness-0"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=SubtitleIntakeIdentityPlan(
                intake_id=SubtitleTranscriptIntakeId("intake-x"),
                # Reuse an existing DomainResult identity to force a collision.
                intake_result_id=DomainResultId("readiness-result-0"),
            ),
        )
        persistence = SQLiteSubtitleIntakeCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_intake(
                intake=prepared.intake, intake_result=prepared.intake_result
            )
        count = self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_transcript_intakes"
        ).fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
