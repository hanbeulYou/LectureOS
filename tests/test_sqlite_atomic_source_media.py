import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.media_import import (
    SourceMediaRecord,
    derive_media_identity,
)
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteSourceMediaCommandPersistence,
    SQLiteSourceMediaRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import SchemaFeatureUnavailableError

_DIGEST = "1234567890abcdef" * 4


def _record(digest=_DIGEST, byte_length=42, path="/abs/source.bin"):
    return SourceMediaRecord(
        identity=derive_media_identity("sha256", digest),
        fingerprint_algorithm="sha256",
        fingerprint_digest=digest,
        byte_length=byte_length,
        observed_source_path=path,
    )


class SQLiteAtomicSourceMediaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _persist(self, record):
        SQLiteSourceMediaCommandPersistence(self.connection).persist_source_media(
            record=record
        )

    def test_persists_and_reconstructs(self) -> None:
        record = _record()
        self._persist(record)
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteSourceMediaRepository(reopened)
            self.assertEqual(repo.get(record.identity), record)
            self.assertEqual(
                repo.get_by_fingerprint("sha256", _DIGEST), record
            )
        finally:
            reopened.close()

    def test_identity_collision_is_reported_and_rolls_back(self) -> None:
        self._persist(_record())
        # A second insert of the same identity must fail without a second row.
        with self.assertRaises(PersistenceIdentityCollisionError):
            self._persist(_record(path="/abs/other.bin"))
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM source_media").fetchone()[0],
            1,
        )

    def test_fingerprint_uniqueness_enforced(self) -> None:
        self._persist(_record())
        # Even a different identity string cannot share the fingerprint (UNIQUE algorithm+digest).
        conflicting = SourceMediaRecord.__new__(SourceMediaRecord)
        object.__setattr__(conflicting, "identity", derive_media_identity("sha256", _DIGEST))
        object.__setattr__(conflicting, "fingerprint_algorithm", "sha256")
        object.__setattr__(conflicting, "fingerprint_digest", _DIGEST)
        object.__setattr__(conflicting, "byte_length", 99)
        object.__setattr__(conflicting, "observed_source_path", "/abs/dup.bin")
        with self.assertRaises(PersistenceIdentityCollisionError):
            self._persist(conflicting)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM source_media").fetchone()[0],
            1,
        )

    def test_two_distinct_contents_coexist(self) -> None:
        self._persist(_record(digest="a" * 64))
        self._persist(_record(digest="b" * 64))
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM source_media").fetchone()[0],
            2,
        )

    def test_repository_rejects_pre_v30_schema(self) -> None:
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
        connection.execute("INSERT INTO schema_metadata VALUES (1, 29)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteSourceMediaRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
