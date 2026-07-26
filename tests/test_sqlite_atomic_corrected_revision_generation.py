"""Atomic SQLite persistence tests for Corrected Revision Generation (040 §19)."""

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
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteCorrectedRevisionGenerationRepository,
    SQLiteCorrectedTranscriptRevisionRepository,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import SchemaFeatureUnavailableError
from lectureos.validation import validate_database


def _seed(connection, base: Path):
    """Full healthy chain up to an accepted candidate; returns (candidate_id, raw_id, segment_texts)."""

    source = base / "a.bin"
    source.write_bytes(b"rev-atomic \x00\x01")
    media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
    intake = compose_sqlite_transcript_source_intake_service(connection).admit(
        media.identity.value
    ).intake
    raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
        intake_id=intake.identity.value,
        document=build_provider_transcript_document(
            {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
             "segments": [{"start": 0.0, "end": 2.0, "text": "안녕하세요 여러부"},
                          {"start": 2.0, "end": 4.0, "text": "강의 시작"}]}
        ),
    ).admission
    compose_sqlite_current_raw_transcript_selection_service(connection).select(
        intake.identity.value, raw.raw_transcript_id.value
    )
    raw_record = SQLiteRawTranscriptRepository(connection).get(raw.raw_transcript_id)
    segment = raw_record.segment_ids[0]
    text = SQLiteTranscriptSegmentRepository(connection).get(segment).text
    candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
        intake_id=intake.identity.value,
        candidate=build_correction_candidate_input(
            {"raw_transcript_id": raw.raw_transcript_id.value, "segment_id": segment.value,
             "candidate_ref": "c1", "source_type": "manual", "source_reference": "human",
             "proposed_text": "안녕하세요 여러분", "source_text_snapshot": text, "rationale": "fix"}
        ),
    ).candidate
    compose_sqlite_correction_candidate_decision_service(connection).decide(
        candidate_id=candidate.identity.value, kind="accept", reviewer="r:kim"
    )
    return candidate.identity.value, raw.raw_transcript_id, raw_record


class SQLiteAtomicCorrectedRevisionGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        self.candidate_id, self.raw_id, self.raw_record = _seed(self.connection, self.base)
        self.service = compose_sqlite_corrected_revision_generation_service(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _counts(self):
        return {
            t: self.connection.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in (
                "corrected_revision_generations",
                "corrected_transcript_revisions",
                "corrected_transcript_revision_segments",
                "corrected_transcript_revision_candidates",
                "transcript_segments",
                "domain_result_references",
            )
        }

    def test_persists_all_records_atomically_and_round_trips(self):
        before = self._counts()
        result = self.service.generate(candidate_id=self.candidate_id)
        after = self._counts()
        self.assertEqual(after["corrected_revision_generations"], 1)
        self.assertEqual(after["corrected_transcript_revisions"], 1)
        self.assertEqual(after["corrected_transcript_revision_segments"], 2)
        self.assertEqual(after["corrected_transcript_revision_candidates"], 1)
        self.assertEqual(after["transcript_segments"], before["transcript_segments"] + 1)
        self.assertEqual(after["domain_result_references"], before["domain_result_references"] + 1)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteCorrectedRevisionGenerationRepository(reopened)
            self.assertEqual(repo.get(result.generation.identity), result.generation)
            revision = SQLiteCorrectedTranscriptRevisionRepository(reopened).get(
                result.revision.identity
            )
            self.assertEqual(revision, result.revision)
            segments = SQLiteTranscriptSegmentRepository(reopened)
            self.assertEqual(segments.get(revision.segment_ids[0]).text, "안녕하세요 여러분")
        finally:
            reopened.close()

    def test_replay_after_restart_reuses(self):
        first = self.service.generate(candidate_id=self.candidate_id)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            service = compose_sqlite_corrected_revision_generation_service(reopened)
            again = service.generate(candidate_id=self.candidate_id)
            self.assertEqual(again.outcome, "reused")
            self.assertEqual(again.revision.identity, first.revision.identity)
            self.assertEqual(
                reopened.execute(
                    "SELECT COUNT(*) FROM corrected_transcript_revisions"
                ).fetchone()[0],
                1,
            )
        finally:
            reopened.close()

    def test_raw_transcript_and_candidate_and_decisions_unchanged(self):
        segments = SQLiteTranscriptSegmentRepository(self.connection)
        raw_seg_before = segments.get(self.raw_record.segment_ids[0])
        decisions_before = self.connection.execute(
            "SELECT COUNT(*) FROM correction_candidate_decisions"
        ).fetchone()[0]
        selection_before = self.connection.execute(
            "SELECT COUNT(*) FROM current_raw_transcript_selections"
        ).fetchone()[0]
        self.service.generate(candidate_id=self.candidate_id)
        self.assertEqual(segments.get(self.raw_record.segment_ids[0]), raw_seg_before)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM correction_candidate_decisions"
            ).fetchone()[0],
            decisions_before,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM current_raw_transcript_selections"
            ).fetchone()[0],
            selection_before,
        )

    def test_generation_failure_leaves_no_partial_state(self):
        # Force an FK failure inside the transaction by tampering the admission's segment reference to a
        # value that passes application checks is impossible; instead verify rollback via the persistence
        # layer directly with a conflicting duplicate insert.
        first = self.service.generate(candidate_id=self.candidate_id)
        before = self._counts()
        from lectureos.persistence import (
            SQLiteCorrectedRevisionGenerationCommandPersistence,
        )
        from lectureos.persistence.errors import PersistenceIdentityCollisionError

        persistence = SQLiteCorrectedRevisionGenerationCommandPersistence(self.connection)
        # Re-persisting the identical bundle must collide and roll back without partial rows.
        segments = SQLiteTranscriptSegmentRepository(self.connection)
        replacement = segments.get(first.revision.segment_ids[0])
        from lectureos.execution.models import DomainResultReference

        result_ref = DomainResultReference(
            identity=first.revision.domain_result_id,
            kind="corrected_transcript_revision",
            source_media=self.raw_record.source_media_id,
            source_timeline=self.raw_record.source_timeline_id,
            upstream_results=(self.raw_record.domain_result_id,),
        )
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_corrected_revision_generation(
                generation=first.generation,
                revision=first.revision,
                replacement_segment=replacement,
                result=result_ref,
            )
        self.assertEqual(self._counts(), before)

    def test_repository_validates_healthy_after_generation(self):
        self.service.generate(candidate_id=self.candidate_id)
        self.connection.close()
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")

    def test_repository_rejects_pre_v36_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 36):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 35)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteCorrectedRevisionGenerationRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
