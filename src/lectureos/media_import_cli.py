"""Runnable entry point for local Media Import (``lectureos media-import``, 045 §1).

Imports one local file as a canonical, content-addressed Source Media record in a LectureOS SQLite repository
(creating the repository if it does not yet exist). It prints the canonical Media identity, the content
fingerprint, the byte length, and whether a new record was created or an existing identical-content record was
reused. It never modifies the source file, and on failure it prints an explicit error, returns non-zero, and
leaves the database unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.media_import_cli <source-path> --database <db-path>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.media_import import MediaImportResult
from lectureos.composition import compose_sqlite_media_import_service
from lectureos.persistence import PersistenceError, initialize_sqlite_database


def run_media_import(*, database: str, source_path: str) -> MediaImportResult:
    """Import one local source file into the repository (bootstrapping the repository if new)."""

    connection = initialize_sqlite_database(database)
    try:
        return compose_sqlite_media_import_service(connection).import_media(source_path)
    finally:
        connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.media_import_cli",
        description=(
            "Import a local file as a canonical, content-addressed Source Media record. Media identity is "
            "derived from a streaming SHA-256 of the file contents, so importing the same content is "
            "idempotent regardless of path or filename. This records file identity and provenance only; it "
            "does not decode, transcode, probe, play, or transcribe media, and it never modifies the source."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  PYTHONPATH=src python3 -m lectureos.media_import_cli lecture.mp4 "
            "--database /data/lectureos.sqlite3\n"
            "\n"
            "exit status: 0 on success; 1 on any error (the database is left unchanged on failure)."
        ),
    )
    parser.add_argument(
        "source_path",
        metavar="SOURCE_PATH",
        help="path to the local source file to import",
    )
    parser.add_argument(
        "--database",
        required=True,
        metavar="PATH",
        help="path to the LectureOS SQLite database (created if it does not exist)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_media_import(database=args.database, source_path=args.source_path)
    except (KeyError, ValueError, OSError, PersistenceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    record = result.record
    status = "created" if result.created else "reused"
    print(
        f"{status} source media {record.identity.value} "
        f"(fingerprint {record.fingerprint_algorithm}:{record.fingerprint_digest}, "
        f"{record.byte_length} bytes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
