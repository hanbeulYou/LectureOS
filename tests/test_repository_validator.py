import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.edit_export_assembly import EditExportAssemblyIdentityPlan
from lectureos.application.identities import EditExportAssemblyId
from lectureos.composition import compose_sqlite_edit_export_assembly_service
from lectureos.edit_export_assembly_acceptance import _seed_representations
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import initialize_sqlite_database
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness
from lectureos.validation import (
    RepositoryHealth,
    Severity,
    validate_database,
    validate_repository,
)

_ASSEMBLY = "val-assembly"


def _seed_healthy(database: Path) -> str:
    connection = initialize_sqlite_database(database)
    execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(connection)
    accepted, modified, again = _seed_representations(connection, execution, run_id, execution_id)
    compose_sqlite_edit_export_assembly_service(connection, execution).record_assembly(
        source_timeline_id=SourceTimelineId(TIMELINE_ID),
        member_representation_ids=(
            accepted.representation.identity,
            modified.representation.identity,
            again.representation.identity,
        ),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=EditExportAssemblyIdentityPlan(
            assembly_id=EditExportAssemblyId(_ASSEMBLY),
            assembly_result_id=DomainResultId(f"{_ASSEMBLY}-result"),
        ),
    )
    connection.close()
    return accepted.representation.identity.value


class RepositoryValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "healthy.db"
        self.member = _seed_healthy(self.healthy)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_repository_is_clean(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)
        self.assertTrue(report.ok)
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.warning_count, 0)
        self.assertEqual(report.schema_version, 29)
        self.assertGreater(report.objects_checked, 0)

    def test_validator_does_not_mutate_the_database(self) -> None:
        before = self.healthy.read_bytes()
        validate_database(str(self.healthy))
        self.assertEqual(self.healthy.read_bytes(), before)

    def test_dangling_non_fk_reference_detected(self) -> None:
        broken = self._corrupt(
            "dangling.db",
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations "
                "SET source_review_decision_id = 'ghost' WHERE identity = ?",
                (self.member,),
            ),
        )
        self.assertIn("DANGLING_REFERENCE", self._codes(broken))

    def test_foreign_key_violation_detected(self) -> None:
        def _delete(c: sqlite3.Connection) -> None:
            decision = c.execute(
                "SELECT source_approved_decision_id FROM approved_edit_export_representations "
                "WHERE identity = ?",
                (self.member,),
            ).fetchone()[0]
            c.execute("DELETE FROM approved_edit_decisions WHERE identity = ?", (decision,))

        broken = self._corrupt("orphan.db", _delete)
        self.assertIn("FOREIGN_KEY_VIOLATION", self._codes(broken))

    def test_empty_assembly_detected(self) -> None:
        broken = self._corrupt(
            "empty.db", lambda c: c.execute("DELETE FROM edit_export_assembly_members")
        )
        self.assertIn("ASSEMBLY_EMPTY", self._codes(broken))

    def test_noncontiguous_ordinals_detected(self) -> None:
        broken = self._corrupt(
            "gap.db",
            lambda c: c.execute(
                "UPDATE edit_export_assembly_members SET ordinal = 9 WHERE ordinal = 1"
            ),
        )
        self.assertIn("ASSEMBLY_MEMBER_ORDINAL_NONCONTIGUOUS", self._codes(broken))

    def test_cross_timeline_member_detected(self) -> None:
        broken = self._corrupt(
            "timeline.db",
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations SET source_timeline_id = 'elsewhere' "
                "WHERE identity = ?",
                (self.member,),
            ),
        )
        self.assertIn("ASSEMBLY_MEMBER_TIMELINE_MISMATCH", self._codes(broken))

    def test_cross_media_member_detected(self) -> None:
        broken = self._corrupt(
            "media.db",
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations SET source_media_id = 'elsewhere' "
                "WHERE identity = ?",
                (self.member,),
            ),
        )
        self.assertIn("ASSEMBLY_MEMBER_MEDIA_MISMATCH", self._codes(broken))

    def test_representation_kind_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "kind.db",
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations SET decision_kind = "
                "CASE decision_kind WHEN 'accept' THEN 'modify' ELSE 'accept' END WHERE identity = ?",
                (self.member,),
            ),
        )
        self.assertIn("REPRESENTATION_KIND_MISMATCH", self._codes(broken))

    def test_malformed_identity_detected(self) -> None:
        broken = self._corrupt(
            "malformed.db",
            lambda c: c.execute("UPDATE edit_export_assemblies SET identity = '  '"),
        )
        self.assertIn("MALFORMED_IDENTITY", self._codes(broken))

    def test_noncanonical_member_order_is_a_warning(self) -> None:
        def _swap(c: sqlite3.Connection) -> None:
            # Swap ordinals 0 and 2 via a temporary slot so membership stays contiguous but out of order.
            c.execute("UPDATE edit_export_assembly_members SET ordinal = 100 WHERE ordinal = 0")
            c.execute("UPDATE edit_export_assembly_members SET ordinal = 0 WHERE ordinal = 2")
            c.execute("UPDATE edit_export_assembly_members SET ordinal = 2 WHERE ordinal = 100")

        broken = self._corrupt("reorder.db", _swap)
        report = validate_database(str(broken))
        codes = {d.code for d in report.diagnostics}
        self.assertIn("ASSEMBLY_MEMBER_ORDER_NONCANONICAL", codes)
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.health, RepositoryHealth.WARNINGS)
        self.assertTrue(report.ok)  # warnings do not make the repository invalid

    def test_multiple_simultaneous_failures_all_reported(self) -> None:
        def _multi(c: sqlite3.Connection) -> None:
            c.execute(
                "UPDATE approved_edit_export_representations SET source_candidate_id = 'ghost' "
                "WHERE identity = ?",
                (self.member,),
            )
            c.execute("DELETE FROM edit_export_assembly_members")

        broken = self._corrupt("multi.db", _multi)
        codes = self._codes(broken)
        self.assertIn("DANGLING_REFERENCE", codes)
        self.assertIn("ASSEMBLY_EMPTY", codes)

    def test_diagnostics_are_deterministic(self) -> None:
        broken = self._corrupt(
            "det.db",
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations SET source_candidate_id = 'ghost' "
                "WHERE identity = ?",
                (self.member,),
            ),
        )
        self.assertEqual(
            validate_database(str(broken)).as_dict(),
            validate_database(str(broken)).as_dict(),
        )

    def test_missing_database_reported(self) -> None:
        report = validate_database(str(self.base / "no-such.db"))
        self.assertEqual({d.code for d in report.diagnostics}, {"DATABASE_NOT_FOUND"})
        self.assertFalse(report.ok)

    def test_non_repository_database_reported(self) -> None:
        empty = self.base / "empty.sqlite3"
        sqlite3.connect(empty).close()
        self.assertIn("SCHEMA_METADATA_MISSING", self._codes(empty))

    def test_duplicate_member_detected_on_tampered_schema(self) -> None:
        # The real schema forbids duplicate members via a UNIQUE constraint; this exercises the check on a
        # minimal tampered schema where that constraint is absent.
        path = self.base / "dupe.db"
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE schema_metadata (singleton INTEGER PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_metadata VALUES (1, 29);
                CREATE TABLE edit_export_assemblies (
                    identity TEXT PRIMARY KEY, domain_result_id TEXT, source_media_id TEXT,
                    source_timeline_id TEXT, processing_run_id TEXT, unit_execution_id TEXT);
                CREATE TABLE edit_export_assembly_members (
                    edit_export_assembly_id TEXT, ordinal INTEGER, source_representation_id TEXT);
                INSERT INTO edit_export_assemblies VALUES ('a', 'r', 'm', 't', 'run', 'exec');
                INSERT INTO edit_export_assembly_members VALUES ('a', 0, 'rep-1');
                INSERT INTO edit_export_assembly_members VALUES ('a', 1, 'rep-1');
                """
            )
            connection.commit()
        finally:
            connection.close()
        report = validate_database(str(path))
        self.assertIn(
            "ASSEMBLY_MEMBER_DUPLICATE", {d.code for d in report.diagnostics}
        )

    def test_representation_provenance_mismatch_detected(self) -> None:
        # Point a representation at a different existing review decision than its approved decision's.
        broken = self._corrupt(
            "prov.db",
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations "
                "SET source_review_decision_id = 'decision-modify' WHERE identity = ?",
                (self.member,),
            ),
        )
        self.assertIn("REPRESENTATION_PROVENANCE_MISMATCH", self._codes(broken))

    def test_approved_decision_kind_invalid_detected(self) -> None:
        def _flip(c: sqlite3.Connection) -> None:
            decision = c.execute(
                "SELECT source_approved_decision_id FROM approved_edit_export_representations "
                "WHERE identity = ?",
                (self.member,),
            ).fetchone()[0]
            c.execute(
                "UPDATE approved_edit_decisions SET decision_kind = "
                "CASE decision_kind WHEN 'accept' THEN 'modify' ELSE 'accept' END WHERE identity = ?",
                (decision,),
            )

        broken = self._corrupt("dkind.db", _flip)
        self.assertIn("APPROVED_DECISION_KIND_INVALID", self._codes(broken))

    def test_approved_decision_provenance_mismatch_detected(self) -> None:
        def _swap_candidate(c: sqlite3.Connection) -> None:
            decision = c.execute(
                "SELECT source_approved_decision_id FROM approved_edit_export_representations "
                "WHERE identity = ?",
                (self.member,),
            ).fetchone()[0]
            c.execute(
                "UPDATE approved_edit_decisions SET source_candidate_id = 'candidate-modify' "
                "WHERE identity = ?",
                (decision,),
            )

        broken = self._corrupt("dprov.db", _swap_candidate)
        self.assertIn("APPROVED_DECISION_PROVENANCE_MISMATCH", self._codes(broken))

    def test_domain_result_upstream_noncontiguous_detected(self) -> None:
        broken = self._corrupt(
            "lineage.db",
            lambda c: c.execute(
                "UPDATE domain_result_upstream_results SET ordinal = 9 "
                "WHERE domain_result_id = ? AND ordinal = 1",
                (f"{_ASSEMBLY}-result",),
            ),
        )
        self.assertIn("DOMAIN_RESULT_UPSTREAM_NONCONTIGUOUS", self._codes(broken))

    def test_unsupported_schema_version_detected(self) -> None:
        broken = self._corrupt(
            "version.db",
            lambda c: c.execute("UPDATE schema_metadata SET version = 999 WHERE singleton = 1"),
        )
        self.assertIn("SCHEMA_VERSION_UNSUPPORTED", self._codes(broken))

    def test_unreadable_database_reported(self) -> None:
        junk = self.base / "junk.db"
        junk.write_bytes(b"this is not a sqlite database" * 8)
        self.assertIn("DATABASE_UNREADABLE", self._codes(junk))

    def test_every_diagnostic_has_required_fields(self) -> None:
        broken = self._corrupt(
            "fields.db", lambda c: c.execute("DELETE FROM edit_export_assembly_members")
        )
        report = validate_database(str(broken))
        self.assertTrue(report.diagnostics)
        for diagnostic in report.diagnostics:
            self.assertTrue(diagnostic.code)
            self.assertIsInstance(diagnostic.severity, Severity)
            self.assertTrue(diagnostic.location)
            self.assertTrue(diagnostic.message)


if __name__ == "__main__":
    unittest.main()
