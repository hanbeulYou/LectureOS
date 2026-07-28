"""Runnable entry point for Effective SRT Publication Authority (GOAL-020).

One CLI over an existing repository (identities only — never media paths). A thin application
boundary with no publication logic:

* ``eligibility`` — derive whether one exact DELIVERED delivery may receive a NEW publish now;
* ``publish`` — explicit Human Authority that this exact delivered subtitle is the published
  output for its intake scope;
* ``withdraw`` — explicit Human Authority that nothing should remain published for the scope;
* ``show`` — one immutable publication record with lineage;
* ``history`` — the append-only publication history of one intake scope;
* ``current`` — the derived current publication authority;
* ``availability`` — the derived operational availability of one scope;
* ``status`` — one record's standing plus separate observational facts.

**Delivery ≠ Publication ≠ Availability ≠ network access**: publication writes no file, creates
no URL, performs no network operation, and implies no recipient acknowledgement; withdrawal
deletes nothing. The optional ``--delivery-root`` enables purely observational destination
agreement; without it, availability honestly reports ``not_observed``. On any pre-persistence
failure it prints an explicit error, returns non-zero, and leaves the repository unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.effective_publish_cli eligibility --delivery <id> [--delivery-root <path>] --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_publish_cli publish --delivery <id> --publisher <actor> [--rationale <text>] [--delivery-root <path>] --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_publish_cli withdraw --intake <id> --publisher <actor> [--rationale <text>] --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_publish_cli show --publication <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_publish_cli history --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_publish_cli current --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_publish_cli availability --intake <id> [--delivery-root <path>] --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_publish_cli status --publication <id> [--delivery-root <path>] --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.effective_srt_delivery import EffectiveSrtDeliveryError
from lectureos.application.effective_srt_publication import (
    EffectiveSrtPublicationError,
    PublicationKind,
)
from lectureos.composition import compose_sqlite_effective_srt_publication_service
from lectureos.persistence import PersistenceError, open_sqlite_database

_NOT_PART = (
    "public URL: not part of this contract",
    "recipient acknowledgement: not part of this contract",
)


def _service(args):
    connection = open_sqlite_database(args.database)
    return connection, compose_sqlite_effective_srt_publication_service(
        connection, getattr(args, "delivery_root", None)
    )


def _print_publication(publication, current: bool | None = None) -> None:
    print(f"publication: {publication.identity.value}")
    print(f"scope intake: {publication.transcript_source_intake_id.value}")
    print(f"kind: {publication.kind.value}")
    if publication.kind is PublicationKind.PUBLISH:
        print(f"target delivery: {publication.target_delivery_id.value}")
        print(f"target artifact: {publication.target_artifact_id.value}")
    else:
        print("target delivery: none (withdrawal records authority only)")
    print(f"publisher: {publication.publisher.value}")
    print(f"sequence: {publication.sequence}")
    if publication.previous_publication_id is not None:
        print(f"previous publication: {publication.previous_publication_id.value}")
    if publication.rationale is not None:
        print(f"rationale: {publication.rationale}")
    if current is not None:
        print(f"current publication authority: {'yes' if current else 'no (historical)'}")
    for line in _NOT_PART:
        print(line)


def _run_eligibility(args) -> int:
    connection, service = _service(args)
    try:
        report = service.publication_eligibility(args.delivery)
    finally:
        connection.close()
    print(f"delivery: {args.delivery}")
    print(f"eligible for a new publish command: {'yes' if report.eligible else 'no'}")
    if report.delivery_state is not None:
        print(f"delivery state: {report.delivery_state.value}")
    print(f"destination observation: {report.destination_observation}")
    if report.blocking_reason is not None:
        print(f"blocking reason: {report.blocking_reason.value}")
    print("eligibility is derived and never persisted; publication remains an explicit command")
    return 0


def _run_publish(args) -> int:
    connection, service = _service(args)
    try:
        result = service.publish(
            delivery_id=args.delivery,
            publisher=args.publisher,
            rationale=args.rationale,
        )
    finally:
        connection.close()
    print(f"{result.outcome.value} effective SRT publication")
    _print_publication(result.publication, current=True)
    print(
        "publication recorded authority only: no file was written, no URL created, and no "
        "delivery, materialization, or artifact record was changed"
    )
    return 0


def _run_withdraw(args) -> int:
    connection, service = _service(args)
    try:
        result = service.withdraw(
            intake_id=args.intake,
            publisher=args.publisher,
            rationale=args.rationale,
        )
    finally:
        connection.close()
    print(f"{result.outcome.value} effective SRT publication withdrawal")
    _print_publication(result.publication, current=True)
    print(
        "withdrawal recorded authority only: no file, delivery, materialization, or artifact "
        "was deleted or changed; history remains append-only"
    )
    return 0


def _run_show(args) -> int:
    connection, service = _service(args)
    try:
        publication = service.get(args.publication)
        if publication is None:
            raise EffectiveSrtPublicationError("unknown effective SRT publication")
        current = service.current(publication.transcript_source_intake_id.value)
    finally:
        connection.close()
    _print_publication(
        publication,
        current=current is not None and current.identity == publication.identity,
    )
    return 0


def _run_history(args) -> int:
    connection, service = _service(args)
    try:
        history = service.history(args.intake)
        current = service.current(args.intake)
    finally:
        connection.close()
    print(f"publication history for intake {args.intake}: {len(history)}")
    for publication in history:
        marker = (
            " [current]"
            if current is not None and current.identity == publication.identity
            else ""
        )
        target = (
            publication.target_delivery_id.value
            if publication.target_delivery_id is not None
            else "-"
        )
        print(
            f"  #{publication.sequence} {publication.kind.value} {target} "
            f"by {publication.publisher.value}{marker} ({publication.identity.value})"
        )
    print("publication history is immutable and append-only; current is derived")
    return 0


def _run_current(args) -> int:
    connection, service = _service(args)
    try:
        current = service.current(args.intake)
    finally:
        connection.close()
    print(f"scope intake: {args.intake}")
    if current is None:
        print("current publication: none (no publication history)")
        return 0
    _print_publication(current, current=True)
    return 0


def _run_availability(args) -> int:
    connection, service = _service(args)
    try:
        availability = service.availability(args.intake)
        current = service.current(args.intake)
    finally:
        connection.close()
    print(f"scope intake: {args.intake}")
    if current is not None:
        print(f"publication authority: {current.kind.value} (sequence {current.sequence})")
    else:
        print("publication authority: none")
    print(f"derived availability: {availability.value}")
    print(
        "availability is derived, never persisted; filesystem observation never mutates "
        "publication history"
    )
    for line in _NOT_PART:
        print(line)
    return 0


def _run_status(args) -> int:
    connection, service = _service(args)
    try:
        status = service.status(args.publication)
    finally:
        connection.close()
    _print_publication(status.publication, current=status.current)
    if status.delivery_state is not None:
        print(f"target delivery state: {status.delivery_state.value}")
    print(f"destination observation: {status.destination_observation}")
    if status.artifact_currentness is not None:
        print(f"artifact currentness: {status.artifact_currentness.value}")
    print(f"scope availability: {status.scope_availability.value}")
    print("authority state and filesystem observation are reported separately")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.effective_publish_cli",
        description=(
            "Explicit publication authority over delivered effective subtitles: derived "
            "eligibility, append-only publish/withdraw Human Authority records, derived "
            "current publication, and derived availability. No URL, network operation, file "
            "write, or recipient acknowledgement exists in this contract. Accepts identities, "
            "never media paths."
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

    def _root(sub):
        sub.add_argument("--delivery-root", metavar="PATH",
                         help="optional approved Delivery Root for observational "
                              "destination agreement (never persisted)")

    eligibility = subparsers.add_parser(
        "eligibility", help="derive whether a delivery may receive a new publish command"
    )
    eligibility.add_argument("--delivery", required=True,
                             metavar="EFFECTIVE_SRT_DELIVERY_ID")
    _root(eligibility)
    _database(eligibility)
    eligibility.set_defaults(func=_run_eligibility)

    publish = subparsers.add_parser(
        "publish", help="explicitly publish one exact delivered subtitle"
    )
    publish.add_argument("--delivery", required=True,
                         metavar="EFFECTIVE_SRT_DELIVERY_ID",
                         help="exact target delivery identity (never latest implicitly)")
    publish.add_argument("--publisher", required=True, metavar="HUMAN_ACTOR_REFERENCE",
                         help="explicit Human actor reference (never inferred)")
    publish.add_argument("--rationale", metavar="TEXT")
    _root(publish)
    _database(publish)
    publish.set_defaults(func=_run_publish)

    withdraw = subparsers.add_parser(
        "withdraw", help="explicitly withdraw the scope's published output"
    )
    withdraw.add_argument("--intake", required=True,
                          metavar="TRANSCRIPT_SOURCE_INTAKE_ID")
    withdraw.add_argument("--publisher", required=True, metavar="HUMAN_ACTOR_REFERENCE")
    withdraw.add_argument("--rationale", metavar="TEXT")
    _database(withdraw)
    withdraw.set_defaults(func=_run_withdraw)

    show = subparsers.add_parser("show", help="show one immutable publication record")
    show.add_argument("--publication", required=True,
                      metavar="EFFECTIVE_SRT_PUBLICATION_ID")
    _database(show)
    show.set_defaults(func=_run_show)

    for name, func, help_text in (
        ("history", _run_history, "append-only publication history of one intake scope"),
        ("current", _run_current, "derived current publication authority"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--intake", required=True,
                         metavar="TRANSCRIPT_SOURCE_INTAKE_ID")
        _database(sub)
        sub.set_defaults(func=func)

    availability = subparsers.add_parser(
        "availability", help="derived operational availability of one intake scope"
    )
    availability.add_argument("--intake", required=True,
                              metavar="TRANSCRIPT_SOURCE_INTAKE_ID")
    _root(availability)
    _database(availability)
    availability.set_defaults(func=_run_availability)

    status = subparsers.add_parser(
        "status", help="one record's standing plus separate observational facts"
    )
    status.add_argument("--publication", required=True,
                        metavar="EFFECTIVE_SRT_PUBLICATION_ID")
    _root(status)
    _database(status)
    status.set_defaults(func=_run_status)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
        EffectiveSrtPublicationError,
        EffectiveSrtDeliveryError,
        KeyError,
        ValueError,
        OSError,
        PersistenceError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
