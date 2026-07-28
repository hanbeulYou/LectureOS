"""Atomic SQLite persistence tests for Lecture Analysis Input Admissions (GOAL-023)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
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
    compose_sqlite_lecture_analysis_input_admission_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteLectureAnalysisInputAdmissionCommandPersistence,
    SQLiteLectureAnalysisInputAdmissionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository


class SQLiteAtomicLectureAnalysisInputAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"admission-atomic \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.intake, raw.raw_transcript_id.value
        )
        segment_id = SQLiteRawTranscriptRepository(self.connection).get(
            raw.raw_transcript_id
        ).segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(self.connection).get(segment_id).text
        candidate = compose_sqlite_correction_candidate_admission_service(
            self.connection
        ).admit(
            intake_id=self.intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw.raw_transcript_id.value,
                 "segment_id": segment_id.value, "candidate_ref": "c1",
                 "source_type": "manual", "source_reference": "human",
                 "proposed_text": "교정", "source_text_snapshot": text,
                 "rationale": "fix"}
            ),
        ).candidate.identity.value
        compose_sqlite_correction_candidate_decision_service(self.connection).decide(
            candidate_id=candidate, kind="accept", reviewer="r:kim"
        )
        revision = compose_sqlite_corrected_revision_generation_service(
            self.connection
        ).generate(candidate_id=candidate).revision.identity.value
        compose_sqlite_corrected_revision_selection_service(self.connection).select_revision(
            revision_id=revision, reviewer="s:kim"
        )
        self.admission = compose_sqlite_lecture_analysis_input_admission_service(
            self.connection
        ).admit(intake_id=self.intake).admission
        self.persistence = SQLiteLectureAnalysisInputAdmissionCommandPersistence(
            self.connection
        )

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def test_reconstruct_after_restart(self):
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteLectureAnalysisInputAdmissionRepository(reopened)
            self.assertEqual(repo.get(self.admission.identity), self.admission)
        finally:
            reopened.close()
            self.connection = open_sqlite_database(self.database)

    def test_identity_collision_rolls_back(self):
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_admission(admission=self.admission)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_analysis_input_admissions"
            ).fetchone()[0],
            1,
        )

    def test_dangling_lineage_rejected_by_foreign_keys(self):
        import dataclasses

        from lectureos.application.lecture_analysis_input_admission import (
            derive_admission_identity,
        )
        from lectureos.transcript.identities import TranscriptRevisionId

        ghost_revision = TranscriptRevisionId("corrected-revision:" + "9" * 64)
        ghost = dataclasses.replace(
            self.admission,
            identity=derive_admission_identity(
                self.admission.transcript_source_intake_id, ghost_revision
            ),
            corrected_revision_id=ghost_revision,
        )
        with self.assertRaises(PersistenceError):
            self.persistence.persist_admission(admission=ghost)

    def test_schema_enforces_snapshot_constraints(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE lecture_analysis_input_admissions SET segment_count = 0"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE lecture_analysis_input_admissions SET content_fingerprint = 'short'"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE lecture_analysis_input_admissions "
                "SET admission_contract_version = 2"
            )

    def test_repository_rejects_pre_v47_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 47):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 46)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteLectureAnalysisInputAdmissionRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
