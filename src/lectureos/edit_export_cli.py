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
            "Derive an Edit Export Assembly's Artifact, serialize it to LectureOS Edit Export JSON v1, "
            "and materialize one local file."
        ),
    )
    parser.add_argument("assembly_id", help="identity of an existing EditExportAssembly")
    parser.add_argument(
        "--database", required=True, help="absolute path to the LectureOS SQLite database"
    )
    parser.add_argument(
        "--output", required=True, help="absolute destination path for the exported JSON file"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="atomically overwrite an existing file that holds different bytes",
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
