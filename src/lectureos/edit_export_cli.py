"""Runnable entry point for the first Edit Export slice (044 §22).

Identifies an existing valid ``EditExportAssembly`` in a LectureOS SQLite database, derives its canonical
``EditExportArtifact``, serializes it into LectureOS Edit Export JSON v1, and materializes the result as one
local physical file, reporting the final path and format/version. On any failure it prints an explicit error to
stderr, returns a non-zero exit code, and leaves no misleading final file.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.edit_export_cli <assembly-id> \\
        --database <db-path> --output <path> [--overwrite]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from lectureos.application.identities import (
    EditExportArtifactId,
    EditExportAssemblyId,
)
from lectureos.application.edit_export_materialization import (
    EditExportMaterializationResult,
)
from lectureos.composition import (
    compose_edit_export_materialization_service,
    compose_sqlite_edit_export_artifact_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database


def run_edit_export(
    *,
    database: str,
    assembly_id: str,
    output: str,
    overwrite: bool = False,
) -> EditExportMaterializationResult:
    """Derive, serialize, and materialize one Edit Export Assembly's Artifact to a local file."""

    connection = open_sqlite_database(database)
    try:
        artifact = compose_sqlite_edit_export_artifact_service(connection).derive_artifact(
            source_assembly_id=EditExportAssemblyId(assembly_id),
            # Deterministic, caller-owned Artifact identity: the same Assembly always derives the same Artifact.
            identity=EditExportArtifactId(f"edit-export:{assembly_id}"),
        )
    finally:
        connection.close()
    return compose_edit_export_materialization_service().materialize_artifact(
        artifact=artifact, destination=Path(output), overwrite=overwrite
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.edit_export_cli",
        description=(
            "Export the approved edits of one Edit Export Assembly to a local file. Derives the Assembly's "
            "canonical Artifact, serializes it to LectureOS Edit Export JSON v1, and writes one local file. "
            "The export is descriptive (approved ranges, labels, rationale, decision kind, actor) — it is not "
            "an executable edit and does not modify the source media."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  # export assembly 'lecture-42' from a LectureOS database to a JSON file\n"
            "  PYTHONPATH=src python3 -m lectureos.edit_export_cli lecture-42 \\\n"
            "      --database /data/lectureos.sqlite3 --output /exports/lecture-42.json\n"
            "\n"
            "  # re-export, replacing an existing file that holds different bytes\n"
            "  PYTHONPATH=src python3 -m lectureos.edit_export_cli lecture-42 \\\n"
            "      --database /data/lectureos.sqlite3 --output /exports/lecture-42.json --overwrite\n"
            "\n"
            "  # no database yet? see the runnable mock demo:\n"
            "  PYTHONPATH=src python3 -m lectureos.edit_export_demo --output-directory /tmp/lectureos\n"
            "\n"
            "exit status: 0 on success; 1 on any error (the destination file is not created on failure)."
        ),
    )
    parser.add_argument(
        "assembly_id",
        metavar="ASSEMBLY_ID",
        help="identity of an existing EditExportAssembly to export",
    )
    parser.add_argument(
        "--database",
        required=True,
        metavar="PATH",
        help="absolute path to an existing LectureOS SQLite database that holds the Assembly",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="absolute destination path for the exported JSON file (parent directories are created)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "atomically overwrite an existing file that holds different bytes "
            "(by default an existing, differing file is left untouched and the command fails)"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_edit_export(
            database=args.database,
            assembly_id=args.assembly_id,
            output=args.output,
            overwrite=args.overwrite,
        )
    except (KeyError, ValueError, OSError, PersistenceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        f"exported {result.format} {result.version} "
        f"({result.byte_length} bytes, {result.encoding}) -> {result.final_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
