"""Atomic SQLite persistence tests for Current Corrected Revision Selection (040 §20)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.corrected_revision_selection import (
    CorrectedRevisionSelection,
    SelectionKind,
    derive_selection_identity,
)
from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteCorrectedRevisionSelectionCommandPersistence,
    SQLiteCorrectedRevisionSelectionRepository,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError
from lectureos.review.identities import HumanActorReference
from lectureos.transcript.identities import TranscriptRevisionId


class SQLiteAtomicCorrectedRevisionSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"sel-atomic \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.intake.value,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.intake.value, raw.raw_transcript_id.value
        )
        raw_record = SQLiteRawTranscriptRepository(self.connection).get(raw.raw_transcript_id)
        segment = raw_record.segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(self.connection).get(segment).text
        candidate = compose_sqlite_correction_candidate_admission_service(self.connection).admit(
            intake_id=self.intake.value,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw.raw_transcript_id.value, "segment_id": segment.value,
                 "candidate_ref": "c1", "source_type": "manual", "source_reference": "human",
                 "proposed_text": "교정", "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate
        compose_sqlite_correction_candidate_decision_service(self.connection).decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="r:kim"
        )
        self.revision = compose_sqlite_corrected_revision_generation_service(self.connection).generate(
            candidate_id=candidate.identity.value
        ).revision.identity
        self.persistence = SQLiteCorrectedRevisionSelectionCommandPersistence(self.connection)
        self.repo = SQLiteCorrectedRevisionSelectionRepository(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _selection(self, kind, sequence, revision=None, previous=None):
        return CorrectedRevisionSelection(
            identity=derive_selection_identity(self.intake, kind, revision, sequence),
            transcript_source_intake_id=self.intake,
            kind=kind,
            reviewer=HumanActorReference("s:kim"),
            sequence=sequence,
            corrected_revision_id=revision,
            previous_selection_id=previous,
        )

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM corrected_revision_selections"
        ).fetchone()[0]

    def test_persist_read_current_and_history_after_restart(self):
        s0 = self._selection(SelectionKind.CORRECTED_REVISION, 0, revision=self.revision)
        self.persistence.persist_selection(selection=s0)
        s1 = self._selection(SelectionKind.RAW_FALLBACK, 1, previous=s0.identity)
        self.persistence.persist_selection(selection=s1)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteCorrectedRevisionSelectionRepository(reopened)
            self.assertEqual(repo.get(s0.identity), s0)
            self.assertEqual(repo.get_current(self.intake), s1)  # current derived from persisted state only
            self.assertEqual([s.kind for s in repo.history(self.intake)],
                             [SelectionKind.CORRECTED_REVISION, SelectionKind.RAW_FALLBACK])
        finally:
            reopened.close()

    def test_identity_collision_rolls_back(self):
        s0 = self._selection(SelectionKind.CORRECTED_REVISION, 0, revision=self.revision)
        self.persistence.persist_selection(selection=s0)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_selection(selection=s0)
        self.assertEqual(self._count(), 1)

    def test_sequence_collision_rolls_back(self):
        self.persistence.persist_selection(
            selection=self._selection(SelectionKind.CORRECTED_REVISION, 0, revision=self.revision)
        )
        clashing = self._selection(SelectionKind.RAW_FALLBACK, 0)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_selection(selection=clashing)
        self.assertEqual(self._count(), 1)

    def test_unknown_previous_supersession_rejected(self):
        s0 = self._selection(SelectionKind.CORRECTED_REVISION, 0, revision=self.revision)
        self.persistence.persist_selection(selection=s0)
        ghost = derive_selection_identity(self.intake, SelectionKind.RAW_FALLBACK, None, 7)
        bad = self._selection(SelectionKind.RAW_FALLBACK, 1, previous=ghost)
        with self.assertRaises(PersistenceError):
            self.persistence.persist_selection(selection=bad)
        self.assertEqual(self._count(), 1)

    def test_dangling_revision_rejected_by_foreign_key(self):
        ghost = TranscriptRevisionId("corrected-revision:" + "0" * 64)
        with self.assertRaises(PersistenceError):
            self.persistence.persist_selection(
                selection=self._selection(SelectionKind.CORRECTED_REVISION, 0, revision=ghost)
            )
        self.assertEqual(self._count(), 0)

    def test_repository_rejects_pre_v37_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 37):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 36)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteCorrectedRevisionSelectionRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
