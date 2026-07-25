import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.media_import import SourceMediaRecord, derive_media_identity
from lectureos.application.transcript_source_intake import (
    TranscriptSourceIntake,
    derive_intake_identity,
)
from lectureos.execution.identities import SourceMediaId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteSourceMediaCommandPersistence,
    SQLiteTranscriptSourceIntakeCommandPersistence,
    SQLiteTranscriptSourceIntakeRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError

_DIGEST = "1234567890abcdef" * 4


def _media(digest=_DIGEST):
    return SourceMediaRecord(
        identity=derive_media_identity("sha256", digest),
        fingerprint_algorithm="sha256",
        fingerprint_digest=digest,
        byte_length=42,
        observed_source_path="/abs/source.bin",
    )


def _intake(digest=_DIGEST):
    media = SourceMediaId(f"sha256:{digest}")
    return TranscriptSourceIntake(
        identity=derive_intake_identity(media), source_media_id=media
    )


class SQLiteAtomicTranscriptSourceIntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        # An intake FKs to source_media, so the media record must exist first.
        SQLiteSourceMediaCommandPersistence(self.connection).persist_source_media(
            record=_media()
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _persist(self, intake):
        SQLiteTranscriptSourceIntakeCommandPersistence(
            self.connection
        ).persist_transcript_source_intake(intake=intake)

    def test_persists_and_reconstructs(self) -> None:
        intake = _intake()
        self._persist(intake)
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteTranscriptSourceIntakeRepository(reopened)
            self.assertEqual(repo.get(intake.identity), intake)
            self.assertEqual(
                repo.get_by_source_media(intake.source_media_id), intake
            )
        finally:
            reopened.close()

    def test_identity_collision_rolls_back(self) -> None:
        self._persist(_intake())
        with self.assertRaises(PersistenceIdentityCollisionError):
            self._persist(_intake())
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM transcript_source_intakes"
            ).fetchone()[0],
            1,
        )

    def test_one_intake_per_source_media_enforced(self) -> None:
        self._persist(_intake())
        # A different intake identity for the same source media violates UNIQUE(source_media_id).
        media = SourceMediaId(f"sha256:{_DIGEST}")
        conflicting = TranscriptSourceIntake.__new__(TranscriptSourceIntake)
        object.__setattr__(conflicting, "identity", derive_intake_identity(media))
        object.__setattr__(conflicting, "source_media_id", media)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self._persist(conflicting)

    def test_dangling_source_media_rejected_by_foreign_key(self) -> None:
        # An intake referencing a source_media that was never imported must be rejected.
        with self.assertRaises(PersistenceError):
            self._persist(_intake(digest="f" * 64))

    def test_repository_rejects_pre_v31_schema(self) -> None:
        legacy_path = Path(self.tempdir.name) / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 31):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 30)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteTranscriptSourceIntakeRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
