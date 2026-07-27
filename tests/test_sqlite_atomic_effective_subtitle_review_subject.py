"""Atomic SQLite persistence tests for Effective-Source Subtitle Review Subjects (GOAL-014)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_subtitle_review_preparation import (
    EffectiveSubtitleReviewSubject,
    PREPARATION_KIND,
    PREPARATION_VERSION,
    derive_candidate_graph_fingerprint,
    derive_preparation_key,
    derive_review_subject_identity,
)
from lectureos.application.identities import EffectiveSubtitleCandidateId
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteEffectiveSubtitleReviewSubjectCommandPersistence,
    SQLiteEffectiveSubtitleReviewSubjectRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError


class SQLiteAtomicEffectiveSubtitleReviewSubjectTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"review-atomic \x00\x01")
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
        generation = compose_sqlite_effective_subtitle_generation_service(self.connection)
        result = generation.generate(intake_id=intake)
        self.candidate = result.candidate
        self.fingerprint = derive_candidate_graph_fingerprint(result.candidate, result.cues)
        self.persistence = SQLiteEffectiveSubtitleReviewSubjectCommandPersistence(self.connection)
        self.repo = SQLiteEffectiveSubtitleReviewSubjectRepository(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _subject(self):
        return EffectiveSubtitleReviewSubject(
            identity=derive_review_subject_identity(self.candidate.identity, self.fingerprint),
            candidate_id=self.candidate.identity,
            candidate_graph_fingerprint=self.fingerprint,
            preparation_kind=PREPARATION_KIND,
            preparation_version=PREPARATION_VERSION,
            preparation_key=derive_preparation_key(self.candidate.identity),
        )

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_review_subjects"
        ).fetchone()[0]

    def test_persist_and_reconstruct_after_restart(self):
        subject = self._subject()
        self.persistence.persist_review_subject(subject=subject)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteEffectiveSubtitleReviewSubjectRepository(reopened)
            self.assertEqual(repo.get(subject.identity), subject)
            self.assertEqual(repo.get_for_candidate(subject.candidate_id), subject)
        finally:
            reopened.close()

    def test_identity_collision_rolls_back(self):
        subject = self._subject()
        self.persistence.persist_review_subject(subject=subject)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_review_subject(subject=subject)
        self.assertEqual(self._count(), 1)

    def test_dangling_candidate_rejected_by_foreign_key(self):
        ghost = EffectiveSubtitleCandidateId("subtitle-effective-candidate:" + "9" * 64)
        subject = EffectiveSubtitleReviewSubject(
            identity=derive_review_subject_identity(ghost, self.fingerprint),
            candidate_id=ghost,
            candidate_graph_fingerprint=self.fingerprint,
            preparation_kind=PREPARATION_KIND,
            preparation_version=PREPARATION_VERSION,
            preparation_key=derive_preparation_key(ghost),
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_review_subject(subject=subject)
        self.assertEqual(self._count(), 0)

    def test_replay_anchor_uniqueness_rejects_second_identity_for_same_anchor(self):
        self.persistence.persist_review_subject(subject=self._subject())
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO subtitle_effective_review_subjects VALUES (?, ?, ?, ?, 1, ?)
                """,
                ("subtitle-effective-review-subject:" + "f" * 64,
                 self.candidate.identity.value, "f" * 64, PREPARATION_KIND,
                 derive_preparation_key(self.candidate.identity)),
            )
        self.assertEqual(self._count(), 1)

    def test_repository_rejects_pre_v40_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 40):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 39)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEffectiveSubtitleReviewSubjectRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
