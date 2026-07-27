"""Runnable entry point for Effective Subtitle Final Selection (GOAL-016).

One CLI over an existing repository (identities only — never media paths). A thin application boundary with no
authority logic:

* ``eligibility`` — derive whether one exact review subject may receive a NEW final selection now
  (requires a current, applicable Accept decision), with explicit blocking reasons;
* ``select`` — record one explicit final selection by a truthful Human selector (append-only; a matching
  current authority state is reused idempotently);
* ``show`` — one selection with its full authority lineage;
* ``history`` — the append-only selection transitions of one intake scope;
* ``current`` — the derived current final selection of one intake scope;
* ``status`` — one selection's derived currentness and applicability.

Accept ≠ Final Selection ≠ export: selecting requires an explicit command over an eligible subject, and a
current applicable selection grants no export eligibility (export is a later goal). The selector is explicit
provenance (never inferred from the reviewer, and never authorization). No ``--force``. On any failure it
prints an explicit error, returns non-zero, and leaves the repository unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.effective_selection_cli eligibility --review-subject <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_selection_cli select --review-subject <id> --selector selector:kim --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_selection_cli show --selection <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_selection_cli history --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_selection_cli current --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_selection_cli status --selection <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.effective_subtitle_final_selection import (
    EffectiveSubtitleFinalSelectionError,
    SelectionApplicability,
)
from lectureos.application.effective_subtitle_review_decision import (
    EffectiveSubtitleReviewDecisionError,
)
from lectureos.application.effective_subtitle_review_preparation import (
    EffectiveSubtitleReviewPreparationError,
)
from lectureos.composition import (
    compose_sqlite_effective_subtitle_final_selection_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database


def _service(database: str):
    connection = open_sqlite_database(database)
    return connection, compose_sqlite_effective_subtitle_final_selection_service(connection)


def _print_selection(selection, current=None, applicability=None) -> None:
    print(f"selection: {selection.identity.value}")
    print(f"scope intake: {selection.transcript_source_intake_id.value}")
    print(f"sequence: {selection.sequence}")
    print(f"candidate: {selection.candidate_id.value}")
    print(f"review subject: {selection.review_subject_id.value}")
    print(f"supporting accept decision: {selection.supporting_decision_id.value}")
    print(f"selector: {selection.selector.value}")
    if selection.previous_selection_id is not None:
        print(f"previous selection: {selection.previous_selection_id.value}")
    if current is not None:
        marker = "yes" if current.identity == selection.identity else "no"
        print(f"current final selection: {current.identity.value}")
        print(f"this selection is current: {marker}")
    if applicability is not None:
        marker = (
            "applicable"
            if applicability is SelectionApplicability.APPLICABLE
            else applicability.value
        )
        print(f"selection applicability: {marker}")
    print("export state: not part of this contract")


def _run_eligibility(args) -> int:
    connection, service = _service(args.database)
    try:
        report = service.eligibility(args.review_subject)
    finally:
        connection.close()
    print(f"review subject: {report.review_subject_id.value}")
    print(f"candidate: {report.candidate_id.value}")
    print(f"eligible for a new final selection: {'yes' if report.eligible else 'no'}")
    if report.current_decision_id is not None:
        print(f"current decision: {report.current_decision_id.value}")
        print(f"current decision kind: {report.current_decision_kind.value}")
        print(f"decision applicability: {report.decision_applicability.value}")
    else:
        print("current decision: none")
    print(f"candidate source currentness: {report.candidate_source_currentness.value}")
    print(f"review subject currentness: {report.review_subject_currentness.value}")
    if report.blocking_reason is not None:
        print(f"blocking reason: {report.blocking_reason.value}")
    print("eligibility is derived and never persisted; it grants no selection authority")
    return 0


def _run_select(args) -> int:
    connection, service = _service(args.database)
    try:
        result = service.select_final(
            review_subject_id=args.review_subject,
            selector=args.selector,
            rationale=args.rationale,
        )
        applicability = service.applicability(result.selection)
    finally:
        connection.close()
    print(f"{result.outcome.value} effective subtitle final selection")
    _print_selection(result.selection, current=result.selection, applicability=applicability)
    if result.previous is not None:
        print(
            f"superseded selection: {result.previous.identity.value} "
            f"(candidate {result.previous.candidate_id.value})"
        )
    print(
        "no candidate, review subject, decision, export, or legacy selection record was "
        "created or changed (a final selection records authority only)"
    )
    return 0


def _run_show(args) -> int:
    connection, service = _service(args.database)
    try:
        selection = service.get(args.selection)
        if selection is None:
            raise EffectiveSubtitleFinalSelectionError(
                "unknown effective subtitle final selection"
            )
        current = service.current(selection.transcript_source_intake_id.value)
        applicability = service.applicability(selection)
    finally:
        connection.close()
    _print_selection(selection, current=current, applicability=applicability)
    if selection.rationale:
        print(f"rationale: {selection.rationale}")
    return 0


def _run_history(args) -> int:
    connection, service = _service(args.database)
    try:
        history = service.history(args.intake)
        current = history[-1] if history else None
    finally:
        connection.close()
    print(f"final selection history for intake {args.intake}: {len(history)}")
    for selection in history:
        marker = (
            "  *current"
            if current is not None and selection.identity == current.identity
            else ""
        )
        print(
            f"  #{selection.sequence} candidate {selection.candidate_id.value} "
            f"by {selection.selector.value} ({selection.identity.value}){marker}"
        )
    print("history is append-only; earlier selections are never mutated or deleted")
    return 0


def _run_current(args) -> int:
    connection, service = _service(args.database)
    try:
        current = service.current(args.intake)
        applicability = service.applicability(current) if current is not None else None
    finally:
        connection.close()
    if current is None:
        print(f"intake {args.intake} has no final selection history")
        print("export state: not part of this contract")
        return 0
    print("current final selection (derived from the highest immutable sequence):")
    _print_selection(current, current=current, applicability=applicability)
    return 0


def _run_status(args) -> int:
    connection, service = _service(args.database)
    try:
        selection = service.get(args.selection)
        if selection is None:
            raise EffectiveSubtitleFinalSelectionError(
                "unknown effective subtitle final selection"
            )
        applicability = service.applicability(selection)
        supporting = service.supporting_decision(selection)
        supporting_applicability = service.supporting_decision_applicability(selection)
    finally:
        connection.close()
    print(f"selection: {selection.identity.value}")
    print(f"selection applicability: {applicability.value}")
    print(
        f"supporting decision: {supporting.identity.value} ({supporting.kind.value}, "
        f"{supporting_applicability.value})"
    )
    print("a superseded or stale selection remains an immutable historical record")
    print("export state: not part of this contract")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.effective_selection_cli",
        description=(
            "Final Subtitle Selection Authority for effective-source candidates: derived "
            "eligibility (a current applicable Accept is required; reject/modify/superseded "
            "accepts are never eligible), explicit append-only selection with derived current "
            "selection and derived applicability. Accept is not selection; selection is not "
            "export. Accepts identities, never media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success (including idempotent reuse); 1 on malformed/unknown/"
            "ineligible/conflicting input (repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _database(sub):
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    eligibility = subparsers.add_parser(
        "eligibility", help="derive whether a subject may receive a new final selection"
    )
    eligibility.add_argument("--review-subject", required=True,
                             metavar="EFFECTIVE_SUBTITLE_REVIEW_SUBJECT_ID")
    _database(eligibility)
    eligibility.set_defaults(func=_run_eligibility)

    select = subparsers.add_parser("select", help="record one explicit final selection")
    select.add_argument("--review-subject", required=True,
                        metavar="EFFECTIVE_SUBTITLE_REVIEW_SUBJECT_ID",
                        help="exact review subject identity (never latest/current implicitly)")
    select.add_argument("--selector", required=True, metavar="ACTOR",
                        help="the selecting human actor reference (e.g. selector:kim)")
    select.add_argument("--rationale", default=None, metavar="TEXT",
                        help="optional reason recorded with the selection")
    _database(select)
    select.set_defaults(func=_run_select)

    for name, func, arg, metavar, help_text in (
        ("show", _run_show, "--selection", "EFFECTIVE_SUBTITLE_FINAL_SELECTION_ID",
         "show one selection with authority lineage"),
        ("history", _run_history, "--intake", "TRANSCRIPT_SOURCE_INTAKE_ID",
         "list the append-only selection transitions"),
        ("current", _run_current, "--intake", "TRANSCRIPT_SOURCE_INTAKE_ID",
         "show the derived current final selection"),
        ("status", _run_status, "--selection", "EFFECTIVE_SUBTITLE_FINAL_SELECTION_ID",
         "derive one selection's applicability"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument(arg, required=True, metavar=metavar)
        _database(sub)
        sub.set_defaults(func=func)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
        EffectiveSubtitleFinalSelectionError,
        EffectiveSubtitleReviewDecisionError,
        EffectiveSubtitleReviewPreparationError,
        KeyError,
        ValueError,
        OSError,
        PersistenceError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
