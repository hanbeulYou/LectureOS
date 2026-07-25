"""Runnable entry point for Source Media transcription intake eligibility (040 §13).

Admits an already-imported canonical Source Media record (by ``SourceMediaId``) as an eligible input to the
Transcript Pipeline, recording a deterministic, content-derived intake in an existing LectureOS repository. It
reports whether the intake was created or reused, prints the Source Media identity and the intake identity, and
states that **no transcription was executed**. It accepts a Source Media identity — **not** a filesystem path
(raw paths belong to Media Import) — reads no media bytes, and performs no decoding or transcription. On failure
it prints an explicit error, returns non-zero, and leaves the repository unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.transcript_intake_cli --media <source-media-id> --database <db-path>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.transcript_source_intake import TranscriptSourceIntakeResult
from lectureos.composition import compose_sqlite_transcript_source_intake_service
from lectureos.persistence import PersistenceError, open_sqlite_database


def run_transcript_intake(
    *, database: str, source_media_id: str
) -> TranscriptSourceIntakeResult:
    """Admit an existing persisted Source Media as a transcript intake input (existing repository required)."""

    connection = open_sqlite_database(database)
    try:
        return compose_sqlite_transcript_source_intake_service(connection).admit(
            source_media_id
        )
    finally:
        connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.transcript_intake_cli",
        description=(
            "Admit an already-imported Source Media record as an eligible Transcript Pipeline input. This "
            "confirms a Source Media reference from persisted repository facts only — it accepts a "
            "SourceMediaId (not a path), reads no media bytes, decodes nothing, asserts nothing about codecs "
            "or audio, and executes no transcription."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  PYTHONPATH=src python3 -m lectureos.transcript_intake_cli "
            "--media sha256:<digest> --database /data/lectureos.sqlite3\n"
            "\n"
            "import a source first with: python3 -m lectureos.media_import_cli <file> --database <db>\n"
            "exit status: 0 on success; 1 on malformed/unknown media or any error "
            "(the repository is left unchanged)."
        ),
    )
    parser.add_argument(
        "--media",
        required=True,
        metavar="SOURCE_MEDIA_ID",
        help="canonical SourceMediaId of an already-imported Source Media record (e.g. sha256:<digest>)",
    )
    parser.add_argument(
        "--database",
        required=True,
        metavar="PATH",
        help="path to the existing LectureOS SQLite database that holds the Source Media record",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_transcript_intake(
            database=args.database, source_media_id=args.media
        )
    except (KeyError, ValueError, OSError, PersistenceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    status = "created" if result.created else "reused"
    print(
        f"{status} transcript intake {result.intake.identity.value} "
        f"for source media {result.intake.source_media_id.value}"
    )
    print("no transcription was executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
