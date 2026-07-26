"""Runnable entry point for Current Raw Transcript Selection and readiness (040 §16).

One CLI with three subcommands over an existing repository (an intake identity is always accepted — never a media
path):

* ``candidates`` — list an intake's admitted Raw Transcript candidates and their provider/model metadata
  (deterministically ordered by identity; **not ranked**, no candidate is labelled "best");
* ``select`` — choose or switch the current Raw Transcript for an intake (append-only authority; idempotent when
  the requested transcript is already current);
* ``readiness`` — report whether the intake is ready to begin downstream Correction.

Selection is an explicit repository authority decision; it never compares ASR quality, alters transcript content,
or runs Correction. On any failure it prints an explicit error, returns non-zero, and leaves the repository
unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_cli candidates --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_cli select --intake <id> --transcript <rt> --database <db>
    PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_cli readiness --intake <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.current_raw_transcript_selection import (
    RawTranscriptSelectionError,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database


def _service(database: str):
    connection = open_sqlite_database(database)
    return connection, compose_sqlite_current_raw_transcript_selection_service(connection)


def _run_candidates(args) -> int:
    connection, service = _service(args.database)
    try:
        candidates = service.candidates(args.intake)
        current = service.current(args.intake)
    finally:
        connection.close()
    current_id = current.raw_transcript_id.value if current is not None else None
    print(f"raw transcript candidates for intake {args.intake}: {len(candidates)} (not ranked)")
    for candidate in candidates:
        marker = " *current" if candidate.raw_transcript_id.value == current_id else ""
        print(
            f"  {candidate.raw_transcript_id.value}  "
            f"provider={candidate.provider_reference} model={candidate.provider_model} "
            f"language={candidate.declared_language} segments={candidate.segment_count}{marker}"
        )
    return 0


def _run_select(args) -> int:
    connection, service = _service(args.database)
    try:
        result = service.select(args.intake, args.transcript, reason=args.reason)
        readiness = service.readiness(args.intake)
    finally:
        connection.close()
    print(
        f"{result.outcome.value} current raw transcript {result.selection.raw_transcript_id.value} "
        f"for intake {args.intake}"
    )
    print(f"selection: {result.selection.identity.value} (sequence {result.selection.sequence})")
    if result.previous is not None:
        print(f"superseded: {result.previous.raw_transcript_id.value}")
    print(f"readiness: {readiness.readiness.value}")
    return 0


def _run_readiness(args) -> int:
    connection, service = _service(args.database)
    try:
        report = service.readiness(args.intake)
    finally:
        connection.close()
    print(f"readiness for intake {args.intake}: {report.readiness.value}")
    print(f"candidates: {report.candidate_count}")
    if report.current_raw_transcript_id is not None:
        print(f"current raw transcript: {report.current_raw_transcript_id.value}")
        print(f"current selection: {report.current_selection_id.value}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.raw_transcript_selection_cli",
        description=(
            "Enumerate an intake's admitted Raw Transcript candidates, choose/switch the current authoritative "
            "Raw Transcript for downstream Correction, and report readiness. Accepts intake and raw transcript "
            "identities (never paths). Selection is an explicit repository authority decision; it never ranks "
            "candidates, compares ASR quality, alters transcript content, or runs Correction."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on a successful query or valid selection; 1 on malformed/unknown/unrelated/"
            "dangling/conflicting input (repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _common(sub):
        sub.add_argument("--intake", required=True, metavar="TRANSCRIPT_SOURCE_INTAKE_ID",
                         help="canonical TranscriptSourceIntakeId (transcript-source-intake:sha256:<digest>)")
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    candidates = subparsers.add_parser("candidates", help="list admitted Raw Transcript candidates")
    _common(candidates)
    candidates.set_defaults(func=_run_candidates)

    select = subparsers.add_parser("select", help="select or switch the current Raw Transcript")
    _common(select)
    select.add_argument("--transcript", required=True, metavar="RAW_TRANSCRIPT_ID",
                        help="canonical RawTranscript identity (raw-transcript:<digest>) admitted for this intake")
    select.add_argument("--reason", default=None, metavar="TEXT",
                        help="optional human reason recorded with the selection")
    select.set_defaults(func=_run_select)

    readiness = subparsers.add_parser("readiness", help="report intake readiness for Correction")
    _common(readiness)
    readiness.set_defaults(func=_run_readiness)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (RawTranscriptSelectionError, KeyError, ValueError, OSError, PersistenceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
