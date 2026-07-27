"""Runnable entry point for Human Decisions over Effective-Source Review Subjects (GOAL-015).

One CLI over an existing repository (identities only — never media paths). A thin application boundary with no
authority logic:

* ``decide`` — record one explicit Accept/Reject/Modify judgment by a truthful Human actor about one exact
  review subject (append-only; a matching current authority is reused idempotently);
* ``show`` — one decision with its full provenance;
* ``history`` — the append-only decision transitions of one review subject;
* ``current`` — the derived current decision of one review subject;
* ``status`` — one decision's derived currentness and applicability.

The reviewer is explicit provenance (``--reviewer``, a `HumanActorReference` such as ``reviewer:kim``) — never
inferred from the OS user or environment, and never authorization. A decision records authority only: Accept
creates no final selection or export; Reject deletes nothing; Modify edits nothing. No ``--force``. On any
failure it prints an explicit error, returns non-zero, and leaves the repository unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.effective_decision_cli decide --review-subject <id> --decision accept --reviewer reviewer:kim --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_decision_cli show --decision <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_decision_cli history --review-subject <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_decision_cli current --review-subject <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_decision_cli status --decision <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.effective_subtitle_review_decision import (
    EffectiveSubtitleReviewDecisionError,
)
from lectureos.application.effective_subtitle_review_preparation import (
    EffectiveSubtitleReviewPreparationError,
)
from lectureos.composition import (
    compose_sqlite_effective_subtitle_review_decision_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database

_NOT_PART = (
    "final selection state: not part of this contract",
    "export state: not part of this contract",
)


def _service(database: str):
    connection = open_sqlite_database(database)
    return connection, compose_sqlite_effective_subtitle_review_decision_service(connection)


def _print_decision(decision, current=None, applicability=None) -> None:
    print(f"decision: {decision.identity.value}")
    print(f"review subject: {decision.review_subject_id.value}")
    print(f"decision kind: {decision.kind.value}")
    print(f"reviewer: {decision.reviewer.value}")
    print(f"sequence: {decision.sequence}")
    if current is not None:
        marker = "yes" if current.identity == decision.identity else "no"
        print(f"current decision: {current.identity.value}")
        print(f"this decision is current: {marker}")
    if applicability is not None:
        print(f"decision applicability: {applicability.value}")
    for line in _NOT_PART:
        print(line)


def _run_decide(args) -> int:
    connection, service = _service(args.database)
    try:
        result = service.decide(
            review_subject_id=args.review_subject,
            kind=args.decision,
            reviewer=args.reviewer,
            rationale=args.rationale,
        )
        applicability = service.applicability(result.decision)
        status = service.subject_status(result.decision)
    finally:
        connection.close()
    print(f"{result.outcome.value} effective subtitle review decision")
    _print_decision(result.decision, current=result.decision, applicability=applicability)
    if result.previous is not None:
        print(f"superseded decision: {result.previous.identity.value} ({result.previous.kind.value})")
    print(f"candidate source currentness: {status.candidate_source_currentness.value}")
    print(f"review subject currentness: {status.review_subject_currentness.value}")
    print(
        "no candidate, cue, review subject, final selection, or export record was "
        "created or changed (a decision records authority only)"
    )
    return 0


def _run_show(args) -> int:
    connection, service = _service(args.database)
    try:
        decision = service.get(args.decision)
        if decision is None:
            raise EffectiveSubtitleReviewDecisionError(
                "unknown effective subtitle review decision"
            )
        current = service.current(decision.review_subject_id.value)
        applicability = service.applicability(decision)
    finally:
        connection.close()
    _print_decision(decision, current=current, applicability=applicability)
    if decision.rationale:
        print(f"rationale: {decision.rationale}")
    return 0


def _run_history(args) -> int:
    connection, service = _service(args.database)
    try:
        history = service.history(args.review_subject)
        current = history[-1] if history else None
    finally:
        connection.close()
    print(f"decision history for review subject {args.review_subject}: {len(history)}")
    for decision in history:
        marker = (
            "  *current"
            if current is not None and decision.identity == current.identity
            else ""
        )
        print(
            f"  #{decision.sequence} {decision.kind.value} by {decision.reviewer.value} "
            f"({decision.identity.value}){marker}"
        )
    print("history is append-only; earlier decisions are never mutated or deleted")
    return 0


def _run_current(args) -> int:
    connection, service = _service(args.database)
    try:
        current = service.current(args.review_subject)
        applicability = service.applicability(current) if current is not None else None
    finally:
        connection.close()
    if current is None:
        print(f"review subject {args.review_subject} has no decision history")
        for line in _NOT_PART:
            print(line)
        return 0
    print("current decision (derived from the highest immutable sequence):")
    _print_decision(current, current=current, applicability=applicability)
    return 0


def _run_status(args) -> int:
    connection, service = _service(args.database)
    try:
        decision = service.get(args.decision)
        if decision is None:
            raise EffectiveSubtitleReviewDecisionError(
                "unknown effective subtitle review decision"
            )
        applicability = service.applicability(decision)
        status = service.subject_status(decision)
    finally:
        connection.close()
    print(f"decision: {decision.identity.value} ({decision.kind.value})")
    print(f"decision applicability: {applicability.value}")
    print(f"candidate source currentness: {status.candidate_source_currentness.value}")
    print(f"review subject currentness: {status.review_subject_currentness.value}")
    print("a superseded or stale decision remains an immutable historical record")
    for line in _NOT_PART:
        print(line)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.effective_decision_cli",
        description=(
            "Explicit Human Decisions (accept/reject/modify) over effective-source subtitle review "
            "subjects: append-only authority with derived current decision and derived "
            "applicability. Accept implies no final selection or export; Reject deletes nothing; "
            "Modify edits nothing. The reviewer is explicit provenance, never authorization. "
            "Accepts identities, never media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success (including idempotent reuse); 1 on malformed/unknown/"
            "broken-graph/conflicting input (repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _database(sub):
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    decide = subparsers.add_parser(
        "decide", help="record one explicit accept/reject/modify judgment"
    )
    decide.add_argument("--review-subject", required=True,
                        metavar="EFFECTIVE_SUBTITLE_REVIEW_SUBJECT_ID",
                        help="exact review subject identity (never latest/current implicitly)")
    decide.add_argument("--decision", required=True, metavar="KIND",
                        help="accept | reject | modify (closed set)")
    decide.add_argument("--reviewer", required=True, metavar="ACTOR",
                        help="the deciding human actor reference (e.g. reviewer:kim)")
    decide.add_argument("--rationale", default=None, metavar="TEXT",
                        help="optional reason recorded with the decision")
    _database(decide)
    decide.set_defaults(func=_run_decide)

    for name, func, arg, metavar, help_text in (
        ("show", _run_show, "--decision", "EFFECTIVE_SUBTITLE_REVIEW_DECISION_ID",
         "show one decision with provenance"),
        ("history", _run_history, "--review-subject", "EFFECTIVE_SUBTITLE_REVIEW_SUBJECT_ID",
         "list the append-only decision transitions"),
        ("current", _run_current, "--review-subject", "EFFECTIVE_SUBTITLE_REVIEW_SUBJECT_ID",
         "show the derived current decision"),
        ("status", _run_status, "--decision", "EFFECTIVE_SUBTITLE_REVIEW_DECISION_ID",
         "derive one decision's applicability and currentness"),
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
