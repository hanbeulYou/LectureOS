"""Runnable entry point for the Effective Transcript Consumption Boundary (040 §21, GOAL-012).

One CLI over an existing repository (identities only — never media paths). A thin application boundary with no
resolution or authority logic:

* ``resolve-input`` — acquire the effective transcript input through the sole §20 resolver: resolver state,
  authority provenance, source kind, exact immutable source identity, Raw parent, and segment manifest;
* ``consume`` — record (or converge on) the stable consumption binding for the bounded manifest consumer;
* ``status`` — list persisted bindings with their **derived** currentness against the current authority.

No ``--force``, ``--latest``, ``--best``, ``--auto``, ``--repair``, ``--apply-all``, ``--publish``,
``--approve``, or ``--clear-history``. No command mutates a transcript, revision, candidate, decision, or any
selection authority; a selected-but-inapplicable revision fails explicitly (never a silent Raw fallback). On any
failure it prints an explicit error, returns non-zero, and leaves the repository unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.transcript_consumption_cli resolve-input --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.transcript_consumption_cli consume --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.transcript_consumption_cli status --intake <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.corrected_revision_selection import (
    CorrectedRevisionSelectionError,
)
from lectureos.application.effective_transcript_consumption import (
    ConsumedSourceKind,
    ConsumptionCurrentness,
    EffectiveTranscriptConsumptionError,
    SelectionState,
)
from lectureos.composition import (
    compose_sqlite_effective_transcript_consumption_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database

_STATE_LABELS = {
    SelectionState.NO_HISTORY: "no corrected selection history",
    SelectionState.RAW_FALLBACK: "explicit raw fallback",
    SelectionState.CORRECTED_SELECTED: "corrected revision selected",
}


def _service(database: str):
    connection = open_sqlite_database(database)
    return connection, compose_sqlite_effective_transcript_consumption_service(connection)


def _print_input(acquired) -> None:
    print(f"context intake: {acquired.transcript_source_intake_id.value}")
    print(f"resolver state: {_STATE_LABELS[acquired.selection_state]}")
    print(f"raw selection provenance: {acquired.raw_selection_id.value}")
    if acquired.corrected_selection_id is not None:
        print(f"corrected selection provenance: {acquired.corrected_selection_id.value}")
    print(f"source kind: {acquired.source_kind.value}")
    print(f"source identity: {acquired.source_transcript_identity}")
    print(f"parent raw transcript: {acquired.parent_raw_transcript_id.value}")
    print(f"segments: {len(acquired.segments)}")
    print(f"content fingerprint: {acquired.content_fingerprint}")


def _run_resolve_input(args) -> int:
    connection, service = _service(args.database)
    try:
        acquired = service.acquire_input(args.intake)
    finally:
        connection.close()
    _print_input(acquired)
    print("consumability: consumable")
    return 0


def _run_consume(args) -> int:
    connection, service = _service(args.database)
    try:
        result = service.consume(intake_id=args.intake)
    finally:
        connection.close()
    consumption = result.consumption
    print(f"{result.outcome.value} consumption binding {consumption.identity.value}")
    print(f"consumer kind: {consumption.consumer_kind}")
    _print_input(result.input)
    effective = "yes" if result.currently_effective else "no"
    print(f"source currently remains effective: {effective}")
    print("no selection or transcript was mutated (the binding is a new record only)")
    return 0


def _run_status(args) -> int:
    connection, service = _service(args.database)
    try:
        bindings = service.bindings(args.intake)
        currentness = [service.currentness(binding) for binding in bindings]
    finally:
        connection.close()
    print(f"consumption bindings for intake {args.intake}: {len(bindings)}")
    for binding, state in zip(bindings, currentness):
        marker = "current" if state is ConsumptionCurrentness.CURRENT else state.value
        kind = (
            "corrected"
            if binding.source_kind is ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION
            else "raw"
        )
        print(
            f"  {binding.consumer_kind} -> {kind} {binding.source_transcript_identity} "
            f"({binding.segment_count} segments) [{marker}] ({binding.identity.value})"
        )
    print("currentness is derived against the current authority; bindings are never mutated")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.transcript_consumption_cli",
        description=(
            "Effective Transcript Consumption Boundary: acquire one immutable transcript source through the "
            "sole effective-transcript resolver and record the stable consumption binding for the bounded "
            "manifest consumer. A selected-but-inapplicable corrected revision fails explicitly — there is no "
            "silent raw fallback — and no transcript, revision, or selection authority is ever mutated. "
            "Accepts identities, never media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success; 1 on malformed/unknown/unconsumable/conflicting input "
            "(repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, func, help_text in (
        ("resolve-input", _run_resolve_input,
         "acquire and report the effective transcript input (read-only)"),
        ("consume", _run_consume,
         "record or converge on the manifest consumption binding"),
        ("status", _run_status,
         "list persisted bindings with derived currentness"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--intake", required=True, metavar="TRANSCRIPT_SOURCE_INTAKE_ID",
                         help="canonical TranscriptSourceIntakeId (the consumption context)")
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")
        sub.set_defaults(func=func)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
        EffectiveTranscriptConsumptionError,
        CorrectedRevisionSelectionError,
        KeyError,
        ValueError,
        OSError,
        PersistenceError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
