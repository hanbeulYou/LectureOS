import sqlite3
import tempfile
import unittest
from dataclasses import fields
from enum import Enum
from pathlib import Path

from lectureos.execution.identities import CapabilityReference, ProcessingUnitId
from lectureos.execution.models import ProcessingUnit
from lectureos.persistence import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SQLITE_SCHEMA_VERSION,
    SQLiteProcessingUnitRepository,
    UnsupportedSchemaVersionError,
    initialize_sqlite_database,
    open_sqlite_database,
)


class SQLiteLifecycleTests(unittest.TestCase):
    def test_relative_path_is_rejected(self) -> None:
        with self.assertRaises(PersistenceError):
            initialize_sqlite_database("relative.sqlite3")

    def test_memory_and_uri_paths_are_rejected(self) -> None:
        for path in (":memory:", "file:/tmp/lectureos.sqlite3"):
            with self.subTest(path=path), self.assertRaises(PersistenceError):
                initialize_sqlite_database(path)

    def test_missing_parent_is_rejected_without_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            parent = Path(temporary_directory) / "missing"
            with self.assertRaises(PersistenceError):
                initialize_sqlite_database(parent / "lectureos.sqlite3")
            self.assertFalse(parent.exists())

    def test_initializer_creates_version_one_and_enables_foreign_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "lectureos.sqlite3"
            connection = initialize_sqlite_database(path)
            try:
                self.assertTrue(path.is_file())
                self.assertEqual(SQLITE_SCHEMA_VERSION, 1)
                self.assertEqual(
                    connection.execute(
                        "SELECT version FROM schema_metadata WHERE singleton = 1"
                    ).fetchone(),
                    (1,),
                )
                self.assertEqual(
                    connection.execute("PRAGMA foreign_keys").fetchone(), (1,)
                )
            finally:
                connection.close()

    def test_supported_schema_reopens_and_connection_is_caller_owned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "lectureos.sqlite3"
            initialize_sqlite_database(path).close()
            connection = open_sqlite_database(path)
            connection.close()
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")

    def test_unsupported_schema_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "lectureos.sqlite3"
            connection = initialize_sqlite_database(path)
            connection.execute("UPDATE schema_metadata SET version = 2")
            connection.close()
            with self.assertRaises(UnsupportedSchemaVersionError):
                open_sqlite_database(path)

    def test_repository_does_not_initialize_an_empty_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "empty.sqlite3"
            path.touch()
            with self.assertRaises(PersistenceError):
                open_sqlite_database(path)
            raw_connection = sqlite3.connect(path, isolation_level=None)
            raw_connection.execute("PRAGMA foreign_keys = ON")
            try:
                with self.assertRaises(PersistenceError):
                    SQLiteProcessingUnitRepository(raw_connection)
            finally:
                raw_connection.close()

    def test_malformed_version_one_schema_is_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "malformed.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute(
                "CREATE TABLE schema_metadata(singleton INTEGER, version INTEGER)"
            )
            connection.execute("INSERT INTO schema_metadata VALUES (1, 1)")
            connection.commit()
            connection.close()
            with self.assertRaises(PersistenceError):
                open_sqlite_database(path)


class SQLiteProcessingUnitRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "lectureos.sqlite3"
        )
        self.connection = initialize_sqlite_database(self.database_path)
        self.repository = SQLiteProcessingUnitRepository(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def _unit(self, identity: str = "unit-transcribe") -> ProcessingUnit:
        return ProcessingUnit(
            identity=ProcessingUnitId(identity),
            purpose="Create a provider transcript result",
            dependencies=(ProcessingUnitId("unit-source"), ProcessingUnitId("unit-audio")),
            capabilities=(
                CapabilityReference("speech-recognition"),
                CapabilityReference("timestamps"),
            ),
            result_kinds=("provider_transcript", "diagnostic"),
            independently_retryable=False,
        )

    def test_insert_and_read_preserves_exact_model_and_typed_values(self) -> None:
        expected = self._unit()
        self.repository.save(expected)
        restored = self.repository.get(expected.identity)
        self.assertEqual(restored, expected)
        self.assertIsInstance(restored.identity, ProcessingUnitId)
        self.assertTrue(
            all(isinstance(item, ProcessingUnitId) for item in restored.dependencies)
        )
        self.assertTrue(
            all(isinstance(item, CapabilityReference) for item in restored.capabilities)
        )
        self.assertEqual(restored.dependencies, expected.dependencies)
        self.assertEqual(restored.capabilities, expected.capabilities)
        self.assertEqual(restored.result_kinds, expected.result_kinds)
        self.assertIs(restored.independently_retryable, False)

    def test_record_survives_connection_restart(self) -> None:
        expected = self._unit()
        self.repository.save(expected)
        self.connection.close()
        self.connection = open_sqlite_database(self.database_path)
        self.repository = SQLiteProcessingUnitRepository(self.connection)
        self.assertEqual(self.repository.get(expected.identity), expected)

    def test_multiple_units_are_listed_in_insertion_order(self) -> None:
        first = self._unit("unit-first")
        second = ProcessingUnit(
            identity=ProcessingUnitId("unit-second"),
            purpose="Second unit",
            independently_retryable=True,
        )
        self.repository.save(first)
        self.repository.save(second)
        self.assertEqual(self.repository.all(), (first, second))

    def test_duplicate_identity_is_never_idempotent(self) -> None:
        original = self._unit()
        self.repository.save(original)
        for duplicate in (
            original,
            ProcessingUnit(identity=original.identity, purpose="Different content"),
        ):
            with self.assertRaises(PersistenceIdentityCollisionError):
                self.repository.save(duplicate)
        self.assertEqual(self.repository.all(), (original,))

    def test_missing_identity_matches_protocol(self) -> None:
        self.assertIsNone(self.repository.get(ProcessingUnitId("missing")))

    def test_no_update_or_delete_api_is_exposed(self) -> None:
        self.assertFalse(hasattr(self.repository, "update"))
        self.assertFalse(hasattr(self.repository, "delete"))

    def test_parent_insert_failure_rolls_back_and_maps_sqlite_error(self) -> None:
        self.connection.execute(
            """
            CREATE TRIGGER reject_processing_unit
            BEFORE INSERT ON processing_units
            BEGIN SELECT RAISE(ABORT, 'injected parent failure'); END
            """
        )
        with self.assertRaises(PersistenceError) as caught:
            self.repository.save(self._unit())
        self.assertNotIsInstance(caught.exception, sqlite3.Error)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM processing_units").fetchone(),
            (0,),
        )

    def test_child_insert_failure_leaves_no_partial_processing_unit(self) -> None:
        self.connection.execute(
            """
            CREATE TRIGGER reject_capability
            BEFORE INSERT ON processing_unit_capabilities
            BEGIN SELECT RAISE(ABORT, 'injected child failure'); END
            """
        )
        with self.assertRaises(PersistenceError):
            self.repository.save(self._unit())
        for table in (
            "processing_units",
            "processing_unit_dependencies",
            "processing_unit_capabilities",
            "processing_unit_result_kinds",
        ):
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone(),
                (0,),
            )

    def test_unknown_stored_scalar_value_fails_explicitly(self) -> None:
        self.connection.execute("PRAGMA ignore_check_constraints = ON")
        self.connection.execute(
            "INSERT INTO processing_units VALUES (?, ?, ?)",
            ("corrupt-unit", "Corrupt", 2),
        )
        self.connection.execute("PRAGMA ignore_check_constraints = OFF")
        with self.assertRaises(PersistenceError):
            self.repository.get(ProcessingUnitId("corrupt-unit"))

    def test_corrupt_child_ordinal_sequence_fails_explicitly(self) -> None:
        unit = self._unit()
        self.repository.save(unit)
        self.connection.execute(
            """
            DELETE FROM processing_unit_dependencies
            WHERE processing_unit_id = ? AND ordinal = 0
            """,
            (unit.identity.value,),
        )
        with self.assertRaises(PersistenceError):
            self.repository.get(unit.identity)

    def test_processing_unit_currently_has_no_enum_serialization(self) -> None:
        unit = self._unit()
        self.assertFalse(any(isinstance(getattr(unit, field.name), Enum) for field in fields(unit)))


if __name__ == "__main__":
    unittest.main()
