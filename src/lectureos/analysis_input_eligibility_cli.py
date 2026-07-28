"""Runnable entry point for Derived Lecture Analysis Input Eligibility (042 §5.1 / GOAL-022).

One CLI over an existing repository (identities only — never media paths). A thin application
boundary with no analysis logic:

* ``evaluate`` — derive whether one exact intake's current effective transcript authority is
  admissible as a lecture-analysis input, with exact lineage and stable blocking reasons.

**Eligibility ≠ Analysis Input ≠ Analysis Run.** Nothing is persisted, no transcript record is
touched, and no analysis of any kind runs. Per 042 §5.1 only the current applicable corrected-
revision selection is the confirmed admission authority; the result is advisory — a later
explicit admission command must revalidate current authority (the TOCTOU boundary).

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.analysis_input_eligibility_cli evaluate \
        --intake <TRANSCRIPT_SOURCE_INTAKE_ID> --database <db>

Exit status: 0 when eligible; 1 when ineligible (blocking reasons printed) or on malformed/
corrupt input (explicit ``error:`` diagnostic on stderr, repository left unchanged).
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.corrected_revision_selection import (
    CorrectedRevisionSelectionError,
)
from lectureos.application.lecture_analysis_input_eligibility import (
    LectureAnalysisInputEligibilityError,
)
from lectureos.composition import (
    compose_sqlite_lecture_analysis_input_eligibility_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database

_NOT_PART = (
    "analysis input state: not created (admission is a later explicit command)",
    "analysis execution state: not part of this contract",
)


def _run_evaluate(args) -> int:
    connection = open_sqlite_database(args.database)
    try:
        result = compose_sqlite_lecture_analysis_input_eligibility_service(
            connection
        ).evaluate(args.intake)
    finally:
        connection.close()
    print(f"intake: {result.transcript_source_intake_id}")
    print(f"eligible for analysis input: {'yes' if result.eligible else 'no'}")
    for reason in result.blocking_reasons:
        print(f"blocking reason: {reason.value}")
    if result.source_media_id is not None:
        print(f"source media: {result.source_media_id.value}")
    if result.selection_state is not None:
        print(f"selection state: {result.selection_state.value}")
    if result.effective_kind is not None:
        print(f"effective transcript kind: {result.effective_kind.value}")
    if result.corrected_revision_id is not None:
        print(f"corrected revision: {result.corrected_revision_id.value}")
    if result.parent_raw_transcript_id is not None:
        print(f"parent raw transcript: {result.parent_raw_transcript_id.value}")
    if result.raw_selection_id is not None:
        print(f"raw selection: {result.raw_selection_id.value}")
    if result.corrected_selection_id is not None:
        print(f"corrected selection: {result.corrected_selection_id.value}")
    if result.inapplicability_reason is not None:
        print(f"selection inapplicability: {result.inapplicability_reason}")
    if result.segment_count is not None:
        print(f"segments: {result.segment_count}")
    if result.content_fingerprint is not None:
        print(f"content fingerprint: {result.content_fingerprint}")
    print(
        "eligibility is derived and advisory — nothing was persisted; a later explicit "
        "admission command must revalidate current authority"
    )
    for line in _NOT_PART:
        print(line)
    return 0 if result.eligible else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.analysis_input_eligibility_cli",
        description=(
            "Derived Lecture Analysis Input Eligibility (042 Milestone 1): whether one "
            "intake's current effective transcript authority — the validated selected "
            "Corrected Transcript — is admissible as an analysis input. Derived only; "
            "nothing is persisted and no analysis runs. Accepts identities, never media "
            "paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 eligible; 1 ineligible (stable blocking reasons printed) or "
            "malformed/corrupt input (repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    evaluate = subparsers.add_parser(
        "evaluate", help="derive one intake's analysis-input eligibility"
    )
    evaluate.add_argument("--intake", required=True,
                          metavar="TRANSCRIPT_SOURCE_INTAKE_ID")
    evaluate.add_argument("--database", required=True, metavar="PATH",
                          help="path to the existing LectureOS SQLite database")
    evaluate.set_defaults(func=_run_evaluate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
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
