"""Runnable entry point for Effective Subtitle SRT Artifact generation (GOAL-017).

One CLI over an existing repository (identities only — never media paths). A thin application boundary with no
export logic:

* ``eligibility`` — derive whether one exact final selection may generate a NEW SRT artifact now
  (it must be the current, applicable selection of its scope), with explicit blocking reasons;
* ``generate`` — explicitly generate (or converge on) the deterministic logical SRT artifact;
* ``show`` — one artifact with its full authority lineage;
* ``content`` — emit the exact canonical SRT payload;
* ``list`` — artifacts recorded for an intake scope;
* ``status`` — one artifact's derived currentness.

**Final Selection ≠ Artifact ≠ physical file**: an artifact is a logical, immutable record — no file is
created, no path or URL is assigned, and materialization is a later goal. No ``--force``. On any failure it
prints an explicit error, returns non-zero, and leaves the repository unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.effective_srt_cli eligibility --selection <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_srt_cli generate --selection <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_srt_cli show --artifact <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_srt_cli content --artifact <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_srt_cli list --intake <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_srt_cli status --artifact <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.effective_subtitle_final_selection import (
    EffectiveSubtitleFinalSelectionError,
)
from lectureos.application.effective_subtitle_srt_artifact import (
    ArtifactCurrentness,
    EffectiveSubtitleSrtArtifactError,
)
from lectureos.composition import (
    compose_sqlite_effective_subtitle_srt_artifact_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database

_NOT_PART = (
    "materialization state: not part of this contract",
    "physical path: not part of this contract",
)


def _service(database: str):
    connection = open_sqlite_database(database)
    return connection, compose_sqlite_effective_subtitle_srt_artifact_service(connection)


def _mark(state: ArtifactCurrentness) -> str:
    return "current" if state is ArtifactCurrentness.CURRENT else state.value


def _print_artifact(artifact, currentness=None) -> None:
    print(f"artifact: {artifact.identity.value}")
    print(f"scope intake: {artifact.transcript_source_intake_id.value}")
    print(f"final selection: {artifact.final_selection_id.value}")
    print(f"candidate: {artifact.candidate_id.value}")
    print(
        f"serializer: {artifact.serializer_kind} v{artifact.serializer_version} "
        f"(parameters v{artifact.serialization_parameters_version})"
    )
    print(f"cues: {artifact.cue_count}")
    print(f"content fingerprint: {artifact.content_fingerprint}")
    if currentness is not None:
        print(f"artifact currentness: {_mark(currentness)}")
    for line in _NOT_PART:
        print(line)


def _run_eligibility(args) -> int:
    connection, service = _service(args.database)
    try:
        report = service.export_eligibility(args.selection)
    finally:
        connection.close()
    print(f"final selection: {args.selection}")
    print(f"eligible for a new SRT artifact: {'yes' if report.eligible else 'no'}")
    print(f"selection is current: {'yes' if report.selection_is_current else 'no'}")
    if report.selection_applicability is not None:
        print(f"selection applicability: {report.selection_applicability.value}")
    print(f"serializer: {report.serializer_kind} v{report.serializer_version}")
    if report.blocking_reason is not None:
        print(f"blocking reason: {report.blocking_reason.value}")
    print("eligibility is derived and never persisted; export remains an explicit request")
    return 0


def _run_generate(args) -> int:
    connection, service = _service(args.database)
    try:
        result = service.generate_srt_artifact(final_selection_id=args.selection)
    finally:
        connection.close()
    print(f"{result.outcome.value} effective subtitle SRT artifact")
    _print_artifact(result.artifact, result.currentness)
    print(
        "no file was created, no path assigned, and no selection, candidate, decision, "
        "or legacy export record was changed (a logical artifact only)"
    )
    return 0


def _run_show(args) -> int:
    connection, service = _service(args.database)
    try:
        artifact = service.get(args.artifact)
        if artifact is None:
            raise EffectiveSubtitleSrtArtifactError(
                "unknown effective subtitle SRT artifact"
            )
        currentness = service.currentness(artifact)
    finally:
        connection.close()
    _print_artifact(artifact, currentness)
    return 0


def _run_content(args) -> int:
    connection, service = _service(args.database)
    try:
        artifact = service.get(args.artifact)
        if artifact is None:
            raise EffectiveSubtitleSrtArtifactError(
                "unknown effective subtitle SRT artifact"
            )
    finally:
        connection.close()
    sys.stdout.write(artifact.srt_content)
    return 0


def _run_list(args) -> int:
    connection, service = _service(args.database)
    try:
        artifacts = service.list_for_intake(args.intake)
        currentness = [service.currentness(artifact) for artifact in artifacts]
    finally:
        connection.close()
    print(f"effective SRT artifacts for intake {args.intake}: {len(artifacts)}")
    for artifact, state in zip(artifacts, currentness):
        print(
            f"  selection {artifact.final_selection_id.value} "
            f"({artifact.cue_count} cues) [{_mark(state)}] ({artifact.identity.value})"
        )
    print("artifacts are immutable logical records; currentness is derived")
    return 0


def _run_status(args) -> int:
    connection, service = _service(args.database)
    try:
        artifact = service.get(args.artifact)
        if artifact is None:
            raise EffectiveSubtitleSrtArtifactError(
                "unknown effective subtitle SRT artifact"
            )
        currentness = service.currentness(artifact)
    finally:
        connection.close()
    print(f"artifact: {artifact.identity.value}")
    print(f"final selection: {artifact.final_selection_id.value}")
    print(f"artifact currentness: {_mark(currentness)}")
    print("a superseded or stale artifact remains an immutable historical record")
    for line in _NOT_PART:
        print(line)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.effective_srt_cli",
        description=(
            "Deterministic logical SRT artifact generation from the current applicable effective "
            "final selection: derived export eligibility, the released canonical SRT serializer, "
            "and immutable content-fingerprinted artifacts. No file, path, URL, or "
            "materialization exists in this contract. Accepts identities, never media paths."
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

    for name, func, help_text in (
        ("eligibility", _run_eligibility,
         "derive whether a selection may generate a new SRT artifact"),
        ("generate", _run_generate,
         "explicitly generate or reuse the deterministic logical SRT artifact"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--selection", required=True,
                         metavar="EFFECTIVE_SUBTITLE_FINAL_SELECTION_ID",
                         help="exact final selection identity (never latest implicitly)")
        _database(sub)
        sub.set_defaults(func=func)

    for name, func, help_text in (
        ("show", _run_show, "show one artifact with authority lineage"),
        ("content", _run_content, "emit the exact canonical SRT payload"),
        ("status", _run_status, "derive one artifact's currentness"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--artifact", required=True,
                         metavar="EFFECTIVE_SUBTITLE_SRT_ARTIFACT_ID")
        _database(sub)
        sub.set_defaults(func=func)

    lst = subparsers.add_parser("list", help="list artifacts recorded for an intake scope")
    lst.add_argument("--intake", required=True, metavar="TRANSCRIPT_SOURCE_INTAKE_ID")
    _database(lst)
    lst.set_defaults(func=_run_list)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
        EffectiveSubtitleSrtArtifactError,
        EffectiveSubtitleFinalSelectionError,
        KeyError,
        ValueError,
        OSError,
        PersistenceError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
