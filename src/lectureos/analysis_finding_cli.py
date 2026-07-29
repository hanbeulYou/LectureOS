"""Runnable entry point for effective-generation Analysis Finding admission (042 §8.2, GOAL-025).

One CLI over an existing repository (identities only — never media paths). A thin application
boundary with no analysis logic:

* ``admit`` — admit one provider-independent finding against a CURRENT analysis input admission
  (the anchor's authority standing is re-derived at command time; exact replay reuses);
* ``show`` — one immutable canonical finding;
* ``status`` — derived: does this finding's anchor still bind the current authority?
* ``list`` — the append-only findings recorded against one admission.

**Analysis Finding admission ≠ Analysis Execution.** No analysis is performed and no provider,
prompt, model, AI call, ProcessingRun, or UnitExecution exists in this contract: the payload is
supplied by the caller and recorded verbatim as canonical Application-owned meaning. A finding
whose anchor later becomes superseded remains valid immutable history.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.analysis_finding_cli admit --admission <id> \\
        --type <token> --evidence <text> [--confidence F] [--uncertainty F] \\
        [--range-start F --range-end F] --database <db>
    PYTHONPATH=src python3 -m lectureos.analysis_finding_cli show --finding <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.analysis_finding_cli status --finding <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.analysis_finding_cli list --admission <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.corrected_revision_selection import (
    CorrectedRevisionSelectionError,
)
from lectureos.application.lecture_analysis_finding import LectureAnalysisFindingError
from lectureos.application.lecture_analysis_input_admission import (
    LectureAnalysisInputAdmissionError,
)
from lectureos.application.lecture_analysis_input_eligibility import (
    LectureAnalysisInputEligibilityError,
)
from lectureos.composition import compose_sqlite_lecture_analysis_finding_service
from lectureos.persistence import PersistenceError, open_sqlite_database

_NOT_PART = (
    "analysis execution: not part of this contract",
    "provider invocation: not part of this contract",
)


def _service(args):
    connection = open_sqlite_database(args.database)
    return connection, compose_sqlite_lecture_analysis_finding_service(connection)


def _print_finding(finding) -> None:
    print(f"analysis finding: {finding.identity.value}")
    print(f"anchor analysis input: {finding.admission_id.value}")
    print(f"finding type: {finding.finding_type}")
    print(f"evidence: {finding.evidence}")
    print(
        "confidence: "
        + ("(not recorded)" if finding.confidence is None else str(finding.confidence))
    )
    print(
        "uncertainty: "
        + ("(not recorded)" if finding.uncertainty is None else str(finding.uncertainty))
    )
    if finding.has_source_range:
        print(f"source range: {finding.range_start} -> {finding.range_end}")
    else:
        print("source range: (not located)")
    print(f"finding contract version: {finding.finding_contract_version}")
    for line in _NOT_PART:
        print(line)


def _run_admit(args) -> int:
    connection, service = _service(args)
    try:
        result = service.admit(
            admission_id=args.admission,
            finding_type=args.type,
            evidence=args.evidence,
            confidence=args.confidence,
            uncertainty=args.uncertainty,
            range_start=args.range_start,
            range_end=args.range_end,
        )
    finally:
        connection.close()
    print(f"{result.outcome.value} lecture analysis finding")
    _print_finding(result.finding)
    print(
        "the anchor's authority standing was re-derived at command time; the finding is an "
        "immutable record — later authority changes never mutate it"
    )
    return 0


def _run_show(args) -> int:
    connection, service = _service(args)
    try:
        finding = service.get(args.finding)
        if finding is None:
            raise LectureAnalysisFindingError("unknown lecture analysis finding")
    finally:
        connection.close()
    _print_finding(finding)
    return 0


def _run_status(args) -> int:
    connection, service = _service(args)
    try:
        finding = service.get(args.finding)
        if finding is None:
            raise LectureAnalysisFindingError("unknown lecture analysis finding")
        match = service.anchor_status(finding)
    finally:
        connection.close()
    print(f"analysis finding: {finding.identity.value}")
    print(f"anchor analysis input: {finding.admission_id.value}")
    print(f"anchor authority match: {match.value}")
    print(
        "a finding whose anchor became superseded remains a valid immutable historical "
        "record; currentness is derived, never stored"
    )
    for line in _NOT_PART:
        print(line)
    return 0


def _run_list(args) -> int:
    connection, service = _service(args)
    try:
        findings = service.list_for_admission(args.admission)
    finally:
        connection.close()
    print(f"lecture analysis findings for admission {args.admission}: {len(findings)}")
    for finding in findings:
        located = (
            f"{finding.range_start}->{finding.range_end}"
            if finding.has_source_range
            else "not located"
        )
        print(f"  {finding.finding_type} [{located}] ({finding.identity.value})")
    print("findings are immutable append-only records; anchor currentness is derived")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.analysis_finding_cli",
        description=(
            "Analysis Finding Application Foundation for the effective-transcript generation "
            "(042 §8.2 / PATCH-0030): one immutable identity-owning provenance-bearing finding "
            "per exact canonical content, anchored to a CURRENT analysis input admission, with "
            "idempotent replay. No analysis, provider, prompt, model, AI, ProcessingRun, or "
            "UnitExecution exists in this contract. Accepts identities, never media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success (including idempotent reuse); 1 on malformed/unknown/"
            "superseded-anchor/conflicting input (repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _database(sub):
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    admit = subparsers.add_parser(
        "admit", help="admit one finding against a current analysis input admission"
    )
    admit.add_argument("--admission", required=True, metavar="LECTURE_ANALYSIS_INPUT_ID")
    admit.add_argument("--type", required=True, metavar="FINDING_TYPE",
                       help="canonical Application-owned token (^[a-z][a-z0-9_]*$); an open "
                            "vocabulary, never a closed taxonomy")
    admit.add_argument("--evidence", required=True, metavar="TEXT",
                       help="recorded human-reviewable supporting evidence (non-empty)")
    admit.add_argument("--confidence", type=float, default=None, metavar="F",
                       help="optional recorded confidence within [0, 1] (never computed here)")
    admit.add_argument("--uncertainty", type=float, default=None, metavar="F",
                       help="optional recorded uncertainty within [0, 1]")
    admit.add_argument("--range-start", type=float, default=None, metavar="F",
                       dest="range_start",
                       help="optional single Source Timeline range start (with --range-end)")
    admit.add_argument("--range-end", type=float, default=None, metavar="F",
                       dest="range_end",
                       help="optional single Source Timeline range end (with --range-start)")
    _database(admit)
    admit.set_defaults(func=_run_admit)

    for name, func, help_text in (
        ("show", _run_show, "show one immutable canonical analysis finding"),
        ("status", _run_status,
         "derive whether a finding's anchor still binds the current authority"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--finding", required=True, metavar="LECTURE_ANALYSIS_FINDING_ID")
        _database(sub)
        sub.set_defaults(func=func)

    lst = subparsers.add_parser(
        "list", help="list analysis findings recorded against one admission"
    )
    lst.add_argument("--admission", required=True, metavar="LECTURE_ANALYSIS_INPUT_ID")
    _database(lst)
    lst.set_defaults(func=_run_list)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
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
