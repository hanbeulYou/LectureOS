"""In-process acceptance for read-only repository validation.

Seeds a real, healthy edit-export repository through the durable pipeline and confirms it validates clean, then
applies a series of independent, deterministic corruptions (via raw SQL, with foreign keys disabled) to a copy
and confirms each is reported with the expected diagnostic code — without the validator ever mutating the
database. It also confirms multiple simultaneous failures are all reported and that diagnostics are
deterministic across runs.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

from lectureos.application.edit_export_assembly import EditExportAssemblyIdentityPlan
from lectureos.application.identities import EditExportAssemblyId
from lectureos.composition import compose_sqlite_edit_export_assembly_service
from lectureos.edit_export_assembly_acceptance import _seed_representations
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import initialize_sqlite_database
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness
from lectureos.validation import validate_database

_ASSEMBLY = "acc-assembly"


def _seed_healthy(database: Path) -> tuple[str, str, str]:
    connection = initialize_sqlite_database(database)
    execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(connection)
    accepted, modified, again = _seed_representations(connection, execution, run_id, execution_id)
    members = (
        accepted.representation.identity.value,
        modified.representation.identity.value,
        again.representation.identity.value,
    )
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
    return members


def _corrupt(source: Path, target: Path, mutate) -> None:
    shutil.copyfile(source, target)
    connection = sqlite3.connect(target)
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN")
        mutate(connection)
        connection.execute("COMMIT")
    finally:
        connection.close()


def _codes(database: Path) -> set[str]:
    return {d.code for d in validate_database(str(database)).diagnostics}


def run_repository_validation_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        healthy = base / "healthy.db"
        members = _seed_healthy(healthy)
        first_member = members[0]

        healthy_report = validate_database(str(healthy))
        healthy_is_clean = (
            healthy_report.health.value == "healthy"
            and healthy_report.ok
            and healthy_report.error_count == 0
            and healthy_report.warning_count == 0
            and healthy_report.schema_version == 46
            and healthy_report.objects_checked > 0
        )

        # The validator must not mutate the database.
        before = healthy.read_bytes()
        validate_database(str(healthy))
        read_only = healthy.read_bytes() == before

        # Dangling non-FK reference: point a representation's review id at a missing decision.
        dangling = base / "dangling.db"
        _corrupt(
            healthy,
            dangling,
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations "
                "SET source_review_decision_id = 'ghost-review' WHERE identity = ?",
                (first_member,),
            ),
        )
        detects_dangling = "DANGLING_REFERENCE" in _codes(dangling)

        # Orphan / FK violation: delete a referenced approved decision (FK from representation).
        orphan = base / "orphan.db"

        def _delete_decision(c: sqlite3.Connection) -> None:
            decision = c.execute(
                "SELECT source_approved_decision_id FROM approved_edit_export_representations "
                "WHERE identity = ?",
                (first_member,),
            ).fetchone()[0]
            c.execute("DELETE FROM approved_edit_decisions WHERE identity = ?", (decision,))

        _corrupt(healthy, orphan, _delete_decision)
        detects_orphan = "FOREIGN_KEY_VIOLATION" in _codes(orphan)

        # Empty assembly: remove all members of the assembly.
        empty = base / "empty.db"
        _corrupt(
            healthy,
            empty,
            lambda c: c.execute("DELETE FROM edit_export_assembly_members"),
        )
        detects_empty = "ASSEMBLY_EMPTY" in _codes(empty)

        # Invalid ordering: leave a gap in the member ordinals.
        noncontiguous = base / "noncontiguous.db"
        _corrupt(
            healthy,
            noncontiguous,
            lambda c: c.execute(
                "UPDATE edit_export_assembly_members SET ordinal = 7 WHERE ordinal = 1"
            ),
        )
        detects_noncontiguous = (
            "ASSEMBLY_MEMBER_ORDINAL_NONCONTIGUOUS" in _codes(noncontiguous)
        )

        # Cross-timeline member: move one representation to a different timeline.
        cross_timeline = base / "cross_timeline.db"
        _corrupt(
            healthy,
            cross_timeline,
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations SET source_timeline_id = 'other-timeline' "
                "WHERE identity = ?",
                (first_member,),
            ),
        )
        detects_cross_timeline = "ASSEMBLY_MEMBER_TIMELINE_MISMATCH" in _codes(cross_timeline)

        # Invalid artifact source: a representation whose decision kind no longer matches its approved decision.
        kind_mismatch = base / "kind.db"
        _corrupt(
            healthy,
            kind_mismatch,
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations SET decision_kind = "
                "CASE decision_kind WHEN 'accept' THEN 'modify' ELSE 'accept' END WHERE identity = ?",
                (first_member,),
            ),
        )
        detects_kind_mismatch = "REPRESENTATION_KIND_MISMATCH" in _codes(kind_mismatch)

        # Malformed identity: blank an assembly identity.
        malformed = base / "malformed.db"
        _corrupt(
            healthy,
            malformed,
            lambda c: c.execute("UPDATE edit_export_assemblies SET identity = '   '"),
        )
        detects_malformed = "MALFORMED_IDENTITY" in _codes(malformed)

        # Multiple simultaneous failures.
        multi = base / "multi.db"

        def _multi(c: sqlite3.Connection) -> None:
            c.execute(
                "UPDATE approved_edit_export_representations SET source_candidate_id = 'ghost-candidate' "
                "WHERE identity = ?",
                (first_member,),
            )
            c.execute("DELETE FROM edit_export_assembly_members")

        _corrupt(healthy, multi, _multi)
        multi_codes = _codes(multi)
        detects_multiple = {"DANGLING_REFERENCE", "ASSEMBLY_EMPTY"} <= multi_codes

        # Determinism: two validations of the same corrupted database are identical.
        deterministic = (
            validate_database(str(dangling)).as_dict()
            == validate_database(str(dangling)).as_dict()
        )

        # Not-a-LectureOS-database and missing database.
        empty_file = base / "empty.sqlite3"
        sqlite3.connect(empty_file).close()
        detects_non_repository = "SCHEMA_METADATA_MISSING" in _codes(empty_file)
        detects_missing = "DATABASE_NOT_FOUND" in _codes(base / "does-not-exist.db")

        return {
            "healthy_is_clean": healthy_is_clean,
            "validator_is_read_only": read_only,
            "detects_dangling_reference": detects_dangling,
            "detects_orphan_fk_violation": detects_orphan,
            "detects_empty_assembly": detects_empty,
            "detects_noncontiguous_ordinal": detects_noncontiguous,
            "detects_cross_timeline_member": detects_cross_timeline,
            "detects_kind_mismatch": detects_kind_mismatch,
            "detects_malformed_identity": detects_malformed,
            "detects_multiple_failures": detects_multiple,
            "diagnostics_are_deterministic": deterministic,
            "detects_non_repository": detects_non_repository,
            "detects_missing_database": detects_missing,
        }


def main() -> int:
    print(json.dumps(run_repository_validation_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
