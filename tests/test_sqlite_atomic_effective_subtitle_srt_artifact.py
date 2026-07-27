"""Atomic SQLite persistence tests for Effective Subtitle SRT Artifacts (GOAL-017)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_subtitle_srt_artifact import (
    EffectiveSubtitleSrtArtifact,
    SRT_SERIALIZER_KIND,
    SRT_SERIALIZER_VERSION,
    SRT_SERIALIZATION_PARAMETERS_VERSION,
    derive_srt_artifact_identity,
    derive_srt_content_fingerprint,
)
from lectureos.application.identities import EffectiveSubtitleFinalSelectionId
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_final_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteEffectiveSubtitleSrtArtifactCommandPersistence,
    SQLiteEffectiveSubtitleSrtArtifactRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError


class SQLiteAtomicEffectiveSubtitleSrtArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"srt-atomic \x00\x01")
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
        self.selection = compose_sqlite_effective_subtitle_final_selection_service(
            self.connection
        ).select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        ).selection
        self.persistence = SQLiteEffectiveSubtitleSrtArtifactCommandPersistence(self.connection)
        self.repo = SQLiteEffectiveSubtitleSrtArtifactRepository(self.connection)
        self.srt = "1\n00:00:00,000 --> 00:00:01,000\n하나\n"

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _artifact(self, content=None):
        content = content if content is not None else self.srt
        fingerprint = derive_srt_content_fingerprint(content)
        return EffectiveSubtitleSrtArtifact(
            identity=derive_srt_artifact_identity(
                self.selection.identity, self.selection.candidate_id, fingerprint
            ),
            transcript_source_intake_id=self.selection.transcript_source_intake_id,
            final_selection_id=self.selection.identity,
            candidate_id=self.selection.candidate_id,
            serializer_kind=SRT_SERIALIZER_KIND,
            serializer_version=SRT_SERIALIZER_VERSION,
            serialization_parameters_version=SRT_SERIALIZATION_PARAMETERS_VERSION,
            cue_count=1,
            content_fingerprint=fingerprint,
            srt_content=content,
        )

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_srt_artifacts"
        ).fetchone()[0]

    def test_persist_and_reconstruct_after_restart(self):
        artifact = self._artifact()
        self.persistence.persist_artifact(artifact=artifact)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteEffectiveSubtitleSrtArtifactRepository(reopened)
            self.assertEqual(repo.get(artifact.identity), artifact)
            self.assertEqual(repo.get_for_selection(self.selection.identity), artifact)
            self.assertEqual(
                repo.list_for_intake(self.selection.transcript_source_intake_id),
                (artifact,),
            )
        finally:
            reopened.close()

    def test_identity_collision_rolls_back(self):
        artifact = self._artifact()
        self.persistence.persist_artifact(artifact=artifact)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_artifact(artifact=artifact)
        self.assertEqual(self._count(), 1)

    def test_replay_anchor_uniqueness_rejects_second_artifact_for_same_selection(self):
        self.persistence.persist_artifact(artifact=self._artifact())
        divergent = self._artifact("1\n00:00:00,000 --> 00:00:01,000\n다름\n")
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_artifact(artifact=divergent)
        self.assertEqual(self._count(), 1)

    def test_dangling_selection_rejected_by_foreign_key(self):
        ghost = EffectiveSubtitleFinalSelectionId(
            "subtitle-effective-final-selection:" + "9" * 64
        )
        fingerprint = derive_srt_content_fingerprint(self.srt)
        artifact = EffectiveSubtitleSrtArtifact(
            identity=derive_srt_artifact_identity(
                ghost, self.selection.candidate_id, fingerprint
            ),
            transcript_source_intake_id=self.selection.transcript_source_intake_id,
            final_selection_id=ghost,
            candidate_id=self.selection.candidate_id,
            serializer_kind=SRT_SERIALIZER_KIND,
            serializer_version=SRT_SERIALIZER_VERSION,
            serialization_parameters_version=SRT_SERIALIZATION_PARAMETERS_VERSION,
            cue_count=1,
            content_fingerprint=fingerprint,
            srt_content=self.srt,
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_artifact(artifact=artifact)
        self.assertEqual(self._count(), 0)

    def test_repository_rejects_pre_v43_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 43):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 42)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEffectiveSubtitleSrtArtifactRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
