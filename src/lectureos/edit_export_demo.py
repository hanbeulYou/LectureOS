"""Runnable mock end-to-end demonstration of the LectureOS Edit Export pipeline (Developer Preview).

Runs the complete edit-export pipeline in a single process without a real media file, real Whisper model, or
any network access, and materializes one real local JSON export file. The workflow is::

    Fake Transcript
        -> Lecture Analysis + Review (human decision)
        -> Approved Edit Decision
        -> Approved Edit Export Representation
        -> Edit Export Assembly
        -> Edit Export Artifact
        -> LectureOS Edit Export JSON (serialize)
        -> Local File (materialize)

The demonstration reuses the deterministic in-process fixtures that back the acceptance suite (a fake
speech-transcription provider result, a seeded analysis finding, human accept/modify review decisions, and the
resulting approved decisions), then drives the real Assembly, Artifact, serializer, and local materializer. It
reads no wall-clock and uses fixed identities, so the produced file is byte-deterministic — the same run always
yields the same export. A throwaway SQLite database is created in a temporary directory; only the JSON export
file is written to the caller's output directory.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.edit_export_demo --output-directory /absolute/existing/directory
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from lectureos.application.edit_export_assembly import EditExportAssemblyIdentityPlan
from lectureos.application.identities import (
    EditExportArtifactId,
    EditExportAssemblyId,
)
from lectureos.composition import (
    compose_edit_export_materialization_service,
    compose_sqlite_edit_export_artifact_service,
    compose_sqlite_edit_export_assembly_service,
)
from lectureos.edit_export_assembly_acceptance import _seed_representations
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import initialize_sqlite_database
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_ASSEMBLY_ID = "edit-export-demo-assembly"
_ARTIFACT_ID = "edit-export-demo"
# The seeded fixture builds a fake transcript with two segments (see subtitle_intake_acceptance).
_TRANSCRIPT_SEGMENTS = 2
_ANALYSIS_FINDINGS = 1
_EDIT_CANDIDATES = 2
_REVIEW_DECISIONS = 2
_APPROVED_DECISIONS = 2


@dataclass(frozen=True, slots=True)
class EditExportDemoResult:
    """Structured summary of one deterministic mock export run."""

    transcript_segments: int
    analysis_findings: int
    edit_candidates: int
    review_decisions: int
    approved_decisions: int
    export_representations: int
    assembly_id: str
    assembly_members: int
    artifact_id: str
    artifact_entries: int
    output_path: str
    format: str
    version: str
    byte_length: int


def run_edit_export_demo(
    output_directory: str,
    *,
    filename: str = "edit-export.json",
    overwrite: bool = False,
) -> EditExportDemoResult:
    """Drive the full mock pipeline and materialize one deterministic local JSON export file."""

    destination = Path(output_directory) / filename
    with tempfile.TemporaryDirectory() as working:
        database = Path(working) / "lectureos-demo.sqlite3"
        connection = initialize_sqlite_database(database)
        try:
            # Fake transcript -> readiness -> analysis + human review -> approved decisions -> representations.
            execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(
                connection
            )
            accepted, modified, accepted_again = _seed_representations(
                connection, execution, run_id, execution_id
            )
            members = (
                accepted.representation.identity,
                modified.representation.identity,
                accepted_again.representation.identity,
            )

            # Assembly: gather the approved export representations into one coherent Export Scope.
            compose_sqlite_edit_export_assembly_service(
                connection, execution
            ).record_assembly(
                source_timeline_id=SourceTimelineId(TIMELINE_ID),
                member_representation_ids=members,
                run_id=run_id,
                unit_execution_id=execution_id,
                identities=EditExportAssemblyIdentityPlan(
                    assembly_id=EditExportAssemblyId(_ASSEMBLY_ID),
                    assembly_result_id=DomainResultId(f"{_ASSEMBLY_ID}-result"),
                ),
            )

            # Artifact: derive the canonical external representation of the Assembly's complete meaning.
            artifact = compose_sqlite_edit_export_artifact_service(connection).derive_artifact(
                source_assembly_id=EditExportAssemblyId(_ASSEMBLY_ID),
                identity=EditExportArtifactId(_ARTIFACT_ID),
            )
        finally:
            connection.close()

        # Serialize to LectureOS Edit Export JSON and materialize one local file.
        result = compose_edit_export_materialization_service().materialize_artifact(
            artifact=artifact, destination=destination, overwrite=overwrite
        )

    return EditExportDemoResult(
        transcript_segments=_TRANSCRIPT_SEGMENTS,
        analysis_findings=_ANALYSIS_FINDINGS,
        edit_candidates=_EDIT_CANDIDATES,
        review_decisions=_REVIEW_DECISIONS,
        approved_decisions=_APPROVED_DECISIONS,
        export_representations=len(members),
        assembly_id=_ASSEMBLY_ID,
        assembly_members=len(members),
        artifact_id=_ARTIFACT_ID,
        artifact_entries=len(artifact.entries),
        output_path=result.final_path,
        format=result.format,
        version=result.version,
        byte_length=result.byte_length,
    )


def _render(result: EditExportDemoResult) -> str:
    return "\n".join(
        (
            "LectureOS Edit Export — mock end-to-end demo",
            "",
            f"  fake transcript segments : {result.transcript_segments}",
            f"  analysis findings        : {result.analysis_findings}",
            f"  edit candidates          : {result.edit_candidates}",
            f"  human review decisions   : {result.review_decisions}",
            f"  approved edit decisions  : {result.approved_decisions}",
            f"  export representations   : {result.export_representations}",
            f"  assembly                 : {result.assembly_id} ({result.assembly_members} members)",
            f"  artifact                 : {result.artifact_id} ({result.artifact_entries} edits)",
            "",
            f"  exported {result.format} {result.version} ({result.byte_length} bytes)",
            f"  -> {result.output_path}",
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.edit_export_demo",
        description=(
            "Run the LectureOS Edit Export pipeline end to end without a real media file and write one "
            "deterministic local JSON export file."
        ),
    )
    parser.add_argument(
        "--output-directory",
        required=True,
        help="absolute existing directory the demo writes the JSON export file into",
    )
    parser.add_argument(
        "--filename",
        default="edit-export.json",
        help="name of the exported JSON file (default: edit-export.json)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="atomically overwrite an existing export file that holds different bytes",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_edit_export_demo(
            args.output_directory, filename=args.filename, overwrite=args.overwrite
        )
    except (KeyError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(_render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
