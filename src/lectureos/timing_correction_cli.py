"""Runnable entry point for Human Timing Correction (040 §17 sibling / §18 / §19, PATCH-0047).

One CLI over an existing repository (identities only — never media paths):

* ``admit`` — record a **human-authored** replacement interval for one segment of the intake's current
  Raw Transcript, from a local JSON document. The proposal is a suggestion: it is **not applied**, it
  changes no Raw Transcript timing, and it creates no revision or decision;
* ``list`` — list the intake's admitted timing candidates and their applicability to the current selection
  (**not ranked**; no candidate is labelled "best");
* ``decide`` — record one explicit human ``accept``/``reject`` over one timing candidate. **Reject is a
  normal, complete judgement** meaning "the source timing is correct", not an error;
* ``generate`` — explicitly apply one currently Accepted timing candidate into one immutable corrected
  revision. The revision is **not** selected as current; selection stays an explicit separate act.

The CLI proposes nothing on its own: the interval is always supplied by the person. It never converts a
timing diagnostic finding into a candidate, never reads media, and never estimates a speech onset.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.timing_correction_cli admit --intake <id> --input <proposal.json> --database <db>
    PYTHONPATH=src python3 -m lectureos.timing_correction_cli list --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.timing_correction_cli decide --candidate <id> --kind accept --reviewer <who> --database <db>
    PYTHONPATH=src python3 -m lectureos.timing_correction_cli generate --candidate <id> --database <db>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from lectureos.application.timing_correction_candidate_admission import (
    TimingCorrectionCandidateError,
    build_timing_correction_candidate_input,
)
from lectureos.application.timing_correction_candidate_decision import (
    TimingCorrectionDecisionError,
)
from lectureos.application.timing_correction_revision_generation import (
    TimingCorrectionGenerationError,
)
from lectureos.composition import (
    compose_sqlite_timing_correction_candidate_admission_service,
    compose_sqlite_timing_correction_decision_service,
    compose_sqlite_timing_correction_revision_generation_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database


def _open(database: str, compose):
    connection = open_sqlite_database(database)
    return connection, compose(connection)


def _run_admit(args) -> int:
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    candidate = build_timing_correction_candidate_input(payload)
    connection, service = _open(
        args.database, compose_sqlite_timing_correction_candidate_admission_service
    )
    try:
        result = service.admit(intake_id=args.intake, candidate=candidate)
    finally:
        connection.close()
    record = result.candidate
    status = "created" if result.created else "reused"
    print(
        f"{status} timing correction candidate {record.identity.value} "
        f"for intake {record.transcript_source_intake_id.value}"
    )
    print(f"raw transcript: {record.raw_transcript_id.value}")
    print(f"segment: {record.segment_id.value}")
    print(f"author: {record.author.value} (ref {record.candidate_ref})")
    print(
        f"source interval: [{record.source_start_snapshot}, {record.source_end_snapshot}]"
    )
    print(f"proposed interval: [{record.proposed_start}, {record.proposed_end}]")
    print("the timing correction was NOT applied (Raw Transcript timing is unchanged)")
    return 0


def _run_list(args) -> int:
    connection, service = _open(
        args.database, compose_sqlite_timing_correction_candidate_admission_service
    )
    try:
        views = service.candidates(args.intake)
    finally:
        connection.close()
    if not views:
        print("no timing correction candidates for this intake")
        return 0
    print(f"timing correction candidates: {len(views)} (not ranked)")
    for view in views:
        record = view.candidate
        applicable = (
            "applicable" if view.applicable_to_current_selection else "not applicable"
        )
        print(f"- {record.identity.value} [{applicable}]")
        print(f"    segment: {record.segment_id.value}")
        print(
            f"    [{record.source_start_snapshot}, {record.source_end_snapshot}] -> "
            f"[{record.proposed_start}, {record.proposed_end}]"
        )
        print(f"    author: {record.author.value} (ref {record.candidate_ref})")
    return 0


def _run_decide(args) -> int:
    connection, service = _open(
        args.database, compose_sqlite_timing_correction_decision_service
    )
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
        f"{result.outcome.value} human decision {decision.kind.value} "
        f"on {decision.timing_correction_candidate_id.value}"
    )
    print(f"decision: {decision.identity.value} (sequence {decision.sequence})")
    print(f"reviewer: {decision.reviewer.value}")
    print(f"current authority: {authority.status.value}")
    if decision.kind.value == "reject":
        print("reject is a normal outcome: it records that the source timing is correct")
    else:
        print("accepted: generation is a separate explicit act and has NOT happened")
    return 0


def _run_generate(args) -> int:
    connection, service = _open(
        args.database, compose_sqlite_timing_correction_revision_generation_service
    )
    try:
        result = service.generate(candidate_id=args.candidate)
    finally:
        connection.close()
    generation = result.generation
    print(f"{result.outcome} corrected revision {result.revision.identity.value}")
    print(f"generation: {generation.identity.value}")
    print(f"authorizing decision: {generation.authorizing_decision_id.value}")
    print(
        f"replaced segment: {generation.replaced_segment_id.value} -> "
        f"{generation.replacement_segment_id.value}"
    )
    print("segment text is preserved exactly; only the interval changed")
    print("the revision was NOT selected as current (selection is an explicit separate act)")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="timing_correction_cli",
        description=(
            "Human timing correction: propose a replacement interval, decide on it, "
            "and explicitly apply an accepted proposal (040 §17/§18/§19, PATCH-0047)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    admit = subparsers.add_parser(
        "admit", help="record a human-authored replacement interval (never applied)"
    )
    admit.add_argument("--intake", required=True)
    admit.add_argument("--input", required=True, help="path to the proposal JSON document")
    admit.add_argument("--database", required=True)
    admit.set_defaults(handler=_run_admit)

    listing = subparsers.add_parser(
        "list", help="list admitted timing candidates for an intake (not ranked)"
    )
    listing.add_argument("--intake", required=True)
    listing.add_argument("--database", required=True)
    listing.set_defaults(handler=_run_list)

    decide = subparsers.add_parser(
        "decide", help="record one explicit human accept/reject on a timing candidate"
    )
    decide.add_argument("--candidate", required=True)
    decide.add_argument("--kind", required=True, choices=("accept", "reject"))
    decide.add_argument("--reviewer", required=True)
    decide.add_argument("--rationale", default=None)
    decide.add_argument("--database", required=True)
    decide.set_defaults(handler=_run_decide)

    generate = subparsers.add_parser(
        "generate", help="apply one currently accepted timing candidate into a corrected revision"
    )
    generate.add_argument("--candidate", required=True)
    generate.add_argument("--database", required=True)
    generate.set_defaults(handler=_run_generate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.handler(args)
    except (
        TimingCorrectionCandidateError,
        TimingCorrectionDecisionError,
        TimingCorrectionGenerationError,
        PersistenceError,
        OSError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())
