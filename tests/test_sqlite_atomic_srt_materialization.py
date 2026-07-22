import tempfile
import unittest
from pathlib import Path

from lectureos.application import (
    SubtitleMaterializationState,
    SubtitleMaterializationStorageKind,
    SubtitleSrtMaterialization,
    SubtitleSrtMaterializationOutcome,
)
from lectureos.application.identities import SubtitleSrtMaterializationId
from lectureos.application.subtitle_srt_materialization import (
    SUBTITLE_SRT_MATERIALIZATION_RESULT_KIND,
)
from lectureos.execution.identities import (
    ArtifactId,
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.persistence import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleSrtMaterializationCommandPersistence,
    SQLiteSubtitleSrtMaterializationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)

MEDIA = SourceMediaId("media")
TIMELINE = SourceTimelineId("timeline")


def _materialization(name="materialization"):
    return SubtitleSrtMaterialization(
        identity=SubtitleSrtMaterializationId(name),
        domain_result_id=DomainResultId(f"{name}-result"),
        source_artifact_id=ArtifactId("artifact"),
        storage_kind=SubtitleMaterializationStorageKind.LOCAL_FILE,
        relative_location=f"{name}.srt",
        source_media_id=MEDIA,
        source_timeline_id=TIMELINE,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="materialized the srt artifact",
    )


def _result(name="materialization"):
    return DomainResultReference(
        identity=DomainResultId(f"{name}-result"),
        kind=SUBTITLE_SRT_MATERIALIZATION_RESULT_KIND,
        source_media=MEDIA,
        source_timeline=TIMELINE,
        upstream_results=(DomainResultId("artifact-result"),),
    )


class SQLiteAtomicSrtMaterializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.persistence = SQLiteSubtitleSrtMaterializationCommandPersistence(
            self.connection
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_intent_then_outcome_and_reconstructs(self) -> None:
        materialization = _materialization()
        self.persistence.persist_materialization_intent(
            materialization=materialization, materialization_result=_result()
        )
        # before the outcome the state is derived PENDING (no outcome row)
        repo = SQLiteSubtitleSrtMaterializationRepository(self.connection)
        self.assertIsNone(repo.get_outcome(materialization.identity))
        outcome = SubtitleSrtMaterializationOutcome(
            materialization_id=materialization.identity,
            state=SubtitleMaterializationState.MATERIALIZED,
            byte_length=42,
        )
        self.persistence.persist_materialization_outcome(outcome=outcome)
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteSubtitleSrtMaterializationRepository(reopened)
            self.assertEqual(repo.get(materialization.identity), materialization)
            self.assertEqual(repo.get_outcome(materialization.identity), outcome)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                materialization.domain_result_id
            )
            self.assertEqual(result.kind, SUBTITLE_SRT_MATERIALIZATION_RESULT_KIND)
        finally:
            reopened.close()

    def test_failed_outcome_round_trips(self) -> None:
        materialization = _materialization()
        self.persistence.persist_materialization_intent(
            materialization=materialization, materialization_result=_result()
        )
        outcome = SubtitleSrtMaterializationOutcome(
            materialization_id=materialization.identity,
            state=SubtitleMaterializationState.FAILED,
            failure_reason="different bytes present",
        )
        self.persistence.persist_materialization_outcome(outcome=outcome)
        repo = SQLiteSubtitleSrtMaterializationRepository(self.connection)
        self.assertEqual(repo.get_outcome(materialization.identity), outcome)

    def test_intent_identity_collision_rolls_back(self) -> None:
        self.persistence.persist_materialization_intent(
            materialization=_materialization(), materialization_result=_result()
        )
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_materialization_intent(
                materialization=_materialization(), materialization_result=_result()
            )

    def test_intent_result_collision_rolls_back(self) -> None:
        self.persistence.persist_materialization_intent(
            materialization=_materialization("a"), materialization_result=_result("a")
        )
        # reuse the same DomainResult id under a new materialization identity
        clashing = SubtitleSrtMaterialization(
            identity=SubtitleSrtMaterializationId("b"),
            domain_result_id=DomainResultId("a-result"),
            source_artifact_id=ArtifactId("artifact"),
            storage_kind=SubtitleMaterializationStorageKind.LOCAL_FILE,
            relative_location="b.srt",
            source_media_id=MEDIA,
            source_timeline_id=TIMELINE,
            run_id=ProcessingRunId("run"),
            unit_execution_id=UnitExecutionId("execution"),
            sequence=0,
            reason="clash",
        )
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_materialization_intent(
                materialization=clashing,
                materialization_result=DomainResultReference(
                    identity=DomainResultId("a-result"),
                    kind=SUBTITLE_SRT_MATERIALIZATION_RESULT_KIND,
                    source_media=MEDIA,
                    source_timeline=TIMELINE,
                    upstream_results=(DomainResultId("artifact-result"),),
                ),
            )
        self.assertIsNone(
            SQLiteSubtitleSrtMaterializationRepository(self.connection).get(
                SubtitleSrtMaterializationId("b")
            )
        )

    def test_outcome_requires_existing_materialization(self) -> None:
        with self.assertRaises(PersistenceError):
            self.persistence.persist_materialization_outcome(
                outcome=SubtitleSrtMaterializationOutcome(
                    materialization_id=SubtitleSrtMaterializationId("missing"),
                    state=SubtitleMaterializationState.MATERIALIZED,
                    byte_length=1,
                )
            )

    def test_duplicate_outcome_is_rejected(self) -> None:
        materialization = _materialization()
        self.persistence.persist_materialization_intent(
            materialization=materialization, materialization_result=_result()
        )
        outcome = SubtitleSrtMaterializationOutcome(
            materialization_id=materialization.identity,
            state=SubtitleMaterializationState.MATERIALIZED,
            byte_length=42,
        )
        self.persistence.persist_materialization_outcome(outcome=outcome)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_materialization_outcome(outcome=outcome)


if __name__ == "__main__":
    unittest.main()
