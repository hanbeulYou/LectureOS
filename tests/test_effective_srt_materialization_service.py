"""Application tests for Effective SRT Physical Materialization (GOAL-018)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_srt_materialization import (
    EffectiveSrtMaterializationError,
    MaterializationState,
    default_relative_location,
    derive_materialization_identity,
)
from lectureos.application.identities import EffectiveSubtitleSrtArtifactId
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_srt_materialization_service,
    compose_sqlite_effective_subtitle_final_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_effective_subtitle_srt_artifact_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database

_ART = EffectiveSubtitleSrtArtifactId("subtitle-effective-srt-artifact:" + "a" * 64)


class IdentityTests(unittest.TestCase):
    def test_identity_deterministic_and_input_sensitive(self):
        a = derive_materialization_identity(_ART, "a.srt", 0)
        self.assertEqual(a, derive_materialization_identity(_ART, "a.srt", 0))
        self.assertTrue(a.value.startswith("subtitle-effective-srt-materialization:"))
        self.assertNotEqual(a, derive_materialization_identity(_ART, "b.srt", 0))
        self.assertNotEqual(a, derive_materialization_identity(_ART, "a.srt", 1))

    def test_default_location_policy(self):
        self.assertEqual(default_relative_location(_ART), f"{_ART.value}.srt")


class EffectiveSrtMaterializationServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.storage_root = self.base / "out"
        self.storage_root.mkdir()
        self.connection = initialize_sqlite_database(self.base / "lectureos.sqlite3")
        source = self.base / "a.bin"
        source.write_bytes(b"materialize \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "원본"}]}
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
        self.materializer = compose_sqlite_effective_srt_materialization_service(
            self.connection, str(self.storage_root)
        )

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_srt_materializations"
        ).fetchone()[0]

    def test_first_materialization_writes_exact_bytes_record_first(self):
        record = self.materializer.materialize(artifact_id=self.artifact.identity.value)
        self.assertEqual(record.kind.value, "created")
        self.assertIs(record.state, MaterializationState.MATERIALIZED)
        self.assertEqual(record.outcome.byte_length, len(self.artifact.srt_content.encode("utf-8")))
        path = self.storage_root / record.materialization.relative_location
        self.assertEqual(path.read_bytes(), self.artifact.srt_content.encode("utf-8"))
        self.assertEqual(
            record.materialization.payload_fingerprint, self.artifact.content_fingerprint
        )

    def test_replay_reuses_without_new_record(self):
        first = self.materializer.materialize(artifact_id=self.artifact.identity.value)
        replay = self.materializer.materialize(artifact_id=self.artifact.identity.value)
        self.assertEqual(replay.kind.value, "reused")
        self.assertEqual(replay.materialization.identity, first.materialization.identity)
        self.assertEqual(self._count(), 1)

    def test_existing_different_file_records_failed_outcome(self):
        location = "manual.srt"
        (self.storage_root / location).write_bytes(b"different\n")
        record = self.materializer.materialize(
            artifact_id=self.artifact.identity.value, relative_location=location
        )
        self.assertIs(record.state, MaterializationState.FAILED)
        self.assertIn("Collision", record.outcome.failure_reason)
        self.assertEqual((self.storage_root / location).read_bytes(), b"different\n")

    def test_explicit_overwrite_replaces_as_new_event(self):
        location = "manual.srt"
        (self.storage_root / location).write_bytes(b"different\n")
        blocked = self.materializer.materialize(
            artifact_id=self.artifact.identity.value, relative_location=location
        )
        overwritten = self.materializer.materialize(
            artifact_id=self.artifact.identity.value, relative_location=location,
            overwrite=True,
        )
        self.assertIs(overwritten.state, MaterializationState.MATERIALIZED)
        self.assertEqual(
            overwritten.materialization.sequence, blocked.materialization.sequence + 1
        )
        self.assertEqual(
            overwritten.materialization.previous_materialization_id,
            blocked.materialization.identity,
        )
        self.assertEqual(
            (self.storage_root / location).read_bytes(),
            self.artifact.srt_content.encode("utf-8"),
        )

    def test_deleted_file_never_mutates_records(self):
        first = self.materializer.materialize(artifact_id=self.artifact.identity.value)
        path = self.storage_root / first.materialization.relative_location
        path.unlink()
        self.assertIs(
            self.materializer.state(first.materialization),
            MaterializationState.MATERIALIZED,
        )
        self.assertIsNone(self.materializer.file_matches(first.materialization))
        again = self.materializer.materialize(artifact_id=self.artifact.identity.value)
        self.assertEqual(again.kind.value, "created")
        self.assertEqual(again.materialization.sequence, 1)
        self.assertEqual(path.read_bytes(), self.artifact.srt_content.encode("utf-8"))

    def test_escaping_and_absolute_locations_refused(self):
        for bad in ("../escape.srt", "/abs.srt", "  "):
            with self.assertRaises(EffectiveSrtMaterializationError):
                self.materializer.materialize(
                    artifact_id=self.artifact.identity.value, relative_location=bad
                )
        self.assertEqual(self._count(), 0)

    def test_unknown_artifact_refused(self):
        with self.assertRaises(EffectiveSrtMaterializationError):
            self.materializer.materialize(
                artifact_id="subtitle-effective-srt-artifact:" + "0" * 64
            )
        with self.assertRaises(EffectiveSrtMaterializationError):
            self.materializer.materialize(artifact_id="not-an-artifact")
        self.assertEqual(self._count(), 0)

    def test_dangling_pending_intent_is_completed_not_duplicated(self):
        # Simulate a crash between intent and outcome: intent persisted, no outcome.
        from lectureos.application.effective_srt_materialization import (
            EffectiveSrtMaterialization,
            MATERIALIZATION_STORAGE_KIND,
        )
        from lectureos.persistence import (
            SQLiteEffectiveSrtMaterializationCommandPersistence,
        )

        location = default_relative_location(self.artifact.identity)
        intent = EffectiveSrtMaterialization(
            identity=derive_materialization_identity(self.artifact.identity, location, 0),
            artifact_id=self.artifact.identity,
            storage_kind=MATERIALIZATION_STORAGE_KIND,
            relative_location=location,
            payload_fingerprint=self.artifact.content_fingerprint,
            sequence=0,
        )
        SQLiteEffectiveSrtMaterializationCommandPersistence(
            self.connection
        ).persist_materialization_intent(materialization=intent)
        record = self.materializer.materialize(artifact_id=self.artifact.identity.value)
        self.assertEqual(record.materialization.identity, intent.identity)
        self.assertIs(record.state, MaterializationState.MATERIALIZED)
        self.assertEqual(self._count(), 1)


if __name__ == "__main__":
    unittest.main()
