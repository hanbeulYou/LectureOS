"""Runnable entry point for Effective SRT Physical Materialization (GOAL-018).

One CLI over an existing repository and one approved Storage Root. A thin application boundary:

* ``materialize`` — explicitly realize one exact logical artifact as a physical file (record-first:
  the immutable intent is durable before the write, the immutable terminal outcome after; failures
  are honest FAILED outcomes); ``--overwrite`` is required to replace an existing different file;
* ``show`` — one materialization record with derived state;
* ``status`` — derived state plus whether the physical file currently matches the payload;
* ``list`` — the append-only materialization history of one artifact.

**Artifact ≠ Materialization ≠ physical path**: the artifact's identity never depends on any path;
the relative location is provenance of one write event beneath the approved root; a later deleted
file never mutates any record. No delivery, publication, upload, or URL exists here. On any failure
the CLI prints an explicit error and returns non-zero; a FAILED write outcome is reported honestly
with exit 1 while the record remains.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.effective_materialize_cli materialize --artifact <id> --storage-root <dir> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_materialize_cli show --materialization <id> --storage-root <dir> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_materialize_cli status --materialization <id> --storage-root <dir> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_materialize_cli list --artifact <id> --storage-root <dir> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.effective_srt_materialization import (
    EffectiveSrtMaterializationError,
    MaterializationState,
)
from lectureos.application.effective_subtitle_srt_artifact import (
    EffectiveSubtitleSrtArtifactError,
)
from lectureos.composition import (
    compose_sqlite_effective_srt_materialization_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database


def _service(database: str, storage_root: str):
    connection = open_sqlite_database(database)
    return connection, compose_sqlite_effective_srt_materialization_service(
        connection, storage_root
    )


def _print_record(materialization, state, outcome=None, file_matches=None) -> None:
    print(f"materialization: {materialization.identity.value}")
    print(f"artifact: {materialization.artifact_id.value}")
    print(f"storage kind: {materialization.storage_kind}")
    print(f"relative location: {materialization.relative_location}")
    print(f"sequence: {materialization.sequence}")
    print(f"payload fingerprint: {materialization.payload_fingerprint}")
    print(f"materialization state: {state.value}")
    if outcome is not None and outcome.state is MaterializationState.MATERIALIZED:
        print(f"bytes written: {outcome.byte_length}")
    if outcome is not None and outcome.state is MaterializationState.FAILED:
        print(f"failure reason: {outcome.failure_reason}")
    if file_matches is not None:
        print(f"physical file currently matches payload: {file_matches}")
    print("the relative location is write provenance, never artifact identity")
    print("delivery state: not part of this contract")


def _run_materialize(args) -> int:
    connection, service = _service(args.database, args.storage_root)
    try:
        record = service.materialize(
            artifact_id=args.artifact,
            relative_location=args.location,
            overwrite=args.overwrite,
        )
    finally:
        connection.close()
    print(f"{record.kind.value} effective SRT materialization")
    _print_record(record.materialization, record.state, record.outcome)
    if record.state is MaterializationState.FAILED:
        print("the failed act is an honest immutable record; nothing was overwritten")
        return 1
    print("no artifact, selection, decision, or upstream record was changed")
    return 0


def _run_show(args) -> int:
    connection, service = _service(args.database, args.storage_root)
    try:
        materialization = service.get(args.materialization)
        if materialization is None:
            raise EffectiveSrtMaterializationError(
                "unknown effective SRT materialization"
            )
        state = service.state(materialization)
        outcome = service.outcome(materialization)
    finally:
        connection.close()
    _print_record(materialization, state, outcome)
    return 0


def _run_status(args) -> int:
    connection, service = _service(args.database, args.storage_root)
    try:
        materialization = service.get(args.materialization)
        if materialization is None:
            raise EffectiveSrtMaterializationError(
                "unknown effective SRT materialization"
            )
        state = service.state(materialization)
        outcome = service.outcome(materialization)
        matches = service.file_matches(materialization)
    finally:
        connection.close()
    _print_record(
        materialization, state, outcome,
        file_matches="absent" if matches is None else ("yes" if matches else "no"),
    )
    print("a missing or diverged physical file never mutates the immutable record")
    return 0


def _run_list(args) -> int:
    connection, service = _service(args.database, args.storage_root)
    try:
        materializations = service.list_for_artifact(args.artifact)
        states = [service.state(m) for m in materializations]
    finally:
        connection.close()
    print(f"materializations for artifact {args.artifact}: {len(materializations)}")
    for materialization, state in zip(materializations, states):
        print(
            f"  #{materialization.sequence} {materialization.relative_location} "
            f"[{state.value}] ({materialization.identity.value})"
        )
    print("history is append-only; records are never mutated or deleted")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.effective_materialize_cli",
        description=(
            "Physical materialization of effective logical SRT artifacts beneath one approved "
            "storage root: record-first immutable intent/outcome records, exact canonical bytes, "
            "no-overwrite-by-default, explicit --overwrite only. Artifact identity never depends "
            "on any path; deletion of a file never mutates history."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success (including idempotent reuse); 1 on malformed/unknown "
            "input or an honestly recorded FAILED write outcome."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _common(sub):
        sub.add_argument("--storage-root", required=True, metavar="DIR",
                         help="absolute path of the approved storage root directory")
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    materialize = subparsers.add_parser(
        "materialize", help="explicitly realize one exact artifact as a physical file"
    )
    materialize.add_argument("--artifact", required=True,
                             metavar="EFFECTIVE_SUBTITLE_SRT_ARTIFACT_ID")
    materialize.add_argument("--location", default=None, metavar="RELATIVE_PATH",
                             help="optional contained relative location (default: <artifact-id>.srt)")
    materialize.add_argument("--overwrite", action="store_true",
                             help="explicitly replace an existing different file (never the default)")
    _common(materialize)
    materialize.set_defaults(func=_run_materialize)

    for name, func, arg, metavar, help_text in (
        ("show", _run_show, "--materialization",
         "EFFECTIVE_SRT_MATERIALIZATION_ID", "show one materialization record"),
        ("status", _run_status, "--materialization",
         "EFFECTIVE_SRT_MATERIALIZATION_ID",
         "derived state plus current physical-file agreement"),
        ("list", _run_list, "--artifact",
         "EFFECTIVE_SUBTITLE_SRT_ARTIFACT_ID",
         "list the append-only materialization history"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument(arg, required=True, metavar=metavar)
        _common(sub)
        sub.set_defaults(func=func)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
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
