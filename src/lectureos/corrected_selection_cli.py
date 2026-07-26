"""Runnable entry point for Current Corrected Revision Selection (040 §20, GOAL-011).

One CLI over an existing repository (identities only — never media paths). A thin application boundary with no
authority logic:

* ``select`` — explicitly select one eligible corrected revision as current (context derived from the revision's
  own lineage);
* ``fallback`` — explicitly select the authoritative Raw Transcript (Raw fallback); revisions remain persisted;
* ``status`` — distinguish no-history / explicit Raw fallback / selected+applicable / selected-but-inapplicable;
* ``history`` — the append-only selection transitions in semantic order;
* ``resolve`` — the deterministic effective transcript (never a silent fallback for an inapplicable selection).

No ``--force``, ``--latest``, ``--best``, ``--auto``, ``--repair``, ``--publish``, or ``--clear-history``. No
command mutates a revision, candidate, decision, raw transcript, or the current Raw Transcript selection. On any
failure it prints an explicit error, returns non-zero, and leaves the repository unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.corrected_selection_cli select --revision <id> --reviewer <actor> --database <db>
    PYTHONPATH=src python3 -m lectureos.corrected_selection_cli fallback --intake <id> --reviewer <actor> --database <db>
    PYTHONPATH=src python3 -m lectureos.corrected_selection_cli status --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.corrected_selection_cli history --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.corrected_selection_cli resolve --intake <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.corrected_revision_selection import (
    CorrectedRevisionSelectionError,
    EffectiveKind,
    SelectionKind,
    SelectionState,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_selection_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database


def _service(database: str):
    connection = open_sqlite_database(database)
    return connection, compose_sqlite_corrected_revision_selection_service(connection)


def _previous_state(previous) -> str:
    if previous is None:
        return "no selection history"
    if previous.kind is SelectionKind.RAW_FALLBACK:
        return "raw fallback"
    return previous.corrected_revision_id.value


def _run_select(args) -> int:
    connection, service = _service(args.database)
    try:
        result = service.select_revision(
            revision_id=args.revision, reviewer=args.reviewer, rationale=args.rationale
        )
        intake = result.selection.transcript_source_intake_id.value
        applicability = service.applicability(intake)
    finally:
        connection.close()
    selection = result.selection
    print(f"{result.outcome.value} corrected revision selection {selection.identity.value}")
    print(f"context intake: {selection.transcript_source_intake_id.value}")
    print(f"selected revision: {selection.corrected_revision_id.value}")
    print(f"previous state: {_previous_state(result.previous)}")
    print(f"current selection: {selection.corrected_revision_id.value} (sequence {selection.sequence})")
    applicable = applicability.applicable if applicability is not None else False
    print(f"current applicability: {'applicable' if applicable else 'not applicable'}")
    print("no revision content was mutated (selection is authority only)")
    return 0


def _run_fallback(args) -> int:
    connection, service = _service(args.database)
    try:
        result = service.select_raw_fallback(
            intake_id=args.intake, reviewer=args.reviewer, rationale=args.rationale
        )
        effective = service.resolve_effective_transcript(args.intake)
    finally:
        connection.close()
    print(f"{result.outcome.value} raw transcript fallback {result.selection.identity.value}")
    print(f"context intake: {args.intake}")
    print(f"previous state: {_previous_state(result.previous)}")
    print("current state: raw fallback (no corrected revision selected)")
    print(f"effective raw transcript: {effective.raw_transcript_id.value}")
    print("corrected revisions remain persisted and queryable (nothing was deleted)")
    return 0


def _run_status(args) -> int:
    connection, service = _service(args.database)
    try:
        state = service.selection_state(args.intake)
        current = service.current(args.intake)
        applicability = service.applicability(args.intake)
    finally:
        connection.close()
    if state is SelectionState.NO_HISTORY:
        print("selection state: no selection history")
        print("effective transcript: authoritative raw transcript")
    elif state is SelectionState.RAW_FALLBACK:
        print("selection state: explicit raw fallback")
        print("effective transcript: authoritative raw transcript")
    else:
        print("selection state: corrected revision selected")
        print(f"selected revision: {current.corrected_revision_id.value}")
        if applicability.applicable:
            print("applicability: applicable")
        else:
            print(f"applicability: not applicable ({applicability.reason})")
    return 0


def _run_history(args) -> int:
    connection, service = _service(args.database)
    try:
        history = service.history(args.intake)
        current = history[-1] if history else None
    finally:
        connection.close()
    print(f"selection history for intake {args.intake}: {len(history)}")
    for selection in history:
        target = (
            selection.corrected_revision_id.value
            if selection.kind is SelectionKind.CORRECTED_REVISION
            else "raw fallback"
        )
        marker = "  *current" if current is not None and selection.identity == current.identity else ""
        print(
            f"  #{selection.sequence} {selection.kind.value} -> {target} "
            f"by {selection.reviewer.value} ({selection.identity.value}){marker}"
        )
    return 0


def _run_resolve(args) -> int:
    connection, service = _service(args.database)
    try:
        effective = service.resolve_effective_transcript(args.intake)
    finally:
        connection.close()
    print(f"selection state: {effective.selection_state.value}")
    if effective.effective_kind is EffectiveKind.RAW_TRANSCRIPT:
        print(f"effective transcript: raw {effective.raw_transcript_id.value}")
    elif effective.effective_kind is EffectiveKind.CORRECTED_REVISION:
        print(f"effective transcript: corrected {effective.corrected_revision_id.value}")
    else:
        print(
            f"selected corrected revision is INAPPLICABLE: {effective.corrected_revision_id.value} "
            f"({effective.inapplicability_reason})"
        )
        print("no silent fallback was performed (the authority conflict is explicit)")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.corrected_selection_cli",
        description=(
            "Explicit append-only selection of the current corrected transcript revision for an intake, "
            "explicit Raw Transcript fallback, and deterministic effective-transcript resolution. Selection is "
            "authority only: no revision, candidate, decision, or raw transcript is mutated, nothing is "
            "auto-promoted, and an inapplicable selected revision is reported explicitly, never silently "
            "replaced. Accepts identities, never media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success; 1 on malformed/unknown/ineligible/conflicting input "
            "(repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _database(sub):
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    def _reviewer(sub):
        sub.add_argument("--reviewer", required=True, metavar="ACTOR",
                         help="the selecting human actor reference (e.g. selector:kim)")
        sub.add_argument("--rationale", default=None, metavar="TEXT",
                         help="optional reason recorded with the selection")

    select = subparsers.add_parser("select", help="select one eligible corrected revision as current")
    select.add_argument("--revision", required=True, metavar="CORRECTED_REVISION_ID",
                        help="corrected revision identity (corrected-revision:<digest>); context is derived from it")
    _reviewer(select)
    _database(select)
    select.set_defaults(func=_run_select)

    fallback = subparsers.add_parser("fallback", help="explicitly select the raw transcript (raw fallback)")
    fallback.add_argument("--intake", required=True, metavar="TRANSCRIPT_SOURCE_INTAKE_ID",
                          help="canonical TranscriptSourceIntakeId (the selection context)")
    _reviewer(fallback)
    _database(fallback)
    fallback.set_defaults(func=_run_fallback)

    for name, func, help_text in (
        ("status", _run_status, "distinguish no-history / fallback / selected(+applicability)"),
        ("history", _run_history, "list the append-only selection transitions"),
        ("resolve", _run_resolve, "resolve the deterministic effective transcript"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--intake", required=True, metavar="TRANSCRIPT_SOURCE_INTAKE_ID",
                         help="canonical TranscriptSourceIntakeId (the selection context)")
        _database(sub)
        sub.set_defaults(func=func)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (CorrectedRevisionSelectionError, KeyError, ValueError, OSError, PersistenceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
