"""Runnable entry point for effective-generation Edit Candidate admission (042 §9.3, GOAL-027).

One CLI over an existing repository (identities only — never media paths). A thin application
boundary with no candidate-generation logic:

* ``admit`` — admit one provider-independent candidate against a Finding whose analysis input
  admission is CURRENT (the chain's standing is re-derived at command time; exact replay reuses);
* ``show`` — one immutable canonical candidate;
* ``status`` — derived: does this candidate's chain still bind the current authority?
* ``list`` — the append-only candidates recorded against one Finding.

**Edit Candidate admission ≠ candidate generation, ≠ Review, ≠ Analysis Execution.** No candidate
is proposed here and no provider, prompt, model, AI call, ProcessingRun, UnitExecution, or
DomainResult exists in this contract. No Lecture Segment is required or referenced. A candidate
whose chain later becomes superseded remains valid immutable history, and it carries no review or
selection state.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.analysis_edit_candidate_cli admit --finding <id> \\
        --candidate-type <token> --start 0.0 --end 12.5 --rationale <text> --database <db>
    PYTHONPATH=src python3 -m lectureos.analysis_edit_candidate_cli show --candidate <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.analysis_edit_candidate_cli status --candidate <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.analysis_edit_candidate_cli list --finding <id> --database <db>
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
from lectureos.composition import compose_sqlite_lecture_analysis_edit_candidate_service
from lectureos.persistence import PersistenceError, open_sqlite_database

_NOT_PART = (
    "candidate provider: not part of this contract",
    "review workflow: not part of this contract",
    "analysis execution: not part of this contract",
)


def _service(args):
    connection = open_sqlite_database(args.database)
    return connection, compose_sqlite_lecture_analysis_edit_candidate_service(connection)


def _print_candidate(candidate) -> None:
    print(f"edit candidate: {candidate.identity.value}")
    print(f"anchor analysis finding: {candidate.finding_id.value}")
    print(f"candidate type: {candidate.candidate_type}")
    print(f"source range: {candidate.range_start} -> {candidate.range_end}")
    print(f"rationale: {candidate.rationale}")
    print(f"candidate contract version: {candidate.candidate_contract_version}")
    for line in _NOT_PART:
        print(line)


def _run_admit(args) -> int:
    connection, service = _service(args)
    try:
        result = service.admit_edit_candidate(
            finding_id=args.finding,
            candidate_type=args.candidate_type,
            range_start=args.start,
            range_end=args.end,
            rationale=args.rationale,
        )
    finally:
        connection.close()
    print(f"{result.outcome.value} edit candidate")
    _print_candidate(result.candidate)
    print(
        "the anchor chain's authority standing was re-derived at command time; the candidate is "
        "an immutable record — later authority changes never mutate it"
    )
    return 0


def _run_show(args) -> int:
    connection, service = _service(args)
    try:
        candidate = service.get(args.candidate)
        if candidate is None:
            raise LectureAnalysisEditCandidateError("unknown lecture analysis edit candidate")
    finally:
        connection.close()
    _print_candidate(candidate)
    return 0


def _run_status(args) -> int:
    connection, service = _service(args)
    try:
        candidate = service.get(args.candidate)
        if candidate is None:
            raise LectureAnalysisEditCandidateError("unknown lecture analysis edit candidate")
        match = service.anchor_status(candidate)
    finally:
        connection.close()
    print(f"edit candidate: {candidate.identity.value}")
    print(f"anchor analysis finding: {candidate.finding_id.value}")
    print(f"anchor chain authority match: {match.value}")
    print(
        "a candidate whose chain became superseded remains a valid immutable historical record; "
        "currentness is derived, never stored, and no review or selection state exists here"
    )
    for line in _NOT_PART:
        print(line)
    return 0


def _run_list(args) -> int:
    connection, service = _service(args)
    try:
        candidates = service.list_for_finding(args.finding)
    finally:
        connection.close()
    print(f"edit candidates for finding {args.finding}: {len(candidates)}")
    for candidate in candidates:
        print(
            f"  {candidate.candidate_type} "
            f"[{candidate.range_start}->{candidate.range_end}] "
            f"({candidate.identity.value})"
        )
    print(
        "candidates are immutable append-only records listed in a deterministic presentation "
        "order; that order is not a canonical ordinal and chain currentness is derived"
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.analysis_edit_candidate_cli",
        description=(
            "Edit Candidate Foundation for the effective-transcript generation "
            "(042 §9.3 / PATCH-0032): one immutable identity-owning candidate per exact canonical "
            "content, anchored to a current-generation Analysis Finding whose analysis input "
            "admission is CURRENT, with idempotent replay. No candidate provider, prompt, model, "
            "AI, ProcessingRun, UnitExecution, DomainResult, Lecture Segment dependency, review, "
            "or selection exists in this contract. Accepts identities, never media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success (including idempotent reuse); 1 on malformed/unknown/"
            "superseded-chain/conflicting input (repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _database(sub):
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    admit = subparsers.add_parser(
        "admit", help="admit one candidate against a current-chain analysis finding"
    )
    admit.add_argument("--finding", required=True, metavar="LECTURE_ANALYSIS_FINDING_ID")
    admit.add_argument("--candidate-type", required=True, dest="candidate_type",
                       metavar="CANDIDATE_TYPE",
                       help="canonical Application-owned token (^[a-z][a-z0-9_]*$); an open "
                            "vocabulary, never a closed taxonomy")
    admit.add_argument("--start", required=True, type=float, metavar="F",
                       help="source range start (finite, non-negative)")
    admit.add_argument("--end", required=True, type=float, metavar="F",
                       help="source range end (finite, non-negative, >= start; "
                            "zero-duration allowed)")
    admit.add_argument("--rationale", required=True, metavar="TEXT",
                       help="recorded human-reviewable reason for this advisory proposal "
                            "(non-empty, stored verbatim)")
    _database(admit)
    admit.set_defaults(func=_run_admit)

    for name, func, help_text in (
        ("show", _run_show, "show one immutable canonical edit candidate"),
        ("status", _run_status,
         "derive whether a candidate's chain still binds the current authority"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--candidate", required=True,
                         metavar="LECTURE_ANALYSIS_EDIT_CANDIDATE_ID")
        _database(sub)
        sub.set_defaults(func=func)

    lst = subparsers.add_parser(
        "list", help="list edit candidates recorded against one analysis finding"
    )
    lst.add_argument("--finding", required=True, metavar="LECTURE_ANALYSIS_FINDING_ID")
    _database(lst)
    lst.set_defaults(func=_run_list)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
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
