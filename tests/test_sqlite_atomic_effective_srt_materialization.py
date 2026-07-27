"""Atomic SQLite persistence tests for Effective SRT Materializations (GOAL-018)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_srt_materialization import (
    EffectiveSrtMaterialization,
    EffectiveSrtMaterializationOutcome,
    MATERIALIZATION_STORAGE_KIND,
    MaterializationState,
    derive_materialization_identity,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_final_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_effective_subtitle_srt_artifact_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.application.identities import EffectiveSubtitleSrtArtifactId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteEffectiveSrtMaterializationCommandPersistence,
    SQLiteEffectiveSrtMaterializationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError


class SQLiteAtomicEffectiveSrtMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"materialize-atomic \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "하나"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            intake, raw.raw_transcript_id.value
        )
        candidate = compose_sqlite_effective_subtitle_generation_service(self.connection).generate(
            intake_id=intake
        ).candidate
        subject = compose_sqlite_effective_subtitle_review_preparation_service(
            self.connection
        ).prepare_review(candidate_id=candidate.identity.value).subject
        compose_sqlite_effective_subtitle_review_decision_service(self.connection).decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        selection = compose_sqlite_effective_subtitle_final_selection_service(
            self.connection
        ).select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        ).selection
        self.artifact = compose_sqlite_effective_subtitle_srt_artifact_service(
            self.connection
        ).generate_srt_artifact(final_selection_id=selection.identity.value).artifact
        self.persistence = SQLiteEffectiveSrtMaterializationCommandPersistence(self.connection)
        self.repo = SQLiteEffectiveSrtMaterializationRepository(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _intent(self, location="a.srt", sequence=0, previous=None):
        return EffectiveSrtMaterialization(
            identity=derive_materialization_identity(
                self.artifact.identity, location, sequence
            ),
            artifact_id=self.artifact.identity,
            storage_kind=MATERIALIZATION_STORAGE_KIND,
            relative_location=location,
            payload_fingerprint=self.artifact.content_fingerprint,
            sequence=sequence,
            previous_materialization_id=previous,
        )

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_srt_materializations"
        ).fetchone()[0]

    def test_persist_intent_outcome_and_reconstruct_after_restart(self):
        intent = self._intent()
        self.persistence.persist_materialization_intent(materialization=intent)
        outcome = EffectiveSrtMaterializationOutcome(
            materialization_id=intent.identity,
            state=MaterializationState.MATERIALIZED,
            byte_length=42,
        )
        self.persistence.persist_materialization_outcome(outcome=outcome)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteEffectiveSrtMaterializationRepository(reopened)
            self.assertEqual(repo.get(intent.identity), intent)
            self.assertEqual(repo.get_outcome(intent.identity), outcome)
            self.assertEqual(
                repo.get_latest(self.artifact.identity, "a.srt"), intent
            )
            self.assertEqual(repo.list_for_artifact(self.artifact.identity), (intent,))
        finally:
            reopened.close()

    def test_identity_and_sequence_collision_roll_back(self):
        intent = self._intent()
        self.persistence.persist_materialization_intent(materialization=intent)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_materialization_intent(materialization=intent)
        self.assertEqual(self._count(), 1)

    def test_unknown_previous_supersession_rejected(self):
        self.persistence.persist_materialization_intent(materialization=self._intent())
        ghost = derive_materialization_identity(self.artifact.identity, "a.srt", 7)
        bad = self._intent(sequence=1, previous=ghost)
        with self.assertRaises(PersistenceError):
            self.persistence.persist_materialization_intent(materialization=bad)
        self.assertEqual(self._count(), 1)

    def test_dangling_artifact_rejected_by_foreign_key(self):
        ghost = EffectiveSubtitleSrtArtifactId(
            "subtitle-effective-srt-artifact:" + "9" * 64
        )
        intent = EffectiveSrtMaterialization(
            identity=derive_materialization_identity(ghost, "a.srt", 0),
            artifact_id=ghost,
            storage_kind=MATERIALIZATION_STORAGE_KIND,
            relative_location="a.srt",
            payload_fingerprint=self.artifact.content_fingerprint,
            sequence=0,
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_materialization_intent(materialization=intent)
        self.assertEqual(self._count(), 0)

    def test_duplicate_outcome_rejected(self):
        intent = self._intent()
        self.persistence.persist_materialization_intent(materialization=intent)
        outcome = EffectiveSrtMaterializationOutcome(
            materialization_id=intent.identity,
            state=MaterializationState.FAILED,
            failure_reason="write failed",
        )
        self.persistence.persist_materialization_outcome(outcome=outcome)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_materialization_outcome(outcome=outcome)

    def test_repository_rejects_pre_v44_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 44):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 43)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEffectiveSrtMaterializationRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
