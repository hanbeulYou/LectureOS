"""Atomic SQLite persistence tests for Current Raw Transcript Selection (040 §16)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.current_raw_transcript_selection import (
    CurrentRawTranscriptSelection,
    derive_selection_identity,
)
from lectureos.application.identities import TranscriptSourceIntakeId
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteRawTranscriptSelectionCommandPersistence,
    SQLiteRawTranscriptSelectionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError
from lectureos.transcript.identities import TranscriptId


def _doc(ref):
    return build_provider_transcript_document(
        {"provider": "fake", "model": "tiny", "language": "ko",
         "provider_result_ref": ref, "segments": [{"start": 0.0, "end": 1.0, "text": "가"}]}
    )


class SQLiteAtomicRawTranscriptSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"selection-atomic \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake
        admit = compose_sqlite_provider_transcript_admission_service(self.connection)
        self.raw_a = admit.admit(intake_id=self.intake.identity.value, document=_doc("ref-A")).admission.raw_transcript_id
        self.raw_b = admit.admit(intake_id=self.intake.identity.value, document=_doc("ref-B")).admission.raw_transcript_id
        self.persistence = SQLiteRawTranscriptSelectionCommandPersistence(self.connection)
        self.repo = SQLiteRawTranscriptSelectionRepository(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _selection(self, raw, sequence, previous=None, reason=None):
        return CurrentRawTranscriptSelection(
            identity=derive_selection_identity(self.intake.identity, raw, sequence),
            transcript_source_intake_id=self.intake.identity,
            raw_transcript_id=raw,
            sequence=sequence,
            previous_selection_id=previous,
            reason=reason,
        )

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM current_raw_transcript_selections"
        ).fetchone()[0]

    def test_persist_and_read_current(self):
        s0 = self._selection(self.raw_a, 0)
        self.persistence.persist_selection(selection=s0)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteRawTranscriptSelectionRepository(reopened)
            self.assertEqual(repo.get(s0.identity), s0)
            self.assertEqual(repo.get_current(self.intake.identity), s0)
            self.assertEqual(len(repo.candidates(self.intake.identity)), 2)
            self.assertEqual(repo.owning_intake(self.raw_a), self.intake.identity)
        finally:
            reopened.close()

    def test_candidates_ordered_by_identity(self):
        ids = [c.raw_transcript_id.value for c in self.repo.candidates(self.intake.identity)]
        self.assertEqual(ids, sorted(ids))

    def test_append_switch_advances_current(self):
        s0 = self._selection(self.raw_a, 0)
        self.persistence.persist_selection(selection=s0)
        s1 = self._selection(self.raw_b, 1, previous=s0.identity, reason="switch")
        self.persistence.persist_selection(selection=s1)
        self.assertEqual(self.repo.get_current(self.intake.identity).raw_transcript_id, self.raw_b)
        self.assertEqual(self._count(), 2)  # history preserved

    def test_identity_collision_rolls_back(self):
        s0 = self._selection(self.raw_a, 0)
        self.persistence.persist_selection(selection=s0)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_selection(selection=s0)
        self.assertEqual(self._count(), 1)

    def test_sequence_collision_rolls_back(self):
        self.persistence.persist_selection(selection=self._selection(self.raw_a, 0))
        # A different raw transcript but the same (intake, sequence) violates UNIQUE.
        clashing = self._selection(self.raw_b, 0)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_selection(selection=clashing)
        self.assertEqual(self._count(), 1)

    def test_unknown_previous_supersession_rejected(self):
        s0 = self._selection(self.raw_a, 0)
        self.persistence.persist_selection(selection=s0)
        ghost = derive_selection_identity(self.intake.identity, self.raw_b, 5)
        bad = self._selection(self.raw_b, 1, previous=ghost)
        with self.assertRaises(PersistenceError):
            self.persistence.persist_selection(selection=bad)
        self.assertEqual(self._count(), 1)

    def test_dangling_raw_transcript_rejected_by_foreign_key(self):
        ghost = TranscriptId("raw-transcript:" + "0" * 64)
        with self.assertRaises(PersistenceError):
            self.persistence.persist_selection(selection=self._selection(ghost, 0))
        self.assertEqual(self._count(), 0)

    def test_dangling_intake_rejected_by_foreign_key(self):
        other = TranscriptSourceIntakeId("transcript-source-intake:sha256:" + "f" * 64)
        selection = CurrentRawTranscriptSelection(
            identity=derive_selection_identity(other, self.raw_a, 0),
            transcript_source_intake_id=other,
            raw_transcript_id=self.raw_a,
            sequence=0,
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_selection(selection=selection)
        self.assertEqual(self._count(), 0)

    def test_repository_rejects_pre_v33_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 33):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 32)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteRawTranscriptSelectionRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
