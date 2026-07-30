"""Persistence, atomicity, and storage-constraint tests for effective-generation Edit
Candidates (042 §9.3 / PATCH-0032, GOAL-027)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.identities import (
    LectureAnalysisEditCandidateId,
    LectureAnalysisFindingId,
)
from lectureos.application.lecture_analysis_edit_candidate import (
    LectureAnalysisEditCandidate,
    derive_candidate_identity,
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
    compose_sqlite_lecture_analysis_finding_service,
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
from lectureos.persistence.lecture_analysis_edit_candidate import (
    SQLiteLectureAnalysisEditCandidateCommandPersistence,
    SQLiteLectureAnalysisEditCandidateRepository,
)

_RATIONALE = "이 구간은 사람이 검토할 만하다"


def _candidate(
    finding: LectureAnalysisFindingId, ctype: str = "non_lecture_region",
    start: float = 0.0, end: float = 1.0, rationale: str = _RATIONALE,
) -> LectureAnalysisEditCandidate:
    return LectureAnalysisEditCandidate(
        identity=derive_candidate_identity(finding, ctype, start, end, rationale),
        finding_id=finding,
        candidate_type=ctype,
        range_start=start,
        range_end=end,
        rationale=rationale,
    )


class EditCandidatePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        # A real Finding anchor from the released chain: a fabricated row would leave dangling
        # foreign keys and make the repository itself unopenable.
        self.finding = self._admit_finding()
        self.repository = SQLiteLectureAnalysisEditCandidateRepository(self.connection)
        self.persistence = SQLiteLectureAnalysisEditCandidateCommandPersistence(self.connection)

    def _admit_finding(self) -> LectureAnalysisFindingId:
        source = Path(self.tempdir.name) / "a.bin"
        source.write_bytes(b"candidate-records \x00\x01")
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
        admission = compose_sqlite_lecture_analysis_input_admission_service(
            self.connection
        ).admit(intake_id=intake).admission
        return compose_sqlite_lecture_analysis_finding_service(self.connection).admit(
            admission_id=admission.identity.value,
            finding_type="non_lecture_speech",
            evidence="관찰",
        ).finding.identity

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM lecture_analysis_edit_candidates"
        ).fetchone()[0]

    def test_round_trips_every_field(self):
        candidate = _candidate(self.finding, "delivery_concern", 1.5, 2.5, "긴 이유 텍스트")
        self.persistence.persist_candidate(candidate=candidate)
        self.assertEqual(self.repository.get(candidate.identity), candidate)

    def test_rationale_round_trips_verbatim(self):
        rationale = "  앞뒤 공백과   내부 공백을 보존한다  "
        candidate = _candidate(self.finding, rationale=rationale)
        self.persistence.persist_candidate(candidate=candidate)
        self.assertEqual(self.repository.get(candidate.identity).rationale, rationale)

    def test_unknown_identity_reads_none(self):
        self.assertIsNone(
            self.repository.get(
                LectureAnalysisEditCandidateId(
                    "lecture-analysis-edit-candidate:" + "0" * 64
                )
            )
        )

    def test_list_for_finding_is_deterministically_ordered(self):
        candidates = [
            _candidate(self.finding, rationale=f"이유 {index}") for index in range(4)
        ]
        for candidate in candidates:
            self.persistence.persist_candidate(candidate=candidate)
        listed = self.repository.list_for_finding(self.finding)
        self.assertEqual(
            [c.identity.value for c in listed],
            sorted(c.identity.value for c in candidates),
        )

    def test_duplicate_identity_collides_leaving_one_row(self):
        from lectureos.persistence.errors import PersistenceIdentityCollisionError

        candidate = _candidate(self.finding)
        self.persistence.persist_candidate(candidate=candidate)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_candidate(candidate=candidate)
        self.assertEqual(self._count(), 1)

    def test_missing_anchor_rolls_back_leaving_no_row(self):
        from lectureos.persistence.errors import PersistenceIdentityCollisionError

        orphan = LectureAnalysisFindingId("lecture-analysis-finding:" + "9" * 64)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_candidate(candidate=_candidate(orphan))
        self.assertEqual(self._count(), 0)
        self.assertFalse(self.connection.in_transaction)

    def test_storage_rejects_invalid_rows(self):
        cases = (
            ("empty type", ("", 0.0, 1.0, "r", 1)),
            ("empty rationale", ("t", 0.0, 1.0, "   ", 1)),
            ("negative start", ("t", -1.0, 1.0, "r", 1)),
            ("negative end", ("t", 0.0, -1.0, "r", 1)),
            ("inverted range", ("t", 2.0, 1.0, "r", 1)),
            ("bad contract version", ("t", 0.0, 1.0, "r", 2)),
        )
        for label, (ctype, start, end, rationale, version) in cases:
            with self.subTest(case=label):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        "INSERT INTO lecture_analysis_edit_candidates "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        ("lecture-analysis-edit-candidate:" + "1" * 64,
                         self.finding.value, ctype, start, end, rationale, version),
                    )
        self.assertEqual(self._count(), 0)

    def test_no_ordinal_column_exists(self):
        # O-1: 042 §9.2 fixes candidate order as carrying no product meaning, so no canonical
        # ordinal is stored and nothing may imply one.
        columns = [
            row[1] for row in self.connection.execute(
                "PRAGMA table_info(lecture_analysis_edit_candidates)"
            )
        ]
        for forbidden in ("sequence", "ordinal", "position", "order_index"):
            self.assertNotIn(forbidden, columns)

    def test_persistence_requires_v50_schema(self):
        from lectureos.persistence.errors import SchemaFeatureUnavailableError
        from lectureos.persistence import sqlite as lifecycle

        legacy = Path(self.tempdir.name) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 50):
            statements += getattr(lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 49)")
        connection.execute("COMMIT")
        connection.close()

        opened = open_sqlite_database(legacy)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteLectureAnalysisEditCandidateRepository(opened)
        finally:
            opened.close()

    def test_repository_never_exposes_mutation(self):
        for forbidden in ("update", "delete", "remove", "upsert", "save"):
            self.assertFalse(hasattr(self.repository, forbidden))
            self.assertFalse(hasattr(self.persistence, forbidden))


if __name__ == "__main__":
    unittest.main()
