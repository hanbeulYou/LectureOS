"""Runnable entry point for effective-generation Lecture Segmentation (042 §7.2, GOAL-026).

One CLI over an existing repository (identities only — never media paths). A thin application
boundary with no segmentation logic:

* ``admit`` — admit one ORDERED batch of segments against a CURRENT analysis input admission
  (the anchor's authority standing is re-derived at command time; exact replay reuses);
* ``show`` — one immutable canonical segment;
* ``status`` — derived: does this segment's anchor still bind the current authority?
* ``list`` — the append-only segments recorded against one admission, in canonical order.

**Lecture Segmentation ≠ Analysis Execution, and ≠ Analysis Finding.** No segmentation is performed
and no provider, prompt, model, AI call, ProcessingRun, UnitExecution, or DomainResult exists in
this contract. No Analysis Finding is required or created: the two are siblings over the same kind
of admission. A segment whose anchor later becomes superseded remains valid immutable history.

Batch positions are the sequence: ``--segment`` may be repeated, and the order given is the order
recorded (position 0, 1, 2, …).

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.analysis_segment_cli admit --admission <id> \\
        --segment 0.0:12.5 --segment 12.5:30.0 --database <db>
    PYTHONPATH=src python3 -m lectureos.analysis_segment_cli show --segment-id <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.analysis_segment_cli status --segment-id <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.analysis_segment_cli list --admission <id> --database <db>
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
from lectureos.application.lecture_analysis_segment import LectureAnalysisSegmentError
from lectureos.composition import compose_sqlite_lecture_analysis_segmentation_service
from lectureos.persistence import PersistenceError, open_sqlite_database

_NOT_PART = (
    "segmentation provider: not part of this contract",
    "analysis execution: not part of this contract",
)


def _service(args):
    connection = open_sqlite_database(args.database)
    return connection, compose_sqlite_lecture_analysis_segmentation_service(connection)


def _parse_range(value: str) -> tuple[float, float]:
    """Parse ``start:end``. Numeric canonicalization happens in the Application boundary, so an
    integral spelling such as ``1:2`` yields the same canonical identity as ``1.0:2.0``."""

    parts = value.split(":")
    if len(parts) != 2:
        raise LectureAnalysisSegmentError(
            f"segment must be given as start:end (received {value!r})"
        )
    try:
        return float(parts[0]), float(parts[1])
    except ValueError as error:
        raise LectureAnalysisSegmentError(
            f"segment bounds must be numbers (received {value!r})"
        ) from error


def _print_segment(segment) -> None:
    print(f"lecture segment: {segment.identity.value}")
    print(f"anchor analysis input: {segment.admission_id.value}")
    print(f"sequence: {segment.sequence}")
    print(f"source range: {segment.range_start} -> {segment.range_end}")
    print(f"segment contract version: {segment.segment_contract_version}")
    for line in _NOT_PART:
        print(line)


def _run_admit(args) -> int:
    ranges = [_parse_range(value) for value in args.segment]
    connection, service = _service(args)
    try:
        result = service.admit_segmentation(
            admission_id=args.admission, ranges=ranges
        )
    finally:
        connection.close()
    print(f"{result.outcome.value} lecture segmentation")
    print(f"anchor analysis input: {result.admission.identity.value}")
    print(f"segments in batch: {len(result.segments)}")
    print(f"newly recorded: {result.recorded_count}")
    print(f"already present: {result.reused_count}")
    for segment in result.segments:
        print(
            f"  [{segment.sequence}] {segment.range_start} -> {segment.range_end} "
            f"({segment.identity.value})"
        )
    print(
        "the anchor's authority standing was re-derived at command time; segments are "
        "immutable — later authority changes never mutate them"
    )
    for line in _NOT_PART:
        print(line)
    return 0


def _run_show(args) -> int:
    connection, service = _service(args)
    try:
        segment = service.get(args.segment_id)
        if segment is None:
            raise LectureAnalysisSegmentError("unknown lecture analysis segment")
    finally:
        connection.close()
    _print_segment(segment)
    return 0


def _run_status(args) -> int:
    connection, service = _service(args)
    try:
        segment = service.get(args.segment_id)
        if segment is None:
            raise LectureAnalysisSegmentError("unknown lecture analysis segment")
        match = service.anchor_status(segment)
    finally:
        connection.close()
    print(f"lecture segment: {segment.identity.value}")
    print(f"anchor analysis input: {segment.admission_id.value}")
    print(f"anchor authority match: {match.value}")
    print(
        "a segment whose anchor became superseded remains a valid immutable historical "
        "record; currentness is derived, never stored"
    )
    for line in _NOT_PART:
        print(line)
    return 0


def _run_list(args) -> int:
    connection, service = _service(args)
    try:
        segments = service.list_for_admission(args.admission)
    finally:
        connection.close()
    print(f"lecture segments for admission {args.admission}: {len(segments)}")
    for segment in segments:
        print(
            f"  [{segment.sequence}] {segment.range_start} -> {segment.range_end} "
            f"({segment.identity.value})"
        )
    print(
        "segments are immutable append-only records ordered by sequence then identity; "
        "several batches may share a sequence and anchor currentness is derived"
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.analysis_segment_cli",
        description=(
            "Lecture Segmentation Foundation for the effective-transcript generation "
            "(042 §7.2 / PATCH-0031): one ordered batch of immutable identity-owning "
            "provenance-bearing segments per command, anchored to a CURRENT analysis input "
            "admission, recorded atomically with idempotent replay. No segmentation provider, "
            "prompt, model, AI, ProcessingRun, UnitExecution, or Analysis Finding dependency "
            "exists in this contract. Accepts identities, never media paths."
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
        "admit", help="admit one ordered segment batch against a current admission"
    )
    admit.add_argument("--admission", required=True, metavar="LECTURE_ANALYSIS_INPUT_ID")
    admit.add_argument("--segment", required=True, action="append", metavar="START:END",
                       help="repeatable; the order given is the recorded sequence "
                            "(finite, non-negative, start <= end; zero-duration allowed)")
    _database(admit)
    admit.set_defaults(func=_run_admit)

    for name, func, help_text in (
        ("show", _run_show, "show one immutable canonical lecture segment"),
        ("status", _run_status,
         "derive whether a segment's anchor still binds the current authority"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--segment-id", required=True, dest="segment_id",
                         metavar="LECTURE_ANALYSIS_SEGMENT_ID")
        _database(sub)
        sub.set_defaults(func=func)

    lst = subparsers.add_parser(
        "list", help="list lecture segments recorded against one admission"
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
        LectureAnalysisSegmentError,
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
