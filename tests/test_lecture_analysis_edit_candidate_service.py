"""Application tests for effective-generation Edit Candidates (042 §9.3 / PATCH-0032, GOAL-027)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.identities import LectureAnalysisFindingId
from lectureos.application.lecture_analysis_edit_candidate import (
    CANDIDATE_CONTRACT_VERSION,
    EditCandidateAnchorNotAdmissibleError,
    EditCandidateConflictError,
    LectureAnalysisEditCandidate,
    LectureAnalysisEditCandidateError,
    LectureAnalysisEditCandidateService,
    derive_candidate_identity,
    normalize_range,
    require_canonical_candidate_id,
    require_canonical_candidate_type,
    require_rationale,
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
    compose_sqlite_lecture_analysis_edit_candidate_service,
    compose_sqlite_lecture_analysis_finding_service,
    compose_sqlite_lecture_analysis_input_admission_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository

_FINDING = LectureAnalysisFindingId("lecture-analysis-finding:" + "a" * 64)
_OTHER = LectureAnalysisFindingId("lecture-analysis-finding:" + "b" * 64)
_RATIONALE = "이 구간은 사람이 검토할 만하다"


class IdentityTests(unittest.TestCase):
    def _id(self, finding=_FINDING, ctype="non_lecture_region", start=0.0, end=1.0,
            rationale=_RATIONALE):
        return derive_candidate_identity(finding, ctype, start, end, rationale)

    def test_identity_is_deterministic_and_prefixed(self):
        self.assertEqual(self._id(), self._id())
        self.assertTrue(self._id().value.startswith("lecture-analysis-edit-candidate:"))
        self.assertEqual(
            len(self._id().value), len("lecture-analysis-edit-candidate:") + 64
        )

    def test_finding_anchor_participates(self):
        self.assertNotEqual(self._id(), self._id(finding=_OTHER))

    def test_candidate_type_participates(self):
        self.assertNotEqual(self._id(), self._id(ctype="delivery_concern"))

    def test_range_participates(self):
        self.assertNotEqual(self._id(), self._id(end=2.0))
        self.assertNotEqual(self._id(), self._id(start=0.5))

    def test_rationale_participates(self):
        # A different reason is a different proposal; it must never converge onto one record.
        self.assertNotEqual(self._id(), self._id(rationale="다른 이유"))

    def test_rationale_is_not_normalized(self):
        self.assertNotEqual(self._id(), self._id(rationale=_RATIONALE + " "))

    def test_integral_and_negative_zero_spellings_converge(self):
        self.assertEqual(self._id(start=0, end=1), self._id(start=0.0, end=1.0))
        self.assertEqual(self._id(start=-0.0), self._id(start=0.0))

    def test_identity_carries_nothing_volatile(self):
        self.assertEqual(self._id().value, self._id().value)

    def test_malformed_identity_is_refused(self):
        for value in ("", "nope", "lecture-analysis-edit-candidate:short",
                      "lecture-analysis-finding:" + "a" * 64):
            with self.subTest(value=value):
                with self.assertRaises(LectureAnalysisEditCandidateError):
                    require_canonical_candidate_id(value)


class CandidateTypeTests(unittest.TestCase):
    def test_open_vocabulary_accepts_any_canonical_token(self):
        # 042 §9.1 keeps Candidate Type an OPEN key. §9.2's three-key first-slice registry is a
        # legacy provider-slice constraint that PATCH-0032 C-13 did not re-scope, so tokens
        # outside it must be admissible here.
        for token in ("non_lecture_region", "redundant_restatement", "delivery_concern",
                      "some_future_unregistered_type", "a", "x9_y"):
            with self.subTest(token=token):
                self.assertEqual(require_canonical_candidate_type(token), token)

    def test_non_canonical_representations_are_refused(self):
        for token in ("", " ", "Non_Lecture", "non lecture", "9x", "a-b", "a.b", None):
            with self.subTest(token=token):
                with self.assertRaises(LectureAnalysisEditCandidateError):
                    require_canonical_candidate_type(token)


class RationaleTests(unittest.TestCase):
    def test_non_empty_accepted_verbatim(self):
        self.assertEqual(require_rationale("  이유  "), "  이유  ")

    def test_empty_refused(self):
        for value in ("", "   ", "\n", None, 3):
            with self.subTest(value=value):
                with self.assertRaises(LectureAnalysisEditCandidateError):
                    require_rationale(value)


class RangeTests(unittest.TestCase):
    def test_canonical_floats_returned(self):
        self.assertEqual(normalize_range(1, 2), (1.0, 2.0))
        self.assertEqual(normalize_range(-0.0, 1.0), (0.0, 1.0))

    def test_zero_duration_is_structurally_valid(self):
        self.assertEqual(normalize_range(1.5, 1.5), (1.5, 1.5))

    def test_whole_recording_range_is_valid(self):
        self.assertEqual(normalize_range(0.0, 99999.0), (0.0, 99999.0))

    def test_invalid_ranges_refused(self):
        for start, end in ((2.0, 1.0), (-1.0, 1.0), (0.0, -1.0), (float("nan"), 1.0),
                           (0.0, float("inf")), (0.0, float("-inf"))):
            with self.subTest(start=start, end=end):
                with self.assertRaises(LectureAnalysisEditCandidateError):
                    normalize_range(start, end)

    def test_out_of_representable_range_stays_in_the_error_family(self):
        with self.assertRaises(LectureAnalysisEditCandidateError):
            normalize_range(0, 10 ** 400)

    def test_non_numeric_and_bool_refused(self):
        for value in ("1.0", None, True):
            with self.subTest(value=value):
                with self.assertRaises(LectureAnalysisEditCandidateError):
                    normalize_range(value, 1.0)


class ModelInvariantTests(unittest.TestCase):
    def _build(self, ctype="non_lecture_region", start=0.0, end=1.0, rationale=_RATIONALE,
               **overrides):
        return LectureAnalysisEditCandidate(
            identity=derive_candidate_identity(_FINDING, ctype, start, end, rationale),
            finding_id=_FINDING,
            candidate_type=ctype,
            range_start=start,
            range_end=end,
            rationale=rationale,
            **overrides,
        )

    def test_valid_candidate_round_trips(self):
        candidate = self._build(start=1, end=2)
        self.assertEqual(candidate.range_start, 1.0)
        self.assertEqual(candidate.candidate_contract_version, CANDIDATE_CONTRACT_VERSION)

    def test_identity_must_derive_from_payload(self):
        with self.assertRaises(LectureAnalysisEditCandidateError):
            LectureAnalysisEditCandidate(
                identity=derive_candidate_identity(_FINDING, "other", 0.0, 1.0, _RATIONALE),
                finding_id=_FINDING, candidate_type="non_lecture_region",
                range_start=0.0, range_end=1.0, rationale=_RATIONALE,
            )

    def test_unsupported_contract_version_refused(self):
        with self.assertRaises(LectureAnalysisEditCandidateError):
            self._build(candidate_contract_version=2)

    def test_model_carries_no_ordinal_review_selection_or_execution_state(self):
        candidate = self._build()
        for forbidden in (
            "sequence", "ordinal", "order", "current", "stale", "active", "ready",
            "superseded", "valid_now", "selected", "accepted", "rejected", "review_status",
            "run_id", "unit_execution_id", "domain_result_id", "processing_run_id",
            "admission_id", "source_media_id", "source_timeline_id", "segment_id",
            "provider", "model", "prompt", "created_at",
        ):
            with self.subTest(field=forbidden):
                self.assertFalse(hasattr(candidate, forbidden))


class LectureAnalysisEditCandidateServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"candidate \x00\x01")
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
        self.findings = compose_sqlite_lecture_analysis_finding_service(self.connection)
        self.candidates = compose_sqlite_lecture_analysis_edit_candidate_service(
            self.connection
        )
        self.revision_1 = self._revise("c1", "교정 1")
        self.admission = self.admissions.admit(intake_id=self.intake).admission
        self.finding = self.findings.admit(
            admission_id=self.admission.identity.value,
            finding_type="non_lecture_speech",
            evidence="수업과 무관한 발화가 관찰된다",
        ).finding

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
            "SELECT COUNT(*) FROM lecture_analysis_edit_candidates"
        ).fetchone()[0]

    _DEFAULT = object()

    def _admit(self, finding=_DEFAULT, **overrides):
        if finding is self._DEFAULT:
            finding = self.finding.identity.value
        payload = {
            "finding_id": finding,
            "candidate_type": "non_lecture_region",
            "range_start": 0.0,
            "range_end": 1.0,
            "rationale": _RATIONALE,
        }
        payload.update(overrides)
        return self.candidates.admit_edit_candidate(**payload)

    # -- anchoring -------------------------------------------------------------------------

    def test_candidate_anchors_finding_without_duplicating_provenance(self):
        result = self._admit()
        self.assertEqual(result.outcome.value, "recorded")
        self.assertEqual(result.candidate.finding_id, self.finding.identity)
        columns = [
            row[1] for row in self.connection.execute(
                "PRAGMA table_info(lecture_analysis_edit_candidates)"
            )
        ]
        for absent in ("admission_id", "source_media_id", "source_timeline_id",
                       "corrected_revision_id", "domain_result_id", "processing_run_id",
                       "unit_execution_id", "segment_id", "sequence", "review_status"):
            self.assertNotIn(absent, columns)

    def test_no_segment_is_required_or_created(self):
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_analysis_segments"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(self._admit().outcome.value, "recorded")
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_analysis_segments"
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
        self._admit(range_end=2.0)
        self.assertEqual(_domain_results(), before)

    def test_one_finding_grounds_many_candidates(self):
        self._admit()
        self._admit(candidate_type="delivery_concern")
        self.assertEqual(
            len(self.candidates.list_for_finding(self.finding.identity.value)), 2
        )

    # -- chain standing --------------------------------------------------------------------

    def test_current_chain_accepted(self):
        self.assertEqual(self._admit().outcome.value, "recorded")

    def test_superseded_chain_refused_writing_nothing(self):
        self._admit()
        self._revise("c2", "교정 2")
        with self.assertRaises(EditCandidateAnchorNotAdmissibleError):
            self._admit(range_end=2.0)
        self.assertEqual(self._count(), 1)

    def test_current_authority_ineligible_chain_refused(self):
        self._admit()
        self.selection.select_raw_fallback(intake_id=self.intake, reviewer="s:kim")
        with self.assertRaises(EditCandidateAnchorNotAdmissibleError):
            self._admit(range_end=2.0)
        self.assertEqual(self._count(), 1)

    def test_missing_and_malformed_finding_refused(self):
        for finding in ("lecture-analysis-finding:" + "f" * 64, "nope", ""):
            with self.subTest(finding=finding):
                with self.assertRaises(LectureAnalysisEditCandidateError):
                    self._admit(finding=finding)
        self.assertEqual(self._count(), 0)

    def test_returning_authority_restores_admissibility(self):
        first = self._admit()
        self._revise("c2", "교정 2")
        with self.assertRaises(EditCandidateAnchorNotAdmissibleError):
            self._admit()
        self.selection.select_revision(revision_id=self.revision_1, reviewer="s:kim")
        again = self._admit()
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(again.candidate.identity, first.candidate.identity)

    # -- payload ---------------------------------------------------------------------------

    def test_invalid_payloads_refused_before_any_write(self):
        for bad in ({"range_start": 1.0, "range_end": 0.0}, {"range_start": -1.0},
                    {"range_end": float("nan")}, {"range_end": float("inf")},
                    {"rationale": "   "}, {"candidate_type": "Bad Type"},
                    {"candidate_type": ""}):
            with self.subTest(bad=bad):
                with self.assertRaises(LectureAnalysisEditCandidateError):
                    self._admit(**bad)
        self.assertEqual(self._count(), 0)

    def test_zero_duration_and_whole_recording_accepted(self):
        self.assertEqual(self._admit(range_start=1.0, range_end=1.0).outcome.value, "recorded")
        self.assertEqual(self._admit(range_end=99999.0).outcome.value, "recorded")

    def test_no_extent_or_containment_validation_is_applied(self):
        # The transcript spans 0..2 and the Finding carries no range; a candidate far beyond it
        # is valid — 042 §9.3 C-9 forbids adding extent or containment validation here.
        self.assertEqual(
            self._admit(range_start=500.0, range_end=900.0).outcome.value, "recorded"
        )

    def test_integral_and_negative_zero_ranges_round_trip(self):
        first = self._admit(range_start=0, range_end=1)
        stored = self.connection.execute(
            "SELECT typeof(range_start), typeof(range_end) "
            "FROM lecture_analysis_edit_candidates"
        ).fetchone()
        self.assertEqual(stored, ("real", "real"))
        self.assertEqual(
            self.candidates.get(first.candidate.identity.value), first.candidate
        )
        for spelling in ({"range_start": 0.0, "range_end": 1.0},
                         {"range_start": -0.0, "range_end": 1.0}):
            with self.subTest(spelling=spelling):
                again = self._admit(**spelling)
                self.assertEqual(again.outcome.value, "reused")
                self.assertEqual(again.candidate.identity, first.candidate.identity)
        self.assertEqual(self._count(), 1)

    # -- replay, reprocessing, conflict ------------------------------------------------------

    def test_exact_replay_reuses_without_new_row(self):
        first = self._admit()
        again = self._admit()
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(again.candidate.identity, first.candidate.identity)
        self.assertEqual(self._count(), 1)

    def test_same_canonical_proposal_from_reprocessing_converges(self):
        """O-1 consequence, recorded deliberately: with no canonical ordinal, re-proposing the
        identical canonical candidate converges rather than preserving a second copy."""

        first = self._admit()
        for _ in range(3):
            self._admit()
        self.assertEqual(self._count(), 1)
        self.assertEqual(
            self.candidates.get(first.candidate.identity.value), first.candidate
        )

    def test_meaningfully_different_proposal_appends(self):
        base = self._admit()
        for overrides in ({"candidate_type": "delivery_concern"},
                          {"range_end": 2.0},
                          {"rationale": "다른 이유"}):
            with self.subTest(overrides=overrides):
                other = self._admit(**overrides)
                self.assertNotEqual(other.candidate.identity, base.candidate.identity)
        self.assertEqual(self._count(), 4)

    def test_different_finding_creates_distinct_candidate(self):
        first = self._admit()
        other_finding = self.findings.admit(
            admission_id=self.admission.identity.value,
            finding_type="speaker_overlap", evidence="겹침",
        ).finding
        other = self._admit(finding=other_finding.identity.value)
        self.assertNotEqual(other.candidate.identity, first.candidate.identity)

    def test_divergent_stored_payload_is_an_explicit_conflict(self):
        """Option B: unreachable through the command, so the guard is driven with a tampering
        stub — removing it because the happy path cannot reach it would trade an integrity
        guarantee for nothing."""

        first = self._admit()
        tampered = LectureAnalysisEditCandidate.__new__(LectureAnalysisEditCandidate)
        for field, value in (
            ("identity", first.candidate.identity),
            ("finding_id", first.candidate.finding_id),
            ("candidate_type", "non_lecture_region"),
            ("range_start", 0.0),
            ("range_end", 5.0),  # divergent
            ("rationale", _RATIONALE),
            ("candidate_contract_version", 1),
        ):
            object.__setattr__(tampered, field, value)

        class _TamperedQuery:
            def __init__(self, inner, fake):
                self._inner = inner
                self._fake = fake

            def __getattr__(self, name):
                return getattr(self._inner, name)

            def get(self, identity):
                return self._fake

        service = LectureAnalysisEditCandidateService(
            self.candidates._findings,
            _TamperedQuery(self.candidates._candidates, tampered),
            self.candidates._persistence,
        )
        with self.assertRaises(EditCandidateConflictError):
            service.admit_edit_candidate(
                finding_id=self.finding.identity.value,
                candidate_type="non_lecture_region",
                range_start=0.0, range_end=1.0, rationale=_RATIONALE,
            )
        self.assertEqual(self._count(), 1)

    def test_concurrent_identical_admission_converges(self):
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

        first = self._admit()
        racing = LectureAnalysisEditCandidateService(
            self.candidates._findings,
            _StaleQuery(self.candidates._candidates),
            self.candidates._persistence,
        )
        raced = racing.admit_edit_candidate(
            finding_id=self.finding.identity.value,
            candidate_type="non_lecture_region",
            range_start=0.0, range_end=1.0, rationale=_RATIONALE,
        )
        self.assertEqual(raced.outcome.value, "reused")
        self.assertEqual(raced.candidate.identity, first.candidate.identity)
        self.assertEqual(self._count(), 1)

    # -- immutability and history ------------------------------------------------------------

    def test_existing_candidate_unchanged_after_authority_change(self):
        first = self._admit()
        self._revise("c2", "교정 2")
        self.assertEqual(
            self.candidates.get(first.candidate.identity.value), first.candidate
        )

    def test_anchor_status_is_derived_never_stored(self):
        first = self._admit()
        self.assertIs(
            self.candidates.anchor_status(first.candidate), AdmissionAuthorityMatch.CURRENT
        )
        self._revise("c2", "교정 2")
        self.assertIs(
            self.candidates.anchor_status(first.candidate),
            AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE,
        )
        columns = [
            row[1] for row in self.connection.execute(
                "PRAGMA table_info(lecture_analysis_edit_candidates)"
            )
        ]
        for forbidden in ("current", "stale", "active", "ready", "superseded",
                          "selected", "accepted", "rejected"):
            self.assertNotIn(forbidden, columns)

    def test_repository_exposes_no_update_or_delete(self):
        from lectureos.persistence.lecture_analysis_edit_candidate import (
            SQLiteLectureAnalysisEditCandidateRepository,
        )

        repository = SQLiteLectureAnalysisEditCandidateRepository(self.connection)
        for forbidden in ("update", "delete", "remove", "save", "upsert"):
            self.assertFalse(hasattr(repository, forbidden))

    def test_restart_reconstructs_identically(self):
        first = self._admit(range_start=1, range_end=2)
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            service = compose_sqlite_lecture_analysis_edit_candidate_service(reopened)
            self.assertEqual(service.get(first.candidate.identity.value), first.candidate)
        finally:
            reopened.close()
        self.connection = initialize_sqlite_database(self.database)

    # -- isolation ---------------------------------------------------------------------------

    def test_no_execution_legacy_or_downstream_row_is_created(self):
        self._admit()
        for table in (
            "edit_candidates", "analysis_findings", "eligible_analysis_inputs",
            "lecture_segments", "lecture_analysis_segments", "processing_runs",
            "unit_executions", "processing_units", "edit_review_decisions",
            "approved_edit_decisions",
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
