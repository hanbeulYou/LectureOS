"""Runnable entry point for Human Timing Correction (040 §17 sibling / §18 / §19, PATCH-0047).

One CLI over an existing repository (identities only — never media paths):

* ``admit`` — record a **human-authored** replacement interval for one segment of the intake's current
  Raw Transcript, from a local JSON document. The proposal is a suggestion: it is **not applied**, it
  changes no Raw Transcript timing, and it creates no revision or decision;
* ``list`` — list the intake's admitted timing candidates and their applicability to the current selection
  (**not ranked**; no candidate is labelled "best");
* ``decide`` — record one explicit human ``accept``/``reject`` over one timing candidate. **Reject is a
  normal, complete judgement** meaning "the source timing is correct", not an error;
* ``generate`` — explicitly apply an **explicitly named set** of currently Accepted timing candidates
  into one immutable corrected revision (`PATCH-0049`). Repeat ``--candidate`` to name more than one;
  each must target a different source segment of the same Raw Transcript. Naming one candidate is a
  singleton and keeps the released identity exactly. Nothing is discovered, ranked, or inherited: an
  accepted candidate you do not name simply does not participate. The revision is **not** selected as
  current; selection stays an explicit separate act;
* ``inspect`` — print one Raw Transcript segment's canonical snapshot (identity, ordinal, text, current
  interval, and its neighbours' intervals) so a person can author a proposal without opening the
  database by hand. Read-only, and it proposes no interval.

The CLI proposes nothing on its own: the interval is always supplied by the person. It never converts a
timing diagnostic finding into a candidate, never reads media, and never estimates a speech onset.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.timing_correction_cli admit --intake <id> --input <proposal.json> --database <db>
    PYTHONPATH=src python3 -m lectureos.timing_correction_cli list --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.timing_correction_cli decide --candidate <id> --kind accept --reviewer <who> --database <db>
    PYTHONPATH=src python3 -m lectureos.timing_correction_cli generate --candidate <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.timing_correction_cli generate --candidate <id> --candidate <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.timing_correction_cli inspect --raw-transcript <id> --segment <id> --database <db>
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
from lectureos.persistence import (
    PersistenceError,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    open_sqlite_database,
)
from lectureos.persistence.provider_transcript_admission import (
    SQLiteProviderTranscriptAdmissionRepository,
)
from lectureos.transcript.identities import TranscriptId, TranscriptSegmentId


def _open(database: str, compose):
    connection = open_sqlite_database(database)
    return connection, compose(connection)


def _run_inspect(args) -> int:
    """Print the canonical snapshot of one Raw Transcript segment (read-only).

    This is a **query**, not a judgement: it reports what the repository holds so a person can author
    a proposal without opening the database by hand. It proposes no interval, consults no diagnostic,
    and re-implements no admission rule — `§17` K-1, TC-7, TC-8 and TC-9 stay with the admission
    service. It refuses to describe a segment as part of a transcript it is not a member of, because
    that would be reporting the canonical state untruthfully.
    """

    connection = open_sqlite_database(args.database)
    try:
        raw = SQLiteRawTranscriptRepository(connection).get(
            TranscriptId(args.raw_transcript)
        )
        if raw is None:
            print("error: unknown raw transcript", file=sys.stderr)
            return 1
        segment_identity = TranscriptSegmentId(args.segment)
        if segment_identity not in raw.segment_ids:
            print(
                "error: segment is not part of this raw transcript's canonical membership "
                "(a corrected revision's replacement segment is not a Raw Transcript segment)",
                file=sys.stderr,
            )
            return 1
        segments = SQLiteTranscriptSegmentRepository(connection)
        ordinal = raw.segment_ids.index(segment_identity)
        segment = segments.get(segment_identity)
        if segment is None:  # defensive: membership guarantees the row exists
            print("error: segment record could not be resolved", file=sys.stderr)
            return 1
        neighbours = {}
        for label, position in (("previous", ordinal - 1), ("next", ordinal + 1)):
            if 0 <= position < len(raw.segment_ids):
                neighbours[label] = segments.get(raw.segment_ids[position])
            else:
                neighbours[label] = None
        # The intake is the context `admit` requires; it is a released lineage read, not new meaning.
        admission = SQLiteProviderTranscriptAdmissionRepository(
            connection
        ).get_by_raw_transcript(raw.identity)
        intake = (
            None if admission is None else admission.transcript_source_intake_id.value
        )
    finally:
        connection.close()

    def _describe(record):
        if record is None:
            return None
        return {
            "segment_id": record.identity.value,
            "start": record.start,
            "end": record.end,
            "text": record.text,
        }

    snapshot = {
        "transcript_source_intake_id": intake,
        "raw_transcript_id": raw.identity.value,
        "segment_id": segment.identity.value,
        "ordinal": ordinal,
        "segment_count": len(raw.segment_ids),
        "text": segment.text,
        "start": segment.start,
        "end": segment.end,
        "previous": _describe(neighbours["previous"]),
        "next": _describe(neighbours["next"]),
    }
    if args.format == "json":
        # `json.dumps` renders floats with `repr`, so the values round-trip exactly into a proposal.
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0

    print(f"intake: {intake if intake is not None else '(no provider admission binds this transcript)'}")
    print(f"raw transcript: {snapshot['raw_transcript_id']}")
    print(f"segment: {snapshot['segment_id']}")
    print(f"ordinal: {ordinal} of {snapshot['segment_count']}")
    print(f"text: {snapshot['text']}")
    print(f"current interval: [{segment.start}, {segment.end}]")
    for label in ("previous", "next"):
        record = neighbours[label]
        if record is None:
            print(f"{label}: none (this is the {'first' if label == 'previous' else 'last'} segment)")
        else:
            print(f"{label}: [{record.start}, {record.end}] {record.identity.value}")
    print()
    print("to author a proposal, carry this segment's current interval as the source snapshot:")
    print(f'  "source_start_snapshot": {segment.start}, "source_end_snapshot": {segment.end}')
    print(
        "the proposed interval is yours to decide by listening — this command proposes nothing "
        "and reads no media"
    )
    return 0


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
    # The caller enumerates the members explicitly; repeating `--candidate` names a set. Nothing is
    # discovered, ranked, or inherited, and an unnamed accepted candidate never joins (MG-7/MG-9).
    candidate_ids = tuple(args.candidate)
    connection, service = _open(
        args.database, compose_sqlite_timing_correction_revision_generation_service
    )
    try:
        result = service.generate_set(candidate_ids=candidate_ids)
    finally:
        connection.close()
    view = result.view
    print(f"{result.outcome} corrected revision {result.revision.identity.value}")
    print(f"generation: {view.identity.value} ({len(view.members)} member(s))")
    for member in view.members:
        print(f"  [{member.member_ordinal}] candidate: {member.timing_correction_candidate_id.value}")
        print(f"      authorizing decision: {member.authorizing_decision_id.value}")
        print(
            f"      replaced segment: {member.replaced_segment_id.value} -> "
            f"{member.replacement_segment_id.value}"
        )
    print("segment text is preserved exactly; only the intervals changed")
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
        "generate",
        help=(
            "apply an explicitly named set of currently accepted timing candidates into one "
            "corrected revision (repeat --candidate to name more than one)"
        ),
    )
    generate.add_argument("--candidate", required=True, action="append")
    generate.add_argument("--database", required=True)
    generate.set_defaults(handler=_run_generate)

    inspect = subparsers.add_parser(
        "inspect",
        help="print one Raw Transcript segment's canonical snapshot (read-only, proposes nothing)",
    )
    inspect.add_argument("--raw-transcript", required=True, dest="raw_transcript")
    inspect.add_argument("--segment", required=True)
    inspect.add_argument(
        "--format", choices=("text", "json"), default="text",
        help="output format (default: text)",
    )
    inspect.add_argument("--database", required=True)
    inspect.set_defaults(handler=_run_inspect)
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
