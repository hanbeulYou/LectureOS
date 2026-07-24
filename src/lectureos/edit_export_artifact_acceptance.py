"""In-process acceptance for the Edit-Pipeline Export Artifact Foundation — First Slice (044 §21).

Reuses the durable pipeline chain (readiness -> input -> finding -> candidate -> accept/modify review ->
approved decisions -> export representations -> Edit Export Assembly), then derives one Edit Export Artifact
from that Assembly and verifies the full first slice:

    EditExportAssembly -> derived EditExportArtifact

It confirms: the Artifact presents the Assembly's complete approved edit meaning faithfully (one entry per
member, in canonical member order, each carrying the member's approved range/type/rationale/kind/actor); the
Artifact is derived and non-persisted (no Artifact table exists); regeneration from the same upstream preserves
the same Product meaning while a new identity yields another derived Artifact of the same Assembly; the Assembly
and its member representations are never mutated; and the Artifact carries no serializer/format/status/path.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.edit_export_assembly import EditExportAssemblyIdentityPlan
from lectureos.application.identities import (
    EditExportArtifactId,
    EditExportAssemblyId,
)
from lectureos.composition import (
    compose_sqlite_edit_export_artifact_service,
    compose_sqlite_edit_export_assembly_service,
)
from lectureos.edit_export_assembly_acceptance import _seed_representations
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    SQLiteApprovedEditExportRepresentationRepository,
    SQLiteEditExportAssemblyRepository,
    initialize_sqlite_database,
)
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_ARTIFACT = EditExportArtifactId("artifact-1")
_ARTIFACT_AGAIN = EditExportArtifactId("artifact-2")
_ASSEMBLY_PLAN = EditExportAssemblyIdentityPlan(
    assembly_id=EditExportAssemblyId("artifact-source-assembly"),
    assembly_result_id=DomainResultId("artifact-source-assembly-result"),
)


def _record_assembly(connection, execution, run_id, execution_id):
    accepted, modified, accepted_again = _seed_representations(
        connection, execution, run_id, execution_id
    )
    members = (
        accepted.representation.identity,
        modified.representation.identity,
        accepted_again.representation.identity,
    )
    assembly = compose_sqlite_edit_export_assembly_service(
        connection, execution
    ).record_assembly(
        source_timeline_id=SourceTimelineId(TIMELINE_ID),
        member_representation_ids=members,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_ASSEMBLY_PLAN,
    )
    return assembly.assembly, members


def run_edit_export_artifact_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(
            connection
        )
        assembly, members = _record_assembly(
            connection, execution, run_id, execution_id
        )

        representation_repo = SQLiteApprovedEditExportRepresentationRepository(connection)
        assembly_repo = SQLiteEditExportAssemblyRepository(connection)
        assembly_before = assembly_repo.get(assembly.identity)
        members_before = {mid: representation_repo.get(mid) for mid in members}

        service = compose_sqlite_edit_export_artifact_service(connection)
        artifact = service.derive_artifact(
            source_assembly_id=assembly.identity, identity=_ARTIFACT
        )

        canonical = tuple(sorted(members, key=lambda mid: mid.value))
        anchored_to_one_assembly = (
            artifact.source_assembly_id == assembly.identity
            and artifact.source_timeline_id == assembly.source_timeline_id
            and artifact.source_media_id == assembly.source_media_id
        )
        presents_all_members_in_order = (
            tuple(entry.source_representation_id for entry in artifact.entries)
            == canonical
        )
        faithful_presentation = all(
            entry.approved_range_start == members_before[entry.source_representation_id].approved_range_start
            and entry.approved_range_end == members_before[entry.source_representation_id].approved_range_end
            and entry.approved_candidate_type == members_before[entry.source_representation_id].approved_candidate_type
            and entry.approved_rationale == members_before[entry.source_representation_id].approved_rationale
            and entry.decision_kind == members_before[entry.source_representation_id].decision_kind
            and entry.actor == members_before[entry.source_representation_id].actor
            for entry in artifact.entries
        )

        # Derived / non-persisted: no Artifact table exists; the Artifact is regenerated, not stored.
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        derived_not_persisted = not {
            "edit_export_artifacts",
            "edit_export_artifact_entries",
            "edit_export_serializations",
        } & existing_tables
        artifact_fields = set(type(artifact).__dataclass_fields__)
        entry_fields = set(type(artifact.entries[0]).__dataclass_fields__)
        no_deferred_fields = not {
            "status", "state", "format", "mime_type", "filename", "path", "url",
            "checksum", "payload", "serialized", "profile", "configuration",
        } & (artifact_fields | entry_fields)

        # Regeneration preserves the same Product meaning; a new identity yields another derived Artifact.
        regenerated = service.derive_artifact(
            source_assembly_id=assembly.identity, identity=_ARTIFACT
        )
        regeneration_preserves_meaning = regenerated == artifact
        another = service.derive_artifact(
            source_assembly_id=assembly.identity, identity=_ARTIFACT_AGAIN
        )
        multiple_per_assembly = (
            another.identity != artifact.identity and another.entries == artifact.entries
        )

        upstream_unmutated = (
            assembly_repo.get(assembly.identity) == assembly_before
            and all(representation_repo.get(mid) == members_before[mid] for mid in members)
        )
        connection.close()

        return {
            "anchored_to_one_assembly": anchored_to_one_assembly,
            "presents_all_members_in_order": presents_all_members_in_order,
            "faithful_presentation": faithful_presentation,
            "derived_not_persisted": derived_not_persisted,
            "no_deferred_fields": no_deferred_fields,
            "regeneration_preserves_meaning": regeneration_preserves_meaning,
            "multiple_per_assembly": multiple_per_assembly,
            "upstream_unmutated": upstream_unmutated,
        }


def main() -> int:
    print(json.dumps(run_edit_export_artifact_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
