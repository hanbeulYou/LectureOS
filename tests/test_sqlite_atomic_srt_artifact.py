import tempfile
import unittest
from pathlib import Path

from lectureos.application import SubtitleArtifactFormat, SubtitleSrtArtifactIdentityPlan
from lectureos.execution.identities import ArtifactId, DomainResultId
from lectureos.composition import (
    compose_sqlite_subtitle_srt_artifact_generation_service,
)
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleSrtArtifactCommandPersistence,
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


class SQLiteAtomicSrtArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        (
            self.execution,
            self.run_id,
            self.execution_id,
            self.reading,
            self.docs,
            self.time_ids,
        ) = build_persisted_documents(self.connection)
        self.doc = self.docs[1]  # eligible: accept + untouched

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def _generate(self, name):
        service = compose_sqlite_subtitle_srt_artifact_generation_service(
            self.connection, self.execution
        )
        return service.record_generation(
            source_approved_document_id=self.doc.document.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=_plan(name),
        )

    def test_persists_and_reconstructs_artifact_with_payload(self) -> None:
        prepared = self._generate("artifact")
        self.assertIs(prepared.artifact.format, SubtitleArtifactFormat.SRT)
        self.assertGreater(prepared.artifact.byte_length, 0)
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteSubtitleSrtArtifactRepository(reopened)
            restored = repo.get(prepared.artifact.identity)
            self.assertEqual(restored, prepared.artifact)
            self.assertEqual(restored.payload, prepared.artifact.payload)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.artifact_result.identity
            )
            self.assertEqual(result, prepared.artifact_result)
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = self._generate("artifact")
        self.connection.close()
        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id, _, docs, _ = build_persisted_documents(
                replay_connection
            )
            service = compose_sqlite_subtitle_srt_artifact_generation_service(
                replay_connection, execution
            )
            second = service.record_generation(
                source_approved_document_id=docs[1].document.identity,
                run_id=run_id,
                unit_execution_id=execution_id,
                identities=_plan("artifact"),
            )
            self.assertEqual(first.artifact, second.artifact)
            self.assertEqual(first.artifact_result, second.artifact_result)
        finally:
            replay_connection.close()

    def test_repeated_generation_does_not_mutate_upstream_document(self) -> None:
        from lectureos.persistence import SQLiteSubtitleApprovedDocumentRepository

        repo = SQLiteSubtitleApprovedDocumentRepository(self.connection)
        before = repo.get(self.doc.document.identity)
        self._generate("artifact-1")
        self._generate("artifact-2")
        after = repo.get(self.doc.document.identity)
        self.assertEqual(before, after)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_srt_artifacts"
            ).fetchone()[0],
            2,
        )

    def test_result_collision_rolls_back_artifact(self) -> None:
        service = compose_sqlite_subtitle_srt_artifact_generation_service(
            self.connection, self.execution
        )
        prepared = service.generate_artifact(
            source_approved_document_id=self.doc.document.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=SubtitleSrtArtifactIdentityPlan(
                artifact_id=ArtifactId("artifact-x"),
                # reuse the approved document's DomainResult id to force a collision
                artifact_result_id=DomainResultId("doc-b-result"),
            ),
        )
        persistence = SQLiteSubtitleSrtArtifactCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_srt_artifact(
                artifact=prepared.artifact,
                artifact_result=prepared.artifact_result,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_srt_artifacts WHERE identity = 'artifact-x'"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
