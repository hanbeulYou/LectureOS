"""Application tests for Derived Lecture Analysis Input Eligibility (GOAL-022)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.corrected_revision_generation import content_fingerprint_for
from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.lecture_analysis_input_eligibility import (
    AnalysisInputBlockingReason,
    LectureAnalysisInputEligibility,
    LectureAnalysisInputEligibilityError,
    LectureAnalysisInputEligibilityService,
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
    compose_sqlite_lecture_analysis_input_eligibility_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository


class LectureAnalysisInputEligibilityServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"analysis-eligibility \x00\x01")
        self.media = compose_sqlite_media_import_service(self.connection).import_media(
            str(source)
        ).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            self.media.identity.value
        ).intake.identity.value
        self.eligibility = compose_sqlite_lecture_analysis_input_eligibility_service(
            self.connection
        )
        self.selection = compose_sqlite_corrected_revision_selection_service(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _admit_raw(self, ref="A"):
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": ref,
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.intake, raw.raw_transcript_id.value
        )
        return raw

    def _select_corrected(self, raw, ref="c1", text="교정"):
        segment_id = SQLiteRawTranscriptRepository(self.connection).get(
            raw.raw_transcript_id
        ).segment_ids[0]
        source_text = SQLiteTranscriptSegmentRepository(self.connection).get(segment_id).text
        candidate = compose_sqlite_correction_candidate_admission_service(
            self.connection
        ).admit(
            intake_id=self.intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw.raw_transcript_id.value,
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
        return candidate, revision

    def _table_counts(self):
        return {
            table: self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for (table,) in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
        }

    # -- authority states -----------------------------------------------------------------------------

    def test_no_current_raw_transcript_is_ineligible(self):
        result = self.eligibility.evaluate(self.intake)
        self.assertFalse(result.eligible)
        self.assertEqual(
            result.blocking_reasons,
            (AnalysisInputBlockingReason.NO_CURRENT_RAW_TRANSCRIPT,),
        )
        self.assertEqual(result.source_media_id, self.media.identity)

    def test_raw_only_and_raw_fallback_are_ineligible_per_contract(self):
        # 042 §5.1: the admission authority is the validated selected Corrected Transcript.
        self._admit_raw()
        result = self.eligibility.evaluate(self.intake)
        self.assertEqual(
            result.blocking_reasons,
            (AnalysisInputBlockingReason.CORRECTED_TRANSCRIPT_NOT_SELECTED,),
        )
        self.assertEqual(result.selection_state.value, "no_history")
        self.selection.select_raw_fallback(intake_id=self.intake, reviewer="s:kim")
        result = self.eligibility.evaluate(self.intake)
        self.assertEqual(
            result.blocking_reasons,
            (AnalysisInputBlockingReason.CORRECTED_TRANSCRIPT_NOT_SELECTED,),
        )
        self.assertEqual(result.selection_state.value, "raw_fallback")
        self.assertIsNotNone(result.parent_raw_transcript_id)

    def test_current_applicable_corrected_revision_is_eligible_with_lineage(self):
        raw = self._admit_raw()
        _, revision = self._select_corrected(raw)
        result = self.eligibility.evaluate(self.intake)
        self.assertTrue(result.eligible)
        self.assertEqual(result.blocking_reasons, ())
        self.assertEqual(result.corrected_revision_id.value, revision)
        self.assertEqual(result.parent_raw_transcript_id, raw.raw_transcript_id)
        self.assertEqual(result.source_media_id, self.media.identity)
        self.assertEqual(result.effective_kind.value, "corrected_revision")
        self.assertEqual(result.segment_count, 1)
        self.assertIsNotNone(result.raw_selection_id)
        self.assertIsNotNone(result.corrected_selection_id)

    def test_fingerprint_reuses_released_contract(self):
        raw = self._admit_raw()
        _, revision = self._select_corrected(raw)
        result = self.eligibility.evaluate(self.intake)
        from lectureos.persistence.corrected_transcript_revisions import (
            SQLiteCorrectedTranscriptRevisionRepository,
        )

        record = SQLiteCorrectedTranscriptRevisionRepository(self.connection).get(
            result.corrected_revision_id
        )
        segments = tuple(
            SQLiteTranscriptSegmentRepository(self.connection).get(segment_id)
            for segment_id in record.segment_ids
        )
        self.assertEqual(result.content_fingerprint, content_fingerprint_for(segments))

    def test_superseding_revision_changes_result_and_old_result_stays_immutable(self):
        raw = self._admit_raw()
        _, revision_1 = self._select_corrected(raw, "c1", "교정 하나")
        first = self.eligibility.evaluate(self.intake)
        _, revision_2 = self._select_corrected(raw, "c2", "교정 둘")
        second = self.eligibility.evaluate(self.intake)
        self.assertEqual(first.corrected_revision_id.value, revision_1)
        self.assertEqual(second.corrected_revision_id.value, revision_2)
        self.assertNotEqual(first.content_fingerprint, second.content_fingerprint)

    def test_inapplicable_selection_is_ineligible_with_resolver_reason(self):
        raw = self._admit_raw()
        candidate, _ = self._select_corrected(raw)
        compose_sqlite_correction_candidate_decision_service(self.connection).decide(
            candidate_id=candidate, kind="reject", reviewer="r:kim"
        )
        result = self.eligibility.evaluate(self.intake)
        self.assertFalse(result.eligible)
        self.assertEqual(
            result.blocking_reasons,
            (AnalysisInputBlockingReason.CORRECTED_SELECTION_NOT_APPLICABLE,),
        )
        self.assertEqual(result.inapplicability_reason, "candidate_not_accepted")
        self.assertIsNotNone(result.corrected_revision_id)

    def test_unknown_intake_is_stable_ineligibility_and_malformed_raises(self):
        result = self.eligibility.evaluate(
            "transcript-source-intake:sha256:" + "0" * 64
        )
        self.assertEqual(
            result.blocking_reasons, (AnalysisInputBlockingReason.INTAKE_NOT_FOUND,)
        )
        with self.assertRaises(LectureAnalysisInputEligibilityError):
            self.eligibility.evaluate("not-an-intake")

    # -- derived-only, restart, isolation -------------------------------------------------------------

    def test_evaluation_persists_nothing_anywhere(self):
        raw = self._admit_raw()
        self._select_corrected(raw)
        before = self._table_counts()
        self.assertNotIn("lecture_analysis_input_eligibilities", before)
        for _ in range(3):
            self.eligibility.evaluate(self.intake)
        self.assertEqual(self._table_counts(), before)
        self.assertEqual(before.get("processing_runs", 0), 0)
        # The legacy Lecture Intelligence tables (the released execution-coupled 042 §5.1
        # implementation over the legacy transcript pipeline — a separate contract
        # generation) hold zero rows: this derived-only contract never writes them, and no
        # new eligibility table exists anywhere.
        for name, count in before.items():
            if "analysis" in name:
                self.assertEqual(count, 0, name)
        self.assertIn("eligible_analysis_inputs", before)  # legacy table, untouched

    def test_restart_produces_identical_result(self):
        raw = self._admit_raw()
        self._select_corrected(raw)
        first = self.eligibility.evaluate(self.intake)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            second = compose_sqlite_lecture_analysis_input_eligibility_service(
                reopened
            ).evaluate(self.intake)
        finally:
            reopened.close()
            self.connection = open_sqlite_database(self.database)
        self.assertEqual(first, second)

    def test_intakes_are_isolated(self):
        raw = self._admit_raw()
        self._select_corrected(raw)
        other_source = self.base / "b.bin"
        other_source.write_bytes(b"another-media \x00\x02")
        other_media = compose_sqlite_media_import_service(self.connection).import_media(
            str(other_source)
        ).record
        other_intake = compose_sqlite_transcript_source_intake_service(
            self.connection
        ).admit(other_media.identity.value).intake.identity.value
        self.assertTrue(self.eligibility.evaluate(self.intake).eligible)
        other = self.eligibility.evaluate(other_intake)
        self.assertFalse(other.eligible)
        self.assertEqual(
            other.blocking_reasons,
            (AnalysisInputBlockingReason.NO_CURRENT_RAW_TRANSCRIPT,),
        )

    # -- content policy and integrity -----------------------------------------------------------------

    def test_empty_content_policy_blocks_whitespace_only_snapshot(self):
        # The conservative structural rule (no invented token/duration minimums) is unit-
        # tested through stub snapshot queries: the released pipeline cannot produce an
        # empty corrected revision, but a tampered or future store must still be honest.
        class _Segment:
            text = "   "
            start = 0.0
            end = 1.0
            source_order = 0

        class _Revision:
            segment_ids = ("seg-1",)

        raw = self._admit_raw()
        _, revision = self._select_corrected(raw)

        class _BlankSegments:
            def get(self, identity):
                return _Segment()

        class _Revisions:
            def get(self, identity):
                return _Revision()

        service = LectureAnalysisInputEligibilityService(
            self.eligibility._intakes,
            self.eligibility._raw_selections,
            self.eligibility._resolver,
            _Revisions(),
            _BlankSegments(),
        )
        result = service.evaluate(self.intake)
        self.assertFalse(result.eligible)
        self.assertEqual(
            result.blocking_reasons,
            (AnalysisInputBlockingReason.TRANSCRIPT_CONTENT_EMPTY,),
        )

    def test_missing_snapshot_is_integrity_error_not_ineligibility(self):
        raw = self._admit_raw()
        self._select_corrected(raw)

        class _MissingRevisions:
            def get(self, identity):
                return None

        service = LectureAnalysisInputEligibilityService(
            self.eligibility._intakes,
            self.eligibility._raw_selections,
            self.eligibility._resolver,
            _MissingRevisions(),
            SQLiteTranscriptSegmentRepository(self.connection),
        )
        with self.assertRaises(LectureAnalysisInputEligibilityError):
            service.evaluate(self.intake)

    def test_result_model_enforces_ordering_and_lineage_completeness(self):
        with self.assertRaises(ValueError):
            LectureAnalysisInputEligibility(
                transcript_source_intake_id="x", eligible=True,
                blocking_reasons=(AnalysisInputBlockingReason.INTAKE_NOT_FOUND,),
            )
        with self.assertRaises(ValueError):
            LectureAnalysisInputEligibility(
                transcript_source_intake_id="x", eligible=False, blocking_reasons=(),
            )
        with self.assertRaises(ValueError):
            LectureAnalysisInputEligibility(
                transcript_source_intake_id="x", eligible=False,
                blocking_reasons=(
                    AnalysisInputBlockingReason.TRANSCRIPT_CONTENT_EMPTY,
                    AnalysisInputBlockingReason.INTAKE_NOT_FOUND,
                ),
            )
        with self.assertRaises(ValueError):
            LectureAnalysisInputEligibility(
                transcript_source_intake_id="x", eligible=True, blocking_reasons=(),
            )


if __name__ == "__main__":
    unittest.main()
