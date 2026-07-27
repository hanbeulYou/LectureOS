"""Atomic SQLite persistence tests for Effective SRT Deliveries (GOAL-019)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_srt_delivery import (
    DeliveryFailureCategory,
    DeliveryState,
    EffectiveSrtDelivery,
    EffectiveSrtDeliveryOutcome,
    derive_delivery_identity,
)
from lectureos.application.identities import EffectiveSrtMaterializationId
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
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteEffectiveSrtDeliveryCommandPersistence,
    SQLiteEffectiveSrtDeliveryRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError


class SQLiteAtomicEffectiveSrtDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.storage_root = self.base / "storage"
        self.storage_root.mkdir()
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"deliver-atomic \x00\x01")
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
        self.materialization = compose_sqlite_effective_srt_materialization_service(
            self.connection, str(self.storage_root)
        ).materialize(artifact_id=self.artifact.identity.value).materialization
        self.persistence = SQLiteEffectiveSrtDeliveryCommandPersistence(self.connection)
        self.repo = SQLiteEffectiveSrtDeliveryRepository(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _intent(self, location="a.srt", sequence=0, previous=None, overwrite=False):
        return EffectiveSrtDelivery(
            identity=derive_delivery_identity(
                self.materialization.identity, self.artifact.identity, location,
                self.artifact.content_fingerprint, sequence, overwrite,
            ),
            materialization_id=self.materialization.identity,
            artifact_id=self.artifact.identity,
            delivery_kind="local_copy",
            delivery_contract_version=1,
            relative_location=location,
            expected_payload_fingerprint=self.artifact.content_fingerprint,
            sequence=sequence,
            overwrite=overwrite,
            previous_delivery_id=previous,
        )

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_srt_delivery_intents"
        ).fetchone()[0]

    def test_persist_intent_outcome_and_reconstruct_after_restart(self):
        intent = self._intent()
        self.persistence.persist_delivery_intent(delivery=intent)
        outcome = EffectiveSrtDeliveryOutcome(
            delivery_id=intent.identity,
            state=DeliveryState.DELIVERED,
            delivered_payload_fingerprint=self.artifact.content_fingerprint,
            byte_length=42,
        )
        self.persistence.persist_delivery_outcome(outcome=outcome)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteEffectiveSrtDeliveryRepository(reopened)
            self.assertEqual(repo.get(intent.identity), intent)
            self.assertEqual(repo.get_outcome(intent.identity), outcome)
            self.assertEqual(
                repo.get_latest(self.materialization.identity, "a.srt"), intent
            )
            self.assertEqual(
                repo.list_for_materialization(self.materialization.identity), (intent,)
            )
        finally:
            reopened.close()

    def test_identity_collision_rolls_back(self):
        intent = self._intent()
        self.persistence.persist_delivery_intent(delivery=intent)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_delivery_intent(delivery=intent)
        self.assertEqual(self._count(), 1)

    def test_sequence_slot_collision_rolls_back(self):
        # A divergent payload (different overwrite policy) occupying the same
        # (materialization, location, sequence) slot violates the replay-anchor uniqueness.
        self.persistence.persist_delivery_intent(delivery=self._intent())
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_delivery_intent(
                delivery=self._intent(overwrite=True)
            )
        self.assertEqual(self._count(), 1)

    def test_invalid_supersession_rejected(self):
        first = self._intent()
        self.persistence.persist_delivery_intent(delivery=first)
        ghost = derive_delivery_identity(
            self.materialization.identity, self.artifact.identity, "a.srt",
            self.artifact.content_fingerprint, 7, False,
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_delivery_intent(
                delivery=self._intent(sequence=1, previous=ghost)
            )
        # A previous intent from a different destination pair is also rejected.
        other = self._intent(location="b.srt")
        self.persistence.persist_delivery_intent(delivery=other)
        with self.assertRaises(PersistenceError):
            self.persistence.persist_delivery_intent(
                delivery=self._intent(sequence=1, previous=other.identity)
            )
        self.assertEqual(self._count(), 2)

    def test_dangling_materialization_rejected_by_foreign_key(self):
        ghost = EffectiveSrtMaterializationId(
            "subtitle-effective-srt-materialization:" + "9" * 64
        )
        intent = EffectiveSrtDelivery(
            identity=derive_delivery_identity(
                ghost, self.artifact.identity, "a.srt",
                self.artifact.content_fingerprint, 0, False,
            ),
            materialization_id=ghost,
            artifact_id=self.artifact.identity,
            delivery_kind="local_copy",
            delivery_contract_version=1,
            relative_location="a.srt",
            expected_payload_fingerprint=self.artifact.content_fingerprint,
            sequence=0,
            overwrite=False,
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_delivery_intent(delivery=intent)
        self.assertEqual(self._count(), 0)

    def test_duplicate_outcome_rejected(self):
        intent = self._intent()
        self.persistence.persist_delivery_intent(delivery=intent)
        outcome = EffectiveSrtDeliveryOutcome(
            delivery_id=intent.identity,
            state=DeliveryState.FAILED,
            failure_category=DeliveryFailureCategory.WRITE_FAILED,
            failure_reason="write failed",
        )
        self.persistence.persist_delivery_outcome(outcome=outcome)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_delivery_outcome(outcome=outcome)

    def test_outcome_state_exclusivity_enforced_by_schema(self):
        intent = self._intent()
        self.persistence.persist_delivery_intent(delivery=intent)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO subtitle_effective_srt_delivery_outcomes("
                "delivery_id, state, delivered_payload_fingerprint, byte_length, "
                "failure_category, failure_reason) VALUES (?, 'delivered', ?, 10, "
                "'write_failed', 'contradiction')",
                (intent.identity.value, self.artifact.content_fingerprint),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO subtitle_effective_srt_delivery_outcomes("
                "delivery_id, state, delivered_payload_fingerprint, byte_length, "
                "failure_category, failure_reason) "
                "VALUES (?, 'failed', NULL, NULL, NULL, 'no category')",
                (intent.identity.value,),
            )

    def test_repository_rejects_pre_v45_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 45):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 44)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEffectiveSrtDeliveryRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
