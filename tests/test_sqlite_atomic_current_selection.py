import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from lectureos.application import (
    ApplicabilityEvaluationIdentityPlan,
    CurrentSelectionIdentityPlan,
    ReviewDecisionIdentityPlan,
    ReviewPreparationIdentityPlan,
    ReviewPreparationTargetIdentityPlan,
)
from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReviewDecisionId,
    TranscriptReviewPreparationId,
)
from lectureos.composition import (
    compose_sqlite_execution_service,
    compose_sqlite_transcript_applicability_evaluation_service,
    compose_sqlite_transcript_current_selection_service,
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
    SQLiteCurrentSelectionCommandPersistence,
    SQLiteDomainResultReferenceRepository,
    SQLiteTranscriptCurrentSelectionRepository,
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

WHEN = datetime(2026, 7, 22, 16, 0, tzinfo=timezone.utc)


def _build_persisted_applicability(connection):
    run_id = ProcessingRunId("run")
    execution_id = UnitExecutionId("execution")
    media_id = SourceMediaId("media")
    timeline_id = SourceTimelineId("timeline")
    capability = CapabilityReference("transcript.correction")
    execution = compose_sqlite_execution_service(connection)
    unit_id = ProcessingUnitId("unit")
    execution.register_unit(
        ProcessingUnit(identity=unit_id, purpose="select", capabilities=(capability,))
    )
    execution.start_run(
        run_id=run_id,
        intent=ExecutionIntent("select"),
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
    return execution, run_id, execution_id


def _selection_plan() -> CurrentSelectionIdentityPlan:
    return CurrentSelectionIdentityPlan(
        selection_id=TranscriptCurrentSelectionId("selection-0"),
        selection_result_id=DomainResultId("selection-result-0"),
    )


def _record_selection(connection, execution, run_id, execution_id):
    service = compose_sqlite_transcript_current_selection_service(connection, execution)
    return service.record_selection(
        source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation-0"),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_selection_plan(),
    )


class SQLiteAtomicCurrentSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.execution, self.run_id, self.execution_id = _build_persisted_applicability(
            self.connection
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_and_reconstructs_after_restart(self) -> None:
        prepared = _record_selection(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            selection = SQLiteTranscriptCurrentSelectionRepository(reopened).get(
                prepared.selection.identity
            )
            self.assertEqual(selection, prepared.selection)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.selection_result.identity
            )
            self.assertEqual(result, prepared.selection_result)
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = _record_selection(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.connection.close()

        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id = _build_persisted_applicability(
                replay_connection
            )
            second = _record_selection(
                replay_connection, execution, run_id, execution_id
            )
            self.assertEqual(first.selection, second.selection)
            self.assertEqual(first.selection_result, second.selection_result)
            replayed = SQLiteTranscriptCurrentSelectionRepository(
                replay_connection
            ).get(first.selection.identity)
            self.assertEqual(replayed, first.selection)
        finally:
            replay_connection.close()

    def test_repeated_persist_is_rejected_and_atomic(self) -> None:
        prepared = _record_selection(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        persistence = SQLiteCurrentSelectionCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_current_selection(
                selection=prepared.selection,
                selection_result=prepared.selection_result,
            )
        count = self.connection.execute(
            "SELECT COUNT(*) FROM transcript_current_selections"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_result_collision_rolls_back_selection(self) -> None:
        service = compose_sqlite_transcript_current_selection_service(
            self.connection, self.execution
        )
        prepared = service.evaluate_selection(
            source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation-0"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=CurrentSelectionIdentityPlan(
                selection_id=TranscriptCurrentSelectionId("selection-x"),
                # Reuse an existing DomainResult identity to force a collision.
                selection_result_id=DomainResultId("prep-result"),
            ),
        )
        persistence = SQLiteCurrentSelectionCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_current_selection(
                selection=prepared.selection,
                selection_result=prepared.selection_result,
            )
        count = self.connection.execute(
            "SELECT COUNT(*) FROM transcript_current_selections"
        ).fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
