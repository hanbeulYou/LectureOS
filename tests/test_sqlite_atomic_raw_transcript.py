import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
from lectureos.execution.models import (
    DomainResultReference,
    ExecutionIntent,
    ProcessingUnit,
)
from lectureos.execution.repositories import InMemoryRepository
from lectureos.execution.service import ExecutionService
from lectureos.persistence import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteExecutionCommandPersistence,
    SQLiteProcessingRunRepository,
    SQLiteProcessingUnitRepository,
    SQLiteProviderTranscriptResultRepository,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptCommandPersistence,
    SQLiteTranscriptSegmentRepository,
    SQLiteUnitExecutionRepository,
    SchemaFeatureUnavailableError,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle
from lectureos.persistence import transcript_commands
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import (
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)
from lectureos.transcript.service import TranscriptService


class RecordingRawPort:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls = []
        self.error = error

    def persist_raw_transcript(self, **kwargs) -> None:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error


class SaveCountingRepository(InMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.save_count = 0

    def save(self, record) -> None:
        self.save_count += 1
        super().save(record)


def create_v4_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN")
    for statement in (
        *sqlite_lifecycle._V1_TABLE_STATEMENTS,
        *sqlite_lifecycle._V2_ADDITION_STATEMENTS,
        *sqlite_lifecycle._V3_ADDITION_STATEMENTS,
        *sqlite_lifecycle._V4_ADDITION_STATEMENTS,
    ):
        connection.execute(statement)
    connection.execute("INSERT INTO schema_metadata VALUES (1, 4)")
    connection.execute("COMMIT")
    return connection


class AtomicRawTranscriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.unit_id = ProcessingUnitId("unit")
        self.media_id = SourceMediaId("media")
        self.timeline_id = SourceTimelineId("timeline")
        self.provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("provider"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="provider:model",
            original_content="original",
        )
        self.raw = RawTranscript(
            identity=TranscriptId("raw"),
            domain_result_id=DomainResultId("raw-result"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            provider_result_id=self.provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(TranscriptSegmentId("segment-b"), TranscriptSegmentId("segment-a")),
        )
        self.segments = (
            TranscriptSegment(
                identity=self.raw.segment_ids[0],
                transcript_id=self.raw.identity,
                source_timeline_id=self.timeline_id,
                text="second identity first",
                source_order=0,
                start=0.0,
                end=1.0,
            ),
            TranscriptSegment(
                identity=self.raw.segment_ids[1],
                transcript_id=self.raw.identity,
                source_timeline_id=self.timeline_id,
                text="first identity second",
                source_order=1,
                start=1.0,
                end=2.0,
            ),
        )
        self.result = DomainResultReference(
            identity=self.raw.domain_result_id,
            kind="raw_transcript",
            source_media=self.media_id,
            source_timeline=self.timeline_id,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _in_memory_execution(self) -> ExecutionService:
        service = ExecutionService()
        service.register_unit(
            ProcessingUnit(
                identity=self.unit_id,
                purpose="transcribe",
                capabilities=(CapabilityReference("speech.transcription"),),
            )
        )
        service.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("transcribe"),
            working_context=WorkingContextReference("context"),
            unit_ids=(self.unit_id,),
        )
        service.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit_id,
        )
        return service

    def _sqlite_execution(self, connection: sqlite3.Connection) -> ExecutionService:
        runs = SQLiteProcessingRunRepository(connection)
        units = SQLiteProcessingUnitRepository(connection)
        executions = SQLiteUnitExecutionRepository(connection)
        commands = SQLiteExecutionCommandPersistence(connection)
        service = ExecutionService(
            runs=runs,
            units=units,
            executions=executions,
            atomic_start_persistence=commands,
        )
        service.register_unit(
            ProcessingUnit(
                identity=self.unit_id,
                purpose="transcribe",
                capabilities=(CapabilityReference("speech.transcription"),),
            )
        )
        service.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("transcribe"),
            working_context=WorkingContextReference("context"),
            unit_ids=(self.unit_id,),
        )
        service.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit_id,
        )
        return service

    def test_service_computes_result_and_calls_port_once_without_repository_saves(self) -> None:
        providers = InMemoryRepository()
        providers.save(self.provider)
        raws = SaveCountingRepository()
        segments = SaveCountingRepository()
        results = SaveCountingRepository()
        port = RecordingRawPort()
        service = TranscriptService(
            self._in_memory_execution(),
            provider_results=providers,
            raw_transcripts=raws,
            segments=segments,
            domain_results=results,
            atomic_raw_persistence=port,
        )
        service.create_raw_transcript(self.raw, self.segments)
        self.assertEqual(len(port.calls), 1)
        self.assertEqual(
            port.calls[0],
            {"transcript": self.raw, "segments": self.segments, "result": self.result},
        )
        self.assertEqual((raws.save_count, segments.save_count, results.save_count), (0, 0, 0))

    def test_service_validation_and_persistence_errors_do_not_fallback(self) -> None:
        providers = InMemoryRepository()
        providers.save(self.provider)
        port = RecordingRawPort(PersistenceError("injected"))
        service = TranscriptService(
            self._in_memory_execution(),
            provider_results=providers,
            atomic_raw_persistence=port,
        )
        with self.assertRaises(PersistenceError):
            service.create_raw_transcript(self.raw, self.segments)
        self.assertEqual(len(port.calls), 1)

        invalid = RawTranscript(
            identity=TranscriptId("invalid"),
            domain_result_id=DomainResultId("invalid-result"),
            source_media_id=SourceMediaId("wrong"),
            source_timeline_id=self.timeline_id,
            provider_result_id=self.provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(),
        )
        with self.assertRaises(ValueError):
            service.create_raw_transcript(invalid, ())
        self.assertEqual(len(port.calls), 1)

    def test_atomic_success_and_restart_reconstruct_every_record(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        execution = self._sqlite_execution(connection)
        providers = SQLiteProviderTranscriptResultRepository(connection)
        raws = SQLiteRawTranscriptRepository(connection)
        segments = SQLiteTranscriptSegmentRepository(connection)
        results = SQLiteDomainResultReferenceRepository(connection)
        providers.save(self.provider)
        service = TranscriptService(
            execution,
            provider_results=providers,
            raw_transcripts=raws,
            segments=segments,
            domain_results=results,
            atomic_raw_persistence=SQLiteTranscriptCommandPersistence(connection),
        )
        service.create_raw_transcript(self.raw, self.segments)
        self.assertFalse(connection.in_transaction)
        connection.close()

        reopened = open_sqlite_database(self.database_path)
        self.assertEqual(SQLiteRawTranscriptRepository(reopened).get(self.raw.identity), self.raw)
        for segment in self.segments:
            self.assertEqual(SQLiteTranscriptSegmentRepository(reopened).get(segment.identity), segment)
        self.assertEqual(
            SQLiteDomainResultReferenceRepository(reopened).get(self.result.identity),
            self.result,
        )
        reopened.close()

    def test_each_identity_collision_rolls_back_complete_set(self) -> None:
        for collision in ("raw", "segment", "result"):
            with self.subTest(collision=collision):
                path = Path(self.temporary_directory.name) / f"{collision}.sqlite3"
                connection = initialize_sqlite_database(path)
                if collision == "raw":
                    SQLiteRawTranscriptRepository(connection).save(self.raw)
                elif collision == "segment":
                    SQLiteTranscriptSegmentRepository(connection).save(self.segments[0])
                else:
                    SQLiteDomainResultReferenceRepository(connection).save(self.result)
                command = SQLiteTranscriptCommandPersistence(connection)
                with self.assertRaises(PersistenceIdentityCollisionError):
                    command.persist_raw_transcript(
                        transcript=self.raw, segments=self.segments, result=self.result
                    )
                expected_segments = 1 if collision == "segment" else 0
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM transcript_segments").fetchone(),
                    (expected_segments,),
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM raw_transcripts").fetchone(),
                    (1 if collision == "raw" else 0,),
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM domain_result_references").fetchone(),
                    (1 if collision == "result" else 0,),
                )
                self.assertFalse(connection.in_transaction)
                connection.close()

    def test_raw_or_result_write_and_commit_failures_roll_back(self) -> None:
        failures = (
            ("raw", "_insert_raw_transcript", sqlite3.OperationalError("raw")),
            ("result", "_insert_domain_result_reference_record", sqlite3.OperationalError("result")),
            ("commit", "_commit", sqlite3.OperationalError("commit")),
        )
        for name, target, error in failures:
            with self.subTest(stage=name):
                path = Path(self.temporary_directory.name) / f"failure-{name}.sqlite3"
                connection = initialize_sqlite_database(path)
                command = SQLiteTranscriptCommandPersistence(connection)
                owner = transcript_commands if target.startswith("_insert") else command
                with patch.object(owner, target, side_effect=error):
                    with self.assertRaises(PersistenceError):
                        command.persist_raw_transcript(
                            transcript=self.raw,
                            segments=self.segments,
                            result=self.result,
                        )
                for table in (
                    "transcript_segments",
                    "raw_transcripts",
                    "domain_result_references",
                ):
                    self.assertEqual(
                        connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone(),
                        (0,),
                    )
                self.assertFalse(connection.in_transaction)
                self.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))
                connection.close()

    def test_linkage_mismatch_rolls_back_without_writes(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        command = SQLiteTranscriptCommandPersistence(connection)
        mismatches = (
            (self.raw, self.segments[:-1], self.result),
            (self.raw, self.segments, DomainResultReference(DomainResultId("wrong"), "raw_transcript")),
        )
        for transcript, segments, result in mismatches:
            with self.assertRaises(PersistenceError):
                command.persist_raw_transcript(
                    transcript=transcript, segments=segments, result=result
                )
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM raw_transcripts").fetchone(), (0,))
        self.assertFalse(connection.in_transaction)
        connection.close()

    def test_schema_v4_feature_gate_does_not_migrate(self) -> None:
        connection = create_v4_database(self.database_path)
        command = SQLiteTranscriptCommandPersistence(connection)
        with self.assertRaises(SchemaFeatureUnavailableError):
            command.persist_raw_transcript(
                transcript=self.raw, segments=self.segments, result=self.result
            )
        self.assertEqual(connection.execute("SELECT version FROM schema_metadata").fetchone(), (4,))
        connection.close()


if __name__ == "__main__":
    unittest.main()
