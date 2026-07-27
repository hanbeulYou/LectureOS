"""Runnable entry point for Explicit Effective SRT Delivery (GOAL-019).

One CLI over an existing repository (identities only — never media paths) plus explicitly supplied
approved roots. A thin application boundary with no delivery logic:

* ``eligibility`` — derive whether one exact successful materialization may be delivered now,
  with explicit blocking reasons;
* ``deliver`` — explicitly copy the exact materialized bytes beneath an approved Delivery Root,
  record-first (immutable intent before the write, immutable terminal outcome after);
* ``show`` — one delivery attempt with its full lineage;
* ``status`` — derived delivery state plus separate observational source/destination agreement;
* ``list`` — delivery attempts recorded for one materialization;
* ``reconcile`` — explicitly close one dangling PENDING intent from destination observation.

**Artifact ≠ Materialization ≠ Delivery ≠ Publication**: delivery records that one exact
materialized file was copied to one exact destination — it never publishes, never creates a URL,
and never implies recipient acknowledgement. Default ``overwrite`` is false; an existing different
destination file yields an honest FAILED outcome with the file untouched. On a pre-intent
validation failure it prints an explicit error, returns non-zero, and persists nothing.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.effective_deliver_cli eligibility \
        --materialization <id> --storage-root <path> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_deliver_cli deliver \
        --materialization <id> --storage-root <path> --delivery-root <path> \
        [--location <relative>] [--overwrite] --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_deliver_cli show \
        --delivery <id> --storage-root <path> --delivery-root <path> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_deliver_cli status \
        --delivery <id> --storage-root <path> --delivery-root <path> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_deliver_cli list \
        --materialization <id> --storage-root <path> --delivery-root <path> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_deliver_cli reconcile \
        --delivery <id> --storage-root <path> --delivery-root <path> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.effective_srt_delivery import (
    DeliveryState,
    EffectiveSrtDeliveryError,
)
from lectureos.application.effective_srt_materialization import (
    EffectiveSrtMaterializationError,
)
from lectureos.application.effective_subtitle_srt_artifact import (
    EffectiveSubtitleSrtArtifactError,
)
from lectureos.composition import compose_sqlite_effective_srt_delivery_service
from lectureos.persistence import PersistenceError, open_sqlite_database

_NOT_PART = (
    "publication state: not part of this contract",
    "recipient acknowledgement: not part of this contract",
)


def _service(args):
    connection = open_sqlite_database(args.database)
    return connection, compose_sqlite_effective_srt_delivery_service(
        connection, args.storage_root, args.delivery_root
    )


def _print_delivery(service, delivery, outcome) -> None:
    print(f"delivery: {delivery.identity.value}")
    print(f"materialization: {delivery.materialization_id.value}")
    print(f"artifact: {delivery.artifact_id.value}")
    print(
        f"delivery contract: {delivery.delivery_kind} "
        f"v{delivery.delivery_contract_version}"
    )
    print(f"destination location: {delivery.relative_location}")
    print(f"source physical path: {service.source_path(delivery)}")
    print(f"destination physical path: {service.destination_path(delivery)}")
    print(f"expected payload fingerprint: {delivery.expected_payload_fingerprint}")
    print(f"sequence: {delivery.sequence}")
    if delivery.previous_delivery_id is not None:
        print(f"previous delivery: {delivery.previous_delivery_id.value}")
    print(f"overwrite policy: {'explicit overwrite' if delivery.overwrite else 'no overwrite'}")
    if outcome is None:
        print("delivery state: pending (no terminal outcome recorded)")
    elif outcome.state is DeliveryState.DELIVERED:
        print(f"delivery state: delivered ({outcome.byte_length} bytes, verified)")
    else:
        print(
            f"delivery state: failed ({outcome.failure_category.value}: "
            f"{outcome.failure_reason})"
        )
    for line in _NOT_PART:
        print(line)


def _run_eligibility(args) -> int:
    connection = open_sqlite_database(args.database)
    try:
        # Eligibility inspects the source side only; the destination writer is unused, so the
        # Storage Root safely stands in for both approved roots.
        service = compose_sqlite_effective_srt_delivery_service(
            connection, args.storage_root, args.storage_root
        )
        report = service.delivery_eligibility(args.materialization)
    finally:
        connection.close()
    print(f"materialization: {args.materialization}")
    print(f"eligible for delivery: {'yes' if report.eligible else 'no'}")
    if report.materialization_state is not None:
        print(f"materialization state: {report.materialization_state.value}")
    print(
        f"delivery contract: {report.delivery_kind} "
        f"v{report.delivery_contract_version}"
    )
    if report.blocking_reason is not None:
        print(f"blocking reason: {report.blocking_reason.value}")
    print("eligibility is derived and never persisted; delivery remains an explicit request")
    return 0


def _run_deliver(args) -> int:
    connection, service = _service(args)
    try:
        record = service.deliver(
            materialization_id=args.materialization,
            relative_location=args.location,
            overwrite=args.overwrite,
        )
        _print_delivery(service, record.delivery, record.outcome)
    finally:
        connection.close()
    print(f"request result: {record.kind.value}")
    print(
        "delivery copied exact materialized bytes only; no artifact, materialization, "
        "selection, or decision record was changed"
    )
    return 0 if record.state is not DeliveryState.FAILED else 1


def _run_show(args) -> int:
    connection, service = _service(args)
    try:
        delivery = service.get(args.delivery)
        if delivery is None:
            raise EffectiveSrtDeliveryError("unknown effective SRT delivery")
        _print_delivery(service, delivery, service.outcome(delivery))
    finally:
        connection.close()
    return 0


def _run_status(args) -> int:
    connection, service = _service(args)
    try:
        delivery = service.get(args.delivery)
        if delivery is None:
            raise EffectiveSrtDeliveryError("unknown effective SRT delivery")
        status = service.status(delivery)
    finally:
        connection.close()
    print(f"delivery: {delivery.identity.value}")
    print(f"delivery state: {status.delivery_state.value}")
    print(f"source file agreement: {status.source_file_agreement}")
    print(f"destination file agreement: {status.destination_file_agreement}")
    print(f"artifact currentness: {status.artifact_currentness.value}")
    print(f"materialization state: {status.materialization_state.value}")
    print(
        "delivery history is immutable; filesystem agreement is observational and "
        "never rewrites it"
    )
    for line in _NOT_PART:
        print(line)
    return 0


def _run_list(args) -> int:
    connection, service = _service(args)
    try:
        deliveries = service.list_for_materialization(args.materialization)
        states = [service.state(delivery) for delivery in deliveries]
    finally:
        connection.close()
    print(
        f"effective SRT deliveries for materialization {args.materialization}: "
        f"{len(deliveries)}"
    )
    for delivery, state in zip(deliveries, states):
        print(
            f"  {delivery.relative_location} #{delivery.sequence} [{state.value}] "
            f"({delivery.identity.value})"
        )
    print("delivery attempts are immutable append-only records; state is derived")
    return 0


def _run_reconcile(args) -> int:
    connection, service = _service(args)
    try:
        record = service.reconcile(args.delivery)
        _print_delivery(service, record.delivery, record.outcome)
    finally:
        connection.close()
    if record.kind.value == "reused":
        print("reconciliation result: already terminal (no new outcome appended)")
    else:
        print("reconciliation result: one truthful terminal outcome appended")
    print("reconciliation observed the destination only; it never writes or overwrites")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.effective_deliver_cli",
        description=(
            "Explicit delivery of effective SRT materializations: derived eligibility, "
            "record-first immutable intent/outcome, exact-byte local copy beneath an approved "
            "Delivery Root, and explicit reconciliation. No publication, URL, network, or "
            "recipient acknowledgement exists in this contract. Accepts identities, never "
            "media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success (including idempotent reuse); 1 on malformed/unknown/"
            "ineligible/conflicting input (nothing persisted) or on an honest FAILED delivery "
            "outcome (recorded immutably)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _database(sub):
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    def _roots(sub):
        sub.add_argument("--storage-root", required=True, metavar="PATH",
                         help="approved Storage Root holding materialized source files")
        sub.add_argument("--delivery-root", required=True, metavar="PATH",
                         help="approved Delivery Root receiving delivered files")

    eligibility = subparsers.add_parser(
        "eligibility", help="derive whether a materialization may be delivered now"
    )
    eligibility.add_argument("--materialization", required=True,
                             metavar="EFFECTIVE_SRT_MATERIALIZATION_ID")
    eligibility.add_argument("--storage-root", required=True, metavar="PATH",
                             help="approved Storage Root holding materialized source files")
    _database(eligibility)
    eligibility.set_defaults(func=_run_eligibility)

    deliver = subparsers.add_parser(
        "deliver", help="explicitly deliver one exact materialized file"
    )
    deliver.add_argument("--materialization", required=True,
                         metavar="EFFECTIVE_SRT_MATERIALIZATION_ID",
                         help="exact source materialization identity (never latest implicitly)")
    _roots(deliver)
    deliver.add_argument("--location", metavar="RELATIVE_PATH",
                         help="destination-relative location (default: <artifact-id>.srt)")
    deliver.add_argument("--overwrite", action="store_true",
                         help="explicitly replace an existing different destination file")
    _database(deliver)
    deliver.set_defaults(func=_run_deliver)

    for name, func, help_text in (
        ("show", _run_show, "show one delivery attempt with lineage"),
        ("status", _run_status,
         "derived delivery state plus observational filesystem agreement"),
        ("reconcile", _run_reconcile,
         "explicitly close one dangling PENDING intent from destination observation"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--delivery", required=True,
                         metavar="EFFECTIVE_SRT_DELIVERY_ID")
        _roots(sub)
        _database(sub)
        sub.set_defaults(func=func)

    lst = subparsers.add_parser(
        "list", help="list delivery attempts recorded for a materialization"
    )
    lst.add_argument("--materialization", required=True,
                     metavar="EFFECTIVE_SRT_MATERIALIZATION_ID")
    _roots(lst)
    _database(lst)
    lst.set_defaults(func=_run_list)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
        EffectiveSrtDeliveryError,
        EffectiveSrtMaterializationError,
        EffectiveSubtitleSrtArtifactError,
        KeyError,
        ValueError,
        OSError,
        PersistenceError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
