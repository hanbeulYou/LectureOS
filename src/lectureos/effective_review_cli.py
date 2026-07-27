"""Runnable entry point for Effective-Source Subtitle Review Preparation (GOAL-014).

One CLI over an existing repository (identities only — never media paths). A thin application boundary with no
preparation or authority logic:

* ``prepare`` — explicitly prepare one exact effective-source candidate as an immutable review subject;
* ``show`` — one review subject with its exact candidate binding and provenance;
* ``list`` — the canonical subject (if any) prepared for a candidate;
* ``status`` — a subject's **derived** candidate-source and review-subject currentness.

Preparation grants no authority: no Human Decision, reviewer, approval/rejection/completion status, final
selection, export, or legacy review record is created, and no fabricated review status is displayed. No
``--force``, ``--latest``, ``--best``, ``--auto``, or ``--repair``. On any failure it prints an explicit
error, returns non-zero, and leaves the repository unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.effective_review_cli prepare --candidate <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_review_cli show --review-subject <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_review_cli list --candidate <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.effective_review_cli status --review-subject <id> --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.effective_subtitle_generation import (
    EffectiveSubtitleGenerationError,
)
from lectureos.application.effective_subtitle_review_preparation import (
    EffectiveSubtitleReviewPreparationError,
    ReviewSubjectCurrentness,
)
from lectureos.application.effective_transcript_consumption import (
    ConsumptionCurrentness,
    EffectiveTranscriptConsumptionError,
)
from lectureos.composition import (
    compose_sqlite_effective_subtitle_review_preparation_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database


def _service(database: str):
    connection = open_sqlite_database(database)
    return connection, compose_sqlite_effective_subtitle_review_preparation_service(connection)


def _mark(state) -> str:
    if state is ConsumptionCurrentness.CURRENT or state is ReviewSubjectCurrentness.CURRENT:
        return "current"
    return state.value


def _print_subject(subject, candidate, status=None) -> None:
    print(f"review subject: {subject.identity.value}")
    print(f"candidate: {candidate.identity.value}")
    print(f"candidate graph fingerprint: {subject.candidate_graph_fingerprint}")
    print(f"consumption binding: {candidate.consumption_binding_id.value}")
    print(f"source kind: {candidate.source_kind.value}")
    print(f"source identity: {candidate.source_transcript_identity}")
    print(f"parent raw transcript: {candidate.parent_raw_transcript_id.value}")
    print(
        f"generator: {candidate.generator_kind} v{candidate.generator_version} "
        f"(parameters v{candidate.generation_parameters_version})"
    )
    print(f"cues: {candidate.cue_count}")
    print(
        f"preparation contract: {subject.preparation_kind} v{subject.preparation_version}"
    )
    if status is not None:
        print(f"candidate source currentness: {_mark(status.candidate_source_currentness)}")
        print(f"review subject currentness: {_mark(status.review_subject_currentness)}")
    print("human decision state: not part of this contract")


def _run_prepare(args) -> int:
    connection, service = _service(args.database)
    try:
        result = service.prepare_review(candidate_id=args.candidate)
    finally:
        connection.close()
    print(f"{result.outcome.value} effective subtitle review subject")
    _print_subject(result.subject, result.candidate, result.status)
    print(
        "no review record, decision, reviewer, selection, or export was created "
        "(preparation is preparation only)"
    )
    return 0


def _run_show(args) -> int:
    connection, service = _service(args.database)
    try:
        subject = service.get(args.review_subject)
        if subject is None:
            raise EffectiveSubtitleReviewPreparationError(
                "unknown effective subtitle review subject"
            )
        candidate = service.candidate_of(subject)
        status = service.status(subject)
    finally:
        connection.close()
    _print_subject(subject, candidate, status)
    return 0


def _run_list(args) -> int:
    connection, service = _service(args.database)
    try:
        subject = service.subject_for_candidate(args.candidate)
        candidate = service.candidate_of(subject) if subject is not None else None
        status = service.status(subject) if subject is not None else None
    finally:
        connection.close()
    if subject is None:
        print(f"review subjects for candidate {args.candidate}: 0")
        print("(the candidate has not been explicitly prepared for review)")
        return 0
    print(f"review subjects for candidate {args.candidate}: 1")
    _print_subject(subject, candidate, status)
    return 0


def _run_status(args) -> int:
    connection, service = _service(args.database)
    try:
        subject = service.get(args.review_subject)
        if subject is None:
            raise EffectiveSubtitleReviewPreparationError(
                "unknown effective subtitle review subject"
            )
        status = service.status(subject)
    finally:
        connection.close()
    print(f"review subject: {subject.identity.value}")
    print(f"candidate: {subject.candidate_id.value}")
    print(f"candidate source currentness: {_mark(status.candidate_source_currentness)}")
    print(f"review subject currentness: {_mark(status.review_subject_currentness)}")
    print("a stale review subject remains valid historical evidence")
    print("human decision state: not part of this contract")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.effective_review_cli",
        description=(
            "Effective-source subtitle review preparation: explicitly bind one exact immutable "
            "candidate graph as an immutable review subject. Preparation grants no authority — no "
            "Human Decision, reviewer, status, final selection, export, or legacy review record is "
            "created, and currentness is always derived. Accepts identities, never media paths."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit status: 0 on success; 1 on malformed/unknown/broken-graph/conflicting input "
            "(repository left unchanged)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _database(sub):
        sub.add_argument("--database", required=True, metavar="PATH",
                         help="path to the existing LectureOS SQLite database")

    for name, func, help_text in (
        ("prepare", _run_prepare,
         "explicitly prepare one exact candidate as a review subject"),
        ("list", _run_list, "show the canonical subject prepared for a candidate"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--candidate", required=True, metavar="EFFECTIVE_SUBTITLE_CANDIDATE_ID",
                         help="exact effective subtitle candidate identity")
        _database(sub)
        sub.set_defaults(func=func)

    for name, func, help_text in (
        ("show", _run_show, "show one review subject with exact provenance"),
        ("status", _run_status, "derive one review subject's currentness"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--review-subject", required=True,
                         metavar="EFFECTIVE_SUBTITLE_REVIEW_SUBJECT_ID",
                         help="canonical effective subtitle review subject identity")
        _database(sub)
        sub.set_defaults(func=func)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
        EffectiveSubtitleReviewPreparationError,
        EffectiveSubtitleGenerationError,
        EffectiveTranscriptConsumptionError,
        KeyError,
        ValueError,
        OSError,
        PersistenceError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
