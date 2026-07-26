"""Runnable entry point for the first Human Authority Decision on a Correction Candidate (040 §18).

One CLI over an existing repository (identities only — never media paths). It is a thin application boundary: it
contains no authority logic.

* ``decide`` — record a human Accept or Reject on an admitted correction candidate. The decision is an authority
  fact only: it is **not applied** — the candidate, Raw Transcript, current selection, and segments are unchanged,
  and no corrected revision is created;
* ``status`` — report the derived current authority (undecided / accepted / rejected) and revision eligibility;
* ``history`` — list the append-only decision history for a candidate.

On any failure it prints an explicit error, returns non-zero, and leaves the repository unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_cli decide --candidate <id> --kind accept --reviewer <who> --database <db>
    PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_cli status  --candidate <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_cli history --candidate <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.correction_candidate_decision import (
    CorrectionCandidateDecisionError,
)
from lectureos.composition import (
    compose_sqlite_correction_candidate_decision_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database


def _service(database: str):
    connection = open_sqlite_database(database)
    return connection, compose_sqlite_correction_candidate_decision_service(connection)


def _run_decide(args) -> int:
    connection, service = _service(args.database)
    try:
        result = service.decide(
            candidate_id=args.candidate,
            kind=args.kind,
            reviewer=args.reviewer,
            rationale=args.rationale,
        )
        authority = service.authority(args.candidate)
    finally:
        connection.close()
    decision = result.decision
    print(
        f"{result.outcome.value} human decision {decision.identity.value} "
        f"for candidate {decision.correction_candidate_id.value}"
    )
    print(f"kind: {decision.kind.value} (sequence {decision.sequence}, reviewer {decision.reviewer.value})")
    if result.previous is not None:
        print(f"superseded: {result.previous.kind.value}")
    print(f"current authority: {authority.status.value}")
    print("the decision was recorded as authority only — nothing was applied (candidate/transcript unchanged)")
    return 0


def _run_status(args) -> int:
    connection, service = _service(args.database)
    try:
        authority = service.authority(args.candidate)
    finally:
        connection.close()
    print(f"current authority for candidate {args.candidate}: {authority.status.value}")
    print(f"decisions: {authority.decision_count}")
    print(f"eligible for future corrected revision: {'yes' if authority.eligible_for_revision else 'no'}")
    if authority.current_decision_id is not None:
        print(f"current decision: {authority.current_decision_id.value}")
    return 0


def _run_history(args) -> int:
    connection, service = _service(args.database)
    try:
        history = service.history(args.candidate)
    finally:
        connection.close()
    print(f"decision history for candidate {args.candidate}: {len(history)}")
    for decision in history:
        print(
            f"  #{decision.sequence} {decision.kind.value} by {decision.reviewer.value} "
            f"({decision.identity.value})"
        )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.correction_candidate_decision_cli",
        description=(
            "Record or inspect the first Human Authority (Accept/Reject) on an admitted correction candidate. A "
            "decision is an authority fact only — it applies nothing, mutates no candidate or Raw Transcript, and "
            "creates no corrected revision. History is append-only; current authority is derived. Accepts "
            "identities, never media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "authority states: undecided (no decision) / accepted / rejected. Only accepted candidates become "
            "eligible for future corrected-revision generation.\n"
            "exit status: 0 on success; 1 on malformed/unknown/unsupported/conflicting/missing input "
            "(repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _common(sub):
        sub.add_argument("--candidate", required=True, metavar="CORRECTION_CANDIDATE_ID",
                         help="canonical CorrectionCandidateId (correction-candidate:<digest>) that was admitted")
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    decide = subparsers.add_parser("decide", help="record a human accept/reject decision (not applied)")
    _common(decide)
    decide.add_argument("--kind", required=True, choices=("accept", "reject"),
                        help="the human judgement (accept or reject; Modify is deferred)")
    decide.add_argument("--reviewer", required=True, metavar="ACTOR",
                        help="the deciding human actor reference (e.g. reviewer:kim)")
    decide.add_argument("--rationale", default=None, metavar="TEXT",
                        help="optional reason recorded with the decision")
    decide.set_defaults(func=_run_decide)

    status = subparsers.add_parser("status", help="report the derived current authority for a candidate")
    _common(status)
    status.set_defaults(func=_run_status)

    history = subparsers.add_parser("history", help="list the append-only decision history for a candidate")
    _common(history)
    history.set_defaults(func=_run_history)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (CorrectionCandidateDecisionError, KeyError, ValueError, OSError, PersistenceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
