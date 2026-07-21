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
    SubtitleCandidateIdentityPlan,
    SubtitleIntakeIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleCandidateCueId,
    SubtitleCandidateId,
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
    TranscriptReviewPreparationId,
)
from lectureos.composition import (
    compose_sqlite_execution_service,
    compose_sqlite_subtitle_candidate_generation_service,
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
    SQLiteSubtitleCandidateCommandPersistence,
    SQLiteSubtitleCandidateRepository,
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
SEGMENT_IDS = (TranscriptSegmentId("segment-0"), TranscriptSegmentId("segment-1"))


def _build_persisted_intake(connection):
    run_id = ProcessingRunId("run")
    execution_id = UnitExecutionId("execution")
    media_id = SourceMediaId("media")
    timeline_id = SourceTimelineId("timeline")
    capability = CapabilityReference("transcript.correction")
    execution = compose_sqlite_execution_service(connection)
    unit_id = ProcessingUnitId("unit")
    execution.register_unit(
        ProcessingUnit(identity=unit_id, purpose="candidate", capabilities=(capability,))
    )
    execution.start_run(
        run_id=run_id,
        intent=ExecutionIntent("candidate"),
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
        segment_ids=SEGMENT_IDS,
    )
    segments = (
        TranscriptSegment(
            identity=SEGMENT_IDS[0],
            transcript_id=raw.identity,
            source_timeline_id=timeline_id,
            text="one",
            source_order=0,
            start=0.0,
            end=1.0,
        ),
        TranscriptSegment(
            identity=SEGMENT_IDS[1],
            transcript_id=raw.identity,
            source_timeline_id=timeline_id,
            text="two",
            source_order=1,
            start=1.0,
            end=2.0,
        ),
    )
    transcripts.register_provider_result(provider)
    transcripts.create_raw_transcript(raw, segments)
    transcripts.create_correction_candidate(
        CorrectionCandidate(
            identity=CorrectionCandidateId("candidate-0"),
            domain_result_id=DomainResultId("candidate-result-0"),
            transcript_id=raw.identity,
            segment_id=SEGMENT_IDS[0],
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
        segment_ids=SEGMENT_IDS,
        parent_raw_transcript_id=raw.identity,
        correction_candidate_ids=(CorrectionCandidateId("candidate-0"),),
    )
    transcripts.create_corrected_revision(revision, segments)
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
    intake = compose_sqlite_subtitle_transcript_intake_service(connection, execution)
    intake.record_intake(
        source_readiness_id=TranscriptReadinessEvaluationId("readiness-0"),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=SubtitleIntakeIdentityPlan(
            intake_id=SubtitleTranscriptIntakeId("intake-0"),
            intake_result_id=DomainResultId("intake-0-result"),
        ),
    )
    return execution, run_id, execution_id


def _candidate_plan(name="cand-0") -> SubtitleCandidateIdentityPlan:
    return SubtitleCandidateIdentityPlan(
        candidate_id=SubtitleCandidateId(name),
        candidate_result_id=DomainResultId(f"{name}-result"),
        cue_ids=(
            SubtitleCandidateCueId(f"{name}-cue-0"),
            SubtitleCandidateCueId(f"{name}-cue-1"),
        ),
    )


def _record_candidate(connection, execution, run_id, execution_id, name="cand-0"):
    service = compose_sqlite_subtitle_candidate_generation_service(connection, execution)
    return service.record_candidate(
        source_intake_id=SubtitleTranscriptIntakeId("intake-0"),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_candidate_plan(name),
    )


class SQLiteAtomicSubtitleCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.execution, self.run_id, self.execution_id = _build_persisted_intake(
            self.connection
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_and_reconstructs_candidate_and_ordered_cues(self) -> None:
        prepared = _record_candidate(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.assertEqual(len(prepared.cues), 2)
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteSubtitleCandidateRepository(reopened)
            candidate = repo.get(prepared.candidate.identity)
            self.assertEqual(candidate, prepared.candidate)
            # ordered cue ids preserved
            self.assertEqual(candidate.cue_ids, prepared.candidate.cue_ids)
            for cue in prepared.cues:
                self.assertEqual(repo.get_cue(cue.identity), cue)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.candidate_result.identity
            )
            self.assertEqual(result, prepared.candidate_result)
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = _record_candidate(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.connection.close()

        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id = _build_persisted_intake(replay_connection)
            second = _record_candidate(replay_connection, execution, run_id, execution_id)
            self.assertEqual(first.candidate, second.candidate)
            self.assertEqual(first.cues, second.cues)
            self.assertEqual(first.candidate_result, second.candidate_result)
            replayed = SQLiteSubtitleCandidateRepository(replay_connection).get(
                first.candidate.identity
            )
            self.assertEqual(replayed, first.candidate)
        finally:
            replay_connection.close()

    def test_repeated_generation_does_not_mutate_upstream_intake(self) -> None:
        intake_repo = SQLiteSubtitleTranscriptIntakeRepository(self.connection)
        before = intake_repo.get(SubtitleTranscriptIntakeId("intake-0"))
        _record_candidate(self.connection, self.execution, self.run_id, self.execution_id, "c-a")
        _record_candidate(self.connection, self.execution, self.run_id, self.execution_id, "c-b")
        after = intake_repo.get(SubtitleTranscriptIntakeId("intake-0"))
        self.assertEqual(before, after)
        count = self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_candidates"
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_repeated_persist_is_rejected_and_atomic(self) -> None:
        prepared = _record_candidate(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        persistence = SQLiteSubtitleCandidateCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_candidate(
                candidate=prepared.candidate,
                cues=prepared.cues,
                candidate_result=prepared.candidate_result,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_candidates"
            ).fetchone()[0],
            1,
        )
        # the second attempt wrote no additional cues
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_candidate_cues"
            ).fetchone()[0],
            2,
        )

    def test_result_collision_rolls_back_candidate_and_cues(self) -> None:
        service = compose_sqlite_subtitle_candidate_generation_service(
            self.connection, self.execution
        )
        prepared = service.generate_candidate(
            source_intake_id=SubtitleTranscriptIntakeId("intake-0"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=SubtitleCandidateIdentityPlan(
                candidate_id=SubtitleCandidateId("cand-x"),
                # Reuse an existing DomainResult identity to force a collision.
                candidate_result_id=DomainResultId("intake-0-result"),
                cue_ids=(
                    SubtitleCandidateCueId("cand-x-cue-0"),
                    SubtitleCandidateCueId("cand-x-cue-1"),
                ),
            ),
        )
        persistence = SQLiteSubtitleCandidateCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_candidate(
                candidate=prepared.candidate,
                cues=prepared.cues,
                candidate_result=prepared.candidate_result,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_candidates"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_candidate_cues"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_candidate_cue_segments"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
