import tempfile
import unittest
from pathlib import Path

from lectureos.application import (
    ReviewPreparationIdentityPlan,
    ReviewPreparationTargetIdentityPlan,
    TranscriptReviewPreparationService,
)
from lectureos.application.identities import TranscriptReviewPreparationId
from lectureos.composition import (
    compose_sqlite_execution_service,
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
    SQLiteReviewCandidateReferenceRepository,
    SQLiteReviewContextRepository,
    SQLiteReviewItemRepository,
    SQLiteReviewPreparationCommandPersistence,
    SQLiteTranscriptReviewPreparationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.identities import (
    CandidateReferenceId,
    ReviewContextId,
    ReviewItemId,
)
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


class SQLiteAtomicReviewPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.media_id = SourceMediaId("media")
        self.timeline_id = SourceTimelineId("timeline")
        capability = CapabilityReference("transcript.correction")
        self.execution = compose_sqlite_execution_service(self.connection)
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(identity=unit_id, purpose="prepare", capabilities=(capability,))
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("prepare review"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.transcripts = compose_sqlite_transcript_service(
            self.connection, self.execution
        )
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("provider"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="provider:model",
            original_content="source",
        )
        self.raw = RawTranscript(
            identity=TranscriptId("raw"),
            domain_result_id=DomainResultId("raw-result"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(TranscriptSegmentId("segment-0"), TranscriptSegmentId("segment-1")),
        )
        self.segments = tuple(
            TranscriptSegment(
                identity=self.raw.segment_ids[index],
                transcript_id=self.raw.identity,
                source_timeline_id=self.timeline_id,
                text=f"segment {index}",
                source_order=index,
                start=float(index),
                end=float(index) + 1.0,
            )
            for index in range(2)
        )
        self.transcripts.register_provider_result(provider)
        self.transcripts.create_raw_transcript(self.raw, self.segments)
        for index, segment in enumerate(self.segments):
            self.transcripts.create_correction_candidate(
                CorrectionCandidate(
                    identity=CorrectionCandidateId(f"candidate-{index}"),
                    domain_result_id=DomainResultId(f"candidate-result-{index}"),
                    transcript_id=self.raw.identity,
                    segment_id=segment.identity,
                    proposed_text=f"corrected {index}",
                    rationale="recognition",
                    run_id=self.run_id,
                    unit_execution_id=self.execution_id,
                )
            )
        self.revision = CorrectedTranscriptRevision(
            identity=TranscriptRevisionId("revision"),
            transcript_id=self.raw.identity,
            domain_result_id=DomainResultId("revision-result"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=self.raw.segment_ids,
            parent_raw_transcript_id=self.raw.identity,
            correction_candidate_ids=(
                CorrectionCandidateId("candidate-0"),
                CorrectionCandidateId("candidate-1"),
            ),
        )
        self.transcripts.create_corrected_revision(self.revision, self.segments)
        self.persistence = SQLiteReviewPreparationCommandPersistence(self.connection)
        self.service = TranscriptReviewPreparationService(
            self.transcripts, self.execution, self.persistence
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def _plan(self) -> ReviewPreparationIdentityPlan:
        return ReviewPreparationIdentityPlan(
            preparation_id=TranscriptReviewPreparationId("prep"),
            preparation_result_id=DomainResultId("prep-result"),
            context_id=ReviewContextId("context"),
            targets=tuple(
                ReviewPreparationTargetIdentityPlan(
                    candidate_reference_id=CandidateReferenceId(f"candidate-{index}"),
                    review_item_id=ReviewItemId(f"item-{index}"),
                )
                for index in range(2)
            ),
        )

    def test_persists_and_reconstructs_after_restart(self) -> None:
        prepared = self.service.generate_review(
            revision_id=self.revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            preparation = SQLiteTranscriptReviewPreparationRepository(reopened).get(
                prepared.preparation.identity
            )
            self.assertEqual(preparation, prepared.preparation)
            context = SQLiteReviewContextRepository(reopened).get(
                prepared.context.identity
            )
            self.assertEqual(context, prepared.context)
            items = SQLiteReviewItemRepository(reopened)
            for expected in prepared.review_items:
                self.assertEqual(items.get(expected.identity), expected)
            references = SQLiteReviewCandidateReferenceRepository(reopened)
            for expected in prepared.candidate_references:
                self.assertEqual(references.get(expected.identity), expected)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.preparation_result.identity
            )
            self.assertEqual(result, prepared.preparation_result)
        finally:
            reopened.close()

    def test_repeated_persist_is_rejected_and_atomic(self) -> None:
        prepared = self.service.generate_review(
            revision_id=self.revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_review_preparation(
                preparation=prepared.preparation,
                preparation_result=prepared.preparation_result,
                context=prepared.context,
                candidate_references=prepared.candidate_references,
                review_items=prepared.review_items,
            )
        count = self.connection.execute(
            "SELECT COUNT(*) FROM transcript_review_preparations"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_conflicting_review_item_rolls_back_completely(self) -> None:
        prepared = self.service.prepare_review(
            revision_id=self.revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        # Pre-insert a colliding review item so the atomic command must roll back.
        SQLiteReviewItemRepository(self.connection).save(prepared.review_items[0])
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_review_preparation(
                preparation=prepared.preparation,
                preparation_result=prepared.preparation_result,
                context=prepared.context,
                candidate_references=prepared.candidate_references,
                review_items=prepared.review_items,
            )
        preparations = self.connection.execute(
            "SELECT COUNT(*) FROM transcript_review_preparations"
        ).fetchone()[0]
        contexts = self.connection.execute(
            "SELECT COUNT(*) FROM review_contexts"
        ).fetchone()[0]
        self.assertEqual(preparations, 0)
        self.assertEqual(contexts, 0)


if __name__ == "__main__":
    unittest.main()
