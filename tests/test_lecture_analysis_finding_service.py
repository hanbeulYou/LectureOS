"""Application tests for effective-generation Analysis Findings (042 §8.2 / PATCH-0030, GOAL-025)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.identities import LectureAnalysisInputAdmissionId
from lectureos.application.lecture_analysis_finding import (
    FINDING_CONTRACT_VERSION,
    AnalysisFindingAnchorNotAdmissibleError,
    AnalysisFindingConflictError,
    LectureAnalysisFinding,
    LectureAnalysisFindingError,
    derive_finding_identity,
    require_canonical_finding_id,
    require_canonical_finding_type,
)
from lectureos.application.lecture_analysis_input_admission import AdmissionAuthorityMatch
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
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database

from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository

_ADMISSION = LectureAnalysisInputAdmissionId("lecture-analysis-input:" + "a" * 64)
_OTHER_ADMISSION = LectureAnalysisInputAdmissionId("lecture-analysis-input:" + "b" * 64)


class IdentityTests(unittest.TestCase):
    def _id(self, **overrides):
        payload = {
            "admission_id": _ADMISSION,
            "finding_type": "background_noise",
            "evidence": "잡음",
            "range_start": None,
            "range_end": None,
        }
        payload.update(overrides)
        return derive_finding_identity(
            payload["admission_id"],
            payload["finding_type"],
            payload["evidence"],
            payload["range_start"],
            payload["range_end"],
        )

    def test_identity_is_deterministic_and_prefixed(self):
        self.assertEqual(self._id(), self._id())
        self.assertTrue(self._id().value.startswith("lecture-analysis-finding:"))
        self.assertEqual(len(self._id().value), len("lecture-analysis-finding:") + 64)

    def test_anchor_participates(self):
        self.assertNotEqual(self._id(), self._id(admission_id=_OTHER_ADMISSION))

    def test_finding_type_participates(self):
        self.assertNotEqual(self._id(), self._id(finding_type="speaker_overlap"))

    def test_evidence_participates(self):
        self.assertNotEqual(self._id(), self._id(evidence="다른 근거"))

    def test_evidence_is_not_normalized(self):
        # Differing evidence must never converge (042 §8.2 D-9): no trimming or case folding.
        self.assertNotEqual(self._id(), self._id(evidence="잡음 "))

    def test_source_range_participates(self):
        self.assertNotEqual(self._id(), self._id(range_start=0.0, range_end=1.0))
        self.assertNotEqual(
            self._id(range_start=0.0, range_end=1.0),
            self._id(range_start=0.0, range_end=2.0),
        )

    def test_identity_carries_no_timestamp_randomness_or_provider_id(self):
        # Re-deriving across processes/runs must be stable — nothing volatile participates.
        self.assertEqual(self._id().value, self._id().value)

    def test_malformed_identity_is_refused(self):
        for value in ("", "nope", "lecture-analysis-finding:short", "lecture-analysis-input:" + "a" * 64):
            with self.subTest(value=value):
                with self.assertRaises(LectureAnalysisFindingError):
                    require_canonical_finding_id(value)


class CanonicalFindingTypeTests(unittest.TestCase):
    def test_open_vocabulary_accepts_any_canonical_token(self):
        for token in ("background_noise", "a", "x9_y", "some_unregistered_future_type"):
            with self.subTest(token=token):
                self.assertEqual(require_canonical_finding_type(token), token)

    def test_non_canonical_representations_are_refused(self):
        for token in ("", " ", "Background_Noise", "background noise", "9x", "b-n", "b.n", None):
            with self.subTest(token=token):
                with self.assertRaises(LectureAnalysisFindingError):
                    require_canonical_finding_type(token)


class ModelInvariantTests(unittest.TestCase):
    def _build(self, **overrides):
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
                _ADMISSION,
                payload["finding_type"],
                payload["evidence"],
                payload["range_start"],
                payload["range_end"],
            ),
            admission_id=_ADMISSION,
            **payload,
        )

    def test_valid_finding_round_trips(self):
        finding = self._build(confidence=0.25, range_start=1.0, range_end=2.0)
        self.assertTrue(finding.has_source_range)
        self.assertEqual(finding.finding_contract_version, FINDING_CONTRACT_VERSION)

    def test_zero_duration_range_is_structurally_valid(self):
        self.assertTrue(self._build(range_start=1.0, range_end=1.0).has_source_range)

    def test_empty_evidence_is_refused(self):
        for value in ("", "   ", "\n"):
            with self.subTest(value=value):
                with self.assertRaises(LectureAnalysisFindingError):
                    self._build(evidence=value)

    def test_confidence_bounds_are_enforced(self):
        for value in (-0.01, 1.01, float("nan"), float("inf"), True):
            with self.subTest(value=value):
                with self.assertRaises(LectureAnalysisFindingError):
                    self._build(confidence=value)

    def test_uncertainty_bounds_are_enforced(self):
        with self.assertRaises(LectureAnalysisFindingError):
            self._build(uncertainty=1.5)

    def test_partial_range_is_refused(self):
        with self.assertRaises(LectureAnalysisFindingError):
            self._build(range_start=1.0)
        with self.assertRaises(LectureAnalysisFindingError):
            self._build(range_end=1.0)

    def test_negative_and_inverted_ranges_are_refused(self):
        with self.assertRaises(LectureAnalysisFindingError):
            self._build(range_start=-1.0, range_end=1.0)
        with self.assertRaises(LectureAnalysisFindingError):
            self._build(range_start=2.0, range_end=1.0)

    def test_non_finite_range_is_refused(self):
        with self.assertRaises(LectureAnalysisFindingError):
            self._build(range_start=0.0, range_end=float("inf"))

    def test_identity_must_derive_from_payload(self):
        with self.assertRaises(LectureAnalysisFindingError):
            LectureAnalysisFinding(
                identity=derive_finding_identity(_ADMISSION, "other_type", "잡음", None, None),
                admission_id=_ADMISSION,
                finding_type="background_noise",
                evidence="잡음",
            )

    def test_unsupported_contract_version_is_refused(self):
        with self.assertRaises(LectureAnalysisFindingError):
            LectureAnalysisFinding(
                identity=derive_finding_identity(_ADMISSION, "background_noise", "잡음", None, None),
                admission_id=_ADMISSION,
                finding_type="background_noise",
                evidence="잡음",
                finding_contract_version=2,
            )

    def test_model_carries_no_currentness_or_execution_state(self):
        finding = self._build()
        for forbidden in (
            "current", "stale", "active", "ready", "superseded", "valid_now",
            "run_id", "unit_execution_id", "domain_result_id", "processing_run_id",
            "source_input_id", "provider", "model", "prompt",
        ):
            with self.subTest(field=forbidden):
                self.assertFalse(hasattr(finding, forbidden))


class LectureAnalysisFindingServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"finding \x00\x01")
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
        self.findings = compose_sqlite_lecture_analysis_finding_service(self.connection)
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
            "SELECT COUNT(*) FROM lecture_analysis_findings"
        ).fetchone()[0]

    def _admit(self, **overrides):
        payload = {
            "admission_id": self.admission.identity.value,
            "finding_type": "background_noise",
            "evidence": "잡음",
        }
        payload.update(overrides)
        return self.findings.admit(**payload)

    # -- anchoring ---------------------------------------------------------------------------

    def test_finding_anchors_to_admission_and_records_no_duplicate_provenance(self):
        result = self._admit()
        self.assertEqual(result.outcome.value, "recorded")
        self.assertEqual(result.finding.admission_id, self.admission.identity)
        self.assertEqual(self._count(), 1)
        row = self.connection.execute(
            "SELECT * FROM lecture_analysis_findings"
        ).fetchone()
        columns = [
            d[0] for d in self.connection.execute(
                "SELECT * FROM lecture_analysis_findings"
            ).description
        ]
        self.assertNotIn("source_media_id", columns)
        self.assertNotIn("corrected_revision_id", columns)
        self.assertNotIn("content_fingerprint", columns)
        self.assertNotIn("transcript_source_intake_id", columns)
        self.assertIsNotNone(row)

    def test_one_admission_anchors_many_findings(self):
        self._admit(evidence="a")
        self._admit(evidence="b")
        self.assertEqual(len(self.findings.list_for_admission(self.admission.identity.value)), 2)

    # -- admission standing ------------------------------------------------------------------

    def test_current_admission_is_accepted(self):
        self.assertEqual(self._admit().outcome.value, "recorded")

    def test_superseded_admission_is_refused_and_writes_nothing(self):
        self._admit()
        self._revise("c2", "교정 2")
        self.assertIs(
            self.admissions.authority_match(self.admission),
            AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE,
        )
        with self.assertRaises(AnalysisFindingAnchorNotAdmissibleError):
            self._admit(evidence="새 근거")
        self.assertEqual(self._count(), 1)

    def test_current_authority_ineligible_admission_is_refused(self):
        self._admit()
        # Return the intake to raw-only authority: an explicit raw fallback supersedes the
        # corrected selection, so the current authority is no longer analysis-admissible.
        self.selection.select_raw_fallback(intake_id=self.intake, reviewer="s:kim")
        self.assertIs(
            self.admissions.authority_match(self.admission),
            AdmissionAuthorityMatch.CURRENT_AUTHORITY_INELIGIBLE,
        )
        with self.assertRaises(AnalysisFindingAnchorNotAdmissibleError):
            self._admit(evidence="새 근거")
        self.assertEqual(self._count(), 1)

    def test_missing_admission_is_refused_before_standing(self):
        with self.assertRaises(LectureAnalysisFindingError):
            self._admit(admission_id="lecture-analysis-input:" + "f" * 64)
        self.assertEqual(self._count(), 0)

    def test_malformed_admission_identity_is_refused(self):
        for value in ("", "nope", "lecture-analysis-input:short"):
            with self.subTest(value=value):
                with self.assertRaises(LectureAnalysisFindingError):
                    self._admit(admission_id=value)
        self.assertEqual(self._count(), 0)

    def test_returning_authority_restores_admissibility(self):
        first = self._admit()
        revision_2 = self._revise("c2", "교정 2")
        with self.assertRaises(AnalysisFindingAnchorNotAdmissibleError):
            self._admit()
        self.selection.select_revision(revision_id=self.revision_1, reviewer="s:kim")
        again = self._admit()
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(again.finding.identity, first.finding.identity)
        self.assertNotEqual(revision_2, self.revision_1)

    # -- payload validation ------------------------------------------------------------------

    def test_invalid_payloads_are_refused_before_any_write(self):
        cases = (
            {"finding_type": ""},
            {"finding_type": "Bad Type"},
            {"evidence": "   "},
            {"confidence": 1.5},
            {"uncertainty": -0.5},
            {"range_start": 1.0},
            {"range_start": 2.0, "range_end": 1.0},
            {"range_start": -1.0, "range_end": 1.0},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(LectureAnalysisFindingError):
                    self._admit(**overrides)
        self.assertEqual(self._count(), 0)

    def test_single_range_is_supported_and_optional(self):
        located = self._admit(finding_type="speaker_overlap", evidence="겹침",
                              range_start=0.5, range_end=1.5)
        self.assertTrue(located.finding.has_source_range)
        self.assertFalse(self._admit(evidence="비위치").finding.has_source_range)

    def test_admit_accepts_no_multi_range_argument(self):
        with self.assertRaises(TypeError):
            self.findings.admit(
                admission_id=self.admission.identity.value,
                finding_type="t", evidence="e", ranges=[(0.0, 1.0), (2.0, 3.0)],
            )

    # -- replay and conflict -----------------------------------------------------------------

    def test_exact_replay_reuses_without_new_row(self):
        first = self._admit(confidence=0.5)
        again = self._admit(confidence=0.5)
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(again.finding.identity, first.finding.identity)
        self.assertEqual(self._count(), 1)

    def test_divergent_recorded_payload_conflicts(self):
        self._admit(confidence=0.5)
        with self.assertRaises(AnalysisFindingConflictError):
            self._admit(confidence=0.9)
        with self.assertRaises(AnalysisFindingConflictError):
            self._admit(confidence=0.5, uncertainty=0.2)
        self.assertEqual(self._count(), 1)

    def test_distinct_content_creates_distinct_findings(self):
        base = self._admit()
        for overrides in (
            {"finding_type": "speaker_overlap"},
            {"evidence": "다른 근거"},
            {"range_start": 0.0, "range_end": 1.0},
        ):
            with self.subTest(overrides=overrides):
                other = self._admit(**overrides)
                self.assertNotEqual(other.finding.identity, base.finding.identity)
        self.assertEqual(self._count(), 4)

    def test_different_admission_creates_distinct_finding(self):
        first = self._admit()
        self._revise("c2", "교정 2")
        second_admission = self.admissions.admit(intake_id=self.intake).admission
        self.assertNotEqual(second_admission.identity, self.admission.identity)
        other = self._admit(admission_id=second_admission.identity.value)
        self.assertNotEqual(other.finding.identity, first.finding.identity)


    def test_concurrent_identical_admission_converges(self):
        """The collision-convergence branch: a racing caller's existence check misses the
        committed row, the insert collides, and the command converges instead of duplicating
        or failing (042 §8.2 D-9)."""

        from lectureos.application.lecture_analysis_finding import (
            LectureAnalysisFindingService,
        )

        class _StaleQuery:
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

        first = self._admit(confidence=0.5)
        racing = LectureAnalysisFindingService(
            self.findings._admissions,
            _StaleQuery(self.findings._findings),
            self.findings._persistence,
        )
        raced = racing.admit(
            admission_id=self.admission.identity.value,
            finding_type="background_noise",
            evidence="잡음",
            confidence=0.5,
        )
        self.assertEqual(raced.outcome.value, "reused")
        self.assertEqual(raced.finding.identity, first.finding.identity)
        self.assertEqual(self._count(), 1)

    def test_concurrent_divergent_payload_still_conflicts(self):
        """Losing the insert race must not turn a divergent payload into a silent reuse."""

        from lectureos.application.lecture_analysis_finding import (
            LectureAnalysisFindingService,
        )

        class _StaleQuery:
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

        self._admit(confidence=0.5)
        racing = LectureAnalysisFindingService(
            self.findings._admissions,
            _StaleQuery(self.findings._findings),
            self.findings._persistence,
        )
        with self.assertRaises(AnalysisFindingConflictError):
            racing.admit(
                admission_id=self.admission.identity.value,
                finding_type="background_noise",
                evidence="잡음",
                confidence=0.9,
            )
        self.assertEqual(self._count(), 1)

    def test_integer_range_and_confidence_normalize_to_canonical_floats(self):
        """An int-valued range must not mint a second identity: the column has REAL affinity,
        so a non-normalized int would store as a float whose identity no longer re-derives,
        permanently bricking reads of that row in an insert-only table."""

        integral = self._admit(finding_type="speaker_overlap", evidence="겹침",
                               range_start=1, range_end=2, confidence=1)
        self.assertEqual(integral.finding.range_start, 1.0)
        self.assertEqual(integral.finding.confidence, 1.0)
        stored = self.connection.execute(
            "SELECT typeof(range_start), typeof(range_end), typeof(confidence) "
            "FROM lecture_analysis_findings WHERE identity = ?",
            (integral.finding.identity.value,),
        ).fetchone()
        self.assertEqual(stored, ("real", "real", "real"))
        # The row remains readable, and the float spelling of the same range converges.
        self.assertEqual(self.findings.get(integral.finding.identity.value), integral.finding)
        again = self._admit(finding_type="speaker_overlap", evidence="겹침",
                            range_start=1.0, range_end=2.0, confidence=1.0)
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(again.finding.identity, integral.finding.identity)

    def test_canonical_finding_type_rule_agrees_across_layers(self):
        """The token rule is stated in three places; they must not drift apart."""

        from lectureos.application import analysis_finding as legacy
        from lectureos.application import lecture_analysis_finding as current
        from lectureos.validation import repository_validator as validator

        self.assertEqual(
            current._FINDING_TYPE_PATTERN.pattern, legacy._FINDING_TYPE_PATTERN.pattern
        )
        self.assertEqual(
            current._FINDING_TYPE_PATTERN.pattern, validator._CANONICAL_FINDING_TYPE.pattern
        )

    # -- immutability and history ------------------------------------------------------------

    def test_existing_finding_unchanged_after_authority_change(self):
        first = self._admit(confidence=0.5)
        self._revise("c2", "교정 2")
        self.assertEqual(self.findings.get(first.finding.identity.value), first.finding)

    def test_anchor_status_is_derived_never_stored(self):
        first = self._admit()
        self.assertIs(self.findings.anchor_status(first.finding), AdmissionAuthorityMatch.CURRENT)
        self._revise("c2", "교정 2")
        self.assertIs(
            self.findings.anchor_status(first.finding),
            AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE,
        )
        columns = [
            row[1] for row in self.connection.execute(
                "PRAGMA table_info(lecture_analysis_findings)"
            )
        ]
        for forbidden in ("current", "stale", "active", "ready", "superseded", "valid_now"):
            self.assertNotIn(forbidden, columns)

    def test_repository_exposes_no_update_or_delete(self):
        from lectureos.persistence.lecture_analysis_finding import (
            SQLiteLectureAnalysisFindingRepository,
        )

        repository = SQLiteLectureAnalysisFindingRepository(self.connection)
        for forbidden in ("update", "delete", "remove", "save", "upsert"):
            self.assertFalse(hasattr(repository, forbidden))

    def test_restart_reconstructs_identically(self):
        first = self._admit(confidence=0.5, range_start=0.0, range_end=1.0)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            service = compose_sqlite_lecture_analysis_finding_service(reopened)
            self.assertEqual(service.get(first.finding.identity.value), first.finding)
        finally:
            reopened.close()
        self.connection = initialize_sqlite_database(self.database)

    # -- isolation ---------------------------------------------------------------------------

    def test_no_execution_legacy_or_downstream_row_is_created(self):
        self._admit(confidence=0.5)
        for table in (
            "analysis_findings", "eligible_analysis_inputs", "processing_runs",
            "unit_executions", "processing_units", "lecture_segments", "edit_candidates",
        ):
            with self.subTest(table=table):
                self.assertEqual(
                    self.connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0],
                    0,
                )

    def test_finding_admission_creates_no_domain_result(self):
        # The upstream released transcript chain legitimately owns DomainResults; this
        # generation's finding admission adds none of its own (042 §8.2 D-6).
        def _domain_results():
            return self.connection.execute(
                "SELECT COUNT(*) FROM domain_result_references"
            ).fetchone()[0]

        before = _domain_results()
        self._admit(confidence=0.5)
        self._admit(evidence="또 다른 근거")
        self.assertEqual(_domain_results(), before)


if __name__ == "__main__":
    unittest.main()
