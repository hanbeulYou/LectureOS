"""In-process fake-review / fake-transcript acceptance for SRT Artifact Generation (044, stage 2).

Drives the durable pipeline through Approved Subtitle Assembly and then deterministically generates a
canonical SRT Artifact Record from one eligible Approved Subtitle Document.

It verifies the exact serialized SRT payload (contiguous numbering, canonical timestamps, approved text),
that an INELIGIBLE document produces no artifact, provenance and DomainResult chaining, that no existing
canonical artifact is mutated, exact restart reconstruction with a byte-identical payload, deterministic
replay, and that no physical-file / materialization / delivery table is produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    SubtitleArtifactFormat,
    SubtitleArtifactGenerationError,
    SubtitleSrtArtifactIdentityPlan,
)
from lectureos.composition import (
    compose_sqlite_subtitle_srt_artifact_generation_service,
)
from lectureos.execution.identities import ArtifactId, DomainResultId
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleApprovedDocumentRepository,
    SQLiteSubtitleSrtArtifactRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.subtitle_approved_assembly_acceptance import build_persisted_documents


def _plan(name):
    return SubtitleSrtArtifactIdentityPlan(
        artifact_id=ArtifactId(name),
        artifact_result_id=DomainResultId(f"{name}-result"),
    )


def _generate_eligible(connection):
    execution, run_id, execution_id, reading, docs, time_ids = build_persisted_documents(
        connection
    )
    doc_b = docs[1]  # eligible: accept unit 0, untouched unit 1
    doc_c = docs[2]  # ineligible
    service = compose_sqlite_subtitle_srt_artifact_generation_service(
        connection, execution
    )
    artifact = service.record_generation(
        source_approved_document_id=doc_b.document.identity,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_plan("artifact-b"),
    )
    return execution, run_id, execution_id, doc_b, doc_c, artifact, service


def run_subtitle_srt_artifact_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)

        document_repo = SQLiteSubtitleApprovedDocumentRepository(connection)

        (
            execution,
            run_id,
            execution_id,
            doc_b,
            doc_c,
            artifact,
            service,
        ) = _generate_eligible(connection)

        # unit timings are known from the assembly fixture: unit 0 [0,1], unit 1 [1,2]
        unit0, unit1 = doc_b.units
        expected = (
            "1\n00:00:00,000 --> 00:00:01,000\n"
            + "\n".join(unit0.lines)
            + "\n\n2\n00:00:01,000 --> 00:00:02,000\n"
            + "\n".join(unit1.lines)
            + "\n"
        )
        payload_exact = artifact.artifact.payload == expected
        metadata_correct = (
            artifact.artifact.format is SubtitleArtifactFormat.SRT
            and artifact.artifact.encoding == "utf-8"
            and artifact.artifact.cue_count == 2
            and artifact.artifact.byte_length == len(expected.encode("utf-8"))
        )

        # ineligible document produces no artifact
        try:
            service.generate_artifact(
                source_approved_document_id=doc_c.document.identity,
                run_id=run_id,
                unit_execution_id=execution_id,
                identities=_plan("artifact-c"),
            )
            ineligible_rejected = False
        except SubtitleArtifactGenerationError:
            ineligible_rejected = True
        ineligible_rejected = ineligible_rejected and (
            SQLiteSubtitleSrtArtifactRepository(connection).get(ArtifactId("artifact-c"))
            is None
        )

        provenance_linked = (
            artifact.artifact.source_approved_document_id == doc_b.document.identity
            and artifact.artifact_result.kind == "subtitle_srt_artifact"
            and artifact.artifact_result.upstream_results
            == (doc_b.document.domain_result_id,)
        )

        # no upstream mutation: the approved document and its units are unchanged
        no_upstream_mutation = (
            document_repo.get(doc_b.document.identity) == doc_b.document
            and all(document_repo.get_unit(u.identity) == u for u in doc_b.units)
        )

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        no_downstream_tables = not {
            "subtitle_materializations",
            "artifact_files",
            "deliveries",
        } & existing_tables
        connection.close()

        reopened = open_sqlite_database(path)
        artifact_repo = SQLiteSubtitleSrtArtifactRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restored = artifact_repo.get(artifact.artifact.identity)
        restart_reconstructed = (
            restored == artifact.artifact
            and restored.payload == expected
            and results.get(artifact.artifact_result.identity) == artifact.artifact_result
        )
        reopened.close()

        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        _, _, _, _, _, r_artifact, _ = _generate_eligible(replay_connection)
        replay_connection.close()
        deterministic_replay = (
            r_artifact.artifact == artifact.artifact
            and r_artifact.artifact_result == artifact.artifact_result
        )

        return {
            "payload_exact": payload_exact,
            "metadata_correct": metadata_correct,
            "ineligible_rejected": ineligible_rejected,
            "provenance_linked": provenance_linked,
            "no_upstream_mutation": no_upstream_mutation,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_subtitle_srt_artifact_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
