import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    PluginReference,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.execution.models import ProcessingState
from lectureos.execution.repositories import InMemoryRepository
from lectureos.persistence import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SQLiteCorrectionCandidateRepository,
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
)
from lectureos.transcript.models import CorrectionCandidate, RawTranscript, TranscriptSegment
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


class RecordingCandidatePort:
    def __init__(self, error=None) -> None:
        self.calls = []
        self.error = error

    def persist_correction_candidate(self, **kwargs) -> None:
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


class SQLiteCorrectionCandidateTests(unittest.TestCase):
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
            segment_ids=(TranscriptSegmentId("segment"),),
        )
        self.segment = TranscriptSegment(
            identity=self.raw.segment_ids[0],
            transcript_id=self.raw.identity,
            source_timeline_id=self.timeline_id,
            text="source",
            source_order=0,
            start=0.0,
            end=1.0,
        )
        self.candidate = CorrectionCandidate(
            identity=CorrectionCandidateId("candidate"),
            domain_result_id=DomainResultId("candidate-result"),
            transcript_id=self.raw.identity,
            segment_id=self.segment.identity,
            proposed_text="corrected",
            rationale="evidence-backed correction",
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            evidence=("source-b", "source-a", "source-b"),
            confidence=0.8,
            uncertainty=0.2,
            capability=CapabilityReference("text.correction"),
            plugin_reference=PluginReference("plugin"),
            provider_reference="provider:model",
        )
        self.result = DomainResultReference(
            identity=self.candidate.domain_result_id,
            kind="transcript_correction_candidate",
            source_media=self.media_id,
            source_timeline=self.timeline_id,
            upstream_results=(self.raw.domain_result_id,),
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _seed_service(self, **kwargs) -> TranscriptService:
        raws = kwargs.pop("raw_transcripts", InMemoryRepository())
        segments = kwargs.pop("segments", InMemoryRepository())
        raws.save(self.raw)
        segments.save(self.segment)
        return TranscriptService(
            ExecutionQuery(self.run_id, self.execution_id),
            raw_transcripts=raws,
            segments=segments,
            **kwargs,
        )

    def test_repository_full_round_trip_preserves_evidence_order_duplicates_and_restart(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        repository = SQLiteCorrectionCandidateRepository(connection)
        repository.save(self.candidate)
        self.assertEqual(repository.get(self.candidate.identity), self.candidate)
        self.assertEqual(
            connection.execute(
                "SELECT ordinal, evidence FROM correction_candidate_evidence ORDER BY ordinal"
            ).fetchall(),
            [(0, "source-b"), (1, "source-a"), (2, "source-b")],
        )
        connection.close()
        reopened = open_sqlite_database(self.database_path)
        self.assertEqual(
            SQLiteCorrectionCandidateRepository(reopened).get(self.candidate.identity),
            self.candidate,
        )
        reopened.close()

    def test_repository_empty_optionals_unknown_and_duplicate_collision(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        repository = SQLiteCorrectionCandidateRepository(connection)
        minimal = replace(
            self.candidate,
            evidence=(),
            confidence=None,
            uncertainty=None,
            capability=None,
            plugin_reference=None,
            provider_reference=None,
        )
        repository.save(minimal)
        self.assertEqual(repository.get(minimal.identity), minimal)
        self.assertIsNone(repository.get(CorrectionCandidateId("missing")))
        for duplicate in (minimal, replace(minimal, proposed_text="different")):
            with self.assertRaises(PersistenceIdentityCollisionError):
                repository.save(duplicate)
        self.assertEqual(repository.get(minimal.identity), minimal)
        connection.close()

    def test_repository_round_trip_preserves_non_null_target_revision(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        repository = SQLiteCorrectionCandidateRepository(connection)
        record = replace(
            self.candidate,
            target_revision_id=TranscriptRevisionId("target-revision"),
        )
        repository.save(record)
        self.assertEqual(repository.get(record.identity), record)
        connection.close()

    def test_service_calls_atomic_port_once_with_computed_lineage_and_no_saves(self) -> None:
        candidates = SaveCountingRepository()
        results = SaveCountingRepository()
        port = RecordingCandidatePort()
        service = self._seed_service(
            candidates=candidates,
            domain_results=results,
            atomic_candidate_persistence=port,
        )
        service.create_correction_candidate(self.candidate)
        self.assertEqual(port.calls, [{"candidate": self.candidate, "result": self.result}])
        self.assertEqual((candidates.save_count, results.save_count), (0, 0))

    def test_service_validation_and_persistence_failure_do_not_fallback(self) -> None:
        port = RecordingCandidatePort(PersistenceError("injected"))
        service = self._seed_service(atomic_candidate_persistence=port)
        with self.assertRaises(PersistenceError):
            service.create_correction_candidate(self.candidate)
        self.assertEqual(len(port.calls), 1)
        invalid = replace(self.candidate, segment_id=TranscriptSegmentId("missing"))
        with self.assertRaises(KeyError):
            service.create_correction_candidate(invalid)
        self.assertEqual(len(port.calls), 1)

    def test_atomic_success_and_restart_reconstruct_candidate_and_result(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        raws = SQLiteRawTranscriptRepository(connection)
        segments = SQLiteTranscriptSegmentRepository(connection)
        candidates = SQLiteCorrectionCandidateRepository(connection)
        results = SQLiteDomainResultReferenceRepository(connection)
        raws.save(self.raw)
        segments.save(self.segment)
        service = TranscriptService(
            ExecutionQuery(self.run_id, self.execution_id),
            raw_transcripts=raws,
            segments=segments,
            candidates=candidates,
            domain_results=results,
            atomic_candidate_persistence=SQLiteTranscriptCommandPersistence(connection),
        )
        service.create_correction_candidate(self.candidate)
        connection.close()
        reopened = open_sqlite_database(self.database_path)
        self.assertEqual(
            SQLiteCorrectionCandidateRepository(reopened).get(self.candidate.identity),
            self.candidate,
        )
        self.assertEqual(
            SQLiteDomainResultReferenceRepository(reopened).get(self.result.identity),
            self.result,
        )
        reopened.close()

    def test_candidate_or_result_collision_rolls_back_other_record(self) -> None:
        for collision in ("candidate", "result"):
            with self.subTest(collision=collision):
                path = Path(self.temporary_directory.name) / f"{collision}.sqlite3"
                connection = initialize_sqlite_database(path)
                if collision == "candidate":
                    SQLiteCorrectionCandidateRepository(connection).save(self.candidate)
                else:
                    SQLiteDomainResultReferenceRepository(connection).save(self.result)
                with self.assertRaises(PersistenceIdentityCollisionError):
                    SQLiteTranscriptCommandPersistence(connection).persist_correction_candidate(
                        candidate=self.candidate, result=self.result
                    )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM correction_candidates").fetchone(),
                    (1 if collision == "candidate" else 0,),
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM domain_result_references").fetchone(),
                    (1 if collision == "result" else 0,),
                )
                connection.close()

    def test_write_result_and_commit_failures_roll_back_complete_set(self) -> None:
        scenarios = (
            (transcript_commands, "_insert_correction_candidate"),
            (transcript_commands, "_insert_domain_result_reference_record"),
        )
        for index, (owner, target) in enumerate(scenarios):
            path = Path(self.temporary_directory.name) / f"write-{index}.sqlite3"
            connection = initialize_sqlite_database(path)
            command = SQLiteTranscriptCommandPersistence(connection)
            with patch.object(owner, target, side_effect=sqlite3.OperationalError("injected")):
                with self.assertRaises(PersistenceError):
                    command.persist_correction_candidate(candidate=self.candidate, result=self.result)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM correction_candidates").fetchone(), (0,))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM domain_result_references").fetchone(), (0,))
            connection.close()

        path = Path(self.temporary_directory.name) / "commit.sqlite3"
        connection = initialize_sqlite_database(path)
        command = SQLiteTranscriptCommandPersistence(connection)
        with patch.object(command, "_commit", side_effect=sqlite3.OperationalError("commit")):
            with self.assertRaises(PersistenceError):
                command.persist_correction_candidate(candidate=self.candidate, result=self.result)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM correction_candidates").fetchone(), (0,))
        self.assertFalse(connection.in_transaction)
        self.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))
        connection.close()

    def test_linkage_mismatch_and_v4_gate_do_not_mutate(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        command = SQLiteTranscriptCommandPersistence(connection)
        wrong = DomainResultReference(
            identity=DomainResultId("wrong"),
            kind="transcript_correction_candidate",
            upstream_results=(self.raw.domain_result_id,),
        )
        with self.assertRaises(PersistenceError):
            command.persist_correction_candidate(candidate=self.candidate, result=wrong)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM correction_candidates").fetchone(), (0,))
        connection.close()

        v4_path = Path(self.temporary_directory.name) / "v4.sqlite3"
        v4 = create_v4_database(v4_path)
        with self.assertRaises(SchemaFeatureUnavailableError):
            SQLiteTranscriptCommandPersistence(v4).persist_correction_candidate(
                candidate=self.candidate, result=self.result
            )
        self.assertEqual(v4.execute("SELECT version FROM schema_metadata").fetchone(), (4,))
        v4.close()


if __name__ == "__main__":
    unittest.main()
