import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lectureos.execution.identities import (
    CapabilityReference,
    DiagnosticId,
    PluginReference,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.persistence import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SQLiteProviderTranscriptResultRepository,
    SQLiteTranscriptSegmentRepository,
    SchemaFeatureUnavailableError,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence import provider_transcripts, sqlite as sqlite_lifecycle
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import ProviderTranscriptResult, TranscriptSegment


def create_legacy_database(path: Path, version: int) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys = ON")
    statements = list(sqlite_lifecycle._V1_TABLE_STATEMENTS)
    if version >= 2:
        statements.extend(sqlite_lifecycle._V2_ADDITION_STATEMENTS)
    if version >= 3:
        statements.extend(sqlite_lifecycle._V3_ADDITION_STATEMENTS)
    if version >= 4:
        statements.extend(sqlite_lifecycle._V4_ADDITION_STATEMENTS)
    connection.execute("BEGIN")
    for statement in statements:
        connection.execute(statement)
    connection.execute("INSERT INTO schema_metadata VALUES (1, ?)", (version,))
    connection.execute("COMMIT")
    return connection


class SQLiteTranscriptSourceRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def _provider() -> ProviderTranscriptResult:
        return ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("provider-result"),
            source_media_id=SourceMediaId("media"),
            source_timeline_id=SourceTimelineId("timeline"),
            run_id=ProcessingRunId("run"),
            unit_execution_id=UnitExecutionId("execution"),
            capability=CapabilityReference("speech.transcription"),
            provider_reference="provider:model",
            original_content='{"segments":[]}',
            plugin_reference=PluginReference("plugin"),
            diagnostic_references=(
                DiagnosticId("diagnostic-b"),
                DiagnosticId("diagnostic-a"),
                DiagnosticId("diagnostic-b"),
            ),
            uncertainty=0.125,
        )

    @staticmethod
    def _segment() -> TranscriptSegment:
        return TranscriptSegment(
            identity=TranscriptSegmentId("segment"),
            transcript_id=TranscriptId("transcript"),
            source_timeline_id=SourceTimelineId("timeline"),
            text="exact provider text",
            source_order=3,
            start=1.25,
            end=2.75,
            speaker_label="speaker",
            confidence=0.9,
            uncertainty=0.1,
            replaces_segment_id=TranscriptSegmentId("previous-segment"),
        )

    def test_schema_v1_through_v4_reject_both_repositories_without_migration(self) -> None:
        for version in (1, 2, 3, 4):
            with self.subTest(version=version):
                path = Path(self.temporary_directory.name) / f"v{version}.sqlite3"
                connection = create_legacy_database(path, version)
                with self.assertRaises(SchemaFeatureUnavailableError):
                    SQLiteProviderTranscriptResultRepository(connection)
                with self.assertRaises(SchemaFeatureUnavailableError):
                    SQLiteTranscriptSegmentRepository(connection)
                self.assertEqual(
                    connection.execute("SELECT version FROM schema_metadata").fetchone(),
                    (version,),
                )
                connection.close()

    def test_provider_result_full_round_trip_preserves_order_and_duplicates(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        repository = SQLiteProviderTranscriptResultRepository(connection)
        record = self._provider()
        repository.save(record)
        self.assertEqual(repository.get(record.identity), record)
        self.assertEqual(
            connection.execute(
                """SELECT ordinal, diagnostic_id
                FROM provider_transcript_result_diagnostics
                ORDER BY ordinal"""
            ).fetchall(),
            [(0, "diagnostic-b"), (1, "diagnostic-a"), (2, "diagnostic-b")],
        )
        connection.close()

    def test_provider_result_empty_optional_fields_and_children_round_trip(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        repository = SQLiteProviderTranscriptResultRepository(connection)
        record = replace(
            self._provider(),
            plugin_reference=None,
            diagnostic_references=(),
            uncertainty=None,
        )
        repository.save(record)
        self.assertEqual(repository.get(record.identity), record)
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM provider_transcript_result_diagnostics"
            ).fetchone(),
            (0,),
        )
        connection.close()

    def test_segment_full_and_untimed_round_trip(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        repository = SQLiteTranscriptSegmentRepository(connection)
        timed = self._segment()
        untimed = TranscriptSegment(
            identity=TranscriptSegmentId("untimed"),
            transcript_id=timed.transcript_id,
            source_timeline_id=None,
            text="",
            source_order=4,
        )
        repository.save(timed)
        repository.save(untimed)
        self.assertEqual(repository.get(timed.identity), timed)
        self.assertEqual(repository.get(untimed.identity), untimed)
        connection.close()

    def test_unknown_identity_returns_none(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        self.assertIsNone(
            SQLiteProviderTranscriptResultRepository(connection).get(
                ProviderTranscriptResultId("missing")
            )
        )
        self.assertIsNone(
            SQLiteTranscriptSegmentRepository(connection).get(
                TranscriptSegmentId("missing")
            )
        )
        connection.close()

    def test_identical_and_conflicting_duplicate_saves_are_collisions(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        providers = SQLiteProviderTranscriptResultRepository(connection)
        segments = SQLiteTranscriptSegmentRepository(connection)
        provider = self._provider()
        segment = self._segment()
        providers.save(provider)
        segments.save(segment)
        for duplicate in (provider, replace(provider, original_content="changed")):
            with self.assertRaises(PersistenceIdentityCollisionError):
                providers.save(duplicate)
        for duplicate in (segment, replace(segment, text="changed")):
            with self.assertRaises(PersistenceIdentityCollisionError):
                segments.save(duplicate)
        self.assertEqual(providers.get(provider.identity), provider)
        self.assertEqual(segments.get(segment.identity), segment)
        connection.close()

    def test_provider_child_failure_rolls_back_parent_and_preserves_existing(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        repository = SQLiteProviderTranscriptResultRepository(connection)
        existing = replace(
            self._provider(), identity=ProviderTranscriptResultId("existing")
        )
        repository.save(existing)
        with patch.object(
            provider_transcripts,
            "_insert_provider_diagnostics",
            side_effect=sqlite3.OperationalError("injected child failure"),
        ):
            with self.assertRaises(PersistenceError):
                repository.save(self._provider())
        self.assertIsNone(repository.get(self._provider().identity))
        self.assertEqual(repository.get(existing.identity), existing)
        self.assertFalse(connection.in_transaction)
        self.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))
        connection.close()

    def test_records_survive_restart_and_connection_remains_caller_owned(self) -> None:
        connection = initialize_sqlite_database(self.database_path)
        provider = self._provider()
        segment = self._segment()
        SQLiteProviderTranscriptResultRepository(connection).save(provider)
        SQLiteTranscriptSegmentRepository(connection).save(segment)
        self.assertEqual(connection.execute("SELECT 1").fetchone(), (1,))
        connection.close()

        reopened = open_sqlite_database(self.database_path)
        self.assertEqual(
            SQLiteProviderTranscriptResultRepository(reopened).get(provider.identity),
            provider,
        )
        self.assertEqual(
            SQLiteTranscriptSegmentRepository(reopened).get(segment.identity),
            segment,
        )
        reopened.close()


if __name__ == "__main__":
    unittest.main()
