"""Runnable entry point for effective-generation Review (043 §7.5 + §7.6, GOAL-028/GOAL-029).

One CLI over an existing repository (identities only — never media paths). A thin application
boundary that records a human judgment and nothing else:

* ``accept`` — record acceptance of a Candidate's proposal; the approved snapshot is inherited from
  the Candidate verbatim, so no approved values are supplied;
* ``reject`` — record a durable, auditable refusal that approves nothing;
* ``modify`` — record a **complete** approved replacement (range, label, and rationale together);
* ``show`` — one immutable `ReviewDecision` and the approved snapshot it owns, if any;
* ``status`` — derived: does this decision's chain still bind the current authority?
* ``list`` — every human judgment recorded against one Candidate, as coexisting history;
* ``history`` — one (Candidate, actor) authority history, oldest position first (043 §7.6);
* ``current`` — derived: that scope's currently valid judgment and its approved snapshot;
* ``candidate-authority`` — observe whether a Candidate-level current judgment is derivable at all.

**Review ≠ edit application.** None of the three decisions executes anything: no cut, NLE operation,
rendering, export, or automatic edit exists here, and no Review Session, Review Item, withdrawal, or
revocation exists either. A decision whose chain later becomes superseded remains valid immutable
history, and no status, currentness, or selection state is stored — the current judgment of a
(Candidate, actor) scope is **derived** from the append-only authority history. Across actors nothing
is arbitrated: several people's judgments are surfaced as a conflict, never ranked.

The canonical admission is owned by the Application layer — this CLI is an interface over it and
never writes a canonical record itself.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.lecture_review_cli accept --candidate <id> \\
        --actor <human-actor> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_review_cli reject --candidate <id> \\
        --actor <human-actor> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_review_cli modify --candidate <id> \\
        --actor <human-actor> --approved-start=0.0 --approved-end=8.0 \\
        --approved-label <token> --approved-rationale <text> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_review_cli show --decision <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_review_cli status --decision <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_review_cli list --candidate <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_review_cli history --candidate <id> \
        --actor <human-actor> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_review_cli current --candidate <id> \
        --actor <human-actor> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_review_cli candidate-authority --candidate <id> \
        --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.corrected_revision_selection import (
    CorrectedRevisionSelectionError,
)
from lectureos.application.lecture_analysis_edit_candidate import (
    LectureAnalysisEditCandidateError,
)
from lectureos.application.lecture_analysis_finding import LectureAnalysisFindingError
from lectureos.application.lecture_analysis_input_admission import (
    LectureAnalysisInputAdmissionError,
)
from lectureos.application.lecture_analysis_input_eligibility import (
    LectureAnalysisInputEligibilityError,
)
from lectureos.application.lecture_review_authority import LectureReviewAuthorityError
from lectureos.application.lecture_review_decision import LectureReviewError
from lectureos.composition import compose_sqlite_lecture_review_service
from lectureos.persistence import PersistenceError, open_sqlite_database

_NOT_PART = (
    "edit application: not part of this contract",
    "cross-actor arbitration: not part of this contract",
    "review session, review item, and review history model: not part of this contract",
    "revision, withdrawal, and current-selection: not part of this contract",
    "export: not part of this contract",
)


def _service(args):
    connection = open_sqlite_database(args.database)
    return connection, compose_sqlite_lecture_review_service(connection)


def _print_decision(decision, approved) -> None:
    print(f"review decision: {decision.identity.value}")
    print(f"anchor edit candidate: {decision.candidate_id.value}")
    print(f"decision kind: {decision.decision_kind.value}")
    print(f"human actor: {decision.actor.value}")
    print(f"review contract version: {decision.review_contract_version}")
    if approved is None:
        print("approved edit decision: none (this judgment approves nothing)")
    else:
        print(f"approved edit decision: {approved.identity.value}")
        print(f"approved kind: {approved.approved_decision_kind.value}")
        print(
            f"approved range: {approved.approved_range_start} -> "
            f"{approved.approved_range_end}"
        )
        print(f"approved candidate type or label: {approved.approved_label}")
        print(f"approved rationale: {approved.approved_rationale}")
        print(f"approved contract version: {approved.approved_contract_version}")
    for line in _NOT_PART:
        print(line)


def _run_decision(args) -> int:
    connection, service = _service(args)
    try:
        result = service.admit_review_decision(
            candidate_id=args.candidate,
            decision_kind=args.decision_kind,
            actor=args.actor,
            approved_range_start=getattr(args, "approved_start", None),
            approved_range_end=getattr(args, "approved_end", None),
            approved_label=getattr(args, "approved_label", None),
            approved_rationale=getattr(args, "approved_rationale", None),
        )
    finally:
        connection.close()
    print(f"{result.outcome.value} review decision")
    _print_decision(result.decision, result.approved)
    print(f"{result.position_outcome.value} authority position")
    print(f"authority position: {result.position.identity.value}")
    print(f"authority sequence: {result.position.sequence}")
    print(
        "supersedes: "
        + (
            "none (first judgment of this scope)"
            if result.position.previous_position_id is None
            else result.position.previous_position_id.value
        )
    )
    print(
        "the anchor chain's authority standing was re-derived at command time; both records are "
        "immutable — later authority changes never mutate them, and nothing was executed"
    )
    return 0


def _run_show(args) -> int:
    connection, service = _service(args)
    try:
        decision = service.get(args.decision)
        if decision is None:
            raise LectureReviewError("unknown lecture review decision")
        approved = service.get_approved(args.decision)
    finally:
        connection.close()
    _print_decision(decision, approved)
    return 0


def _run_status(args) -> int:
    connection, service = _service(args)
    try:
        decision = service.get(args.decision)
        if decision is None:
            raise LectureReviewError("unknown lecture review decision")
        match = service.anchor_status(decision)
    finally:
        connection.close()
    print(f"review decision: {decision.identity.value}")
    print(f"anchor edit candidate: {decision.candidate_id.value}")
    print(f"anchor chain authority match: {match.value}")
    print(
        "a decision whose chain became superseded remains a valid immutable historical record; "
        "currentness is derived, never stored, and no status or selection state exists here"
    )
    for line in _NOT_PART:
        print(line)
    return 0


def _run_list(args) -> int:
    connection, service = _service(args)
    try:
        decisions = service.list_for_candidate(args.candidate)
    finally:
        connection.close()
    print(f"review decisions for candidate {args.candidate}: {len(decisions)}")
    for decision in decisions:
        print(
            f"  {decision.decision_kind.value} by {decision.actor.value} "
            f"({decision.identity.value})"
        )
    print(
        "judgments are immutable append-only records listed in a deterministic presentation order; "
        "that order is not a canonical ordinal, and this listing does not say which judgment is "
        "currently operative — reversed judgments coexist as history"
    )
    return 0


def _run_history(args) -> int:
    connection, service = _service(args)
    try:
        positions = service.authority_history(args.candidate, args.actor)
    finally:
        connection.close()
    print(f"authority history for {args.candidate} / {args.actor}: {len(positions)}")
    for position in positions:
        marker = "current" if position is positions[-1] else "superseded"
        print(
            f"  [{position.sequence}] {marker} decision={position.review_decision_id.value} "
            f"({position.identity.value})"
        )
    print(
        "every position is valid immutable history; the current judgment is the highest sequence "
        "and is derived, never stored"
    )
    return 0


def _run_current(args) -> int:
    connection, service = _service(args)
    try:
        current = service.current_review(args.candidate, args.actor)
    finally:
        connection.close()
    if current is None:
        print(f"no recorded authority history for {args.candidate} / {args.actor}")
        print(
            "absence of a position is not corruption and does not mean no judgment exists: "
            "judgments admitted before this contract carry no position and are never backfilled"
        )
        return 0
    print(f"current judgment for {args.candidate} / {args.actor}")
    print(f"authority sequence: {current.sequence}")
    print(f"superseded judgments: {current.superseded_count}")
    _print_decision(current.decision, current.approved)
    return 0


def _run_candidate_authority(args) -> int:
    connection, service = _service(args)
    try:
        observation = service.observe_candidate_authority(args.candidate)
    finally:
        connection.close()
    print(f"candidate: {observation.candidate_id.value}")
    print(f"authority status: {observation.status.value}")
    print(f"actors with history: {len(observation.actors)}")
    for actor in observation.actors:
        print(f"  {actor.value}")
    if observation.current is not None:
        print(f"current judgment: {observation.current.decision.decision_kind.value}")
        print(f"current review decision: {observation.current.decision.identity.value}")
    elif observation.is_conflict:
        print("current judgment: none — several people have judged this candidate")
        print(
            "this is a review conflict to be surfaced, not resolved: no priority among actors, no "
            "recency across actors, and no role ranking exists in this contract"
        )
    else:
        print("current judgment: none — no authority history is recorded")
    for line in _NOT_PART:
        print(line)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.lecture_review_cli",
        description=(
            "Review Foundation for the effective-transcript generation (043 §7.5 / PATCH-0033): "
            "one immutable identity-owning ReviewDecision per exact canonical judgment, anchored "
            "to a current-generation Edit Candidate whose analysis input admission is CURRENT, "
            "with exactly one ApprovedEditDecision for accept and modify and none for reject, "
            "admitted atomically with idempotent replay, together with the admission's "
            "authority-history position (043 §7.6 / PATCH-0034). The current judgment of one "
            "(candidate, actor) scope is derived from the highest position and never stored; "
            "across actors nothing is arbitrated. No edit is executed and no provider, AI, "
            "ProcessingRun, UnitExecution, DomainResult, review session, withdrawal, or export "
            "exists in this contract. Accepts identities, never media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success (including idempotent reuse); 1 on malformed/unknown/"
            "superseded-chain/conflicting input (repository left unchanged). Pass negative-looking "
            "values as --approved-start=<value>."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _database(sub):
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    def _judgment(sub):
        sub.add_argument("--candidate", required=True,
                         metavar="LECTURE_ANALYSIS_EDIT_CANDIDATE_ID")
        sub.add_argument("--actor", required=True, metavar="HUMAN_ACTOR",
                         help="human actor reference recorded as Human Authority "
                              "(non-empty, stored verbatim, part of the decision identity)")
        _database(sub)

    accept = subparsers.add_parser(
        "accept",
        help="accept a candidate's proposal as the approved editing intent",
    )
    _judgment(accept)
    accept.set_defaults(func=_run_decision, decision_kind="accept")

    reject = subparsers.add_parser(
        "reject", help="record a durable refusal that approves nothing"
    )
    _judgment(reject)
    reject.set_defaults(func=_run_decision, decision_kind="reject")

    modify = subparsers.add_parser(
        "modify",
        help="record a complete approved replacement of the candidate's review-relevant values",
    )
    _judgment(modify)
    modify.add_argument("--approved-start", required=True, dest="approved_start",
                        type=float, metavar="F",
                        help="approved range start (finite, non-negative)")
    modify.add_argument("--approved-end", required=True, dest="approved_end",
                        type=float, metavar="F",
                        help="approved range end (finite, non-negative, >= start)")
    modify.add_argument("--approved-label", required=True, dest="approved_label",
                        metavar="TOKEN",
                        help="approved candidate type or edit label; one canonical "
                             "Application-owned token (^[a-z][a-z0-9_]*$), an open vocabulary")
    modify.add_argument("--approved-rationale", required=True, dest="approved_rationale",
                        metavar="TEXT",
                        help="approved human-reviewable rationale (non-empty, stored verbatim)")
    modify.set_defaults(func=_run_decision, decision_kind="modify")

    for name, func, help_text in (
        ("show", _run_show, "show one immutable review decision and its approved snapshot"),
        ("status", _run_status,
         "derive whether a decision's chain still binds the current authority"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--decision", required=True, metavar="LECTURE_REVIEW_DECISION_ID")
        _database(sub)
        sub.set_defaults(func=func)

    lst = subparsers.add_parser(
        "list", help="list the human judgments recorded against one edit candidate"
    )
    lst.add_argument("--candidate", required=True,
                     metavar="LECTURE_ANALYSIS_EDIT_CANDIDATE_ID")
    _database(lst)
    lst.set_defaults(func=_run_list)

    for name, func, help_text in (
        ("history", _run_history,
         "show one (candidate, actor) authority history, oldest position first"),
        ("current", _run_current,
         "derive that scope's currently valid judgment and its approved snapshot"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--candidate", required=True,
                         metavar="LECTURE_ANALYSIS_EDIT_CANDIDATE_ID")
        sub.add_argument("--actor", required=True, metavar="HUMAN_ACTOR")
        _database(sub)
        sub.set_defaults(func=func)

    observe = subparsers.add_parser(
        "candidate-authority",
        help="observe whether a candidate-level current judgment is derivable at all",
    )
    observe.add_argument("--candidate", required=True,
                         metavar="LECTURE_ANALYSIS_EDIT_CANDIDATE_ID")
    _database(observe)
    observe.set_defaults(func=_run_candidate_authority)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
        LectureReviewError,
        LectureReviewAuthorityError,
        LectureAnalysisEditCandidateError,
        LectureAnalysisFindingError,
        LectureAnalysisInputAdmissionError,
        LectureAnalysisInputEligibilityError,
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
