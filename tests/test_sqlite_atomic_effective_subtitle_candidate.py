"""Atomic SQLite persistence tests for Effective-Source Subtitle Candidates (041 §15)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_subtitle_generation import (
    GENERATOR_KIND,
    GENERATOR_VERSION,
    GENERATION_PARAMETERS_VERSION,
    EffectiveSubtitleCandidate,
    build_passthrough_cues,
    derive_effective_candidate_identity,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_transcript_consumption_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteEffectiveSubtitleCandidateCommandPersistence,
    SQLiteEffectiveSubtitleCandidateRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError


class SQLiteAtomicEffectiveSubtitleCandidateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"subtitle-atomic \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "하나"},
                              {"start": 1.0, "end": 2.0, "text": "둘"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.intake, raw.raw_transcript_id.value
        )
        consumed = compose_sqlite_effective_transcript_consumption_service(
            self.connection
        ).consume(intake_id=self.intake, consumer_kind="subtitle_candidate_generation")
        self.binding, self.acquired = consumed.consumption, consumed.input
        self.persistence = SQLiteEffectiveSubtitleCandidateCommandPersistence(self.connection)
        self.repo = SQLiteEffectiveSubtitleCandidateRepository(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _candidate(self, cue_count=2):
        identity = derive_effective_candidate_identity(
            self.binding.transcript_source_intake_id, self.binding.identity,
            self.binding.source_kind, self.binding.source_transcript_identity,
            GENERATOR_KIND, GENERATOR_VERSION, GENERATION_PARAMETERS_VERSION,
        )
        candidate = EffectiveSubtitleCandidate(
            identity=identity,
            transcript_source_intake_id=self.binding.transcript_source_intake_id,
            consumption_binding_id=self.binding.identity,
            source_kind=self.binding.source_kind,
            corrected_revision_id=None,
            parent_raw_transcript_id=self.binding.parent_raw_transcript_id,
            source_snapshot_fingerprint=self.binding.content_fingerprint,
            generator_kind=GENERATOR_KIND,
            generator_version=GENERATOR_VERSION,
            generation_parameters_version=GENERATION_PARAMETERS_VERSION,
            cue_count=cue_count,
        )
        return candidate, build_passthrough_cues(identity, self.acquired)

    def _counts(self):
        return self.connection.execute(
            "SELECT (SELECT COUNT(*) FROM subtitle_effective_candidates), "
            "(SELECT COUNT(*) FROM subtitle_effective_candidate_cues), "
            "(SELECT COUNT(*) FROM subtitle_effective_candidate_cue_segments)"
        ).fetchone()

    def test_persist_and_reconstruct_full_graph_after_restart(self):
        candidate, cues = self._candidate()
        self.persistence.persist_candidate(candidate=candidate, cues=cues)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteEffectiveSubtitleCandidateRepository(reopened)
            self.assertEqual(repo.get(candidate.identity), candidate)
            self.assertEqual(repo.cues(candidate.identity), cues)
            self.assertEqual(
                repo.list_for_intake(candidate.transcript_source_intake_id),
                (candidate,),
            )
        finally:
            reopened.close()

    def test_identity_collision_rolls_back(self):
        candidate, cues = self._candidate()
        self.persistence.persist_candidate(candidate=candidate, cues=cues)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_candidate(candidate=candidate, cues=cues)
        self.assertEqual(self._counts(), (1, 2, 2))

    def test_cue_count_disagreement_rejected_before_writes(self):
        candidate, cues = self._candidate(cue_count=1)
        with self.assertRaises(PersistenceError):
            self.persistence.persist_candidate(candidate=candidate, cues=cues)
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_mid_graph_failure_rolls_back_everything(self):
        # A lineage row referencing a missing transcript segment fails the FK AFTER the candidate
        # and first cue rows were inserted — the whole graph must roll back.
        candidate, cues = self._candidate()
        from lectureos.transcript.identities import TranscriptSegmentId

        broken = list(cues)
        last = broken[-1]
        broken[-1] = type(last)(
            identity=last.identity,
            candidate_id=last.candidate_id,
            ordinal=last.ordinal,
            text=last.text,
            source_segment_ids=last.source_segment_ids,
            start=last.start,
            end=last.end,
        )
        object.__setattr__(broken[-1], "source_segment_ids",
                           (TranscriptSegmentId("transcript-segment:" + "9" * 64 + ":0"),))
        with self.assertRaises(PersistenceError):
            self.persistence.persist_candidate(candidate=candidate, cues=tuple(broken))
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_replay_anchor_uniqueness_rejects_second_identity_for_same_anchor(self):
        candidate, cues = self._candidate()
        self.persistence.persist_candidate(candidate=candidate, cues=cues)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO subtitle_effective_candidates VALUES
                (?, ?, ?, 'raw_transcript', NULL, ?, ?, ?, 1, 1, 2)
                """,
                ("subtitle-effective-candidate:" + "f" * 64,
                 self.intake, self.binding.identity.value,
                 self.binding.parent_raw_transcript_id.value,
                 self.binding.content_fingerprint, GENERATOR_KIND),
            )
        self.assertEqual(self._counts()[0], 1)

    def test_check_constraint_rejects_kind_disagreement(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO subtitle_effective_candidates VALUES
                (?, ?, ?, 'raw_transcript', ?, ?, ?, ?, 1, 1, 2)
                """,
                ("subtitle-effective-candidate:" + "e" * 64,
                 self.intake, self.binding.identity.value,
                 "corrected-revision:" + "0" * 64,
                 self.binding.parent_raw_transcript_id.value,
                 self.binding.content_fingerprint, GENERATOR_KIND),
            )

    def test_repository_rejects_pre_v39_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 39):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 38)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteEffectiveSubtitleCandidateRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
