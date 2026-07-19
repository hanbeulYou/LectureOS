import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    ReviewDecisionId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference, ProcessingState
from lectureos.execution.repositories import InMemoryRepository
from lectureos.persistence import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SQLiteCorrectionCandidateRepository,
    SQLiteCorrectedTranscriptRevisionRepository,
    SQLiteDomainResultReferenceRepository,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptCommandPersistence,
    SQLiteTranscriptSegmentRepository,
    SchemaFeatureUnavailableError,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import sqlite as sqlite_lifecycle
from lectureos.persistence import transcript_commands
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import (
    CorrectionCandidate,
    CorrectedTranscriptRevision,
    RawTranscript,
    TranscriptApplicability,
    TranscriptSegment,
)
from lectureos.transcript.service import TranscriptService


class ExecutionQuery:
    def __init__(self, run_id, execution_id) -> None:
        self.run = type("Run", (), {"identity": run_id})()
        self.execution = type(
            "Execution",
            (),
            {
                "identity": execution_id,
                "run_id": run_id,
                "state": ProcessingState.RUNNING,
            },
        )()

    def get_run(self, identity):
        return self.run if identity == self.run.identity else None

    def get_unit_execution(self, identity):
        return self.execution if identity == self.execution.identity else None


class RecordingRevisionPort:
    def __init__(self, error=None) -> None:
        self.calls = []
        self.error = error

    def persist_corrected_revision(self, **kwargs) -> None:
        self.calls.append(kwargs)
        if self.error:
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


class SQLiteCorrectedTranscriptRevisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.media_id = SourceMediaId("media")
        self.timeline_id = SourceTimelineId("timeline")
        self.raw = RawTranscript(
            identity=TranscriptId("raw"),
            domain_result_id=DomainResultId("raw-result"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            provider_result_id=ProviderTranscriptResultId("provider"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(TranscriptSegmentId("source"),),
        )
        self.source_segment = TranscriptSegment(
            identity=self.raw.segment_ids[0],
            transcript_id=self.raw.identity,
            source_timeline_id=self.timeline_id,
            text="source",
            source_order=0,
            start=0.0,
            end=1.0,
        )
        self.replacement = TranscriptSegment(
            identity=TranscriptSegmentId("replacement"),
            transcript_id=self.raw.identity,
            source_timeline_id=self.timeline_id,
            text="corrected",
            source_order=1,
            start=1.0,
            end=2.0,
            replaces_segment_id=self.source_segment.identity,
        )
        self.candidate = CorrectionCandidate(
            identity=CorrectionCandidateId("candidate"),
            domain_result_id=DomainResultId("candidate-result"),
            transcript_id=self.raw.identity,
            segment_id=self.source_segment.identity,
            proposed_text="corrected",
            rationale="reviewed correction",
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )
        self.revision = CorrectedTranscriptRevision(
            identity=TranscriptRevisionId("revision"),
            transcript_id=self.raw.identity,
            domain_result_id=DomainResultId("revision-result"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(self.source_segment.identity, self.replacement.identity),
            parent_raw_transcript_id=self.raw.identity,
            correction_candidate_ids=(self.candidate.identity, self.candidate.identity),
            decision_reference=ReviewDecisionId("decision"),
            validation_id=TranscriptValidationId("validation"),
            applicability=TranscriptApplicability.HISTORICAL,
        )
        self.segments = (self.source_segment, self.replacement)
        self.result = DomainResultReference(
            identity=self.revision.domain_result_id,
            kind="corrected_transcript_revision",
            source_media=self.media_id,
            source_timeline=self.timeline_id,
            upstream_results=(self.raw.domain_result_id,),
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _seed_in_memory(self, **kwargs) -> TranscriptService:
        raws = kwargs.pop("raw_transcripts", InMemoryRepository())
        segments = kwargs.pop("segments", InMemoryRepository())
        candidates = kwargs.pop("candidates", InMemoryRepository())
        results = kwargs.pop("domain_results", InMemoryRepository())
        raws.save(self.raw)
        segments.save(self.source_segment)
        candidates.save(self.candidate)
        results.save(DomainResultReference(self.raw.domain_result_id, "raw_transcript"))
        results.save(DomainResultReference(self.candidate.domain_result_id, "transcript_correction_candidate"))
        return TranscriptService(
            ExecutionQuery(self.run_id, self.execution_id),
            raw_transcripts=raws,
            segments=segments,
            candidates=candidates,
            domain_results=results,
            **kwargs,
        )

    def _seed_sqlite(self, connection):
        raws = SQLiteRawTranscriptRepository(connection)
        segments = SQLiteTranscriptSegmentRepository(connection)
        candidates = SQLiteCorrectionCandidateRepository(connection)
        results = SQLiteDomainResultReferenceRepository(connection)
        raws.save(self.raw)
        segments.save(self.source_segment)
        candidates.save(self.candidate)
        results.save(DomainResultReference(self.raw.domain_result_id, "raw_transcript"))
        results.save(DomainResultReference(self.candidate.domain_result_id, "transcript_correction_candidate"))
        return raws, segments, candidates, results

    def test_repository_full_round_trip_all_order_duplicates_and_restart(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        repository = SQLiteCorrectedTranscriptRevisionRepository(connection)
        repository.save(self.revision)
        second = replace(
            self.revision,
            identity=TranscriptRevisionId("revision-2"),
            domain_result_id=DomainResultId("revision-result-2"),
            parent_raw_transcript_id=None,
            parent_revision_id=self.revision.identity,
            correction_candidate_ids=(),
            decision_reference=None,
            validation_id=None,
            applicability=TranscriptApplicability.UNDETERMINED,
        )
        repository.save(second)
        self.assertEqual(repository.get(self.revision.identity), self.revision)
        self.assertEqual(repository.all(), (self.revision, second))
        self.assertEqual(
            connection.execute(
                "SELECT ordinal, correction_candidate_id FROM corrected_transcript_revision_candidates WHERE transcript_revision_id = 'revision' ORDER BY ordinal"
            ).fetchall(),
            [(0, "candidate"), (1, "candidate")],
        )
        connection.close()
        reopened = open_sqlite_database(self.database_path)
        self.assertEqual(
            SQLiteCorrectedTranscriptRevisionRepository(reopened).all(),
            (self.revision, second),
        )
        reopened.close()

    def test_repository_unknown_and_duplicate_collision_preserve_original(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        repository = SQLiteCorrectedTranscriptRevisionRepository(connection)
        repository.save(self.revision)
        self.assertIsNone(repository.get(TranscriptRevisionId("missing")))
        for duplicate in (self.revision, replace(self.revision, segment_ids=())):
            with self.assertRaises(PersistenceIdentityCollisionError):
                repository.save(duplicate)
        self.assertEqual(repository.get(self.revision.identity), self.revision)
        connection.close()

    def test_service_calls_port_once_with_computed_result_and_no_independent_saves(self) -> None:
        revisions = SaveCountingRepository()
        segment_store = SaveCountingRepository()
        segment_store.save(self.source_segment)
        segment_store.save_count = 0
        results = SaveCountingRepository()
        port = RecordingRevisionPort()
        service = self._seed_in_memory(
            revisions=revisions,
            segments=segment_store,
            domain_results=results,
            atomic_revision_persistence=port,
        )
        segment_store.save_count = 0
        results.save_count = 0
        service.create_corrected_revision(self.revision, self.segments)
        self.assertEqual(
            port.calls,
            [{"revision": self.revision, "segments": self.segments, "result": self.result}],
        )
        self.assertEqual((revisions.save_count, segment_store.save_count, results.save_count), (0, 0, 0))

    def test_service_validation_and_persistence_errors_do_not_fallback(self) -> None:
        port = RecordingRevisionPort(PersistenceError("injected"))
        service = self._seed_in_memory(atomic_revision_persistence=port)
        with self.assertRaises(PersistenceError):
            service.create_corrected_revision(self.revision, self.segments)
        self.assertEqual(len(port.calls), 1)
        invalid = replace(self.revision, correction_candidate_ids=(CorrectionCandidateId("missing"),))
        with self.assertRaises(KeyError):
            service.create_corrected_revision(invalid, self.segments)
        self.assertEqual(len(port.calls), 1)

    def test_atomic_success_reuses_existing_segment_inserts_new_and_restarts(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        raws, segments, candidates, results = self._seed_sqlite(connection)
        revisions = SQLiteCorrectedTranscriptRevisionRepository(connection)
        service = TranscriptService(
            ExecutionQuery(self.run_id, self.execution_id),
            raw_transcripts=raws,
            segments=segments,
            candidates=candidates,
            revisions=revisions,
            domain_results=results,
            atomic_revision_persistence=SQLiteTranscriptCommandPersistence(connection),
        )
        service.create_corrected_revision(self.revision, self.segments)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM transcript_segments").fetchone(), (2,))
        connection.close()
        reopened = open_sqlite_database(self.database_path)
        self.assertEqual(SQLiteCorrectedTranscriptRevisionRepository(reopened).get(self.revision.identity), self.revision)
        self.assertEqual(SQLiteTranscriptSegmentRepository(reopened).get(self.source_segment.identity), self.source_segment)
        self.assertEqual(SQLiteTranscriptSegmentRepository(reopened).get(self.replacement.identity), self.replacement)
        self.assertEqual(SQLiteDomainResultReferenceRepository(reopened).get(self.result.identity), self.result)
        reopened.close()

    def test_revision_result_and_conflicting_segment_collisions_roll_back(self) -> None:
        scenarios = ("revision", "result", "segment")
        for scenario in scenarios:
            path = Path(self.temporary_directory.name) / f"{scenario}.sqlite3"
            connection = initialize_sqlite_database(path)
            SQLiteTranscriptSegmentRepository(connection).save(self.source_segment)
            if scenario == "revision":
                SQLiteCorrectedTranscriptRevisionRepository(connection).save(self.revision)
            elif scenario == "result":
                SQLiteDomainResultReferenceRepository(connection).save(self.result)
            else:
                SQLiteTranscriptSegmentRepository(connection).save(replace(self.replacement, text="conflict"))
            with self.assertRaises(PersistenceIdentityCollisionError):
                SQLiteTranscriptCommandPersistence(connection).persist_corrected_revision(
                    revision=self.revision, segments=self.segments, result=self.result
                )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM transcript_segments WHERE identity = 'replacement'").fetchone(),
                (1 if scenario == "segment" else 0,),
            )
            self.assertFalse(connection.in_transaction)
            connection.close()

    def test_write_and_commit_failures_roll_back_new_segment_revision_and_result(self) -> None:
        targets = (
            "_insert_transcript_segment",
            "_insert_corrected_transcript_revision",
            "_insert_domain_result_reference_record",
        )
        for target in targets:
            path = Path(self.temporary_directory.name) / f"{target}.sqlite3"
            connection = initialize_sqlite_database(path)
            SQLiteTranscriptSegmentRepository(connection).save(self.source_segment)
            command = SQLiteTranscriptCommandPersistence(connection)
            with patch.object(transcript_commands, target, side_effect=sqlite3.OperationalError("injected")):
                with self.assertRaises(PersistenceError):
                    command.persist_corrected_revision(revision=self.revision, segments=self.segments, result=self.result)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM transcript_segments").fetchone(), (1,))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM corrected_transcript_revisions").fetchone(), (0,))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM domain_result_references").fetchone(), (0,))
            connection.close()

        path = Path(self.temporary_directory.name) / "commit.sqlite3"
        connection = initialize_sqlite_database(path)
        SQLiteTranscriptSegmentRepository(connection).save(self.source_segment)
        command = SQLiteTranscriptCommandPersistence(connection)
        with patch.object(command, "_commit", side_effect=sqlite3.OperationalError("commit")):
            with self.assertRaises(PersistenceError):
                command.persist_corrected_revision(revision=self.revision, segments=self.segments, result=self.result)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM transcript_segments").fetchone(), (1,))
        self.assertFalse(connection.in_transaction)
        self.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))
        connection.close()

    def test_linkage_and_v4_gate_fail_without_mutation(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        wrong = replace(self.result, identity=DomainResultId("wrong"))
        with self.assertRaises(PersistenceError):
            SQLiteTranscriptCommandPersistence(connection).persist_corrected_revision(
                revision=self.revision, segments=self.segments, result=wrong
            )
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM corrected_transcript_revisions").fetchone(), (0,))
        connection.close()

        path = Path(self.temporary_directory.name) / "v4.sqlite3"
        v4 = create_v4_database(path)
        with self.assertRaises(SchemaFeatureUnavailableError):
            SQLiteTranscriptCommandPersistence(v4).persist_corrected_revision(
                revision=self.revision, segments=self.segments, result=self.result
            )
        self.assertEqual(v4.execute("SELECT version FROM schema_metadata").fetchone(), (4,))
        v4.close()


if __name__ == "__main__":
    unittest.main()
