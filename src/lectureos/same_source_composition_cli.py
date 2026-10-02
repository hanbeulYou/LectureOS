"""Runnable entry point for Same-Source Text + Timing Composition (040 §19 `PATCH-0050`).

One CLI over an existing repository (identities only — never media paths):

* ``generate`` — explicitly apply **one currently Accepted text candidate** and **one currently
  Accepted timing candidate** that target the same original source segment into one composed
  replacement inside one immutable corrected revision. The two roles are named explicitly:
  ``--text-candidate`` must carry a text correction candidate identity and ``--timing-candidate`` a
  timing correction candidate identity. Putting a text identity in the timing role is a malformed
  request, not an ordering variation; the order of the two options on the command line is irrelevant.
  Nothing is discovered, ranked, or inherited, and the revision is **not** selected as current;
* ``show`` — print one composition with both roles' provenance (candidates, authorizing Decisions,
  replaced source and composed replacement).

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.same_source_composition_cli generate \\
        --text-candidate <correction-candidate:...> --timing-candidate <timing-correction-candidate:...> \\
        --database <db>
    PYTHONPATH=src python3 -m lectureos.same_source_composition_cli show --generation <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.identities import SameSourceCompositionGenerationId
from lectureos.application.same_source_composition_generation import (
    SameSourceCompositionError,
)
from lectureos.composition import compose_sqlite_same_source_composition_generation_service
from lectureos.persistence import (
    PersistenceError,
    SQLiteTranscriptSegmentRepository,
    open_sqlite_database,
)
from lectureos.persistence.same_source_composition_generation import (
    SQLiteSameSourceCompositionRepository,
)


def _describe(generation, segments) -> None:
    print(f"generation: {generation.identity.value}")
    print(f"corrected revision: {generation.corrected_revision_id.value}")
    print(f"parent raw transcript: {generation.parent_raw_transcript_id.value}")
    print(f"replaced source segment: {generation.replaced_segment_id.value}")
    print(f"text candidate: {generation.text_correction_candidate_id.value}")
    print(f"  text authorizing decision: {generation.text_authorizing_decision_id.value}")
    print(f"timing candidate: {generation.timing_correction_candidate_id.value}")
    print(f"  timing authorizing decision: {generation.timing_authorizing_decision_id.value}")
    replacement = segments.get(generation.replacement_segment_id)
    print(f"composed replacement: {generation.replacement_segment_id.value}")
    if replacement is not None:
        print(f"  text: {replacement.text!r}")
        print(f"  interval: [{replacement.start}, {replacement.end}]")


def _run_generate(args) -> int:
    connection = open_sqlite_database(args.database)
    try:
        service = compose_sqlite_same_source_composition_generation_service(connection)
        result = service.generate(
            text_candidate_id=args.text_candidate, timing_candidate_id=args.timing_candidate
        )
        segments = SQLiteTranscriptSegmentRepository(connection)
        print(f"{result.outcome} composed corrected revision {result.revision.identity.value}")
        _describe(result.generation, segments)
    finally:
        connection.close()
    print("text comes from the text candidate and the interval from the timing candidate, exactly")
    print("the revision was NOT selected as current (selection is an explicit separate act)")
    return 0


def _run_show(args) -> int:
    connection = open_sqlite_database(args.database)
    try:
        generation = SQLiteSameSourceCompositionRepository(connection).get(
            SameSourceCompositionGenerationId(args.generation)
        )
        if generation is None:
            print("error: unknown same-source composition generation", file=sys.stderr)
            return 1
        _describe(generation, SQLiteTranscriptSegmentRepository(connection))
    finally:
        connection.close()
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.same_source_composition_cli",
        description=(
            "Explicitly apply one currently accepted text candidate and one currently accepted timing "
            "candidate on the same original source segment into one composed corrected revision "
            "(040 §19 PATCH-0050). Roles are explicit; nothing is discovered, ranked, or merged at "
            "selection; the revision is never selected as current. Accepts identities, never media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success; 1 on a missing/duplicated/mismatched role, unknown identity, "
            "undecided/rejected/stale candidate, structural conflict, integrity failure, or any error "
            "(repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate", help="compose one text and one timing candidate on one source into a revision"
    )
    generate.add_argument(
        "--text-candidate", required=True, dest="text_candidate",
        metavar="CORRECTION_CANDIDATE_ID",
        help="canonical text CorrectionCandidateId whose current authority is Accepted",
    )
    generate.add_argument(
        "--timing-candidate", required=True, dest="timing_candidate",
        metavar="TIMING_CORRECTION_CANDIDATE_ID",
        help="canonical TimingCorrectionCandidateId whose current authority is Accepted",
    )
    generate.add_argument("--database", required=True, metavar="PATH")
    generate.set_defaults(func=_run_generate)

    show = subparsers.add_parser("show", help="show one composition with both roles' provenance")
    show.add_argument("--generation", required=True, metavar="SAME_SOURCE_COMPOSITION_GENERATION_ID")
    show.add_argument("--database", required=True, metavar="PATH")
    show.set_defaults(func=_run_show)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (SameSourceCompositionError, KeyError, ValueError, OSError, PersistenceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
