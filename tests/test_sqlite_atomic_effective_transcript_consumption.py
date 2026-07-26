"""Atomic SQLite persistence tests for Effective Transcript Consumption (040 §21)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.corrected_revision_selection import SelectionState
from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.effective_transcript_consumption import (
    ConsumedSourceKind,
    EffectiveTranscriptConsumption,
    MANIFEST_CONSUMER_KIND,
    derive_consumption_identity,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteEffectiveTranscriptConsumptionCommandPersistence,
    SQLiteEffectiveTranscriptConsumptionRepository,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId


class SQLiteAtomicEffectiveTranscriptConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"consumption-atomic \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.intake.value,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        self.raw_id = raw.raw_transcript_id
        self.raw_selection = compose_sqlite_current_raw_transcript_selection_service(
            self.connection
        ).select(self.intake.value, self.raw_id.value).selection
        raw_record = SQLiteRawTranscriptRepository(self.connection).get(self.raw_id)
        segment = raw_record.segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(self.connection).get(segment).text
        candidate = compose_sqlite_correction_candidate_admission_service(self.connection).admit(
            intake_id=self.intake.value,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": self.raw_id.value, "segment_id": segment.value,
                 "candidate_ref": "c1", "source_type": "manual", "source_reference": "human",
                 "proposed_text": "교정", "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate
        compose_sqlite_correction_candidate_decision_service(self.connection).decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="r:kim"
        )
        self.revision = compose_sqlite_corrected_revision_generation_service(self.connection).generate(
            candidate_id=candidate.identity.value
        ).revision.identity
        self.corrected_selection = compose_sqlite_corrected_revision_selection_service(
            self.connection
        ).select_revision(revision_id=self.revision.value, reviewer="s:kim").selection
        self.persistence = SQLiteEffectiveTranscriptConsumptionCommandPersistence(self.connection)
        self.repo = SQLiteEffectiveTranscriptConsumptionRepository(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _raw_consumption(self, fingerprint="0" * 64):
        return EffectiveTranscriptConsumption(
            identity=derive_consumption_identity(
                MANIFEST_CONSUMER_KIND, self.intake,
                ConsumedSourceKind.RAW_TRANSCRIPT, self.raw_id.value,
            ),
            consumer_kind=MANIFEST_CONSUMER_KIND,
            transcript_source_intake_id=self.intake,
            resolution_state=SelectionState.NO_HISTORY,
            source_kind=ConsumedSourceKind.RAW_TRANSCRIPT,
            parent_raw_transcript_id=self.raw_id,
            corrected_revision_id=None,
            raw_selection_id=self.raw_selection.identity,
            corrected_selection_id=None,
            content_fingerprint=fingerprint,
            segment_count=1,
        )

    def _corrected_consumption(self):
        return EffectiveTranscriptConsumption(
            identity=derive_consumption_identity(
                MANIFEST_CONSUMER_KIND, self.intake,
                ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION, self.revision.value,
            ),
            consumer_kind=MANIFEST_CONSUMER_KIND,
            transcript_source_intake_id=self.intake,
            resolution_state=SelectionState.CORRECTED_SELECTED,
            source_kind=ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION,
            parent_raw_transcript_id=self.raw_id,
            corrected_revision_id=self.revision,
            raw_selection_id=self.raw_selection.identity,
            corrected_selection_id=self.corrected_selection.identity,
            content_fingerprint="1" * 64,
            segment_count=1,
        )

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM effective_transcript_consumptions"
        ).fetchone()[0]

    def test_persist_and_reconstruct_after_restart(self):
        raw_binding = self._raw_consumption()
        corrected_binding = self._corrected_consumption()
        self.persistence.persist_consumption(consumption=raw_binding)
        self.persistence.persist_consumption(consumption=corrected_binding)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteEffectiveTranscriptConsumptionRepository(reopened)
            self.assertEqual(repo.get(raw_binding.identity), raw_binding)
            self.assertEqual(repo.get(corrected_binding.identity), corrected_binding)
            self.assertEqual(len(repo.list_for_intake(self.intake)), 2)
        finally:
            reopened.close()

    def test_identity_collision_rolls_back(self):
        binding = self._raw_consumption()
        self.persistence.persist_consumption(consumption=binding)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_consumption(consumption=binding)
        self.assertEqual(self._count(), 1)

    def test_dangling_raw_source_rejected_by_foreign_key(self):
        ghost_raw = TranscriptId("raw-transcript:" + "9" * 64)
        binding = EffectiveTranscriptConsumption(
            identity=derive_consumption_identity(
                MANIFEST_CONSUMER_KIND, self.intake,
                ConsumedSourceKind.RAW_TRANSCRIPT, ghost_raw.value,
            ),
            consumer_kind=MANIFEST_CONSUMER_KIND,
            transcript_source_intake_id=self.intake,
            resolution_state=SelectionState.NO_HISTORY,
            source_kind=ConsumedSourceKind.RAW_TRANSCRIPT,
            parent_raw_transcript_id=ghost_raw,
            corrected_revision_id=None,
            raw_selection_id=self.raw_selection.identity,
            corrected_selection_id=None,
            content_fingerprint="0" * 64,
            segment_count=1,
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_consumption(consumption=binding)
        self.assertEqual(self._count(), 0)

    def test_dangling_revision_source_rejected_by_foreign_key(self):
        ghost = TranscriptRevisionId("corrected-revision:" + "9" * 64)
        binding = EffectiveTranscriptConsumption(
            identity=derive_consumption_identity(
                MANIFEST_CONSUMER_KIND, self.intake,
                ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION, ghost.value,
            ),
            consumer_kind=MANIFEST_CONSUMER_KIND,
            transcript_source_intake_id=self.intake,
            resolution_state=SelectionState.CORRECTED_SELECTED,
            source_kind=ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION,
            parent_raw_transcript_id=self.raw_id,
            corrected_revision_id=ghost,
            raw_selection_id=self.raw_selection.identity,
            corrected_selection_id=self.corrected_selection.identity,
            content_fingerprint="1" * 64,
            segment_count=1,
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_consumption(consumption=binding)
        self.assertEqual(self._count(), 0)

    def test_replay_anchor_uniqueness_rejects_second_identity_for_same_source(self):
        self.persistence.persist_consumption(consumption=self._raw_consumption())
        # A tampered row claiming the same (consumer, intake, source) anchor under a different
        # identity must hit the UNIQUE replay anchor and roll back.
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO effective_transcript_consumptions VALUES
                (?, ?, ?, 'no_history', 'raw_transcript', ?, ?, NULL, ?, NULL, ?, 1)
                """,
                ("transcript-consumption:" + "f" * 64, MANIFEST_CONSUMER_KIND,
                 self.intake.value, self.raw_id.value, self.raw_id.value,
                 self.raw_selection.identity.value, "0" * 64),
            )
        self.assertEqual(self._count(), 1)

    def test_check_constraint_rejects_kind_state_disagreement(self):
        # kind raw_transcript with a corrected revision attached must be impossible at the
        # schema level even if application validation were bypassed.
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO effective_transcript_consumptions VALUES
                (?, ?, ?, 'no_history', 'raw_transcript', ?, ?, ?, ?, NULL, ?, 1)
                """,
                ("transcript-consumption:" + "e" * 64, MANIFEST_CONSUMER_KIND,
                 self.intake.value, self.raw_id.value, self.raw_id.value,
                 self.revision.value, self.raw_selection.identity.value, "0" * 64),
            )

    def test_repository_rejects_pre_v38_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 38):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 37)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEffectiveTranscriptConsumptionRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
