"""Atomic SQLite persistence tests for Effective SRT Publications (GOAL-020)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_srt_publication import (
    EffectiveSrtPublication,
    PublicationKind,
    derive_publication_identity,
    _content_fingerprint,
)
from lectureos.application.identities import (
    EffectiveSrtDeliveryId,
    TranscriptSourceIntakeId,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_srt_delivery_service,
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
    SQLiteEffectiveSrtPublicationCommandPersistence,
    SQLiteEffectiveSrtPublicationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError
from lectureos.review.identities import HumanActorReference


class SQLiteAtomicEffectiveSrtPublicationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.storage_root = self.base / "storage"
        self.delivery_root = self.base / "delivered"
        self.storage_root.mkdir()
        self.delivery_root.mkdir()
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"publish-atomic \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "하나"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.intake, raw.raw_transcript_id.value
        )
        candidate = compose_sqlite_effective_subtitle_generation_service(self.connection).generate(
            intake_id=self.intake
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
        materialization = compose_sqlite_effective_srt_materialization_service(
            self.connection, str(self.storage_root)
        ).materialize(artifact_id=self.artifact.identity.value).materialization
        self.delivery = compose_sqlite_effective_srt_delivery_service(
            self.connection, str(self.storage_root), str(self.delivery_root)
        ).deliver(materialization_id=materialization.identity.value).delivery
        self.persistence = SQLiteEffectiveSrtPublicationCommandPersistence(self.connection)
        self.repo = SQLiteEffectiveSrtPublicationRepository(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _publication(self, kind=PublicationKind.PUBLISH, sequence=0, previous=None,
                     publisher="publisher:kim", rationale=None, target=None):
        intake = TranscriptSourceIntakeId(self.intake)
        target_delivery = None
        target_artifact = None
        if kind is PublicationKind.PUBLISH:
            target_delivery = target if target is not None else self.delivery.identity
            target_artifact = self.artifact.identity
        actor = HumanActorReference(publisher)
        return EffectiveSrtPublication(
            identity=derive_publication_identity(intake, kind, target_delivery, sequence),
            transcript_source_intake_id=intake,
            kind=kind,
            publisher=actor,
            sequence=sequence,
            content_fingerprint=_content_fingerprint(
                intake, kind, target_delivery, target_artifact, sequence, actor, rationale
            ),
            target_delivery_id=target_delivery,
            target_artifact_id=target_artifact,
            previous_publication_id=previous,
            rationale=rationale,
        )

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_srt_publications"
        ).fetchone()[0]

    def test_persist_and_reconstruct_after_restart(self):
        publication = self._publication(rationale="공개")
        self.persistence.persist_publication(publication=publication)
        withdrawal = self._publication(
            kind=PublicationKind.WITHDRAW, sequence=1, previous=publication.identity
        )
        self.persistence.persist_publication(publication=withdrawal)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteEffectiveSrtPublicationRepository(reopened)
            self.assertEqual(repo.get(publication.identity), publication)
            self.assertEqual(
                repo.get_current(TranscriptSourceIntakeId(self.intake)), withdrawal
            )
            self.assertEqual(
                repo.history(TranscriptSourceIntakeId(self.intake)),
                (publication, withdrawal),
            )
        finally:
            reopened.close()

    def test_identity_and_sequence_slot_collisions_roll_back(self):
        publication = self._publication()
        self.persistence.persist_publication(publication=publication)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_publication(publication=publication)
        # A divergent record occupying the same (intake, sequence) slot is also refused.
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_publication(
                publication=self._publication(publisher="publisher:evil",
                                              rationale="경쟁 명령")
            )
        self.assertEqual(self._count(), 1)

    def test_invalid_supersession_rejected(self):
        self.persistence.persist_publication(publication=self._publication())
        ghost = derive_publication_identity(
            TranscriptSourceIntakeId(self.intake), PublicationKind.WITHDRAW, None, 7
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_publication(
                publication=self._publication(
                    kind=PublicationKind.WITHDRAW, sequence=1, previous=ghost
                )
            )
        self.assertEqual(self._count(), 1)

    def test_dangling_references_rejected_by_foreign_keys(self):
        ghost_delivery = EffectiveSrtDeliveryId(
            "subtitle-effective-srt-delivery:" + "9" * 64
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_publication(
                publication=self._publication(target=ghost_delivery)
            )
        self.assertEqual(self._count(), 0)

    def test_schema_enforces_kind_target_rule_and_publisher(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO subtitle_effective_srt_publications("
                "identity, transcript_source_intake_id, kind, target_delivery_id, "
                "target_artifact_id, publisher, sequence, content_fingerprint, "
                "previous_publication_id, rationale) "
                "VALUES ('x', ?, 'publish', NULL, NULL, 'p:x', 0, ?, NULL, NULL)",
                (self.intake, "0" * 64),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO subtitle_effective_srt_publications("
                "identity, transcript_source_intake_id, kind, target_delivery_id, "
                "target_artifact_id, publisher, sequence, content_fingerprint, "
                "previous_publication_id, rationale) "
                "VALUES ('x', ?, 'release', NULL, NULL, 'p:x', 0, ?, NULL, NULL)",
                (self.intake, "0" * 64),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO subtitle_effective_srt_publications("
                "identity, transcript_source_intake_id, kind, target_delivery_id, "
                "target_artifact_id, publisher, sequence, content_fingerprint, "
                "previous_publication_id, rationale) "
                "VALUES ('x', ?, 'withdraw', NULL, NULL, '   ', 0, ?, NULL, NULL)",
                (self.intake, "0" * 64),
            )

    def test_repository_rejects_pre_v46_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 46):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 45)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEffectiveSrtPublicationRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
