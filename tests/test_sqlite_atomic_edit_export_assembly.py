import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.edit_export_assembly import (
    EditExportAssemblyIdentityPlan,
)
from lectureos.application.identities import EditExportAssemblyId
from lectureos.composition import compose_sqlite_edit_export_assembly_service
from lectureos.edit_export_acceptance import (
    _ACCEPT_DECISION,
    _MODIFY_DECISION,
    _record_exports,
    _seed_approved_decisions,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteApprovedEditExportRepresentationRepository,
    SQLiteDomainResultReferenceRepository,
    SQLiteEditExportAssemblyCommandPersistence,
    SQLiteEditExportAssemblyRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import SchemaFeatureUnavailableError
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_ASSEMBLY = EditExportAssemblyId("assembly-1")
_ASSEMBLY_RESULT = DomainResultId("assembly-1-result")
_TIMELINE = SourceTimelineId(TIMELINE_ID)


def _plan(name="assembly-1"):
    return EditExportAssemblyIdentityPlan(
        assembly_id=EditExportAssemblyId(name),
        assembly_result_id=DomainResultId(f"{name}-result"),
    )


class SQLiteAtomicEditExportAssemblyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        (
            self.execution,
            self.run_id,
            self.execution_id,
            _revision,
            _raw,
        ) = _build_persisted_readiness(self.connection)
        _seed_approved_decisions(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.accepted, self.modified, self.accepted_again = _record_exports(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.members = (
            self.accepted.representation.identity,
            self.modified.representation.identity,
            self.accepted_again.representation.identity,
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def _service(self):
        return compose_sqlite_edit_export_assembly_service(
            self.connection, self.execution
        )

    def _record(self, plan, members=None):
        return self._service().record_assembly(
            source_timeline_id=_TIMELINE,
            member_representation_ids=members if members is not None else self.members,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=plan,
        )

    def test_persists_and_reconstructs_in_canonical_order(self) -> None:
        prepared = self._record(_plan())
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteEditExportAssemblyRepository(reopened)
            results = SQLiteDomainResultReferenceRepository(reopened)
            restored = repo.get(_ASSEMBLY)
            self.assertEqual(restored, prepared.assembly)
            canonical = tuple(sorted(self.members, key=lambda i: i.value))
            self.assertEqual(restored.member_representation_ids, canonical)
            self.assertEqual(
                results.get(_ASSEMBLY_RESULT), prepared.assembly_result
            )
            self.assertEqual(len(prepared.assembly_result.upstream_results), 3)
        finally:
            reopened.close()

    def test_membership_rows_persisted_with_ordinals(self) -> None:
        self._record(_plan())
        rows = self.connection.execute(
            "SELECT ordinal, source_representation_id FROM edit_export_assembly_members "
            "WHERE edit_export_assembly_id = ? ORDER BY ordinal",
            (_ASSEMBLY.value,),
        ).fetchall()
        canonical = tuple(sorted(self.members, key=lambda i: i.value))
        self.assertEqual([r[0] for r in rows], [0, 1, 2])
        self.assertEqual([r[1] for r in rows], [m.value for m in canonical])

    def test_single_member_assembly(self) -> None:
        prepared = self._record(_plan(), members=(self.accepted.representation.identity,))
        self.assertEqual(
            prepared.assembly.member_representation_ids,
            (self.accepted.representation.identity,),
        )

    def test_recording_does_not_mutate_member_representations(self) -> None:
        repo = SQLiteApprovedEditExportRepresentationRepository(self.connection)
        before = {m: repo.get(m) for m in self.members}
        self._record(_plan())
        self.assertTrue(all(repo.get(m) == before[m] for m in self.members))

    def test_identity_collision_rolls_back(self) -> None:
        self._record(_plan("assembly-1"))
        service = self._service()
        prepared = service.evaluate_assembly(
            source_timeline_id=_TIMELINE,
            member_representation_ids=self.members,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=EditExportAssemblyIdentityPlan(
                assembly_id=EditExportAssemblyId("assembly-1"),  # collides
                assembly_result_id=DomainResultId("assembly-1b-result"),
            ),
        )
        persistence = SQLiteEditExportAssemblyCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_edit_export_assembly(prepared=prepared)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM domain_result_references WHERE identity = 'assembly-1b-result'"
            ).fetchone()[0],
            0,
        )

    def test_result_collision_rolls_back_membership(self) -> None:
        service = self._service()
        prepared = service.evaluate_assembly(
            source_timeline_id=_TIMELINE,
            member_representation_ids=self.members,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=EditExportAssemblyIdentityPlan(
                assembly_id=EditExportAssemblyId("assembly-x"),
                # reuse an existing member DomainResult id to force a collision
                assembly_result_id=self.accepted.representation.domain_result_id,
            ),
        )
        persistence = SQLiteEditExportAssemblyCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_edit_export_assembly(prepared=prepared)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM edit_export_assemblies WHERE identity = 'assembly-x'"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM edit_export_assembly_members "
                "WHERE edit_export_assembly_id = 'assembly-x'"
            ).fetchone()[0],
            0,
        )

    def test_membership_foreign_key_enforced(self) -> None:
        # A membership row referencing a non-existent representation must be rejected by the FK.
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("BEGIN")
            self.connection.execute(
                "INSERT INTO edit_export_assemblies(identity, domain_result_id, "
                "source_media_id, source_timeline_id, processing_run_id, unit_execution_id) "
                "VALUES ('a', 'a-result', 'media', ?, 'run', 'exec')",
                (TIMELINE_ID,),
            )
            self.connection.execute(
                "INSERT INTO edit_export_assembly_members(edit_export_assembly_id, ordinal, "
                "source_representation_id) VALUES ('a', 0, 'ghost-representation')"
            )
        if self.connection.in_transaction:
            self.connection.execute("ROLLBACK")

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = self._record(_plan())
        self.connection.close()
        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id, _, _ = _build_persisted_readiness(replay)
            _seed_approved_decisions(replay, execution, run_id, execution_id)
            _record_exports(replay, execution, run_id, execution_id)
            self.connection = replay
            second = compose_sqlite_edit_export_assembly_service(
                replay, execution
            ).record_assembly(
                source_timeline_id=_TIMELINE,
                member_representation_ids=self.members,
                run_id=run_id,
                unit_execution_id=execution_id,
                identities=_plan(),
            )
            self.assertEqual(first.assembly, second.assembly)
            self.assertEqual(first.assembly_result, second.assembly_result)
        finally:
            replay.close()

    def test_repository_rejects_pre_v29_schema(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 29):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 28)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEditExportAssemblyRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
