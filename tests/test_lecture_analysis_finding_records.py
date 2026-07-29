"""Persistence, atomicity, and storage-constraint tests for effective-generation Analysis
Findings (042 §8.2 / PATCH-0030, GOAL-025)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.identities import (
    LectureAnalysisFindingId,
    LectureAnalysisInputAdmissionId,
)
from lectureos.application.lecture_analysis_finding import (
    LectureAnalysisFinding,
    derive_finding_identity,
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
from lectureos.persistence.lecture_analysis_finding import (
    SQLiteLectureAnalysisFindingCommandPersistence,
    SQLiteLectureAnalysisFindingRepository,
)

def _finding(admission: LectureAnalysisInputAdmissionId, **overrides) -> LectureAnalysisFinding:
    payload = {
        "finding_type": "background_noise",
        "evidence": "잡음",
        "confidence": None,
        "uncertainty": None,
        "range_start": None,
        "range_end": None,
    }
    payload.update(overrides)
    return LectureAnalysisFinding(
        identity=derive_finding_identity(
            admission,
            payload["finding_type"],
            payload["evidence"],
            payload["range_start"],
            payload["range_end"],
        ),
        admission_id=admission,
        **payload,
    )


class FindingPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        # A real anchor from the released upstream chain: a fabricated admission row would
        # leave dangling foreign keys and make the repository itself unopenable.
        self.admission = self._admit_analysis_input()
        self.repository = SQLiteLectureAnalysisFindingRepository(self.connection)
        self.persistence = SQLiteLectureAnalysisFindingCommandPersistence(self.connection)

    def _admit_analysis_input(self) -> LectureAnalysisInputAdmissionId:
        source = Path(self.tempdir.name) / "a.bin"
        source.write_bytes(b"records \x00\x01")
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
            "SELECT COUNT(*) FROM lecture_analysis_findings"
        ).fetchone()[0]

    def test_round_trips_every_field(self):
        finding = _finding(self.admission, confidence=0.25, uncertainty=0.75, range_start=1.0, range_end=2.5)
        self.persistence.persist_finding(finding=finding)
        self.assertEqual(self.repository.get(finding.identity), finding)

    def test_optional_fields_round_trip_as_none(self):
        finding = _finding(self.admission)
        self.persistence.persist_finding(finding=finding)
        restored = self.repository.get(finding.identity)
        self.assertIsNone(restored.confidence)
        self.assertIsNone(restored.uncertainty)
        self.assertFalse(restored.has_source_range)

    def test_unknown_identity_reads_none(self):
        self.assertIsNone(
            self.repository.get(LectureAnalysisFindingId("lecture-analysis-finding:" + "0" * 64))
        )

    def test_list_for_admission_is_ordered_by_identity(self):
        findings = [_finding(self.admission, evidence=f"근거 {index}") for index in range(4)]
        for finding in findings:
            self.persistence.persist_finding(finding=finding)
        listed = self.repository.list_for_admission(self.admission)
        self.assertEqual(len(listed), 4)
        self.assertEqual(
            [f.identity.value for f in listed],
            sorted(f.identity.value for f in findings),
        )

    def test_duplicate_identity_collides_and_leaves_one_row(self):
        finding = _finding(self.admission)
        self.persistence.persist_finding(finding=finding)
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_finding(finding=finding)
        self.assertEqual(self._count(), 1)

    def test_missing_anchor_rolls_back_leaving_no_partial_row(self):
        orphan_admission = LectureAnalysisInputAdmissionId("lecture-analysis-input:" + "9" * 64)
        finding = LectureAnalysisFinding(
            identity=derive_finding_identity(orphan_admission, "t", "e", None, None),
            admission_id=orphan_admission,
            finding_type="t",
            evidence="e",
        )
        # A dangling anchor is a foreign-key failure. The released persistence idiom maps every
        # sqlite3.IntegrityError onto the identity-collision error, so pin the exact type here:
        # if that mapping is ever narrowed, this must be updated deliberately, not silently.
        with self.assertRaises(PersistenceIdentityCollisionError):
            self.persistence.persist_finding(finding=finding)
        self.assertEqual(self._count(), 0)
        self.assertFalse(self.connection.in_transaction)

    def test_schema_check_violation_leaves_no_partial_row(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO lecture_analysis_findings VALUES "
                "(?, ?, 'x', 'e', NULL, NULL, NULL, NULL, 2)",
                ("lecture-analysis-finding:" + "1" * 64, self.admission.value),
            )
        self.assertEqual(self._count(), 0)

    def test_storage_rejects_empty_type_and_evidence(self):
        for finding_type, evidence in (("", "e"), ("t", "   ")):
            with self.subTest(finding_type=finding_type, evidence=evidence):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        "INSERT INTO lecture_analysis_findings VALUES "
                        "(?, ?, ?, ?, NULL, NULL, NULL, NULL, 1)",
                        (
                            "lecture-analysis-finding:" + "2" * 64,
                            self.admission.value,
                            finding_type,
                            evidence,
                        ),
                    )

    def test_storage_rejects_out_of_range_confidence(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO lecture_analysis_findings VALUES "
                "(?, ?, 't', 'e', 1.5, NULL, NULL, NULL, 1)",
                ("lecture-analysis-finding:" + "3" * 64, self.admission.value),
            )

    def test_storage_rejects_partial_and_inverted_range(self):
        for start, end in ((1.0, None), (None, 1.0), (2.0, 1.0), (-1.0, 1.0)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        "INSERT INTO lecture_analysis_findings VALUES "
                        "(?, ?, 't', 'e', NULL, NULL, ?, ?, 1)",
                        (
                            "lecture-analysis-finding:" + "4" * 64,
                            self.admission.value,
                            start,
                            end,
                        ),
                    )

    def test_persistence_requires_v48_schema(self):
        from lectureos.persistence.errors import SchemaFeatureUnavailableError
        from lectureos.persistence import sqlite as lifecycle

        legacy = Path(self.tempdir.name) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 48):
            statements += getattr(lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 47)")
        connection.execute("COMMIT")
        connection.close()

        opened = open_sqlite_database(legacy)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteLectureAnalysisFindingRepository(opened)
        finally:
            opened.close()

    def test_repository_never_exposes_mutation(self):
        for forbidden in ("update", "delete", "remove", "upsert", "save"):
            self.assertFalse(hasattr(self.repository, forbidden))
            self.assertFalse(hasattr(self.persistence, forbidden))


if __name__ == "__main__":
    unittest.main()
