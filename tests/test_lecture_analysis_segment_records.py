"""Persistence, atomicity, and storage-constraint tests for effective-generation Lecture
Segments (042 §7.2 / PATCH-0031, GOAL-026)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.identities import (
    LectureAnalysisInputAdmissionId,
    LectureAnalysisSegmentId,
)
from lectureos.application.lecture_analysis_segment import (
    LectureAnalysisSegment,
    derive_segment_identity,
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
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.persistence.lecture_analysis_segment import (
    SQLiteLectureAnalysisSegmentCommandPersistence,
    SQLiteLectureAnalysisSegmentRepository,
)

def _segment(
    admission: LectureAnalysisInputAdmissionId, sequence: int = 0,
    start: float = 0.0, end: float = 1.0,
) -> LectureAnalysisSegment:
    return LectureAnalysisSegment(
        identity=derive_segment_identity(admission, sequence, start, end),
        admission_id=admission,
        sequence=sequence,
        range_start=start,
        range_end=end,
    )


class SegmentPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        # A real anchor from the released upstream chain: a fabricated admission row would
        # leave dangling foreign keys and make the repository itself unopenable.
        self.admission = self._admit_analysis_input()
        self.repository = SQLiteLectureAnalysisSegmentRepository(self.connection)
        self.persistence = SQLiteLectureAnalysisSegmentCommandPersistence(self.connection)

    def _admit_analysis_input(self) -> LectureAnalysisInputAdmissionId:
        source = Path(self.tempdir.name) / "a.bin"
        source.write_bytes(b"segments \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(
            str(source)
        ).record
        intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            intake, raw.raw_transcript_id.value
        )
        segment_id = SQLiteRawTranscriptRepository(self.connection).get(
            raw.raw_transcript_id
        ).segment_ids[0]
        source_text = SQLiteTranscriptSegmentRepository(self.connection).get(segment_id).text
        candidate = compose_sqlite_correction_candidate_admission_service(
            self.connection
        ).admit(
            intake_id=intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw.raw_transcript_id.value,
                 "segment_id": segment_id.value, "candidate_ref": "c1",
                 "source_type": "manual", "source_reference": "human",
                 "proposed_text": "교정", "source_text_snapshot": source_text,
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
        return compose_sqlite_lecture_analysis_input_admission_service(
            self.connection
        ).admit(intake_id=intake).admission.identity

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM lecture_analysis_segments"
        ).fetchone()[0]

    def test_round_trips_every_field(self):
        segment = _segment(self.admission, sequence=2, start=1.5, end=2.5)
        self.persistence.persist_segments(segments=(segment,))
        self.assertEqual(self.repository.get(segment.identity), segment)

    def test_batch_persists_atomically(self):
        batch = tuple(
            _segment(self.admission, sequence=i, start=float(i), end=float(i) + 1.0)
            for i in range(4)
        )
        self.persistence.persist_segments(segments=batch)
        self.assertEqual(self._count(), 4)

    def test_unknown_identity_reads_none(self):
        self.assertIsNone(
            self.repository.get(
                LectureAnalysisSegmentId("lecture-analysis-segment:" + "0" * 64)
            )
        )

    def test_list_is_ordered_by_sequence_then_identity(self):
        batch = (
            _segment(self.admission, sequence=1, start=1.0, end=2.0),
            _segment(self.admission, sequence=0, start=0.0, end=1.0),
            _segment(self.admission, sequence=0, start=5.0, end=6.0),
        )
        self.persistence.persist_segments(segments=batch)
        listed = self.repository.list_for_admission(self.admission)
        self.assertEqual([s.sequence for s in listed], [0, 0, 1])
        first_two = [s.identity.value for s in listed[:2]]
        self.assertEqual(first_two, sorted(first_two))

    def test_duplicate_identity_collides_leaving_prior_rows(self):
        from lectureos.persistence.errors import PersistenceIdentityCollisionError

        segment = _segment(self.admission)
        self.persistence.persist_segments(segments=(segment,))
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_segments(segments=(segment,))
        self.assertEqual(self._count(), 1)

    def test_one_colliding_member_rolls_back_the_whole_batch(self):
        from lectureos.persistence.errors import PersistenceIdentityCollisionError

        existing = _segment(self.admission, sequence=0, start=0.0, end=1.0)
        self.persistence.persist_segments(segments=(existing,))
        batch = (
            _segment(self.admission, sequence=1, start=1.0, end=2.0),
            existing,
            _segment(self.admission, sequence=2, start=2.0, end=3.0),
        )
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_segments(segments=batch)
        self.assertEqual(self._count(), 1)
        self.assertFalse(self.connection.in_transaction)

    def test_missing_anchor_rolls_back_leaving_no_partial_row(self):
        from lectureos.persistence.errors import PersistenceIdentityCollisionError

        orphan = LectureAnalysisInputAdmissionId("lecture-analysis-input:" + "9" * 64)
        batch = (
            _segment(self.admission, sequence=0, start=0.0, end=1.0),
            _segment(orphan, sequence=1, start=1.0, end=2.0),
        )
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_segments(segments=batch)
        self.assertEqual(self._count(), 0)
        self.assertFalse(self.connection.in_transaction)

    def test_empty_batch_is_refused(self):
        from lectureos.persistence.errors import PersistenceError

        with self.assertRaises(PersistenceError):
            self.persistence.persist_segments(segments=())
        self.assertEqual(self._count(), 0)

    def test_storage_rejects_invalid_rows(self):
        cases = (
            ("negative sequence", (-1, 0.0, 1.0, 1)),
            ("negative start", (0, -1.0, 1.0, 1)),
            ("negative end", (0, 0.0, -1.0, 1)),
            ("inverted range", (0, 2.0, 1.0, 1)),
            ("bad contract version", (0, 0.0, 1.0, 2)),
        )
        for label, (sequence, start, end, version) in cases:
            with self.subTest(case=label):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        "INSERT INTO lecture_analysis_segments VALUES (?, ?, ?, ?, ?, ?)",
                        ("lecture-analysis-segment:" + "1" * 64,
                         self.admission.value, sequence, start, end, version),
                    )
        self.assertEqual(self._count(), 0)

    def test_no_uniqueness_constraint_over_admission_and_sequence(self):
        # 042 §7.1 forbids canonical-set/uniqueness constraints, so independent batches may share
        # a sequence. A UNIQUE(admission_id, sequence) index would violate the contract.
        self.persistence.persist_segments(
            segments=(_segment(self.admission, sequence=0, start=0.0, end=1.0),)
        )
        self.persistence.persist_segments(
            segments=(_segment(self.admission, sequence=0, start=5.0, end=6.0),)
        )
        self.assertEqual(self._count(), 2)
        indexes = self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' "
            "AND tbl_name = 'lecture_analysis_segments'"
        ).fetchall()
        for (sql,) in indexes:
            if sql:
                self.assertNotIn("sequence", sql)

    def test_persistence_requires_v49_schema(self):
        from lectureos.persistence.errors import SchemaFeatureUnavailableError
        from lectureos.persistence import sqlite as lifecycle

        legacy = Path(self.tempdir.name) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 49):
            statements += getattr(lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 48)")
        connection.execute("COMMIT")
        connection.close()

        opened = open_sqlite_database(legacy)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteLectureAnalysisSegmentRepository(opened)
        finally:
            opened.close()

    def test_repository_never_exposes_mutation(self):
        for forbidden in ("update", "delete", "remove", "upsert", "save"):
            self.assertFalse(hasattr(self.repository, forbidden))
            self.assertFalse(hasattr(self.persistence, forbidden))


if __name__ == "__main__":
    unittest.main()
