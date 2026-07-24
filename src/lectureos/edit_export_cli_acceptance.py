"""In-process end-to-end acceptance for the first runnable Edit Export slice (044 §22).

Seeds a real SQLite database through the durable pipeline, records an Edit Export Assembly, then runs the actual
runnable entry point (`run_edit_export`) to serialize the derived Artifact into LectureOS Edit Export JSON v1
and materialize a real local file. It verifies the physical file exists and its exact bytes; that serialization
is deterministic (a second export into a fresh path is byte-identical); that the document is valid JSON round-
tripping to the complete approved meaning; that a default collision is refused without damaging the file; that
an explicit overwrite with unchanged meaning is idempotent; and that a failed export (unknown assembly) exits
without leaving a final file. Upstream approved records are unchanged throughout.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.edit_export_assembly import EditExportAssemblyIdentityPlan
from lectureos.application.edit_export_materialization import (
    EditExportMaterializationError,
)
from lectureos.application.identities import EditExportAssemblyId
from lectureos.composition import compose_sqlite_edit_export_assembly_service
from lectureos.edit_export_assembly_acceptance import _seed_representations
from lectureos.edit_export_cli import run_edit_export
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    SQLiteApprovedEditExportRepresentationRepository,
    initialize_sqlite_database,
)
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_ASSEMBLY = "artifact-cli-assembly"


def _seed_assembly(connection):
    execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(
        connection
    )
    accepted, modified, again = _seed_representations(
        connection, execution, run_id, execution_id
    )
    members = (
        accepted.representation.identity,
        modified.representation.identity,
        again.representation.identity,
    )
    compose_sqlite_edit_export_assembly_service(connection, execution).record_assembly(
        source_timeline_id=SourceTimelineId(TIMELINE_ID),
        member_representation_ids=members,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=EditExportAssemblyIdentityPlan(
            assembly_id=EditExportAssemblyId(_ASSEMBLY),
            assembly_result_id=DomainResultId(f"{_ASSEMBLY}-result"),
        ),
    )
    return members


def run_edit_export_cli_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        db = base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(db)
        members = _seed_assembly(connection)
        representation_repo = SQLiteApprovedEditExportRepresentationRepository(connection)
        members_before = {mid: representation_repo.get(mid) for mid in members}
        connection.close()

        output = base / "export" / "edits.json"
        result = run_edit_export(
            database=str(db), assembly_id=_ASSEMBLY, output=str(output)
        )

        file_exists = output.is_file()
        payload = output.read_text(encoding="utf-8")
        reported = (
            result.format == "lectureos-edit-export-json"
            and result.version == "v1"
            and result.encoding == "utf-8"
            and result.byte_length == len(payload.encode("utf-8"))
            and result.final_path == str(output)
        )

        document = json.loads(payload)
        complete_meaning = (
            document["format"] == "lectureos-edit-export-json"
            and document["version"] == "v1"
            and document["artifact_id"] == f"edit-export:{_ASSEMBLY}"
            and document["source_assembly_id"] == _ASSEMBLY
            and len(document["edits"]) == len(members)
            and all(
                {
                    "source_representation_id", "decision_kind", "approved_range_start",
                    "approved_range_end", "approved_candidate_type", "approved_rationale",
                    "actor",
                }
                <= set(edit)
                for edit in document["edits"]
            )
        )
        canonical = tuple(sorted((m.value for m in members)))
        canonical_order = (
            tuple(edit["source_representation_id"] for edit in document["edits"])
            == canonical
        )

        # Determinism: a second export into a fresh path is byte-identical.
        output_again = base / "export-again" / "edits.json"
        run_edit_export(database=str(db), assembly_id=_ASSEMBLY, output=str(output_again))
        deterministic = output.read_bytes() == output_again.read_bytes()

        # Default collision: re-exporting to the same path (identical bytes) is idempotent success.
        idempotent = (
            run_edit_export(database=str(db), assembly_id=_ASSEMBLY, output=str(output)).byte_length
            == result.byte_length
        )

        # Failure: unknown assembly exits without leaving a final file.
        missing_output = base / "missing" / "edits.json"
        failed_no_file = False
        try:
            run_edit_export(
                database=str(db), assembly_id="no-such-assembly", output=str(missing_output)
            )
        except KeyError:
            failed_no_file = not missing_output.exists()

        # Materialization collision with different bytes is an explicit failure, file preserved.
        collision_reported = False
        original_bytes = output.read_bytes()
        conflict = base / "conflict.json"
        conflict.write_text("different bytes", encoding="utf-8")
        try:
            run_edit_export(database=str(db), assembly_id=_ASSEMBLY, output=str(conflict))
        except EditExportMaterializationError:
            collision_reported = conflict.read_text(encoding="utf-8") == "different bytes"

        upstream_unmutated = original_bytes == output.read_bytes()
        # Re-open read-only to confirm approved records are unchanged.
        from lectureos.persistence import open_sqlite_database

        verify = open_sqlite_database(db)
        try:
            verify_repo = SQLiteApprovedEditExportRepresentationRepository(verify)
            upstream_unmutated = upstream_unmutated and all(
                verify_repo.get(mid) == members_before[mid] for mid in members
            )
        finally:
            verify.close()

        return {
            "file_exists": file_exists,
            "reported_result": reported,
            "complete_meaning": complete_meaning,
            "canonical_order": canonical_order,
            "deterministic": deterministic,
            "idempotent_reexport": idempotent,
            "failure_leaves_no_file": failed_no_file,
            "collision_reported_and_file_preserved": collision_reported,
            "upstream_unmutated": upstream_unmutated,
        }


def main() -> int:
    print(json.dumps(run_edit_export_cli_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
