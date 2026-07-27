"""Atomic SQLite persistence tests for Effective Subtitle Review Decisions (GOAL-015)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_subtitle_review_decision import (
    EffectiveSubtitleReviewDecision,
    derive_decision_identity,
    _content_fingerprint,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.application.identities import EffectiveSubtitleReviewSubjectId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteEffectiveSubtitleReviewDecisionCommandPersistence,
    SQLiteEffectiveSubtitleReviewDecisionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError
from lectureos.review.identities import HumanActorReference
from lectureos.review.models import DecisionKind


class SQLiteAtomicEffectiveSubtitleReviewDecisionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"decision-atomic \x00\x01")
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
        self.subject = compose_sqlite_effective_subtitle_review_preparation_service(
            self.connection
        ).prepare_review(candidate_id=candidate.identity.value).subject
        self.persistence = SQLiteEffectiveSubtitleReviewDecisionCommandPersistence(self.connection)
        self.repo = SQLiteEffectiveSubtitleReviewDecisionRepository(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _decision(self, kind, sequence=0, previous=None, reviewer="reviewer:kim"):
        actor = HumanActorReference(reviewer)
        return EffectiveSubtitleReviewDecision(
            identity=derive_decision_identity(self.subject.identity, kind, sequence),
            review_subject_id=self.subject.identity,
            kind=kind,
            reviewer=actor,
            sequence=sequence,
            content_fingerprint=_content_fingerprint(
                self.subject.identity, kind, sequence, actor, None
            ),
            previous_decision_id=previous,
        )

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_review_decisions"
        ).fetchone()[0]

    def test_persist_read_current_and_history_after_restart(self):
        d0 = self._decision(DecisionKind.REJECT)
        self.persistence.persist_decision(decision=d0)
        d1 = self._decision(DecisionKind.ACCEPT, sequence=1, previous=d0.identity)
        self.persistence.persist_decision(decision=d1)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteEffectiveSubtitleReviewDecisionRepository(reopened)
            self.assertEqual(repo.get(d0.identity), d0)
            self.assertEqual(repo.get_current(self.subject.identity), d1)
            self.assertEqual(
                [d.kind for d in repo.history(self.subject.identity)],
                [DecisionKind.REJECT, DecisionKind.ACCEPT],
            )
        finally:
            reopened.close()

    def test_identity_collision_rolls_back(self):
        d0 = self._decision(DecisionKind.ACCEPT)
        self.persistence.persist_decision(decision=d0)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_decision(decision=d0)
        self.assertEqual(self._count(), 1)

    def test_sequence_collision_rolls_back(self):
        self.persistence.persist_decision(decision=self._decision(DecisionKind.ACCEPT))
        clashing = self._decision(DecisionKind.REJECT)  # also sequence 0
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_decision(decision=clashing)
        self.assertEqual(self._count(), 1)

    def test_unknown_previous_supersession_rejected(self):
        self.persistence.persist_decision(decision=self._decision(DecisionKind.ACCEPT))
        ghost = derive_decision_identity(self.subject.identity, DecisionKind.MODIFY, 7)
        bad = self._decision(DecisionKind.REJECT, sequence=1, previous=ghost)
        with self.assertRaises(PersistenceError):
            self.persistence.persist_decision(decision=bad)
        self.assertEqual(self._count(), 1)

    def test_dangling_subject_rejected_by_foreign_key(self):
        ghost_subject = EffectiveSubtitleReviewSubjectId(
            "subtitle-effective-review-subject:" + "9" * 64
        )
        actor = HumanActorReference("reviewer:kim")
        decision = EffectiveSubtitleReviewDecision(
            identity=derive_decision_identity(ghost_subject, DecisionKind.ACCEPT, 0),
            review_subject_id=ghost_subject,
            kind=DecisionKind.ACCEPT,
            reviewer=actor,
            sequence=0,
            content_fingerprint=_content_fingerprint(
                ghost_subject, DecisionKind.ACCEPT, 0, actor, None
            ),
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_decision(decision=decision)
        self.assertEqual(self._count(), 0)

    def test_repository_rejects_pre_v41_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 41):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 40)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEffectiveSubtitleReviewDecisionRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
