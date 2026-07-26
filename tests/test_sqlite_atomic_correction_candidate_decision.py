"""Atomic SQLite persistence tests for Correction Candidate Human Decisions (040 §18)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.correction_candidate_decision import (
    CorrectionCandidateDecision,
    derive_decision_identity,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteCorrectionCandidateDecisionCommandPersistence,
    SQLiteCorrectionCandidateDecisionRepository,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError
from lectureos.review.identities import HumanActorReference
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import CorrectionCandidateId


class SQLiteAtomicCorrectionCandidateDecisionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"decide-atomic \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=intake.identity.value,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            intake.identity.value, raw.raw_transcript_id.value
        )
        raw_record = SQLiteRawTranscriptRepository(self.connection).get(raw.raw_transcript_id)
        segment = raw_record.segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(self.connection).get(segment).text
        self.candidate = compose_sqlite_correction_candidate_admission_service(self.connection).admit(
            intake_id=intake.identity.value,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw.raw_transcript_id.value, "segment_id": segment.value,
                 "candidate_ref": "c1", "source_type": "manual", "source_reference": "human",
                 "proposed_text": "교정", "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate.identity
        self.persistence = SQLiteCorrectionCandidateDecisionCommandPersistence(self.connection)
        self.repo = SQLiteCorrectionCandidateDecisionRepository(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _decision(self, kind, sequence, previous=None, reviewer="r:kim"):
        return CorrectionCandidateDecision(
            identity=derive_decision_identity(self.candidate, kind, sequence),
            correction_candidate_id=self.candidate,
            kind=kind,
            reviewer=HumanActorReference(reviewer),
            sequence=sequence,
            content_fingerprint="0" * 64,
            previous_decision_id=previous,
            rationale=None,
        )

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM correction_candidate_decisions"
        ).fetchone()[0]

    def test_persist_and_read_current(self):
        d0 = self._decision(DecisionKind.ACCEPT, 0)
        self.persistence.persist_decision(decision=d0)
        self.assertTrue(self.repo.is_admitted_candidate(self.candidate))
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteCorrectionCandidateDecisionRepository(reopened)
            self.assertEqual(repo.get(d0.identity), d0)
            self.assertEqual(repo.get_current(self.candidate), d0)
            self.assertEqual(len(repo.history(self.candidate)), 1)
        finally:
            reopened.close()

    def test_append_advances_current_and_preserves_history(self):
        d0 = self._decision(DecisionKind.ACCEPT, 0)
        self.persistence.persist_decision(decision=d0)
        d1 = self._decision(DecisionKind.REJECT, 1, previous=d0.identity)
        self.persistence.persist_decision(decision=d1)
        self.assertEqual(self.repo.get_current(self.candidate).kind, DecisionKind.REJECT)
        self.assertEqual([d.kind for d in self.repo.history(self.candidate)],
                         [DecisionKind.ACCEPT, DecisionKind.REJECT])
        self.assertEqual(self._count(), 2)  # append-only

    def test_history_reconstruction_after_restart(self):
        d0 = self._decision(DecisionKind.ACCEPT, 0)
        self.persistence.persist_decision(decision=d0)
        self.persistence.persist_decision(decision=self._decision(DecisionKind.REJECT, 1, previous=d0.identity))
        self.connection.close()
        # Reopen from persisted state only — current authority must reconstruct identically.
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteCorrectionCandidateDecisionRepository(reopened)
            self.assertEqual(repo.get_current(self.candidate).kind, DecisionKind.REJECT)
            self.assertEqual(len(repo.history(self.candidate)), 2)
        finally:
            reopened.close()

    def test_identity_collision_rolls_back(self):
        d0 = self._decision(DecisionKind.ACCEPT, 0)
        self.persistence.persist_decision(decision=d0)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_decision(decision=d0)
        self.assertEqual(self._count(), 1)

    def test_sequence_collision_rolls_back(self):
        self.persistence.persist_decision(decision=self._decision(DecisionKind.ACCEPT, 0))
        # A different kind at the same (candidate, sequence) violates UNIQUE(candidate, sequence).
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_decision(decision=self._decision(DecisionKind.REJECT, 0))
        self.assertEqual(self._count(), 1)

    def test_unknown_previous_supersession_rejected(self):
        d0 = self._decision(DecisionKind.ACCEPT, 0)
        self.persistence.persist_decision(decision=d0)
        ghost = derive_decision_identity(self.candidate, DecisionKind.REJECT, 7)
        bad = self._decision(DecisionKind.REJECT, 1, previous=ghost)
        with self.assertRaises(PersistenceError):
            self.persistence.persist_decision(decision=bad)
        self.assertEqual(self._count(), 1)

    def test_dangling_candidate_rejected_by_foreign_key(self):
        ghost = CorrectionCandidateId("correction-candidate:" + "0" * 64)
        decision = CorrectionCandidateDecision(
            identity=derive_decision_identity(ghost, DecisionKind.ACCEPT, 0),
            correction_candidate_id=ghost, kind=DecisionKind.ACCEPT,
            reviewer=HumanActorReference("r"), sequence=0, content_fingerprint="0" * 64,
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_decision(decision=decision)
        self.assertEqual(self._count(), 0)

    def test_repository_rejects_pre_v35_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 35):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 34)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteCorrectionCandidateDecisionRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
