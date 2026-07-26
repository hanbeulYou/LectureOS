"""Runnable entry point for Transcript Correction Candidate Admission (040 §17).

One CLI over an existing repository (identities only — never media paths):

* ``admit`` — record a proposed correction for one segment of the intake's current Raw Transcript, from a local
  JSON document. The candidate is a **suggestion**: it is **not applied**, does not change the Raw Transcript
  text, the current selection, or create a corrected revision or decision;
* ``list`` — list the intake's admitted correction candidates and their applicability to the current selection
  (**not ranked**; no candidate is labelled "best").

On any failure it prints an explicit error, returns non-zero, and leaves the repository unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.correction_candidate_cli admit --intake <id> --input <candidate.json> --database <db>
    PYTHONPATH=src python3 -m lectureos.correction_candidate_cli list --intake <id> --database <db>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from lectureos.application.correction_candidate_admission import (
    CorrectionCandidateAdmissionError,
    build_correction_candidate_input,
)
from lectureos.composition import (
    compose_sqlite_correction_candidate_admission_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database


def _service(database: str):
    connection = open_sqlite_database(database)
    return connection, compose_sqlite_correction_candidate_admission_service(connection)


def _run_admit(args) -> int:
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    candidate = build_correction_candidate_input(payload)
    connection, service = _service(args.database)
    try:
        result = service.admit(intake_id=args.intake, candidate=candidate)
    finally:
        connection.close()
    admission = result.admission
    status = "created" if result.created else "reused"
    print(
        f"{status} correction candidate {admission.correction_candidate_id.value} "
        f"for intake {admission.transcript_source_intake_id.value}"
    )
    print(f"raw transcript: {admission.raw_transcript_id.value}")
    print(f"segment: {admission.segment_id.value}")
    print(
        f"source: {admission.source_type.value}/{admission.source_reference} "
        f"(ref {admission.candidate_ref})"
    )
    print(f"proposed text: {result.candidate.proposed_text}")
    print("the correction candidate was NOT applied (Raw Transcript is unchanged)")
    return 0


def _run_list(args) -> int:
    connection, service = _service(args.database)
    try:
        candidates = service.candidates(args.intake)
    finally:
        connection.close()
    print(f"correction candidates for intake {args.intake}: {len(candidates)} (not ranked)")
    for view in candidates:
        applicable = "applicable" if view.applicable_to_current_selection else "not-applicable"
        print(
            f"  {view.correction_candidate_id.value}  segment={view.segment_id.value} "
            f"source={view.source_type.value}/{view.source_reference} ref={view.candidate_ref} "
            f"[{applicable}]"
        )
        print(f"      source:   {view.source_text}")
        print(f"      proposed: {view.proposed_text}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.correction_candidate_cli",
        description=(
            "Admit a proposed correction for one segment of an intake's current Raw Transcript, or list admitted "
            "candidates. A candidate is a suggestion only: admission never applies it, changes the Raw Transcript "
            "text or current selection, ranks candidates, or creates a corrected revision. Accepts identities, "
            "never media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "the admit --input JSON document has the shape:\n"
            "  {\n"
            '    "raw_transcript_id": "raw-transcript:<digest>",   (must be the intake current selection)\n'
            '    "segment_id": "transcript-segment:<digest>:<n>",\n'
            '    "candidate_ref": "<distinguishes this suggestion>",\n'
            '    "source_type": "manual|external|rule",\n'
            '    "source_reference": "<who/what proposed it>",\n'
            '    "model_reference": "<optional model/rule id>",\n'
            '    "proposed_text": "<corrected text>",\n'
            '    "source_text_snapshot": "<must equal the current segment text>",\n'
            '    "rationale": "<why>"\n'
            "  }\n"
            "\n"
            "exit status: 0 on success; 1 on malformed/not-ready/unrelated/stale/no-op/conflicting/missing input "
            "(repository left unchanged). There is no --apply option."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _common(sub):
        sub.add_argument("--intake", required=True, metavar="TRANSCRIPT_SOURCE_INTAKE_ID",
                         help="canonical TranscriptSourceIntakeId (transcript-source-intake:sha256:<digest>)")
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    admit = subparsers.add_parser("admit", help="admit a proposed correction candidate (not applied)")
    _common(admit)
    admit.add_argument("--input", required=True, metavar="PATH",
                       help="path to a local correction candidate JSON document")
    admit.set_defaults(func=_run_admit)

    listing = subparsers.add_parser("list", help="list admitted correction candidates for an intake")
    _common(listing)
    listing.set_defaults(func=_run_list)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (CorrectionCandidateAdmissionError, KeyError, ValueError, OSError, PersistenceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
