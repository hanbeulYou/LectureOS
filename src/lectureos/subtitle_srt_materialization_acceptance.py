"""In-process fake-review / fake-transcript acceptance for SRT Physical Materialization (044 §17).

Drives the durable pipeline through SRT Artifact Generation and then materializes the canonical artifact
to a real physical file under a temporary approved Storage Root, exercising the record-first lifecycle,
collision handling, reconciliation of a dangling PENDING, rematerialization, and deterministic replay.

It verifies the exact realized bytes, the PENDING→MATERIALIZED|FAILED records, provenance and DomainResult
chaining, that no existing canonical artifact is mutated (and the Artifact carries no materialization
status), restart reconstruction, deterministic replay, and that no Delivery/URL table is produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    SubtitleMaterializationState,
    SubtitleMaterializationStorageKind,
    SubtitleSrtMaterialization,
    SubtitleSrtMaterializationIdentityPlan,
)
from lectureos.application.identities import SubtitleSrtMaterializationId
from lectureos.composition import (
    compose_sqlite_subtitle_srt_materialization_service,
)
from lectureos.execution.identities import ArtifactId, DomainResultId
from lectureos.execution.models import DomainResultReference
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleSrtArtifactRepository,
    SQLiteSubtitleSrtMaterializationCommandPersistence,
    SQLiteSubtitleSrtMaterializationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.subtitle_srt_artifact_acceptance import _generate_eligible


def _plan(name):
    return SubtitleSrtMaterializationIdentityPlan(
        materialization_id=SubtitleSrtMaterializationId(name),
        materialization_result_id=DomainResultId(f"{name}-result"),
    )


def _persisted_artifact(connection):
    execution, run_id, execution_id, _doc_b, _doc_c, artifact, _service = _generate_eligible(
        connection
    )
    return execution, run_id, execution_id, artifact.artifact


def _materialize(connection, execution, run_id, execution_id, artifact, root, name):
    service = compose_sqlite_subtitle_srt_materialization_service(
        connection, execution, root
    )
    return service.record_materialization(
        source_artifact_id=artifact.identity,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_plan(name),
    )


def run_subtitle_srt_materialization_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        path = base / "acceptance.sqlite3"
        root = base / "root"
        root.mkdir()
        connection = initialize_sqlite_database(path)

        artifact_repo = SQLiteSubtitleSrtArtifactRepository(connection)
        execution, run_id, execution_id, artifact = _persisted_artifact(connection)
        payload_bytes = artifact.payload.encode("utf-8")
        artifact_before = artifact_repo.get(artifact.identity)

        record = _materialize(
            connection, execution, run_id, execution_id, artifact, root, "mat-a"
        )
        # exact realized bytes on disk
        exact_bytes = (root / "mat-a.srt").read_bytes() == payload_bytes
        materialized = (
            record.outcome.state is SubtitleMaterializationState.MATERIALIZED
            and record.outcome.byte_length == len(payload_bytes)
        )
        # provenance + DomainResult chaining
        result = SQLiteDomainResultReferenceRepository(connection).get(
            record.materialization.domain_result_id
        )
        provenance_linked = (
            record.materialization.source_artifact_id == artifact.identity
            and result.kind == "subtitle_srt_materialization"
            and result.upstream_results == (artifact.domain_result_id,)
        )
        # no upstream mutation + Artifact carries no materialization status
        artifact_after = artifact_repo.get(artifact.identity)
        no_upstream_mutation = artifact_before == artifact_after
        no_materialization_status = not any(
            "material" in field or "delivery" in field
            for field in type(artifact).__dataclass_fields__
        )

        # rematerialization: a second act with a new identity -> a new record, both files exact
        record2 = _materialize(
            connection, execution, run_id, execution_id, artifact, root, "mat-b"
        )
        rematerialized = (
            record2.materialization.identity != record.materialization.identity
            and record2.outcome.state is SubtitleMaterializationState.MATERIALIZED
            and (root / "mat-b.srt").read_bytes() == payload_bytes
        )
        # idempotent repeat of the first act
        record_again = _materialize(
            connection, execution, run_id, execution_id, artifact, root, "mat-a"
        )
        idempotent = (
            record_again.materialization == record.materialization
            and record_again.outcome == record.outcome
        )

        # different-bytes collision -> FAILED, existing file untouched
        (root / "mat-diff.srt").write_bytes(b"pre-existing different bytes")
        record_diff = _materialize(
            connection, execution, run_id, execution_id, artifact, root, "mat-diff"
        )
        collision_failed = (
            record_diff.outcome.state is SubtitleMaterializationState.FAILED
            and (root / "mat-diff.srt").read_bytes() == b"pre-existing different bytes"
        )

        # crash recovery: a durable PENDING (intent only, no file) reconciles to MATERIALIZED
        intent = SubtitleSrtMaterialization(
            identity=SubtitleSrtMaterializationId("mat-crash"),
            domain_result_id=DomainResultId("mat-crash-result"),
            source_artifact_id=artifact.identity,
            storage_kind=SubtitleMaterializationStorageKind.LOCAL_FILE,
            relative_location="mat-crash.srt",
            source_media_id=artifact.source_media_id,
            source_timeline_id=artifact.source_timeline_id,
            run_id=run_id,
            unit_execution_id=execution_id,
            sequence=0,
            reason="crashed before outcome",
        )
        SQLiteSubtitleSrtMaterializationCommandPersistence(
            connection
        ).persist_materialization_intent(
            materialization=intent,
            materialization_result=DomainResultReference(
                identity=DomainResultId("mat-crash-result"),
                kind="subtitle_srt_materialization",
                source_media=artifact.source_media_id,
                source_timeline=artifact.source_timeline_id,
                upstream_results=(artifact.domain_result_id,),
            ),
        )
        materialization_repo = SQLiteSubtitleSrtMaterializationRepository(connection)
        pending_before = (
            materialization_repo.get_outcome(SubtitleSrtMaterializationId("mat-crash"))
            is None
        )
        reconcile_service = compose_sqlite_subtitle_srt_materialization_service(
            connection, execution, root
        )
        reconciled_record = reconcile_service.reconcile_materialization(
            materialization_id=SubtitleSrtMaterializationId("mat-crash")
        )
        reconciled = (
            pending_before
            and reconciled_record.outcome.state is SubtitleMaterializationState.MATERIALIZED
            and (root / "mat-crash.srt").read_bytes() == payload_bytes
        )

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        no_downstream_tables = not {
            "subtitle_deliveries",
            "deliveries",
            "artifact_urls",
        } & existing_tables
        connection.close()

        # restart reconstruction
        reopened = open_sqlite_database(path)
        repo = SQLiteSubtitleSrtMaterializationRepository(reopened)
        restart_reconstructed = (
            repo.get(record.materialization.identity) == record.materialization
            and repo.get_outcome(record.materialization.identity) == record.outcome
        )
        reopened.close()

        # deterministic replay into a fresh database + root
        replay_path = base / "replay.sqlite3"
        replay_root = base / "replay-root"
        replay_root.mkdir()
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, r_artifact = _persisted_artifact(replay_connection)
        r_record = _materialize(
            replay_connection, r_execution, r_run, r_exec, r_artifact, replay_root, "mat-a"
        )
        replay_connection.close()
        deterministic_replay = (
            r_record.materialization == record.materialization
            and r_record.outcome == record.outcome
            and (replay_root / "mat-a.srt").read_bytes() == payload_bytes
        )

        return {
            "exact_bytes": exact_bytes,
            "materialized": materialized,
            "provenance_linked": provenance_linked,
            "no_upstream_mutation": no_upstream_mutation,
            "no_materialization_status": no_materialization_status,
            "rematerialized": rematerialized,
            "idempotent": idempotent,
            "collision_failed": collision_failed,
            "reconciled": reconciled,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_subtitle_srt_materialization_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
