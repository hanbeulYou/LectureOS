"""Runnable entry point for Effective-Transcript Subtitle Candidate generation (041 §15, GOAL-013).

One CLI over an existing repository (identities only — never media paths). A thin application boundary with no
generation or authority logic:

* ``generate`` — explicitly generate (or converge on) the deterministic effective-source candidate for an
  intake; the transcript source is acquired solely through the GOAL-012 consumption boundary (the binding
  exists before generation); a selected-but-inapplicable corrected revision fails explicitly — never a silent
  Raw fallback;
* ``show`` — one candidate with its full source lineage and ordered cue set;
* ``list`` — candidates generated for an intake;
* ``status`` — one candidate's **derived** source currentness against the current authority.

No ``--force``, ``--latest``, ``--best``, ``--auto``, ``--repair``, ``--apply-all``, ``--publish``,
``--approve``, or ``--clear-history``. No command creates review records, Human Decisions, final selections,
exports, or files, and none touches the legacy subtitle pipeline. On any failure it prints an explicit error,
returns non-zero, and leaves the repository unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli generate --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli show --candidate <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli list --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli status --candidate <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.corrected_revision_selection import (
    CorrectedRevisionSelectionError,
)
from lectureos.application.effective_subtitle_generation import (
    EffectiveSubtitleGenerationError,
)
from lectureos.application.effective_transcript_consumption import (
    ConsumptionCurrentness,
    EffectiveTranscriptConsumptionError,
)
from lectureos.composition import (
    compose_sqlite_effective_subtitle_generation_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database


def _service(database: str):
    connection = open_sqlite_database(database)
    return connection, compose_sqlite_effective_subtitle_generation_service(connection)


def _print_candidate(candidate, currentness=None) -> None:
    print(f"candidate: {candidate.identity.value}")
    print(f"context intake: {candidate.transcript_source_intake_id.value}")
    print(f"consumption binding: {candidate.consumption_binding_id.value}")
    print(f"source kind: {candidate.source_kind.value}")
    print(f"source identity: {candidate.source_transcript_identity}")
    print(f"parent raw transcript: {candidate.parent_raw_transcript_id.value}")
    print(
        f"generator: {candidate.generator_kind} "
        f"v{candidate.generator_version} (parameters v{candidate.generation_parameters_version})"
    )
    print(f"cues: {candidate.cue_count}")
    if currentness is not None:
        marker = "current" if currentness is ConsumptionCurrentness.CURRENT else currentness.value
        print(f"source currentness: {marker}")


def _run_generate(args) -> int:
    connection, service = _service(args.database)
    try:
        result = service.generate(intake_id=args.intake)
    finally:
        connection.close()
    print(f"{result.outcome.value} effective subtitle candidate")
    _print_candidate(result.candidate, result.currentness)
    print(
        "no review, decision, final selection, export, or file materialization was "
        "created or changed"
    )
    return 0


def _run_show(args) -> int:
    connection, service = _service(args.database)
    try:
        candidate = service.get(args.candidate)
        if candidate is None:
            raise EffectiveSubtitleGenerationError("unknown effective subtitle candidate")
        cues = service.cues(args.candidate)
        currentness = service.currentness(candidate)
    finally:
        connection.close()
    _print_candidate(candidate, currentness)
    for cue in cues:
        timing = f"{cue.start}..{cue.end}" if cue.start is not None else "untimed"
        lineage = ", ".join(s.value for s in cue.source_segment_ids)
        print(f"  #{cue.ordinal} [{timing}] {cue.text!r} <- {lineage}")
    return 0


def _run_list(args) -> int:
    connection, service = _service(args.database)
    try:
        candidates = service.list_for_intake(args.intake)
        currentness = [service.currentness(candidate) for candidate in candidates]
    finally:
        connection.close()
    print(f"effective subtitle candidates for intake {args.intake}: {len(candidates)}")
    for candidate, state in zip(candidates, currentness):
        marker = "current" if state is ConsumptionCurrentness.CURRENT else state.value
        print(
            f"  {candidate.source_kind.value} {candidate.source_transcript_identity} "
            f"({candidate.cue_count} cues) [{marker}] ({candidate.identity.value})"
        )
    print("currentness is derived against the current authority; candidates are never mutated")
    return 0


def _run_status(args) -> int:
    connection, service = _service(args.database)
    try:
        candidate = service.get(args.candidate)
        if candidate is None:
            raise EffectiveSubtitleGenerationError("unknown effective subtitle candidate")
        currentness = service.currentness(candidate)
    finally:
        connection.close()
    print(f"candidate: {candidate.identity.value}")
    print(f"source: {candidate.source_kind.value} {candidate.source_transcript_identity}")
    marker = "current" if currentness is ConsumptionCurrentness.CURRENT else currentness.value
    print(f"source currentness: {marker}")
    print("a stale candidate remains an immutable, historically valid record")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.effective_subtitle_cli",
        description=(
            "Effective-transcript subtitle candidate generation (041 §15): one deterministic local "
            "generator over the exact immutable transcript source acquired solely through the "
            "effective-transcript consumption boundary. A selected-but-inapplicable corrected revision "
            "fails explicitly — no silent raw fallback — and no review, decision, selection, export, or "
            "legacy subtitle record is created or changed. Accepts identities, never media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success; 1 on malformed/unknown/unconsumable/conflicting input "
            "(repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _database(sub):
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    for name, func in (("generate", _run_generate), ("list", _run_list)):
        sub = subparsers.add_parser(
            name,
            help=("explicitly generate or reuse the deterministic candidate"
                  if name == "generate" else "list candidates generated for an intake"),
        )
        sub.add_argument("--intake", required=True, metavar="TRANSCRIPT_SOURCE_INTAKE_ID",
                         help="canonical TranscriptSourceIntakeId (the generation context)")
        _database(sub)
        sub.set_defaults(func=func)

    for name, func, help_text in (
        ("show", _run_show, "show one candidate with lineage and ordered cues"),
        ("status", _run_status, "derive one candidate's source currentness"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--candidate", required=True, metavar="EFFECTIVE_SUBTITLE_CANDIDATE_ID",
                         help="canonical effective subtitle candidate identity")
        _database(sub)
        sub.set_defaults(func=func)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
        EffectiveSubtitleGenerationError,
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
