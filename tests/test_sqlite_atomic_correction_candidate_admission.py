"""Atomic SQLite persistence tests for Correction Candidate Admission (040 §17)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    CorrectionCandidateAdmission,
    CorrectionCandidateSourceType,
)
from lectureos.application.identities import CorrectionCandidateAdmissionId
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.execution.identities import CapabilityReference, DomainResultId
from lectureos.execution.models import DomainResultReference
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteCorrectionCandidateAdmissionCommandPersistence,
    SQLiteCorrectionCandidateAdmissionRepository,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError
from lectureos.transcript.identities import CorrectionCandidateId, TranscriptSegmentId
from lectureos.execution.identities import ProcessingRunId, UnitExecutionId
from lectureos.transcript.models import CorrectionCandidate


class SQLiteAtomicCorrectionCandidateAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"corr-atomic \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake
        doc = build_provider_transcript_document(
            {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
             "segments": [{"start": 0.0, "end": 2.0, "text": "원본 텍스트"}]}
        )
        self.raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.intake.identity.value, document=doc
        ).admission.raw_transcript_id
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.intake.identity.value, self.raw.value
        )
        raw_record = SQLiteRawTranscriptRepository(self.connection).get(self.raw)
        self.segment_id = raw_record.segment_ids[0]
        self.segment_text = SQLiteTranscriptSegmentRepository(self.connection).get(self.segment_id).text
        self.raw_domain = raw_record.domain_result_id
        self.source_media = raw_record.source_media_id
        self.source_timeline = raw_record.source_timeline_id
        self.persistence = SQLiteCorrectionCandidateAdmissionCommandPersistence(self.connection)
        self.repo = SQLiteCorrectionCandidateAdmissionRepository(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _bundle(self, anchor="anchor-1", segment=None, proposed="교정된 텍스트"):
        segment = segment if segment is not None else self.segment_id
        candidate_id = CorrectionCandidateId(f"correction-candidate:{anchor}")
        domain_id = DomainResultId(f"domain-result:transcript-correction-candidate:{anchor}")
        candidate = CorrectionCandidate(
            identity=candidate_id,
            domain_result_id=domain_id,
            transcript_id=self.raw,
            segment_id=segment,
            proposed_text=proposed,
            rationale="fix",
            run_id=ProcessingRunId(f"external-correction-run:{anchor}"),
            unit_execution_id=UnitExecutionId(f"external-correction-execution:{anchor}"),
            capability=CapabilityReference("capability:transcript-correction"),
            provider_reference="human:editor",
        )
        result = DomainResultReference(
            identity=domain_id,
            kind="transcript_correction_candidate",
            source_media=self.source_media,
            source_timeline=self.source_timeline,
            upstream_results=(self.raw_domain,),
        )
        admission = CorrectionCandidateAdmission(
            identity=CorrectionCandidateAdmissionId(f"correction-candidate-admission:{anchor}"),
            correction_candidate_id=candidate_id,
            transcript_source_intake_id=self.intake.identity,
            raw_transcript_id=self.raw,
            segment_id=segment,
            source_type=CorrectionCandidateSourceType.MANUAL,
            source_reference="human:editor",
            candidate_ref=anchor,
            source_text_snapshot=self.segment_text,
            content_fingerprint="0" * 64,
        )
        return admission, candidate, result

    def _persist(self, bundle):
        admission, candidate, result = bundle
        self.persistence.persist_correction_candidate_admission(
            admission=admission, candidate=candidate, result=result
        )

    def _counts(self):
        return {
            t: self.connection.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("correction_candidate_admissions", "correction_candidates", "domain_result_references")
        }

    def test_persists_all_records_atomically_and_round_trips(self):
        before = self._counts()
        admission = self._bundle()[0]
        self._persist(self._bundle())
        after = self._counts()
        self.assertEqual(after["correction_candidate_admissions"], 1)
        self.assertEqual(after["correction_candidates"], before["correction_candidates"] + 1)
        self.assertEqual(after["domain_result_references"], before["domain_result_references"] + 1)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            repo = SQLiteCorrectionCandidateAdmissionRepository(reopened)
            self.assertEqual(repo.get(admission.identity), admission)
            self.assertEqual(repo.candidate(admission.correction_candidate_id).proposed_text, "교정된 텍스트")
            views = repo.candidates_for_intake(self.intake.identity, self.raw)
            self.assertEqual(len(views), 1)
            self.assertTrue(views[0].applicable_to_current_selection)
        finally:
            reopened.close()

    def test_identity_collision_rolls_back(self):
        self._persist(self._bundle())
        before = self._counts()
        with self.assertRaises(PersistenceIdentityCollisionError):
            self._persist(self._bundle())
        self.assertEqual(self._counts(), before)

    def test_dangling_segment_rejected_by_foreign_key(self):
        ghost = TranscriptSegmentId("transcript-segment:" + "0" * 64 + ":9")
        before = self._counts()
        with self.assertRaises(PersistenceError):
            self._persist(self._bundle(anchor="x", segment=ghost))
        self.assertEqual(self._counts(), before)  # no partial correction_candidates row either

    def test_distinct_admissions_coexist(self):
        self._persist(self._bundle(anchor="a"))
        self._persist(self._bundle(anchor="b", proposed="다른 교정"))
        self.assertEqual(self._counts()["correction_candidate_admissions"], 2)

    def test_repository_rejects_pre_v34_schema(self):
        legacy_path = self.base / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 34):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 33)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteCorrectionCandidateAdmissionRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
