"""Application tests for effective-generation Lecture Segmentation (042 §7.2 / PATCH-0031, GOAL-026)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.identities import LectureAnalysisInputAdmissionId
from lectureos.application.lecture_analysis_input_admission import AdmissionAuthorityMatch
from lectureos.application.lecture_analysis_segment import (
    SEGMENT_CONTRACT_VERSION,
    LectureAnalysisSegment,
    LectureAnalysisSegmentError,
    LectureAnalysisSegmentationService,
    SegmentationAnchorNotAdmissibleError,
    SegmentationConflictError,
    derive_segment_identity,
    normalize_range,
    require_canonical_segment_id,
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
    compose_sqlite_lecture_analysis_segmentation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository

_ADMISSION = LectureAnalysisInputAdmissionId("lecture-analysis-input:" + "a" * 64)
_OTHER = LectureAnalysisInputAdmissionId("lecture-analysis-input:" + "b" * 64)


class IdentityTests(unittest.TestCase):
    def _id(self, admission=_ADMISSION, sequence=0, start=0.0, end=1.0):
        return derive_segment_identity(admission, sequence, start, end)

    def test_identity_is_deterministic_and_prefixed(self):
        self.assertEqual(self._id(), self._id())
        self.assertTrue(self._id().value.startswith("lecture-analysis-segment:"))
        self.assertEqual(len(self._id().value), len("lecture-analysis-segment:") + 64)

    def test_anchor_participates(self):
        self.assertNotEqual(self._id(), self._id(admission=_OTHER))

    def test_sequence_participates(self):
        self.assertNotEqual(self._id(sequence=0), self._id(sequence=1))

    def test_range_participates(self):
        self.assertNotEqual(self._id(start=0.0), self._id(start=0.5))
        self.assertNotEqual(self._id(end=1.0), self._id(end=2.0))

    def test_negative_zero_and_zero_share_one_identity(self):
        self.assertEqual(self._id(start=-0.0), self._id(start=0.0))
        self.assertEqual(self._id(start=-0.0, end=-0.0), self._id(start=0.0, end=0.0))

    def test_integral_and_float_spellings_converge(self):
        # The GOAL-025 defect class, prevented here: REAL affinity would store 1.0 either way, so
        # a non-normalized int would mint an identity the stored row can never re-derive.
        self.assertEqual(self._id(start=1, end=2), self._id(start=1.0, end=2.0))
        self.assertEqual(self._id(start=0, end=0), self._id(start=0.0, end=0.0))

    def test_identity_carries_nothing_volatile(self):
        self.assertEqual(self._id().value, self._id().value)

    def test_malformed_identity_is_refused(self):
        for value in ("", "nope", "lecture-analysis-segment:short",
                      "lecture-analysis-finding:" + "a" * 64):
            with self.subTest(value=value):
                with self.assertRaises(LectureAnalysisSegmentError):
                    require_canonical_segment_id(value)


class RangeNormalizationTests(unittest.TestCase):
    def test_canonical_floats_returned(self):
        self.assertEqual(normalize_range(1, 2), (1.0, 2.0))
        self.assertIsInstance(normalize_range(1, 2)[0], float)

    def test_negative_zero_collapses_to_canonical_zero(self):
        # `-0.0 < 0` is False so it passes the non-negative check, json.dumps spells it `-0.0`,
        # and SQLite stores plain `0.0` — without collapsing, the stored row could never re-derive
        # its own identity (the GOAL-025 defect class).
        import math

        start, _ = normalize_range(-0.0, 1.0)
        self.assertEqual(start, 0.0)
        self.assertGreater(math.copysign(1.0, start), 0.0)

    def test_zero_duration_is_valid(self):
        self.assertEqual(normalize_range(1.5, 1.5), (1.5, 1.5))

    def test_whole_recording_range_is_valid(self):
        self.assertEqual(normalize_range(0.0, 99999.0), (0.0, 99999.0))

    def test_invalid_ranges_are_refused(self):
        for start, end in ((2.0, 1.0), (-1.0, 1.0), (0.0, -1.0),
                           (float("nan"), 1.0), (0.0, float("inf")),
                           (0.0, float("-inf"))):
            with self.subTest(start=start, end=end):
                with self.assertRaises(LectureAnalysisSegmentError):
                    normalize_range(start, end)

    def test_out_of_representable_range_stays_in_the_error_family(self):
        # `isfinite` raises OverflowError for an int too large for a double; without a guard that
        # would escape this boundary's error family and reach callers as a traceback.
        with self.assertRaises(LectureAnalysisSegmentError):
            normalize_range(0, 10 ** 400)
        with self.assertRaises(LectureAnalysisSegmentError):
            normalize_range(10 ** 400, 10 ** 400)

    def test_non_numeric_and_bool_refused(self):
        for value in ("1.0", None, True):
            with self.subTest(value=value):
                with self.assertRaises(LectureAnalysisSegmentError):
                    normalize_range(value, 1.0)


class ModelInvariantTests(unittest.TestCase):
    def _build(self, sequence=0, start=0.0, end=1.0, **overrides):
        return LectureAnalysisSegment(
            identity=derive_segment_identity(_ADMISSION, sequence, start, end),
            admission_id=_ADMISSION,
            sequence=sequence,
            range_start=start,
            range_end=end,
            **overrides,
        )

    def test_valid_segment_round_trips(self):
        segment = self._build(sequence=3, start=1, end=2)
        self.assertEqual(segment.range_start, 1.0)
        self.assertEqual(segment.segment_contract_version, SEGMENT_CONTRACT_VERSION)

    def test_negative_and_non_integer_sequence_refused(self):
        with self.assertRaises(LectureAnalysisSegmentError):
            LectureAnalysisSegment(
                identity=derive_segment_identity(_ADMISSION, 0, 0.0, 1.0),
                admission_id=_ADMISSION, sequence=-1, range_start=0.0, range_end=1.0,
            )
        with self.assertRaises(LectureAnalysisSegmentError):
            LectureAnalysisSegment(
                identity=derive_segment_identity(_ADMISSION, 0, 0.0, 1.0),
                admission_id=_ADMISSION, sequence=True, range_start=0.0, range_end=1.0,
            )

    def test_identity_must_derive_from_payload(self):
        with self.assertRaises(LectureAnalysisSegmentError):
            LectureAnalysisSegment(
                identity=derive_segment_identity(_ADMISSION, 9, 0.0, 1.0),
                admission_id=_ADMISSION, sequence=0, range_start=0.0, range_end=1.0,
            )

    def test_unsupported_contract_version_refused(self):
        with self.assertRaises(LectureAnalysisSegmentError):
            self._build(segment_contract_version=2)

    def test_model_carries_no_currentness_execution_or_finding_state(self):
        segment = self._build()
        for forbidden in (
            "current", "stale", "active", "ready", "superseded", "valid_now",
            "run_id", "unit_execution_id", "domain_result_id", "processing_run_id",
            "source_input_id", "finding_id", "analysis_finding_id", "label",
            "provider", "model", "prompt", "created_at",
        ):
            with self.subTest(field=forbidden):
                self.assertFalse(hasattr(segment, forbidden))


class LectureAnalysisSegmentationServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"segment \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(
            str(source)
        ).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
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
        self.segmentation = compose_sqlite_lecture_analysis_segmentation_service(
            self.connection
        )
        self.revision_1 = self._revise("c1", "교정 1")
        self.admission = self.admissions.admit(intake_id=self.intake).admission

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _revise(self, ref, text):
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
            "SELECT COUNT(*) FROM lecture_analysis_segments"
        ).fetchone()[0]

    _DEFAULT = object()

    def _admit(self, ranges=((0.0, 1.0), (1.0, 2.0)), admission=_DEFAULT):
        # `is _DEFAULT`, not truthiness: an empty-string admission is a case under test and must
        # not silently fall back to the real one.
        if admission is self._DEFAULT:
            admission = self.admission.identity.value
        return self.segmentation.admit_segmentation(
            admission_id=admission, ranges=list(ranges)
        )

    # -- anchoring and Finding independence ----------------------------------------------------

    def test_batch_anchors_to_admission_without_duplicating_provenance(self):
        result = self._admit()
        self.assertEqual(result.outcome.value, "recorded")
        self.assertEqual([s.sequence for s in result.segments], [0, 1])
        columns = [
            row[1] for row in self.connection.execute(
                "PRAGMA table_info(lecture_analysis_segments)"
            )
        ]
        for absent in ("source_media_id", "corrected_revision_id", "content_fingerprint",
                       "transcript_source_intake_id", "source_timeline_id"):
            self.assertNotIn(absent, columns)

    def test_segmentation_requires_no_analysis_finding(self):
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_analysis_findings"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(self._admit().outcome.value, "recorded")
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_analysis_findings"
            ).fetchone()[0],
            0,
        )

    def test_no_domain_result_is_created(self):
        def _domain_results():
            return self.connection.execute(
                "SELECT COUNT(*) FROM domain_result_references"
            ).fetchone()[0]

        before = _domain_results()
        self._admit()
        self._admit(ranges=[(5.0, 6.0)])
        self.assertEqual(_domain_results(), before)

    # -- admission standing --------------------------------------------------------------------

    def test_current_admission_accepted(self):
        self.assertEqual(self._admit().outcome.value, "recorded")

    def test_superseded_admission_refused_writing_nothing(self):
        self._admit()
        self._revise("c2", "교정 2")
        with self.assertRaises(SegmentationAnchorNotAdmissibleError):
            self._admit(ranges=[(3.0, 4.0)])
        self.assertEqual(self._count(), 2)

    def test_current_authority_ineligible_refused(self):
        self._admit()
        self.selection.select_raw_fallback(intake_id=self.intake, reviewer="s:kim")
        self.assertIs(
            self.admissions.authority_match(self.admission),
            AdmissionAuthorityMatch.CURRENT_AUTHORITY_INELIGIBLE,
        )
        with self.assertRaises(SegmentationAnchorNotAdmissibleError):
            self._admit(ranges=[(3.0, 4.0)])
        self.assertEqual(self._count(), 2)

    def test_missing_and_malformed_admission_refused(self):
        for admission in ("lecture-analysis-input:" + "f" * 64, "nope", ""):
            with self.subTest(admission=admission):
                with self.assertRaises(LectureAnalysisSegmentError):
                    self._admit(admission=admission)
        self.assertEqual(self._count(), 0)

    def test_returning_authority_restores_admissibility(self):
        first = self._admit()
        self._revise("c2", "교정 2")
        with self.assertRaises(SegmentationAnchorNotAdmissibleError):
            self._admit()
        self.selection.select_revision(revision_id=self.revision_1, reviewer="s:kim")
        again = self._admit()
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(
            [s.identity for s in again.segments], [s.identity for s in first.segments]
        )

    # -- ordered batch -------------------------------------------------------------------------

    def test_batch_position_is_the_sequence(self):
        result = self._admit(ranges=[(2.0, 3.0), (0.0, 1.0), (1.0, 2.0)])
        self.assertEqual([s.sequence for s in result.segments], [0, 1, 2])
        self.assertEqual(result.segments[0].range_start, 2.0)

    def test_empty_batch_is_refused(self):
        with self.assertRaises(LectureAnalysisSegmentError):
            self._admit(ranges=[])
        self.assertEqual(self._count(), 0)

    def test_single_segment_batch_is_valid(self):
        self.assertEqual(len(self._admit(ranges=[(0.0, 1.0)]).segments), 1)

    def test_identical_ranges_at_different_positions_are_distinct(self):
        result = self._admit(ranges=[(0.0, 1.0), (0.0, 1.0)])
        self.assertNotEqual(result.segments[0].identity, result.segments[1].identity)
        self.assertEqual(self._count(), 2)

    def test_malformed_payload_shape_refused(self):
        for bad in ([(0.0,)], [(0.0, 1.0, 2.0)], [0.0]):
            with self.subTest(bad=bad):
                with self.assertRaises(LectureAnalysisSegmentError):
                    self._admit(ranges=bad)
        self.assertEqual(self._count(), 0)

    def test_several_batches_may_share_a_sequence(self):
        # 042 §7.1 forbids canonical-set/uniqueness constraints, so this must be permitted; a
        # UNIQUE(admission, sequence) constraint would violate the contract.
        self._admit(ranges=[(0.0, 1.0)])
        self._admit(ranges=[(5.0, 6.0)])
        shared = self.connection.execute(
            "SELECT COUNT(*) FROM lecture_analysis_segments WHERE sequence = 0"
        ).fetchone()[0]
        self.assertEqual(shared, 2)

    # -- range semantics -----------------------------------------------------------------------

    def test_zero_duration_and_whole_recording_ranges_accepted(self):
        result = self._admit(ranges=[(1.0, 1.0), (0.0, 99999.0)])
        self.assertEqual(result.outcome.value, "recorded")

    def test_invalid_ranges_refused_before_any_write(self):
        for bad in ([(1.0, 0.0)], [(-1.0, 1.0)], [(0.0, float("nan"))],
                    [(0.0, float("inf"))], [(0.0, 1.0), (2.0, 1.0)]):
            with self.subTest(bad=bad):
                with self.assertRaises(LectureAnalysisSegmentError):
                    self._admit(ranges=bad)
        self.assertEqual(self._count(), 0)

    def test_no_extent_or_coverage_validation_is_applied(self):
        # The transcript spans 0..2; ranges far beyond it, with gaps and overlaps, are valid —
        # 042 §7.2 S-8 forbids adding extent, coverage, gap, or overlap validation here.
        result = self._admit(ranges=[(500.0, 900.0), (0.0, 900.0), (10.0, 20.0)])
        self.assertEqual(result.outcome.value, "recorded")
        self.assertEqual(self._count(), 3)

    def test_negative_zero_round_trips_and_replays(self):
        first = self._admit(ranges=[(-0.0, 1.0)])
        self.assertEqual(first.segments[0].range_start, 0.0)
        # The row must remain readable and converge with the plain-zero spelling.
        self.assertEqual(
            self.segmentation.get(first.segments[0].identity.value), first.segments[0]
        )
        again = self._admit(ranges=[(0.0, 1.0)])
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(again.segments[0].identity, first.segments[0].identity)
        self.assertEqual(self._count(), 1)

    def test_integral_ranges_normalize_and_persist_as_real(self):
        integral = self._admit(ranges=[(1, 2)])
        self.assertEqual(integral.segments[0].range_start, 1.0)
        stored = self.connection.execute(
            "SELECT typeof(range_start), typeof(range_end) FROM lecture_analysis_segments"
        ).fetchone()
        self.assertEqual(stored, ("real", "real"))
        self.assertEqual(
            self.segmentation.get(integral.segments[0].identity.value),
            integral.segments[0],
        )
        again = self._admit(ranges=[(1.0, 2.0)])
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(again.segments[0].identity, integral.segments[0].identity)

    # -- replay, partial pre-existence, conflict -----------------------------------------------

    def test_exact_replay_reuses_without_new_rows(self):
        first = self._admit()
        again = self._admit()
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(again.reused_count, 2)
        self.assertEqual(self._count(), 2)
        self.assertEqual(
            [s.identity for s in again.segments], [s.identity for s in first.segments]
        )

    def test_partial_pre_existence_records_only_the_new_members(self):
        first = self._admit(ranges=[(0.0, 1.0), (1.0, 2.0)])
        mixed = self._admit(ranges=[(0.0, 1.0), (7.0, 8.0)])
        self.assertEqual(mixed.outcome.value, "recorded")
        self.assertEqual(mixed.recorded_count, 1)
        self.assertEqual(mixed.reused_count, 1)
        self.assertEqual(mixed.segments[0].identity, first.segments[0].identity)
        self.assertEqual(self._count(), 3)

    def test_different_admission_creates_distinct_segments(self):
        first = self._admit()
        self._revise("c2", "교정 2")
        second_admission = self.admissions.admit(intake_id=self.intake).admission
        other = self._admit(admission=second_admission.identity.value)
        self.assertNotEqual(other.segments[0].identity, first.segments[0].identity)

    def test_divergent_stored_payload_is_an_explicit_conflict(self):
        """Option B: unreachable through the command, so the guard is driven directly with a
        tampering stub — removing the check because the happy path cannot reach it would trade an
        integrity guarantee for nothing."""

        first = self._admit(ranges=[(0.0, 1.0)])
        tampered = LectureAnalysisSegment.__new__(LectureAnalysisSegment)
        object.__setattr__(tampered, "identity", first.segments[0].identity)
        object.__setattr__(tampered, "admission_id", first.segments[0].admission_id)
        object.__setattr__(tampered, "sequence", 0)
        object.__setattr__(tampered, "range_start", 0.0)
        object.__setattr__(tampered, "range_end", 5.0)  # divergent
        object.__setattr__(tampered, "segment_contract_version", 1)

        class _TamperedQuery:
            def __init__(self, inner, fake):
                self._inner = inner
                self._fake = fake

            def __getattr__(self, name):
                return getattr(self._inner, name)

            def get(self, identity):
                return self._fake

        service = LectureAnalysisSegmentationService(
            self.segmentation._admissions,
            _TamperedQuery(self.segmentation._segments, tampered),
            self.segmentation._persistence,
        )
        with self.assertRaises(SegmentationConflictError):
            service.admit_segmentation(
                admission_id=self.admission.identity.value, ranges=[(0.0, 1.0)]
            )
        self.assertEqual(self._count(), 1)

    def test_concurrent_identical_batch_converges(self):
        class _StaleQuery:
            def __init__(self, inner):
                self._inner = inner
                self._missed = set()

            def __getattr__(self, name):
                return getattr(self._inner, name)

            def get(self, identity):
                if identity.value not in self._missed:
                    self._missed.add(identity.value)
                    return None
                return self._inner.get(identity)

        first = self._admit()
        racing = LectureAnalysisSegmentationService(
            self.segmentation._admissions,
            _StaleQuery(self.segmentation._segments),
            self.segmentation._persistence,
        )
        raced = racing.admit_segmentation(
            admission_id=self.admission.identity.value, ranges=[(0.0, 1.0), (1.0, 2.0)]
        )
        self.assertEqual(raced.outcome.value, "reused")
        self.assertEqual(self._count(), 2)
        self.assertEqual(
            [s.identity for s in raced.segments], [s.identity for s in first.segments]
        )

    def test_partially_overlapping_race_reports_honestly_and_writes_nothing(self):
        """S-11 mandates convergence only for identical near-concurrent admissions. A racing
        batch that overlaps only partly rolls back completely and must say so in this boundary's
        own error type, not leak a persistence 'already exists' message."""

        class _StaleForFirstOnly:
            def __init__(self, inner, miss):
                self._inner = inner
                self._miss = miss

            def __getattr__(self, name):
                return getattr(self._inner, name)

            def get(self, identity):
                if identity.value in self._miss:
                    self._miss.discard(identity.value)
                    return None
                return self._inner.get(identity)

        first = self._admit(ranges=[(0.0, 1.0), (1.0, 2.0)])
        rows_before = self._count()
        racing = LectureAnalysisSegmentationService(
            self.segmentation._admissions,
            _StaleForFirstOnly(
                self.segmentation._segments, {first.segments[0].identity.value}
            ),
            self.segmentation._persistence,
        )
        with self.assertRaises(LectureAnalysisSegmentError) as caught:
            racing.admit_segmentation(
                admission_id=self.admission.identity.value,
                ranges=[(0.0, 1.0), (7.0, 8.0)],
            )
        self.assertIn("retry", str(caught.exception))
        self.assertEqual(self._count(), rows_before)

    # -- immutability and history --------------------------------------------------------------

    def test_existing_segments_unchanged_after_authority_change(self):
        first = self._admit()
        self._revise("c2", "교정 2")
        for segment in first.segments:
            self.assertEqual(self.segmentation.get(segment.identity.value), segment)

    def test_anchor_status_is_derived_never_stored(self):
        first = self._admit()
        self.assertIs(
            self.segmentation.anchor_status(first.segments[0]),
            AdmissionAuthorityMatch.CURRENT,
        )
        self._revise("c2", "교정 2")
        self.assertIs(
            self.segmentation.anchor_status(first.segments[0]),
            AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE,
        )
        columns = [
            row[1] for row in self.connection.execute(
                "PRAGMA table_info(lecture_analysis_segments)"
            )
        ]
        for forbidden in ("current", "stale", "active", "ready", "superseded", "valid_now"):
            self.assertNotIn(forbidden, columns)

    def test_repository_exposes_no_update_or_delete(self):
        from lectureos.persistence.lecture_analysis_segment import (
            SQLiteLectureAnalysisSegmentRepository,
        )

        repository = SQLiteLectureAnalysisSegmentRepository(self.connection)
        for forbidden in ("update", "delete", "remove", "save", "upsert"):
            self.assertFalse(hasattr(repository, forbidden))

    def test_list_is_deterministically_ordered(self):
        self._admit(ranges=[(0.0, 1.0), (1.0, 2.0)])
        self._admit(ranges=[(0.0, 0.5)])
        listed = self.segmentation.list_for_admission(self.admission.identity.value)
        sequences = [s.sequence for s in listed]
        self.assertEqual(sequences, sorted(sequences))
        self.assertEqual(
            [s.identity.value for s in listed],
            [s.identity.value for s in
             self.segmentation.list_for_admission(self.admission.identity.value)],
        )

    def test_restart_reconstructs_identically(self):
        first = self._admit(ranges=[(1, 2), (2, 3)])
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            service = compose_sqlite_lecture_analysis_segmentation_service(reopened)
            for segment in first.segments:
                self.assertEqual(service.get(segment.identity.value), segment)
        finally:
            reopened.close()
        self.connection = initialize_sqlite_database(self.database)

    # -- isolation ---------------------------------------------------------------------------

    def test_no_execution_legacy_or_downstream_row_is_created(self):
        self._admit()
        for table in (
            "lecture_segments", "eligible_analysis_inputs", "analysis_findings",
            "processing_runs", "unit_executions", "processing_units",
            "lecture_analysis_findings", "edit_candidates",
        ):
            with self.subTest(table=table):
                self.assertEqual(
                    self.connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0],
                    0,
                )


if __name__ == "__main__":
    unittest.main()
