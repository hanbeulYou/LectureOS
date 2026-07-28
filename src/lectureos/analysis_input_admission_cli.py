"""Runnable entry point for Explicit Lecture Analysis Input Admission (GOAL-023).

One CLI over an existing repository (identities only — never media paths). A thin application
boundary with no analysis logic:

* ``admit`` — explicitly admit the intake's CURRENT effective transcript authority as one
  immutable analysis input (eligibility is revalidated at command time; replay reuses);
* ``show`` — one immutable admitted analysis input with its exact authority snapshot;
* ``status`` — derived: does an admission still bind the current authority?
* ``list`` — the append-only admissions recorded for one intake scope.

**Admission ≠ Analysis Execution.** No Analysis Run, ProcessingRun, Finding, Artifact, or AI
reasoning exists in this contract; the admitted record is the durable 042 §5.1 analysis basis
only. A superseded admission remains valid immutable history.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.analysis_input_admission_cli admit --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.analysis_input_admission_cli show --admission <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.analysis_input_admission_cli status --admission <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.analysis_input_admission_cli list --intake <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.corrected_revision_selection import (
    CorrectedRevisionSelectionError,
)
from lectureos.application.lecture_analysis_input_admission import (
    LectureAnalysisInputAdmissionError,
)
from lectureos.application.lecture_analysis_input_eligibility import (
    LectureAnalysisInputEligibilityError,
)
from lectureos.composition import (
    compose_sqlite_lecture_analysis_input_admission_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database

_NOT_PART = (
    "analysis execution state: not part of this contract",
    "analysis findings: not part of this contract",
)


def _service(args):
    connection = open_sqlite_database(args.database)
    return connection, compose_sqlite_lecture_analysis_input_admission_service(connection)


def _print_admission(admission) -> None:
    print(f"analysis input: {admission.identity.value}")
    print(f"scope intake: {admission.transcript_source_intake_id.value}")
    print(f"source media: {admission.source_media_id.value}")
    print(f"corrected revision: {admission.corrected_revision_id.value}")
    print(f"parent raw transcript: {admission.parent_raw_transcript_id.value}")
    print(f"raw selection: {admission.raw_selection_id.value}")
    print(f"corrected selection: {admission.corrected_selection_id.value}")
    print(f"content fingerprint: {admission.content_fingerprint}")
    print(f"segments: {admission.segment_count}")
    print(f"admission contract version: {admission.admission_contract_version}")
    for line in _NOT_PART:
        print(line)


def _run_admit(args) -> int:
    connection, service = _service(args)
    try:
        result = service.admit(intake_id=args.intake)
    finally:
        connection.close()
    print(f"{result.outcome.value} lecture analysis input")
    _print_admission(result.admission)
    print(
        "eligibility was revalidated at command time; the record is an immutable snapshot "
        "of the authority as admitted — later authority changes never mutate it"
    )
    return 0


def _run_show(args) -> int:
    connection, service = _service(args)
    try:
        admission = service.get(args.admission)
        if admission is None:
            raise LectureAnalysisInputAdmissionError(
                "unknown lecture analysis input admission"
            )
    finally:
        connection.close()
    _print_admission(admission)
    return 0


def _run_status(args) -> int:
    connection, service = _service(args)
    try:
        admission = service.get(args.admission)
        if admission is None:
            raise LectureAnalysisInputAdmissionError(
                "unknown lecture analysis input admission"
            )
        match = service.authority_match(admission)
    finally:
        connection.close()
    print(f"analysis input: {admission.identity.value}")
    print(f"admitted corrected revision: {admission.corrected_revision_id.value}")
    print(f"current authority match: {match.value}")
    print("a superseded admission remains a valid immutable historical record")
    for line in _NOT_PART:
        print(line)
    return 0


def _run_list(args) -> int:
    connection, service = _service(args)
    try:
        admissions = service.list_for_intake(args.intake)
        matches = [service.authority_match(admission) for admission in admissions]
    finally:
        connection.close()
    print(f"lecture analysis inputs for intake {args.intake}: {len(admissions)}")
    for admission, match in zip(admissions, matches):
        print(
            f"  revision {admission.corrected_revision_id.value} "
            f"({admission.segment_count} segments) [{match.value}] "
            f"({admission.identity.value})"
        )
    print("admissions are immutable append-only records; authority match is derived")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.analysis_input_admission_cli",
        description=(
            "Explicit Lecture Analysis Input Admission (042 Milestone 1, durable record): "
            "revalidated eligibility, one immutable identity-owning provenance-bearing "
            "analysis input per exact admitted authority, idempotent replay. No analysis, "
            "execution, or AI exists in this contract. Accepts identities, never media paths."
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

    admit = subparsers.add_parser(
        "admit", help="explicitly admit the current effective authority as analysis input"
    )
    admit.add_argument("--intake", required=True,
                       metavar="TRANSCRIPT_SOURCE_INTAKE_ID")
    _database(admit)
    admit.set_defaults(func=_run_admit)

    for name, func, help_text in (
        ("show", _run_show, "show one immutable admitted analysis input"),
        ("status", _run_status,
         "derive whether an admission still binds the current authority"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--admission", required=True,
                         metavar="LECTURE_ANALYSIS_INPUT_ID")
        _database(sub)
        sub.set_defaults(func=func)

    lst = subparsers.add_parser(
        "list", help="list admitted analysis inputs for an intake scope"
    )
    lst.add_argument("--intake", required=True, metavar="TRANSCRIPT_SOURCE_INTAKE_ID")
    _database(lst)
    lst.set_defaults(func=_run_list)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
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
