"""Runnable entry point for First Corrected Transcript Revision generation (040 §19, GOAL-010).

One CLI over an existing repository (identities only — never media paths). A thin application boundary with no
authority logic:

* ``generate`` — explicitly apply one **currently Accepted** correction candidate to its source Raw Transcript,
  producing (or reusing) one immutable canonical Corrected Transcript Revision. Acceptance alone never generates;
  this command is the explicit application boundary. The revision is **not** selected as current;
* ``show`` — load one revision by identity with its corrected content and lineage;
* ``list`` — list the generations recorded for a candidate.

On any failure it prints an explicit error, returns non-zero, and leaves the repository unchanged. There is no
``--force``, ``--apply-all``, ``--auto``, ``--best``, or ``--select`` option.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.corrected_revision_cli generate --candidate <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.corrected_revision_cli show --revision <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.corrected_revision_cli list --candidate <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.corrected_revision_generation import (
    CorrectedRevisionGenerationError,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
)
from lectureos.persistence import (
    PersistenceError,
    SQLiteCorrectedTranscriptRevisionRepository,
    SQLiteTranscriptSegmentRepository,
    open_sqlite_database,
)
from lectureos.transcript.identities import TranscriptRevisionId


def _run_generate(args) -> int:
    connection = open_sqlite_database(args.database)
    try:
        service = compose_sqlite_corrected_revision_generation_service(connection)
        result = service.generate(candidate_id=args.candidate)
    finally:
        connection.close()
    generation = result.generation
    print(
        f"{result.outcome} corrected transcript revision {generation.corrected_revision_id.value}"
    )
    print(f"candidate: {generation.correction_candidate_id.value}")
    print(f"authorizing accepted decision: {generation.authorizing_decision_id.value}")
    print(f"source raw transcript: {generation.parent_raw_transcript_id.value}")
    print(f"generation: {generation.identity.value}")
    print("the revision was NOT selected as current (current corrected revision selection is a later stage)")
    return 0


def _run_show(args) -> int:
    connection = open_sqlite_database(args.database)
    try:
        revisions = SQLiteCorrectedTranscriptRevisionRepository(connection)
        revision = revisions.get(TranscriptRevisionId(args.revision))
        if revision is None:
            print("error: unknown corrected transcript revision", file=sys.stderr)
            return 1
        segments = SQLiteTranscriptSegmentRepository(connection)
        rows = [segments.get(segment_id) for segment_id in revision.segment_ids]
    finally:
        connection.close()
    print(f"corrected transcript revision {revision.identity.value}")
    parent = revision.parent_raw_transcript_id.value if revision.parent_raw_transcript_id else "-"
    print(f"parent raw transcript: {parent}")
    print(f"applied candidates: {', '.join(c.value for c in revision.correction_candidate_ids)}")
    print(f"segments: {len(rows)}")
    for segment in rows:
        marker = " *corrected" if segment.replaces_segment_id is not None else ""
        print(f"  [{segment.start}-{segment.end}] {segment.text}{marker}")
    return 0


def _run_list(args) -> int:
    connection = open_sqlite_database(args.database)
    try:
        service = compose_sqlite_corrected_revision_generation_service(connection)
        generations = service.generations_for_candidate(args.candidate)
    finally:
        connection.close()
    print(f"corrected revision generations for candidate {args.candidate}: {len(generations)}")
    for generation in generations:
        print(
            f"  {generation.corrected_revision_id.value}  "
            f"authorized-by={generation.authorizing_decision_id.value}"
        )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.corrected_revision_cli",
        description=(
            "Explicitly apply one currently accepted correction candidate to its source Raw Transcript, "
            "producing one immutable Corrected Transcript Revision — or inspect generated revisions. Acceptance "
            "alone never generates a revision, and a generated revision is never selected as current. Accepts "
            "identities, never media paths. Exactly one candidate is applied per revision."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success; 1 on undecided/rejected/stale candidate, unknown identity, identity "
            "conflict, or any error (repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _database(sub):
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    generate = subparsers.add_parser("generate", help="apply one currently accepted candidate into a revision")
    generate.add_argument("--candidate", required=True, metavar="CORRECTION_CANDIDATE_ID",
                          help="canonical CorrectionCandidateId whose current authority is Accepted")
    _database(generate)
    generate.set_defaults(func=_run_generate)

    show = subparsers.add_parser("show", help="show one corrected revision with content and lineage")
    show.add_argument("--revision", required=True, metavar="TRANSCRIPT_REVISION_ID",
                      help="corrected transcript revision identity (corrected-revision:<digest>)")
    _database(show)
    show.set_defaults(func=_run_show)

    listing = subparsers.add_parser("list", help="list generations recorded for a candidate")
    listing.add_argument("--candidate", required=True, metavar="CORRECTION_CANDIDATE_ID",
                         help="canonical CorrectionCandidateId")
    _database(listing)
    listing.set_defaults(func=_run_list)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (CorrectedRevisionGenerationError, KeyError, ValueError, OSError, PersistenceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
