"""Application tests for Explicit Lecture Analysis Input Admission (GOAL-023)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.lecture_analysis_input_admission import (
    AdmissionAuthorityMatch,
    AnalysisInputAdmissionConflictError,
    AnalysisInputNotAdmissibleError,
    LectureAnalysisInputAdmissionError,
    LectureAnalysisInputAdmissionService,
    derive_admission_identity,
)
from lectureos.application.identities import TranscriptSourceIntakeId
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
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository
from lectureos.transcript.identities import TranscriptRevisionId

_INTAKE = TranscriptSourceIntakeId("transcript-source-intake:sha256:" + "a" * 64)
_REVISION = TranscriptRevisionId("corrected-revision:" + "b" * 64)


class IdentityTests(unittest.TestCase):
    def test_identity_deterministic_and_input_sensitive(self):
        a = derive_admission_identity(_INTAKE, _REVISION)
        self.assertEqual(a, derive_admission_identity(_INTAKE, _REVISION))
        self.assertTrue(a.value.startswith("lecture-analysis-input:"))
        other_intake = TranscriptSourceIntakeId(
            "transcript-source-intake:sha256:" + "0" * 64
        )
        other_revision = TranscriptRevisionId("corrected-revision:" + "1" * 64)
        self.assertNotEqual(a, derive_admission_identity(other_intake, _REVISION))
        self.assertNotEqual(a, derive_admission_identity(_INTAKE, other_revision))


class LectureAnalysisInputAdmissionServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"admission \x00\x01")
        self.media = compose_sqlite_media_import_service(self.connection).import_media(
            str(source)
        ).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            self.media.identity.value
        ).intake.identity.value
        self.raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.intake, self.raw.raw_transcript_id.value
        )
        self.selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        self.admissions = compose_sqlite_lecture_analysis_input_admission_service(
            self.connection
        )

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _revise(self, ref="c1", text="교정"):
        segment_id = SQLiteRawTranscriptRepository(self.connection).get(
            self.raw.raw_transcript_id
        ).segment_ids[0]
        source_text = SQLiteTranscriptSegmentRepository(self.connection).get(segment_id).text
        candidate = compose_sqlite_correction_candidate_admission_service(
            self.connection
        ).admit(
            intake_id=self.intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": self.raw.raw_transcript_id.value,
                 "segment_id": segment_id.value, "candidate_ref": ref,
                 "source_type": "manual", "source_reference": "human",
                 "proposed_text": text, "source_text_snapshot": source_text,
                 "rationale": "fix"}
            ),
        ).candidate.identity.value
        compose_sqlite_correction_candidate_decision_service(self.connection).decide(
            candidate_id=candidate, kind="accept", reviewer="r:kim"
        )
        revision = compose_sqlite_corrected_revision_generation_service(
            self.connection
        ).generate(candidate_id=candidate).revision.identity.value
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        return revision

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM lecture_analysis_input_admissions"
        ).fetchone()[0]

    def test_ineligible_intake_refused_before_persistence(self):
        # No corrected selection yet (raw-only authority): revalidation blocks admission.
        with self.assertRaises(AnalysisInputNotAdmissibleError):
            self.admissions.admit(intake_id=self.intake)
        self.selection.select_raw_fallback(intake_id=self.intake, reviewer="s:kim")
        with self.assertRaises(AnalysisInputNotAdmissibleError):
            self.admissions.admit(intake_id=self.intake)
        self.assertEqual(self._count(), 0)

    def test_unknown_and_malformed_intakes(self):
        with self.assertRaises(AnalysisInputNotAdmissibleError):
            self.admissions.admit(
                intake_id="transcript-source-intake:sha256:" + "0" * 64
            )
        with self.assertRaises(ValueError):
            self.admissions.admit(intake_id="not-an-intake")
        self.assertEqual(self._count(), 0)

    def test_eligible_authority_admits_exact_snapshot(self):
        revision = self._revise()
        result = self.admissions.admit(intake_id=self.intake)
        self.assertEqual(result.outcome.value, "admitted")
        admission = result.admission
        self.assertEqual(admission.transcript_source_intake_id.value, self.intake)
        self.assertEqual(admission.source_media_id, self.media.identity)
        self.assertEqual(admission.corrected_revision_id.value, revision)
        self.assertEqual(admission.parent_raw_transcript_id, self.raw.raw_transcript_id)
        self.assertEqual(
            admission.content_fingerprint, result.eligibility.content_fingerprint
        )
        self.assertEqual(admission.segment_count, 1)
        self.assertEqual(
            admission.raw_selection_id, result.eligibility.raw_selection_id
        )
        self.assertEqual(
            admission.corrected_selection_id, result.eligibility.corrected_selection_id
        )

    def test_exact_replay_reuses_without_new_row(self):
        self._revise()
        first = self.admissions.admit(intake_id=self.intake)
        replay = self.admissions.admit(intake_id=self.intake)
        self.assertEqual(replay.outcome.value, "reused")
        self.assertEqual(replay.admission.identity, first.admission.identity)
        self.assertEqual(self._count(), 1)

    def test_authority_change_appends_and_preserves_history(self):
        revision_1 = self._revise("c1", "교정 하나")
        first = self.admissions.admit(intake_id=self.intake)
        revision_2 = self._revise("c2", "교정 둘")
        second = self.admissions.admit(intake_id=self.intake)
        self.assertEqual(second.outcome.value, "admitted")
        self.assertEqual(second.admission.corrected_revision_id.value, revision_2)
        self.assertNotEqual(second.admission.identity, first.admission.identity)
        self.assertEqual(self._count(), 2)
        # The prior admission is byte-identical immutable history with derived status.
        self.assertEqual(
            self.admissions.get(first.admission.identity.value), first.admission
        )
        self.assertIs(
            self.admissions.authority_match(first.admission),
            AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE,
        )
        self.assertIs(
            self.admissions.authority_match(second.admission),
            AdmissionAuthorityMatch.CURRENT,
        )
        self.assertEqual(first.admission.corrected_revision_id.value, revision_1)

    def test_returning_authority_converges_on_existing_record(self):
        revision_1 = self._revise("c1", "교정 하나")
        first = self.admissions.admit(intake_id=self.intake)
        self._revise("c2", "교정 둘")
        self.admissions.admit(intake_id=self.intake)
        self.selection.select_revision(revision_id=revision_1, reviewer="s:kim")
        converged = self.admissions.admit(intake_id=self.intake)
        self.assertEqual(converged.outcome.value, "reused")
        self.assertEqual(converged.admission.identity, first.admission.identity)
        self.assertEqual(self._count(), 2)

    def test_ineligible_current_authority_reported_on_historical_admission(self):
        self._revise()
        first = self.admissions.admit(intake_id=self.intake)
        # A new raw selection makes the selected revision inapplicable.
        raw_b = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": "B",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.intake, raw_b.raw_transcript_id.value
        )
        self.assertIs(
            self.admissions.authority_match(first.admission),
            AdmissionAuthorityMatch.CURRENT_AUTHORITY_INELIGIBLE,
        )
        with self.assertRaises(AnalysisInputNotAdmissibleError):
            self.admissions.admit(intake_id=self.intake)
        self.assertEqual(self._count(), 1)

    def test_concurrent_identical_admission_converges(self):
        self._revise()

        class _StaleQuery:
            """The racing caller's first existence check misses the committed row."""

            def __init__(self, inner):
                self._inner = inner
                self._missed = False

            def __getattr__(self, name):
                return getattr(self._inner, name)

            def get(self, identity):
                if not self._missed:
                    self._missed = True
                    return None
                return self._inner.get(identity)

        first = self.admissions.admit(intake_id=self.intake)
        racing = LectureAnalysisInputAdmissionService(
            self.admissions._eligibility,
            _StaleQuery(self.admissions._admissions),
            self.admissions._persistence,
        )
        raced = racing.admit(intake_id=self.intake)
        self.assertEqual(raced.outcome.value, "reused")
        self.assertEqual(raced.admission.identity, first.admission.identity)
        self.assertEqual(self._count(), 1)

    def test_divergent_existing_snapshot_is_explicit_conflict(self):
        self._revise()
        first = self.admissions.admit(intake_id=self.intake)

        class _TamperedQuery:
            def __init__(self, inner, tampered):
                self._inner = inner
                self._tampered = tampered

            def __getattr__(self, name):
                return getattr(self._inner, name)

            def get(self, identity):
                return self._tampered

        import dataclasses

        tampered = dataclasses.replace(
            first.admission, content_fingerprint="f" * 64
        )
        conflicted = LectureAnalysisInputAdmissionService(
            self.admissions._eligibility,
            _TamperedQuery(self.admissions._admissions, tampered),
            self.admissions._persistence,
        )
        with self.assertRaises(AnalysisInputAdmissionConflictError):
            conflicted.admit(intake_id=self.intake)

    def test_restart_reconstructs_identically(self):
        self._revise()
        first = self.admissions.admit(intake_id=self.intake)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            service = compose_sqlite_lecture_analysis_input_admission_service(reopened)
            restored = service.get(first.admission.identity.value)
            self.assertEqual(restored, first.admission)
            self.assertEqual(
                service.list_for_intake(self.intake), (first.admission,)
            )
            self.assertIs(
                service.authority_match(restored), AdmissionAuthorityMatch.CURRENT
            )
        finally:
            reopened.close()
            self.connection = open_sqlite_database(self.database)

    def test_queries_validate_identities(self):
        with self.assertRaises(LectureAnalysisInputAdmissionError):
            self.admissions.get("not-an-admission")
        with self.assertRaises(LectureAnalysisInputAdmissionError):
            self.admissions.list_for_intake("not-an-intake")
        self.assertIsNone(
            self.admissions.get("lecture-analysis-input:" + "0" * 64)
        )


if __name__ == "__main__":
    unittest.main()
