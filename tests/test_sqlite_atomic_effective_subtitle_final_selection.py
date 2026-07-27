"""Atomic SQLite persistence tests for Effective Subtitle Final Selections (GOAL-016)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_subtitle_final_selection import (
    EffectiveSubtitleFinalSelection,
    derive_final_selection_identity,
    _content_fingerprint,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.application.identities import EffectiveSubtitleReviewSubjectId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteEffectiveSubtitleFinalSelectionCommandPersistence,
    SQLiteEffectiveSubtitleFinalSelectionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError
from lectureos.review.identities import HumanActorReference


class SQLiteAtomicEffectiveSubtitleFinalSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"selection-atomic \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.intake.value,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "하나"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.intake.value, raw.raw_transcript_id.value
        )
        self.candidate = compose_sqlite_effective_subtitle_generation_service(self.connection).generate(
            intake_id=self.intake.value
        ).candidate
        self.subject = compose_sqlite_effective_subtitle_review_preparation_service(
            self.connection
        ).prepare_review(candidate_id=self.candidate.identity.value).subject
        self.decision = compose_sqlite_effective_subtitle_review_decision_service(
            self.connection
        ).decide(
            review_subject_id=self.subject.identity.value, kind="accept",
            reviewer="reviewer:kim",
        ).decision
        self.persistence = SQLiteEffectiveSubtitleFinalSelectionCommandPersistence(self.connection)
        self.repo = SQLiteEffectiveSubtitleFinalSelectionRepository(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _selection(self, sequence=0, previous=None, selector="selector:park"):
        actor = HumanActorReference(selector)
        return EffectiveSubtitleFinalSelection(
            identity=derive_final_selection_identity(
                self.intake, self.candidate.identity, self.subject.identity,
                self.decision.identity, sequence,
            ),
            transcript_source_intake_id=self.intake,
            candidate_id=self.candidate.identity,
            review_subject_id=self.subject.identity,
            supporting_decision_id=self.decision.identity,
            selector=actor,
            sequence=sequence,
            content_fingerprint=_content_fingerprint(
                self.intake, self.candidate.identity, self.subject.identity,
                self.decision.identity, sequence, actor, None,
            ),
            previous_selection_id=previous,
        )

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_final_selections"
        ).fetchone()[0]

    def test_persist_read_current_and_history_after_restart(self):
        s0 = self._selection()
        self.persistence.persist_selection(selection=s0)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteEffectiveSubtitleFinalSelectionRepository(reopened)
            self.assertEqual(repo.get(s0.identity), s0)
            self.assertEqual(repo.get_current(self.intake), s0)
            self.assertEqual(repo.history(self.intake), (s0,))
        finally:
            reopened.close()

    def test_identity_and_sequence_collision_roll_back(self):
        s0 = self._selection()
        self.persistence.persist_selection(selection=s0)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_selection(selection=s0)
        clashing = self._selection(selector="selector:other")  # same identity slot, same seq
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_selection(selection=clashing)
        self.assertEqual(self._count(), 1)

    def test_unknown_previous_supersession_rejected(self):
        s0 = self._selection()
        self.persistence.persist_selection(selection=s0)
        ghost = derive_final_selection_identity(
            self.intake, self.candidate.identity, self.subject.identity,
            self.decision.identity, 7,
        )
        bad = self._selection(sequence=1, previous=ghost)
        with self.assertRaises(PersistenceError):
            self.persistence.persist_selection(selection=bad)
        self.assertEqual(self._count(), 1)

    def test_dangling_subject_rejected_by_foreign_key(self):
        ghost_subject = EffectiveSubtitleReviewSubjectId(
            "subtitle-effective-review-subject:" + "9" * 64
        )
        actor = HumanActorReference("selector:park")
        selection = EffectiveSubtitleFinalSelection(
            identity=derive_final_selection_identity(
                self.intake, self.candidate.identity, ghost_subject,
                self.decision.identity, 0,
            ),
            transcript_source_intake_id=self.intake,
            candidate_id=self.candidate.identity,
            review_subject_id=ghost_subject,
            supporting_decision_id=self.decision.identity,
            selector=actor,
            sequence=0,
            content_fingerprint=_content_fingerprint(
                self.intake, self.candidate.identity, ghost_subject,
                self.decision.identity, 0, actor, None,
            ),
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_selection(selection=selection)
        self.assertEqual(self._count(), 0)

    def test_repository_rejects_pre_v42_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 42):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 41)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEffectiveSubtitleFinalSelectionRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
