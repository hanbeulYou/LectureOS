import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lectureos.application import (
    CorrectionCandidateIdentityPlan,
    CorrectionGenerationIdentityPlan,
    CorrectionProposal,
    TranscriptCorrectionGenerationService,
)
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
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
    SQLiteCorrectionCandidateRepository,
    SQLiteCorrectedTranscriptRevisionRepository,
    SQLiteDomainResultReferenceRepository,
    SQLiteTranscriptCommandPersistence,
    SQLiteTranscriptSegmentRepository,
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
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
    TranscriptValidation,
)
from lectureos.transcript.validation import TranscriptValidationService


class FakeCorrectionCapability:
    def __init__(self, proposals) -> None:
        self.proposals = proposals
        self.requests = []

    def generate_corrections(self, request):
        self.requests.append(request)
        return self.proposals


class RecordingGeneratedPersistence:
    def __init__(self, error=None) -> None:
        self.calls = []
        self.error = error

    def persist_generated_correction(self, **kwargs) -> None:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error


class RecordingStructuralValidation:
    def __init__(self, *, structural_valid=False, error=None, events=None) -> None:
        self.structural_valid = structural_valid
        self.error = error
        self.events = events
        self.calls = []

    def validate_corrected_revision(self, **kwargs):
        self.calls.append(kwargs)
        if self.events is not None:
            self.events.append("validate")
        if self.error is not None:
            raise self.error
        return TranscriptValidation(
            identity=kwargs["validation_id"],
            run_id=kwargs["run_id"],
            unit_execution_id=kwargs["unit_execution_id"],
            structural_valid=self.structural_valid,
            timeline_traceable=self.structural_valid,
            provenance_complete=self.structural_valid,
            target_revision_id=kwargs["revision_id"],
        )


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


class SQLiteAtomicGeneratedCorrectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.unit_id = ProcessingUnitId("unit")
        self.media_id = SourceMediaId("media")
        self.timeline_id = SourceTimelineId("timeline")
        self.capability = CapabilityReference("transcript.correction")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _seed(self, connection):
        execution = compose_sqlite_execution_service(connection)
        execution.register_unit(
            ProcessingUnit(
                identity=self.unit_id,
                purpose="correct transcript",
                capabilities=(self.capability,),
            )
        )
        execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("correct transcript"),
            working_context=WorkingContextReference("context"),
            unit_ids=(self.unit_id,),
        )
        execution.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit_id,
        )
        transcripts = compose_sqlite_transcript_service(connection, execution)
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
        raw = RawTranscript(
            identity=TranscriptId("raw"),
            domain_result_id=DomainResultId("raw-result"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(TranscriptSegmentId("source-0"), TranscriptSegmentId("source-1")),
        )
        segments = tuple(
            TranscriptSegment(
                identity=identity,
                transcript_id=raw.identity,
                source_timeline_id=self.timeline_id,
                text=f"wrong {index}",
                source_order=index,
                start=float(index),
                end=float(index + 1),
            )
            for index, identity in enumerate(raw.segment_ids)
        )
        transcripts.register_provider_result(provider)
        transcripts.create_raw_transcript(raw, segments)
        return execution, transcripts, raw, segments

    def _plan(self):
        return CorrectionGenerationIdentityPlan(
            candidates=(
                CorrectionCandidateIdentityPlan(
                    CorrectionCandidateId("candidate"),
                    DomainResultId("candidate-result"),
                    TranscriptSegmentId("replacement"),
                ),
            ),
            revision_id=TranscriptRevisionId("revision"),
            revision_result_id=DomainResultId("revision-result"),
            validation_id=TranscriptValidationId("validation"),
        )

    def _proposal(self, target):
        return CorrectionProposal(
            target_segment_id=target,
            proposed_text="corrected",
            rationale="recognition correction",
            evidence=("evidence",),
            uncertainty=0.2,
        )

    def _service(
        self,
        connection,
        execution,
        transcripts,
        proposal,
        persistence=None,
        validation=None,
    ):
        command = persistence or SQLiteTranscriptCommandPersistence(connection)
        validator = validation
        if validator is None:
            validator = (
                TranscriptValidationService(transcripts, execution)
                if not isinstance(command, RecordingGeneratedPersistence)
                else RecordingStructuralValidation(structural_valid=True)
            )
        return TranscriptCorrectionGenerationService(
            transcripts,
            execution,
            FakeCorrectionCapability((proposal,)),
            command,
            validator,
        )

    def _generate(self, service, raw):
        return service.generate_correction(
            transcript_id=raw.identity,
            parent_revision_id=None,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=self.capability,
            identities=self._plan(),
        )

    def test_service_invokes_atomic_port_once_with_exact_records(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        execution, transcripts, raw, segments = self._seed(connection)
        port = RecordingGeneratedPersistence()
        prepared = self._generate(
            self._service(connection, execution, transcripts, self._proposal(segments[0].identity), port),
            raw,
        )
        self.assertEqual(len(port.calls), 1)
        self.assertEqual(port.calls[0]["candidates"], prepared.candidates)
        self.assertEqual(port.calls[0]["replacement_segments"], prepared.replacement_segments)
        self.assertEqual(port.calls[0]["revision"], prepared.revision)
        self.assertTrue(prepared.validation.structural_valid)
        self.assertIsNone(transcripts.get_candidate(prepared.candidates[0].identity))
        connection.close()

    def test_structurally_invalid_result_is_returned_without_approval(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        execution, transcripts, raw, segments = self._seed(connection)
        validation = RecordingStructuralValidation(structural_valid=False)
        prepared = self._generate(
            self._service(
                connection,
                execution,
                transcripts,
                self._proposal(segments[0].identity),
                RecordingGeneratedPersistence(),
                validation,
            ),
            raw,
        )
        self.assertFalse(prepared.validation.structural_valid)
        self.assertIsNone(prepared.revision.decision_reference)
        self.assertIsNone(prepared.revision.validation_id)
        self.assertEqual(len(validation.calls), 1)
        connection.close()

    def test_validation_failure_propagates_after_canonical_commit(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        execution, transcripts, raw, segments = self._seed(connection)
        validation = RecordingStructuralValidation(error=RuntimeError("validation failed"))
        service = self._service(
            connection,
            execution,
            transcripts,
            self._proposal(segments[0].identity),
            SQLiteTranscriptCommandPersistence(connection),
            validation,
        )
        with self.assertRaisesRegex(RuntimeError, "validation failed"):
            self._generate(service, raw)
        self.assertIsNotNone(
            SQLiteCorrectionCandidateRepository(connection).get(
                CorrectionCandidateId("candidate")
            )
        )
        self.assertIsNotNone(
            SQLiteCorrectedTranscriptRevisionRepository(connection).get(
                TranscriptRevisionId("revision")
            )
        )
        self.assertFalse(connection.in_transaction)
        connection.close()

    def test_zero_proposals_does_not_invoke_persistence(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        execution, transcripts, raw, _ = self._seed(connection)
        port = RecordingGeneratedPersistence()
        service = TranscriptCorrectionGenerationService(
            transcripts,
            execution,
            FakeCorrectionCapability(()),
            port,
            TranscriptValidationService(transcripts, execution),
        )
        empty_plan = replace(self._plan(), candidates=())
        prepared = service.generate_correction(
            transcript_id=raw.identity,
            parent_revision_id=None,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=self.capability,
            identities=empty_plan,
        )
        self.assertIsNone(prepared.revision)
        self.assertIsNone(prepared.validation)
        self.assertEqual(port.calls, [])
        connection.close()

    def test_schema_v4_rejects_command_without_migration(self) -> None:
        connection = create_v4_database(self.database_path)
        command = SQLiteTranscriptCommandPersistence(connection)
        with self.assertRaises(SchemaFeatureUnavailableError):
            command.persist_generated_correction(
                candidates=(),
                candidate_results=(),
                replacement_segments=(),
                revision=None,
                revision_result=None,
            )
        self.assertEqual(
            connection.execute("SELECT version FROM schema_metadata").fetchone()[0], 4
        )
        self.assertFalse(connection.in_transaction)
        connection.close()

    def test_atomic_success_restarts_with_exact_records(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        execution, transcripts, raw, segments = self._seed(connection)
        prepared = self._generate(
            self._service(connection, execution, transcripts, self._proposal(segments[0].identity)),
            raw,
        )
        self.assertFalse(connection.in_transaction)
        self.assertTrue(prepared.validation.structural_valid)
        connection.close()

        reopened = open_sqlite_database(self.database_path)
        self.assertEqual(
            SQLiteCorrectionCandidateRepository(reopened).get(prepared.candidates[0].identity),
            prepared.candidates[0],
        )
        self.assertEqual(
            SQLiteTranscriptSegmentRepository(reopened).get(
                prepared.replacement_segments[0].identity
            ),
            prepared.replacement_segments[0],
        )
        self.assertEqual(
            SQLiteCorrectedTranscriptRevisionRepository(reopened).get(
                prepared.revision.identity
            ),
            prepared.revision,
        )
        results = SQLiteDomainResultReferenceRepository(reopened)
        self.assertEqual(results.get(prepared.candidate_results[0].identity), prepared.candidate_results[0])
        self.assertEqual(results.get(prepared.revision_result.identity), prepared.revision_result)
        reopened.close()

    def test_collision_rolls_back_complete_command(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        execution, transcripts, raw, segments = self._seed(connection)
        service = self._service(
            connection, execution, transcripts, self._proposal(segments[0].identity)
        )
        prepared = service.prepare_correction(
            transcript_id=raw.identity,
            parent_revision_id=None,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=self.capability,
            identities=self._plan(),
        )
        SQLiteCorrectionCandidateRepository(connection).save(prepared.candidates[0])
        with self.assertRaises(PersistenceIdentityCollisionError):
            SQLiteTranscriptCommandPersistence(connection).persist_generated_correction(
                candidates=prepared.candidates,
                candidate_results=prepared.candidate_results,
                replacement_segments=prepared.replacement_segments,
                revision=prepared.revision,
                revision_result=prepared.revision_result,
            )
        self.assertIsNone(
            SQLiteCorrectedTranscriptRevisionRepository(connection).get(prepared.revision.identity)
        )
        self.assertIsNone(
            SQLiteTranscriptSegmentRepository(connection).get(prepared.replacement_segments[0].identity)
        )
        connection.close()

    def test_late_write_and_commit_failures_roll_back(self) -> None:
        for target in ("_insert_corrected_transcript_revision", "_commit"):
            with self.subTest(target=target):
                path = Path(self.temporary_directory.name) / f"{target}.sqlite3"
                connection = initialize_sqlite_database(path)
                execution, transcripts, raw, segments = self._seed(connection)
                command = SQLiteTranscriptCommandPersistence(connection)
                service = self._service(
                    connection,
                    execution,
                    transcripts,
                    self._proposal(segments[0].identity),
                    command,
                )
                patch_target = (
                    patch.object(
                        transcript_commands,
                        "_insert_corrected_transcript_revision",
                        side_effect=sqlite3.OperationalError("injected"),
                    )
                    if target.startswith("_insert")
                    else patch.object(
                        command,
                        "_commit",
                        side_effect=sqlite3.OperationalError("injected"),
                    )
                )
                with patch_target:
                    with self.assertRaises(PersistenceError):
                        self._generate(service, raw)
                self.assertFalse(connection.in_transaction)
                self.assertIsNone(
                    SQLiteCorrectionCandidateRepository(connection).get(
                        CorrectionCandidateId("candidate")
                    )
                )
                self.assertIsNone(
                    SQLiteCorrectedTranscriptRevisionRepository(connection).get(
                        TranscriptRevisionId("revision")
                    )
                )
                self.assertIsNotNone(transcripts.get_raw_transcript(raw.identity))
                connection.close()

    def test_linkage_mismatch_rolls_back_without_raw_sql_error(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        execution, transcripts, raw, segments = self._seed(connection)
        service = self._service(
            connection, execution, transcripts, self._proposal(segments[0].identity)
        )
        prepared = service.prepare_correction(
            transcript_id=raw.identity,
            parent_revision_id=None,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=self.capability,
            identities=self._plan(),
        )
        bad_revision = replace(prepared.revision, correction_candidate_ids=())
        with self.assertRaises(PersistenceError):
            SQLiteTranscriptCommandPersistence(connection).persist_generated_correction(
                candidates=prepared.candidates,
                candidate_results=prepared.candidate_results,
                replacement_segments=prepared.replacement_segments,
                revision=bad_revision,
                revision_result=prepared.revision_result,
            )
        self.assertFalse(connection.in_transaction)
        self.assertIsNone(
            SQLiteCorrectionCandidateRepository(connection).get(prepared.candidates[0].identity)
        )
        connection.close()

    def test_unknown_parent_target_and_wrong_upstream_are_rejected(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        execution, transcripts, raw, segments = self._seed(connection)
        service = self._service(
            connection, execution, transcripts, self._proposal(segments[0].identity)
        )
        prepared = service.prepare_correction(
            transcript_id=raw.identity,
            parent_revision_id=None,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=self.capability,
            identities=self._plan(),
        )
        command = SQLiteTranscriptCommandPersistence(connection)
        unknown = TranscriptSegmentId("unknown-parent-target")
        with self.assertRaises(PersistenceError):
            command.persist_generated_correction(
                candidates=(replace(prepared.candidates[0], segment_id=unknown),),
                candidate_results=prepared.candidate_results,
                replacement_segments=(
                    replace(prepared.replacement_segments[0], replaces_segment_id=unknown),
                ),
                revision=prepared.revision,
                revision_result=prepared.revision_result,
            )
        with self.assertRaises(PersistenceError):
            command.persist_generated_correction(
                candidates=prepared.candidates,
                candidate_results=(
                    replace(
                        prepared.candidate_results[0],
                        upstream_results=(DomainResultId("wrong-upstream"),),
                    ),
                ),
                replacement_segments=prepared.replacement_segments,
                revision=prepared.revision,
                revision_result=replace(
                    prepared.revision_result,
                    upstream_results=(DomainResultId("wrong-upstream"),),
                ),
            )
        self.assertFalse(connection.in_transaction)
        self.assertIsNone(
            SQLiteCorrectionCandidateRepository(connection).get(
                prepared.candidates[0].identity
            )
        )
        connection.close()


if __name__ == "__main__":
    unittest.main()
