import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lectureos.composition import (
    compose_sqlite_execution_service,
    compose_sqlite_transcript_service,
)
from lectureos.execution.identities import (
    CapabilityReference,
    DiagnosticId,
    DomainResultId,
    PluginReference,
    ProcessingRunId,
    ProcessingUnitId,
    ReviewDecisionId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import ExecutionIntent, ProcessingUnit
from lectureos.persistence import (
    PersistenceError,
    SQLiteCorrectedTranscriptRevisionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import transcript_commands
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import (
    CorrectionCandidate,
    CorrectedTranscriptRevision,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptApplicability,
    TranscriptSegment,
)


class SQLiteTranscriptCompositionAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.unit_id = ProcessingUnitId("unit")
        self.media_id = SourceMediaId("media")
        self.timeline_id = SourceTimelineId("timeline")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _compose_seeded(self, connection):
        execution = compose_sqlite_execution_service(connection)
        execution.register_unit(
            ProcessingUnit(
                identity=self.unit_id,
                purpose="transcribe",
                capabilities=(CapabilityReference("speech.transcription"),),
            )
        )
        execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("transcribe"),
            working_context=WorkingContextReference("context"),
            unit_ids=(self.unit_id,),
        )
        execution.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit_id,
        )
        return execution, compose_sqlite_transcript_service(connection, execution)

    def _records(self):
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("provider"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="provider:model",
            original_content="provider content",
            plugin_reference=PluginReference("plugin"),
            diagnostic_references=(DiagnosticId("diagnostic-b"), DiagnosticId("diagnostic-b")),
            uncertainty=0.2,
        )
        raw = RawTranscript(
            identity=TranscriptId("raw"),
            domain_result_id=DomainResultId("raw-result"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(TranscriptSegmentId("segment-b"), TranscriptSegmentId("segment-a")),
        )
        source_segments = (
            TranscriptSegment(
                identity=raw.segment_ids[0], transcript_id=raw.identity,
                source_timeline_id=self.timeline_id, text="source one", source_order=0,
                start=0.0, end=1.0,
            ),
            TranscriptSegment(
                identity=raw.segment_ids[1], transcript_id=raw.identity,
                source_timeline_id=self.timeline_id, text="source two", source_order=1,
                start=1.0, end=2.0,
            ),
        )
        candidate = CorrectionCandidate(
            identity=CorrectionCandidateId("candidate"),
            domain_result_id=DomainResultId("candidate-result"),
            transcript_id=raw.identity,
            segment_id=source_segments[0].identity,
            proposed_text="corrected one",
            rationale="recognition correction",
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            evidence=("evidence-b", "evidence-b"),
        )
        replacement = TranscriptSegment(
            identity=TranscriptSegmentId("replacement"), transcript_id=raw.identity,
            source_timeline_id=self.timeline_id, text="corrected one", source_order=0,
            start=0.0, end=1.0, replaces_segment_id=source_segments[0].identity,
        )
        first = CorrectedTranscriptRevision(
            identity=TranscriptRevisionId("revision-1"),
            transcript_id=raw.identity,
            domain_result_id=DomainResultId("revision-result-1"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(replacement.identity, source_segments[1].identity),
            parent_raw_transcript_id=raw.identity,
            correction_candidate_ids=(candidate.identity, candidate.identity),
            decision_reference=ReviewDecisionId("opaque-decision"),
            applicability=TranscriptApplicability.HISTORICAL,
        )
        second = CorrectedTranscriptRevision(
            identity=TranscriptRevisionId("revision-2"),
            transcript_id=raw.identity,
            domain_result_id=DomainResultId("revision-result-2"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=first.segment_ids,
            parent_revision_id=first.identity,
            correction_candidate_ids=(),
        )
        return provider, raw, source_segments, candidate, replacement, first, second

    def test_complete_lineage_reconstructs_exactly_after_restart(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        _, transcripts = self._compose_seeded(connection)
        provider, raw, source_segments, candidate, replacement, first, second = self._records()

        transcripts.register_provider_result(provider)
        transcripts.create_raw_transcript(raw, source_segments)
        transcripts.create_correction_candidate(candidate)
        transcripts.create_corrected_revision(first, (replacement, source_segments[1]))
        transcripts.create_corrected_revision(second, (replacement, source_segments[1]))
        connection.close()

        reopened = open_sqlite_database(self.database_path)
        execution = compose_sqlite_execution_service(reopened)
        restored = compose_sqlite_transcript_service(reopened, execution)
        self.assertEqual(restored.get_provider_result(provider.identity), provider)
        self.assertEqual(restored.get_raw_transcript(raw.identity), raw)
        self.assertEqual(restored.get_candidate(candidate.identity), candidate)
        self.assertEqual(restored.get_corrected_revision(first.identity), first)
        self.assertEqual(restored.get_corrected_revision(second.identity), second)
        self.assertEqual(restored.get_lineage(raw.identity), (raw, (first, second)))
        self.assertEqual(restored.get_segment(replacement.identity), replacement)
        self.assertEqual(
            tuple(
                restored.get_domain_result_reference(identity).kind
                for identity in (raw.domain_result_id, candidate.domain_result_id,
                                 first.domain_result_id, second.domain_result_id)
            ),
            ("raw_transcript", "transcript_correction_candidate",
             "corrected_transcript_revision", "corrected_transcript_revision"),
        )
        reopened.close()

    def test_failed_second_revision_preserves_restart_lineage(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        _, transcripts = self._compose_seeded(connection)
        provider, raw, source_segments, candidate, replacement, first, second = self._records()
        transcripts.register_provider_result(provider)
        transcripts.create_raw_transcript(raw, source_segments)
        transcripts.create_correction_candidate(candidate)
        transcripts.create_corrected_revision(first, (replacement, source_segments[1]))

        with patch.object(
            transcript_commands,
            "_insert_domain_result_reference_record",
            side_effect=PersistenceError("injected"),
        ):
            with self.assertRaises(PersistenceError):
                transcripts.create_corrected_revision(second, (replacement, source_segments[1]))
        self.assertFalse(connection.in_transaction)
        connection.close()

        reopened = open_sqlite_database(self.database_path)
        execution = compose_sqlite_execution_service(reopened)
        restored = compose_sqlite_transcript_service(reopened, execution)
        self.assertEqual(restored.get_lineage(raw.identity), (raw, (first,)))
        self.assertIsNone(restored.get_corrected_revision(second.identity))
        self.assertIsNone(restored.get_domain_result_reference(second.domain_result_id))
        self.assertEqual(SQLiteCorrectedTranscriptRevisionRepository(reopened).all(), (first,))
        reopened.close()


if __name__ == "__main__":
    unittest.main()
