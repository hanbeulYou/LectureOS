"""Runnable entry point for provider evidence inspection and the transcript quality diagnostic (040 §15).

Two read-only views over an already-admitted provider transcript result:

* ``inspect`` — what provider decode evidence was preserved with the result, and at what granularity.
* ``diagnose`` — the derived quality diagnostic: its algorithm anchor, what it could decide, and
  **why it could not decide the rest**.

Neither command writes anything. `PATCH-0045` QD-10 makes the diagnostic a derived observation that is
never stored, and QD-16 forbids any automatic correction or deletion, so there is deliberately no
subcommand that changes a transcript.

The output never says "clean". Zero findings today means the threshold policy is deferred and the
repetition rule is uncontracted, not that the transcript was examined and found sound — QD-9 requires
that difference to stay visible, so every undecided reason is printed with its cause.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.transcript_quality_cli inspect \\
        --admission <provider-transcript-admission-id> --database <db-path>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.transcript_quality_diagnostic import (
    DiagnosticCompleteness,
    TranscriptQualityDiagnosticError,
)
from lectureos.composition import compose_sqlite_transcript_quality_diagnostic_service
from lectureos.persistence import PersistenceError, open_sqlite_database


def run_diagnostic(*, database: str, admission_id: str):
    connection = open_sqlite_database(database)
    try:
        service = compose_sqlite_transcript_quality_diagnostic_service(connection)
        return service.diagnose(admission_id=admission_id)
    finally:
        connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.transcript_quality_cli",
        description=(
            "Inspect the provider decode evidence preserved with an admitted provider transcript "
            "result, and compute the derived transcript quality diagnostic. Both commands are "
            "read-only: the diagnostic is never stored, and nothing here corrects or deletes "
            "transcript text."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success; 1 on a malformed or unknown admission identity, a missing "
            "provider result or raw transcript, or any repository error."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("inspect", "show the preserved provider decode evidence and its granularity"),
        ("diagnose", "compute the derived quality diagnostic and report what it could not decide"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument(
            "--admission",
            required=True,
            metavar="PROVIDER_TRANSCRIPT_ADMISSION_ID",
            help="canonical ProviderTranscriptAdmissionId",
        )
        sub.add_argument(
            "--database",
            required=True,
            metavar="PATH",
            help="path to the existing LectureOS SQLite database",
        )
    return parser


def _print_inspection(result) -> None:
    print(f"provider transcript result: {result.provider_transcript_result_id}")
    print(f"raw transcript: {result.raw_transcript_id}")
    print(f"segments: {result.segment_count}")
    if not result.evidence_available:
        # The distinction QD-9 insists on: nothing was preserved, so nothing can be read. Saying
        # "0 windows" alone would invite reading this as a healthy result.
        print("provider evidence: unavailable (admitted without preserved decode evidence)")
        print("  note: evidence unavailable is NOT the same as quality clean")
        return
    print("provider evidence: available")
    print(f"decode evidence windows: {result.decode_window_count}")
    print(f"segments covered by evidence: {result.evidence_covered_segment_count}")
    shared = result.evidence_covered_segment_count - result.decode_window_count
    if shared > 0:
        print(
            f"  granularity: window-scoped — {shared} more covered segment(s) than windows, so "
            "several segments share one window's values; a window value is not that segment's own "
            "confidence"
        )


def _print_diagnostic(result) -> None:
    print(f"algorithm: {result.algorithm_kind} v{result.algorithm_version}")
    print(
        "provider parameter version: "
        + (
            "unavailable (threshold policy deferred)"
            if result.provider_parameter_version is None
            else result.provider_parameter_version
        )
    )
    print(f"provider transcript result: {result.provider_transcript_result_id}")
    print(f"raw transcript: {result.raw_transcript_id}")
    print(f"provider evidence: {'available' if result.evidence_available else 'unavailable'}")
    print(f"completeness: {result.completeness.value}")
    print(f"findings: {len(result.findings)}")
    for finding in result.findings:
        target = finding.segment_id.value if finding.segment_id else f"ordinal {finding.segment_ordinal}"
        print(
            f"  - {finding.reason.value} [{finding.evidence_scope.value}] "
            f"{target} via {finding.evidence_source}: {finding.detail}"
        )
    if result.undetermined:
        print(f"undetermined reasons: {len(result.undetermined)}")
        for entry in result.undetermined:
            print(f"  - {entry.reason.value}: {entry.cause}")
    if result.completeness is not DiagnosticCompleteness.COMPLETE:
        # Printed unconditionally whenever anything was left undecided, so an empty finding list can
        # never be mistaken for a verdict.
        print(
            "note: this result does NOT assert the transcript is clean — "
            f"{len(result.undetermined)} reason(s) could not be decided (see above)"
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_diagnostic(database=args.database, admission_id=args.admission)
    except (
        TranscriptQualityDiagnosticError,
        KeyError,
        ValueError,
        OSError,
        PersistenceError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.command == "inspect":
        _print_inspection(result)
    else:
        _print_diagnostic(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
