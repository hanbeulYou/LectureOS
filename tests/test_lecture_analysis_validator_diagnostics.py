"""Repository-validator diagnostics for the effective-generation analysis graph.

Covers the integrity checks added by GOAL-025 (Analysis Finding), GOAL-026 (Lecture Segmentation),
and GOAL-027 (Edit Candidate). Those checks previously had **no** test at all in any of the three
milestones, which is why a defect in one of them — a probe whose condition the schema's own foreign
key already makes unreachable — was only caught by manual review. Each check here is driven by a
targeted corruption injected with foreign keys disabled, plus the healthy and
historical-but-superseded baselines that must never be flagged.
"""

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
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_lecture_analysis_edit_candidate_service,
    compose_sqlite_lecture_analysis_finding_service,
    compose_sqlite_lecture_analysis_input_admission_service,
    compose_sqlite_lecture_analysis_segmentation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository
from lectureos.validation import validate_database


class AnalysisGraphValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"validator \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(
            str(source)
        ).record
        self.intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            self.intake, raw.raw_transcript_id.value
        )
        self.connection = connection
        self.raw = raw
        self.selection = compose_sqlite_corrected_revision_selection_service(connection)
        self.revision_1 = self._revise("c1", "교정 1")
        admission = compose_sqlite_lecture_analysis_input_admission_service(
            connection
        ).admit(intake_id=self.intake).admission
        self.finding = compose_sqlite_lecture_analysis_finding_service(connection).admit(
            admission_id=admission.identity.value,
            finding_type="non_lecture_speech",
            evidence="관찰",
            range_start=0.0,
            range_end=1.0,
        ).finding
        compose_sqlite_lecture_analysis_segmentation_service(connection).admit_segmentation(
            admission_id=admission.identity.value, ranges=[(0.0, 1.0), (1.0, 2.0)]
        )
        self.candidate = compose_sqlite_lecture_analysis_edit_candidate_service(
            connection
        ).admit_edit_candidate(
            finding_id=self.finding.identity.value,
            candidate_type="non_lecture_region",
            range_start=0.0,
            range_end=1.0,
            rationale="사람이 검토할 만하다",
        ).candidate
        connection.close()

    def tearDown(self):
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

    # -- helpers ---------------------------------------------------------------------------

    def _corrupt(self, statement, parameters=()):
        """Apply one out-of-band edit with foreign keys off, mirroring a tampered repository."""

        connection = sqlite3.connect(self.database, isolation_level=None)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute(statement, parameters)
        finally:
            connection.close()

    def _codes(self):
        report = validate_database(str(self.database))
        return report.health.value, sorted({d.code for d in report.diagnostics})

    def _assert_flags(self, code):
        health, codes = self._codes()
        self.assertEqual(health, "errors")
        self.assertIn(code, codes)

    # -- baselines that must never be flagged ------------------------------------------------

    def test_healthy_graph_is_clean(self):
        health, codes = self._codes()
        self.assertEqual(health, "healthy", codes)
        self.assertEqual(codes, [])

    def test_superseded_chain_is_never_corruption(self):
        # Authority moves on: the admission, its finding, its segments, and its candidate all
        # become historical. None of that is corruption (042 §8.2 D-5, §7.2 S-6, §9.3 C-6).
        self.connection = sqlite3.connect(self.database, isolation_level=None)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        self._revise("c2", "교정 2")
        self.connection.close()
        health, codes = self._codes()
        self.assertEqual(health, "healthy", codes)

    # -- Edit Candidate checks (GOAL-027) ----------------------------------------------------

    def test_candidate_identity_mismatch_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_analysis_edit_candidates SET range_end = 5.0 WHERE identity = ?",
            (self.candidate.identity.value,),
        )
        self._assert_flags("LECTURE_ANALYSIS_EDIT_CANDIDATE_IDENTITY_MISMATCH")

    def test_candidate_anchor_missing_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_analysis_edit_candidates SET finding_id = ? WHERE identity = ?",
            ("lecture-analysis-finding:" + "9" * 64, self.candidate.identity.value),
        )
        self._assert_flags("LECTURE_ANALYSIS_EDIT_CANDIDATE_ANCHOR_MISSING")

    def test_candidate_type_malformed_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_analysis_edit_candidates SET candidate_type = 'Bad Type' "
            "WHERE identity = ?",
            (self.candidate.identity.value,),
        )
        self._assert_flags("LECTURE_ANALYSIS_EDIT_CANDIDATE_TYPE_MALFORMED")

    def test_candidate_range_not_canonical_is_flagged(self):
        # A non-float bound cannot have been produced by the Application boundary; it means the
        # stored value was written out of band.
        self._corrupt(
            "UPDATE lecture_analysis_edit_candidates SET range_end = 'x' WHERE identity = ?",
            (self.candidate.identity.value,),
        )
        self._assert_flags("LECTURE_ANALYSIS_EDIT_CANDIDATE_RANGE_NOT_CANONICAL")

    def test_candidate_legacy_anchor_leak_probe_is_defence_in_depth_only(self):
        """The v50 foreign key already makes a non-current-generation anchor impossible, so this
        probe cannot fire on a normally written database.

        It is documented as defence-in-depth rather than as a contract guarantee. This test pins
        that reading: a genuine legacy anchor is refused by the FK, so the probe is unreachable
        through any supported path.
        """

        connection = sqlite3.connect(self.database, isolation_level=None)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE lecture_analysis_edit_candidates SET finding_id = 'finding-0' "
                    "WHERE identity = ?",
                    (self.candidate.identity.value,),
                )
        finally:
            connection.close()
        health, _ = self._codes()
        self.assertEqual(health, "healthy")

    # -- Analysis Finding checks (GOAL-025) --------------------------------------------------

    def test_finding_identity_mismatch_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_analysis_findings SET evidence = '조작된 근거' WHERE identity = ?",
            (self.finding.identity.value,),
        )
        self._assert_flags("LECTURE_ANALYSIS_FINDING_IDENTITY_MISMATCH")

    def test_finding_anchor_missing_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_analysis_findings SET admission_id = ? WHERE identity = ?",
            ("lecture-analysis-input:" + "9" * 64, self.finding.identity.value),
        )
        self._assert_flags("LECTURE_ANALYSIS_FINDING_ANCHOR_MISSING")

    def test_segment_identity_mismatch_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_analysis_segments SET range_end = 7.0 WHERE sequence = 0"
        )
        self._assert_flags("LECTURE_ANALYSIS_SEGMENT_IDENTITY_MISMATCH")

    def test_segment_anchor_missing_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_analysis_segments SET admission_id = ?",
            ("lecture-analysis-input:" + "9" * 64,),
        )
        self._assert_flags("LECTURE_ANALYSIS_SEGMENT_ANCHOR_MISSING")

    def test_several_segments_sharing_a_sequence_is_never_corruption(self):
        # 042 §7.1 forbids canonical-set/uniqueness constraints, so independent batches may share
        # a sequence value. The validator must not treat that as corruption.
        connection = sqlite3.connect(self.database, isolation_level=None)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            shared = connection.execute(
                "SELECT COUNT(*) FROM lecture_analysis_segments WHERE sequence = 0"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertGreaterEqual(shared, 1)
        health, codes = self._codes()
        self.assertEqual(health, "healthy", codes)


    # -- where the schema is the first line of defence ---------------------------------------

    def test_schema_refuses_the_corruptions_its_checks_cover(self):
        """Several validator branches cannot be reached by SQL at all: the table CHECKs refuse the
        write, and CHECKs are unaffected by `PRAGMA foreign_keys = OFF`.

        Those branches are therefore **defence-in-depth for out-of-band writes** — a file produced
        by another tool, or a row written before a CHECK existed — not guards against anything a
        connected client can do. Pinning that split here keeps the implementation documents honest
        about which layer actually protects each invariant, and stops a future reader from assuming
        the validator is the only barrier.
        """

        cases = (
            ("candidate contract version",
             "UPDATE lecture_analysis_edit_candidates SET candidate_contract_version = 2"),
            ("candidate rationale",
             "UPDATE lecture_analysis_edit_candidates SET rationale = '   '"),
            ("candidate negative range",
             "UPDATE lecture_analysis_edit_candidates SET range_start = -1.0"),
            ("finding evidence",
             "UPDATE lecture_analysis_findings SET evidence = '  '"),
            ("finding confidence bounds",
             "UPDATE lecture_analysis_findings SET confidence = 1.5"),
            ("finding inverted range",
             "UPDATE lecture_analysis_findings SET range_start = 9.0"),
            ("segment sequence",
             "UPDATE lecture_analysis_segments SET sequence = -1"),
            ("segment non-numeric range",
             "UPDATE lecture_analysis_segments SET range_start = 'x'"),
            ("segment contract version",
             "UPDATE lecture_analysis_segments SET segment_contract_version = 3"),
        )
        for label, statement in cases:
            with self.subTest(case=label):
                with self.assertRaises(sqlite3.IntegrityError):
                    self._corrupt(statement)
        # Nothing was written, so the repository is still clean.
        health, codes = self._codes()
        self.assertEqual(health, "healthy", codes)

    def test_every_new_analysis_diagnostic_code_is_either_reached_or_schema_guarded(self):
        """Guard against a silently dead diagnostic.

        Each code added by GOAL-025/026/027 must be either exercised by a corruption test in this
        module or explicitly accounted for as schema-guarded / defence-in-depth. The list below is
        the accounting; adding a code without updating it fails this test.
        """

        from lectureos.validation import repository_validator as validator

        source = Path(validator.__file__).read_text(encoding="utf-8")
        declared = {
            code for code in
            __import__("re").findall(r"\"(LECTURE_ANALYSIS_(?:FINDING|SEGMENT|EDIT_CANDIDATE)_[A-Z_]+)\"", source)
        }
        reached_by_test = {
            "LECTURE_ANALYSIS_EDIT_CANDIDATE_IDENTITY_MISMATCH",
            "LECTURE_ANALYSIS_EDIT_CANDIDATE_ANCHOR_MISSING",
            "LECTURE_ANALYSIS_EDIT_CANDIDATE_TYPE_MALFORMED",
            "LECTURE_ANALYSIS_EDIT_CANDIDATE_RANGE_NOT_CANONICAL",
            "LECTURE_ANALYSIS_FINDING_IDENTITY_MISMATCH",
            "LECTURE_ANALYSIS_FINDING_ANCHOR_MISSING",
            "LECTURE_ANALYSIS_SEGMENT_IDENTITY_MISMATCH",
            "LECTURE_ANALYSIS_SEGMENT_ANCHOR_MISSING",
        }
        schema_guarded = {
            "LECTURE_ANALYSIS_EDIT_CANDIDATE_CONTRACT_VERSION_MISMATCH",
            "LECTURE_ANALYSIS_EDIT_CANDIDATE_RATIONALE_EMPTY",
            "LECTURE_ANALYSIS_EDIT_CANDIDATE_RANGE_INVALID",
            "LECTURE_ANALYSIS_EDIT_CANDIDATE_LEGACY_ANCHOR_LEAK",
            "LECTURE_ANALYSIS_FINDING_CONTRACT_VERSION_MISMATCH",
            "LECTURE_ANALYSIS_FINDING_TYPE_MALFORMED",
            "LECTURE_ANALYSIS_FINDING_EVIDENCE_EMPTY",
            "LECTURE_ANALYSIS_FINDING_RANGE_INVALID",
            "LECTURE_ANALYSIS_FINDING_CONFIDENCE_OUT_OF_RANGE",
            "LECTURE_ANALYSIS_SEGMENT_CONTRACT_VERSION_MISMATCH",
            "LECTURE_ANALYSIS_SEGMENT_SEQUENCE_INVALID",
            "LECTURE_ANALYSIS_SEGMENT_RANGE_NOT_CANONICAL",
            "LECTURE_ANALYSIS_SEGMENT_RANGE_INVALID",
        }
        self.assertEqual(
            declared - reached_by_test - schema_guarded,
            set(),
            "a new analysis diagnostic code is neither exercised nor accounted for",
        )


if __name__ == "__main__":
    unittest.main()
