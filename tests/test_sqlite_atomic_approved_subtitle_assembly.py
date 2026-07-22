import tempfile
import unittest
from pathlib import Path

from lectureos.application import (
    SubtitleApprovedAssemblyIdentityPlan,
    SubtitleExportEligibility,
)
from lectureos.application.identities import (
    SubtitleApprovedDocumentId,
    SubtitleApprovedUnitId,
    SubtitleTimeRevisionId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_approved_assembly_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleApprovedDocumentCommandPersistence,
    SQLiteSubtitleApprovedDocumentRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)

from lectureos.subtitle_approved_assembly_acceptance import build_persisted_documents


class SQLiteAtomicApprovedSubtitleAssemblyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        (
            self.execution,
            self.run_id,
            self.execution_id,
            self.reading,
            self.docs,
            self.time_ids,
        ) = build_persisted_documents(self.connection)

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_and_reconstructs_eligible_document(self) -> None:
        doc = self.docs[1]  # document B: accept + untouched
        self.assertIs(doc.document.eligibility, SubtitleExportEligibility.ELIGIBLE)
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteSubtitleApprovedDocumentRepository(reopened)
            self.assertEqual(repo.get(doc.document.identity), doc.document)
            for unit in doc.units:
                self.assertEqual(repo.get_unit(unit.identity), unit)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                doc.document_result.identity
            )
            self.assertEqual(result, doc.document_result)
        finally:
            reopened.close()

    def test_persists_and_reconstructs_ineligible_document(self) -> None:
        doc = self.docs[2]  # document C: ineligible, no units
        self.assertIs(doc.document.eligibility, SubtitleExportEligibility.INELIGIBLE)
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteSubtitleApprovedDocumentRepository(reopened)
            restored = repo.get(doc.document.identity)
            self.assertEqual(restored, doc.document)
            self.assertEqual(restored.approved_unit_ids, ())
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = self.docs
        self.connection.close()
        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            _, _, _, _, second, _ = build_persisted_documents(replay_connection)
            for a, b in zip(first, second):
                self.assertEqual(a.document, b.document)
                self.assertEqual(a.units, b.units)
        finally:
            replay_connection.close()

    def test_result_collision_rolls_back_document(self) -> None:
        service = compose_sqlite_subtitle_approved_assembly_service(
            self.connection, self.execution
        )
        # Reuse an existing DomainResult identity to force a collision on persist.
        plan = SubtitleApprovedAssemblyIdentityPlan(
            document_id=SubtitleApprovedDocumentId("collision-doc"),
            document_result_id=DomainResultId("asm-b-result"),  # time revision B's result id
            unit_ids=(
                SubtitleApprovedUnitId("c0"),
                SubtitleApprovedUnitId("c1"),
            ),
        )
        prepared = service.assemble(
            source_time_revision_id=self.time_ids[1],
            source_reading_revision_id=self.reading.revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=plan,
        )
        persistence = SQLiteSubtitleApprovedDocumentCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_approved_document(
                document=prepared.document,
                units=prepared.units,
                document_result=prepared.document_result,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_approved_documents WHERE identity = 'collision-doc'"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_approved_units WHERE identity IN ('c0', 'c1')"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
