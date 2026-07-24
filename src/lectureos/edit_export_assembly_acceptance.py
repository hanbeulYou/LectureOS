"""In-process acceptance for the Edit-Pipeline Export Assembly Application Foundation — First Slice (044 §20).

Reuses the durable pipeline chain, records an Eligible Analysis Input, Analysis Finding, Edit Candidate, an
accept-review and a modify-review Approved Edit Decision, and their durable Approved Edit Export
Representations, then admits one Edit Export Assembly from an explicitly supplied set of those representation
identities through the Edit Export Assembly Application boundary and verifies the full first slice:

    {ApprovedEditExportRepresentation, ...} -> durable EditExportAssembly

It confirms: the Assembly is anchored to exactly one Source Timeline and coherent; the ordered membership
snapshot is deterministically normalized to canonical identity order regardless of caller input order; the
Assembly's DomainResult has one direct upstream per member representation (multi-upstream lineage); the source
representations stay unchanged (the Assembly copies no approved edit meaning); no serializer / Artifact / file /
scope-selection / status is created; and the Assembly reconstructs after reopen with deterministic replay.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.edit_export_assembly import EDIT_EXPORT_ASSEMBLY_RESULT_KIND
from lectureos.application.identities import (
    ApprovedEditExportRepresentationId,
    EditExportAssemblyId,
)
from lectureos.composition import compose_sqlite_edit_export_assembly_service
from lectureos.edit_export_acceptance import (
    _record_exports,
    _seed_approved_decisions,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    SQLiteApprovedEditExportRepresentationRepository,
    SQLiteDomainResultReferenceRepository,
    SQLiteEditExportAssemblyRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_ASSEMBLY = EditExportAssemblyId("assembly-1")
_ASSEMBLY_RESULT = DomainResultId("assembly-1-result")


def _identities():
    from lectureos.application.edit_export_assembly import EditExportAssemblyIdentityPlan

    return EditExportAssemblyIdentityPlan(
        assembly_id=_ASSEMBLY, assembly_result_id=_ASSEMBLY_RESULT
    )


def _seed_representations(connection, execution, run_id, execution_id):
    _seed_approved_decisions(connection, execution, run_id, execution_id)
    accepted, modified, accepted_again = _record_exports(
        connection, execution, run_id, execution_id
    )
    return accepted, modified, accepted_again


def run_edit_export_assembly_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(
            connection
        )
        accepted, modified, accepted_again = _seed_representations(
            connection, execution, run_id, execution_id
        )

        representation_repo = SQLiteApprovedEditExportRepresentationRepository(connection)
        member_ids = (
            accepted.representation.identity,
            modified.representation.identity,
            accepted_again.representation.identity,
        )
        before_members = {mid: representation_repo.get(mid) for mid in member_ids}

        service = compose_sqlite_edit_export_assembly_service(connection, execution)
        # Supply members in a deliberately non-canonical order to prove canonical normalization.
        prepared = service.record_assembly(
            source_timeline_id=SourceTimelineId(TIMELINE_ID),
            member_representation_ids=tuple(reversed(member_ids)),
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_identities(),
        )

        canonical = tuple(sorted(member_ids, key=lambda mid: mid.value))
        deterministic_order = prepared.assembly.member_representation_ids == canonical
        one_timeline = prepared.assembly.source_timeline_id == SourceTimelineId(TIMELINE_ID)
        multi_upstream_lineage = (
            prepared.assembly_result.kind == EDIT_EXPORT_ASSEMBLY_RESULT_KIND
            and prepared.assembly_result.upstream_results
            == tuple(before_members[mid].domain_result_id for mid in canonical)
            and len(prepared.assembly_result.upstream_results) == len(member_ids)
        )
        members_unmutated = all(
            representation_repo.get(mid) == before_members[mid] for mid in member_ids
        )

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        no_deferred_tables = not {
            "edit_export_artifacts",
            "edit_export_serializations",
            "edit_export_profiles",
            "edit_export_materializations",
        } & existing_tables
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(edit_export_assemblies)"
            ).fetchall()
        }
        member_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(edit_export_assembly_members)"
            ).fetchall()
        }
        no_deferred_columns = not {
            "status", "state", "current", "superseded", "revision", "profile",
            "configuration", "format", "mime_type", "filename", "path", "url",
            "checksum", "payload", "serialized",
        } & (columns | member_columns)
        connection.close()

        reopened = open_sqlite_database(path)
        assembly_repo = SQLiteEditExportAssemblyRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = (
            assembly_repo.get(_ASSEMBLY) == prepared.assembly
            and results.get(_ASSEMBLY_RESULT) == prepared.assembly_result
        )
        reopened.close()

        replay_path = Path(directory) / "replay.sqlite3"
        replay = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _, _ = _build_persisted_readiness(replay)
        _seed_representations(replay, r_execution, r_run, r_exec)
        r_prepared = compose_sqlite_edit_export_assembly_service(
            replay, r_execution
        ).record_assembly(
            source_timeline_id=SourceTimelineId(TIMELINE_ID),
            member_representation_ids=member_ids,
            run_id=r_run,
            unit_execution_id=r_exec,
            identities=_identities(),
        )
        replay.close()
        deterministic_replay = r_prepared.assembly == prepared.assembly

        return {
            "deterministic_order": deterministic_order,
            "one_timeline_anchor": one_timeline,
            "multi_upstream_lineage": multi_upstream_lineage,
            "members_unmutated": members_unmutated,
            "no_deferred_tables": no_deferred_tables,
            "no_deferred_columns": no_deferred_columns,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
        }


def main() -> int:
    print(json.dumps(run_edit_export_assembly_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
