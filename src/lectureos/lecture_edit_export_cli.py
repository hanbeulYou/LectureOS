"""Runnable entry point for effective-generation Edit Export Assembly (044 §23, GOAL-030).

One CLI over an existing repository (identities only — never media paths):

* ``scope`` — derive the export scope of one Source Timeline: every Edit Candidate with its export
  eligibility and, for the eligible ones, the approved edit that would become a member;
* ``assemble`` — record one immutable Assembly for that timeline's **complete** eligible scope;
* ``show`` — one recorded Assembly and its ordered membership;
* ``history`` — every Assembly recorded for one timeline;
* ``artifact`` — derive one Assembly's canonical external representation (044 §24);
* ``serialize`` — project that representation into LectureOS Lecture Edit Export JSON v1 (044 §25);
* ``materialize`` — place the serialized payload at a caller-supplied local destination (044 §25).

**Assembling approves nothing (EA-6).** Review remains the only place Human Authority is exercised;
this command records which already-approved edits belong together and changes no Review record.
Membership is derived and total (EA-3) — there is no subset, filter, selection, or Final Selection —
and export eligibility is the conjunction of a current operative judgment, a single actor holding
authority history, and a `current` chain standing (EA-4).

``artifact`` presents the Assembly's complete approved meaning as the canonical **external
representation** — *what* is communicated. It re-evaluates no eligibility, standing, authority, or
Conflict (AR-8): membership was fixed when the Assembly was admitted, so an Assembly whose members
were later superseded still yields a correct Artifact. Deriving one approves nothing, writes nothing,
and is not persisted — it is regenerable from the Assembly on demand (AR-9, AR-11).

``serialize`` and ``materialize`` are non-authoritative projections (S-11): they approve nothing,
change no upstream record, and never add, drop, or reinterpret an approved value. Serialization is
deterministic — the same Artifact always yields the same bytes — and the file is **not** the
Artifact's identity: no path, name, URL, time, or filesystem metadata participates in any identity
(S-6). Neither the payload nor the file outcome is stored in the database (S-10).

**Nothing downstream exists here.** No second format, output timeline, package, download, URL,
provider, NLE adapter, Export Profile, Export Configuration, or publication is produced.

``assemble`` stops without acting in the two situations `044 §23` leaves undecided — a cross-actor
Review Conflict on the timeline, or a scope with no eligible member. That stop is a **contract gap,
not a product refusal**: the Blueprint does not yet say what should happen, and an implementation may
not settle it by choosing. Use ``scope`` to see the situation; it never stops.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.lecture_edit_export_cli scope \\
        --source-timeline <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_edit_export_cli assemble \\
        --source-timeline <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_edit_export_cli show \\
        --assembly <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_edit_export_cli history \\
        --source-timeline <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_edit_export_cli artifact \\
        --assembly <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_edit_export_cli serialize \\
        --assembly <id> --database <db>
    PYTHONPATH=src python3 -m lectureos.lecture_edit_export_cli materialize \\
        --assembly <id> --destination <absolute path> [--overwrite] --database <db>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.lecture_analysis_edit_candidate import (
    LectureAnalysisEditCandidateError,
)
from lectureos.application.lecture_edit_export_artifact import (
    LectureEditExportArtifactError,
)
from lectureos.application.lecture_edit_export_materialization import (
    LectureEditExportMaterializationError,
)
from lectureos.application.lecture_edit_export_serialization import (
    LectureEditExportSerializationError,
    serialize_lecture_edit_export_json,
)
from lectureos.application.lecture_edit_export_assembly import (
    LectureEditExportAssemblyError,
)
from lectureos.application.lecture_review_authority import LectureReviewAuthorityError
from lectureos.application.lecture_review_decision import LectureReviewError
from lectureos.composition import (
    compose_lecture_edit_export_materialization_service,
    compose_sqlite_lecture_edit_export_artifact_service,
    compose_sqlite_lecture_edit_export_assembly_service,
)
from lectureos.persistence import PersistenceError, open_sqlite_database

_NOT_PART = (
    "other concrete formats: not part of this contract",
    "export profile and configuration: not part of this contract",
    "selection and final selection: not part of this pipeline at all",
    "overlap adjudication: not part of this contract",
    "new approval authority: not part of this contract (review owns it)",
)

_ELIGIBILITY_EXPLANATIONS = {
    "eligible": "current operative judgment approves it, one actor, chain standing current",
    "no_recorded_authority": (
        "no recorded authority history for this candidate — this does NOT mean no judgment "
        "exists; a judgment admitted before the authority-history contract carries no position"
    ),
    "cross_actor_conflict": (
        "two or more actors hold authority history — a §3.12 Review Conflict that is surfaced, "
        "never arbitrated; resolve it in Review"
    ),
    "current_judgment_approves_nothing": (
        "the current operative judgment is a reject, which owns no approved edit"
    ),
    "superseded_by_authority_change": (
        "the anchor chain no longer binds the current authority; the approval remains valid "
        "immutable history"
    ),
    "current_authority_ineligible": (
        "the chain's current authority is itself ineligible; the approval remains valid "
        "immutable history"
    ),
}


def _service(args):
    connection = open_sqlite_database(args.database)
    return connection, compose_sqlite_lecture_edit_export_assembly_service(connection)


def _print_assembly(assembly) -> None:
    print(f"edit export assembly: {assembly.identity.value}")
    print(f"source timeline: {assembly.source_timeline_id.value}")
    print(f"assembly contract version: {assembly.assembly_contract_version}")
    print(f"members: {len(assembly.members)}")
    for member in assembly.members:
        print(f"  [{member.ordinal}] {member.approved_edit_decision_id.value}")
    print(
        "member order is deterministic presentation only — never an execution, timeline, or "
        "overlap order"
    )


def _run_scope(args) -> int:
    connection, service = _service(args)
    try:
        observation = service.observe_scope(args.source_timeline)
    finally:
        connection.close()
    print(f"source timeline: {observation.source_timeline_id.value}")
    print(f"edit candidates on this timeline: {len(observation.standings)}")
    for standing in observation.standings:
        print(f"  candidate {standing.candidate_id.value}")
        print(f"    export eligibility: {standing.eligibility.value}")
        print(f"    why: {_ELIGIBILITY_EXPLANATIONS[standing.eligibility.value]}")
        if standing.actors:
            print(
                "    actors with authority history: "
                + ", ".join(actor.value for actor in standing.actors)
            )
        if standing.approved is not None:
            print(
                f"    approved edit decision: {standing.approved.identity.value}"
            )
    print(f"export-eligible members: {len(observation.eligible)}")
    if observation.has_conflict:
        print(
            f"cross-actor review conflicts: {len(observation.conflicts)} — assembly admission is "
            "undecided by the Blueprint while any conflict stands"
        )
    print("this observation is derived and stored nothing")
    for line in _NOT_PART:
        print(line)
    return 0


def _run_assemble(args) -> int:
    connection, service = _service(args)
    try:
        result = service.admit_assembly(args.source_timeline)
    finally:
        connection.close()
    print(f"{result.outcome.value} edit export assembly")
    _print_assembly(result.assembly)
    print(
        f"derived from {len(result.observation.standings)} candidate(s) on this timeline; "
        "membership is the complete export-eligible set, never a selection"
    )
    print("no human authority was exercised: review already decided what is approved")
    for line in _NOT_PART:
        print(line)
    return 0


def _run_show(args) -> int:
    connection, service = _service(args)
    try:
        assembly = service.get(args.assembly)
    finally:
        connection.close()
    if assembly is None:
        print("no such edit export assembly")
        return 1
    _print_assembly(assembly)
    for line in _NOT_PART:
        print(line)
    return 0


def _run_history(args) -> int:
    connection, service = _service(args)
    try:
        assemblies = service.history(args.source_timeline)
    finally:
        connection.close()
    print(f"source timeline: {args.source_timeline}")
    print(f"recorded assemblies: {len(assemblies)}")
    for assembly in assemblies:
        print(f"  {assembly.identity.value} ({len(assembly.members)} member(s))")
    print(
        "several assemblies may exist: membership is derived and total, so an upstream authority "
        "change makes a NEW assembly gather a different set — no recorded assembly is ever "
        "rewritten, and this contract defines no currentness among them"
    )
    return 0


def _run_artifact(args) -> int:
    connection = open_sqlite_database(args.database)
    try:
        artifact = compose_sqlite_lecture_edit_export_artifact_service(
            connection
        ).derive_artifact(args.assembly)
    finally:
        connection.close()
    print(f"edit export artifact: {artifact.identity.value}")
    print(f"source assembly: {artifact.source_assembly_id.value}")
    print(f"source timeline: {artifact.source_timeline_id.value}")
    print(f"artifact contract version: {artifact.artifact_contract_version}")
    print(f"presented edits: {len(artifact.entries)}")
    for entry in artifact.entries:
        print(f"  [{entry.ordinal}] {entry.decision_kind.value} by {entry.actor.value}")
        print(
            f"      source timeline range: {entry.approved_range_start} -> "
            f"{entry.approved_range_end}"
        )
        print(f"      approved candidate type or label: {entry.approved_label}")
        print(f"      approved rationale: {entry.approved_rationale}")
        print(
            f"      approved edit decision: {entry.source_approved_edit_decision_id.value}"
        )
    print(
        "ranges are Source Timeline ranges, never output-timeline coordinates; this "
        "representation is descriptive and carries no executable edit meaning"
    )
    print(
        "derived, regenerable, and not stored: nothing was written, and re-deriving from the same "
        "assembly yields the same artifact"
    )
    print("no eligibility, standing, authority, or conflict was re-evaluated")
    for line in _NOT_PART:
        print(line)
    return 0


def _derive(args):
    connection = open_sqlite_database(args.database)
    try:
        return compose_sqlite_lecture_edit_export_artifact_service(
            connection
        ).derive_artifact(args.assembly)
    finally:
        connection.close()


def _print_format(serialized) -> None:
    print(f"format: {serialized.format}")
    print(f"format version: {serialized.version}")
    print(f"media type: {serialized.media_type}")
    print(f"encoding: {serialized.encoding}")
    print(f"byte length: {serialized.byte_length}")


def _run_serialize(args) -> int:
    serialized = serialize_lecture_edit_export_json(_derive(args))
    _print_format(serialized)
    print("--- payload ---")
    print(serialized.payload, end="")
    print("--- end payload ---")
    print(
        "this format identity is distinct from the legacy lectureos-edit-export-json: the payload "
        "shape differs and neither generation supersedes the other"
    )
    print("deterministic: the same assembly always yields these exact bytes")
    print("nothing was written and nothing was stored")
    for line in _NOT_PART:
        print(line)
    return 0


def _run_materialize(args) -> int:
    result = compose_lecture_edit_export_materialization_service().materialize_artifact(
        artifact=_derive(args),
        destination=args.destination,
        overwrite=args.overwrite,
    )
    print(f"materialized: {result.final_path}")
    _print_format(result)
    print(
        "the destination was supplied by the caller; this contract chooses no path, and the file "
        "is not the artifact's identity"
    )
    print(
        "the write was atomic: on failure no partial file is left at the final path; identical "
        "bytes are an idempotent success and different bytes are refused unless --overwrite"
    )
    print("nothing was stored in the database, and no approval was made")
    for line in _NOT_PART:
        print(line)
    return 0


def _database(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--database", required=True, metavar="SQLITE_PATH")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lectureos.lecture_edit_export_cli",
        description=(
            "Edit Export Assembly for the effective-transcript generation (044 §23): gather one "
            "Source Timeline's complete export-eligible approved edits into one immutable scope"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scope = subparsers.add_parser(
        "scope", help="derive one Source Timeline's export scope (never stops, stores nothing)"
    )
    scope.add_argument("--source-timeline", required=True, metavar="SOURCE_TIMELINE_ID")
    _database(scope)
    scope.set_defaults(func=_run_scope)

    assemble = subparsers.add_parser(
        "assemble", help="record one immutable assembly for the complete eligible scope"
    )
    assemble.add_argument(
        "--source-timeline", required=True, metavar="SOURCE_TIMELINE_ID"
    )
    _database(assemble)
    assemble.set_defaults(func=_run_assemble)

    show = subparsers.add_parser("show", help="one recorded assembly and its membership")
    show.add_argument("--assembly", required=True, metavar="LECTURE_EDIT_EXPORT_ASSEMBLY_ID")
    _database(show)
    show.set_defaults(func=_run_show)

    history = subparsers.add_parser(
        "history", help="every assembly recorded for one Source Timeline"
    )
    history.add_argument(
        "--source-timeline", required=True, metavar="SOURCE_TIMELINE_ID"
    )
    _database(history)
    history.set_defaults(func=_run_history)

    artifact = subparsers.add_parser(
        "artifact",
        help="derive one assembly's canonical external representation (never stored)",
    )
    artifact.add_argument(
        "--assembly", required=True, metavar="LECTURE_EDIT_EXPORT_ASSEMBLY_ID"
    )
    _database(artifact)
    artifact.set_defaults(func=_run_artifact)

    serialize = subparsers.add_parser(
        "serialize",
        help="project one assembly's artifact into LectureOS Lecture Edit Export JSON v1",
    )
    serialize.add_argument(
        "--assembly", required=True, metavar="LECTURE_EDIT_EXPORT_ASSEMBLY_ID"
    )
    _database(serialize)
    serialize.set_defaults(func=_run_serialize)

    materialize = subparsers.add_parser(
        "materialize",
        help="place the serialized payload at a caller-supplied local destination",
    )
    materialize.add_argument(
        "--assembly", required=True, metavar="LECTURE_EDIT_EXPORT_ASSEMBLY_ID"
    )
    materialize.add_argument("--destination", required=True, metavar="ABSOLUTE_PATH")
    materialize.add_argument(
        "--overwrite",
        action="store_true",
        help="atomically replace an existing regular file holding different bytes",
    )
    _database(materialize)
    materialize.set_defaults(func=_run_materialize)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (
        LectureEditExportSerializationError,
        LectureEditExportMaterializationError,
        LectureEditExportArtifactError,
        LectureEditExportAssemblyError,
        LectureReviewError,
        LectureReviewAuthorityError,
        LectureAnalysisEditCandidateError,
        KeyError,
        ValueError,
        OSError,
        PersistenceError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
