"""Repository-validator diagnostics for the effective-generation analysis graph.

Covers the integrity checks added by GOAL-025 (Analysis Finding), GOAL-026 (Lecture Segmentation),
GOAL-027 (Edit Candidate), GOAL-028 (Review), and GOAL-029 (Review authority history). The first
three milestones shipped their checks with **no** test at all, which is why a defect in one of them
— a probe whose condition the schema's own foreign key already makes unreachable — was only caught
by manual review. Each check here is driven by a targeted corruption injected with foreign keys
disabled, plus the healthy and historical-but-superseded baselines that must never be flagged.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.lecture_review_authority import (
    derive_authority_position_identity,
)
from lectureos.application.lecture_review_decision import (
    ReviewDecisionKind,
    derive_review_decision_identity,
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
    compose_sqlite_lecture_review_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository
from lectureos.review.identities import HumanActorReference
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
        reviews = compose_sqlite_lecture_review_service(connection)
        self.accepted = reviews.admit_review_decision(
            candidate_id=self.candidate.identity.value,
            decision_kind="accept",
            actor="reviewer:lee",
        )
        self.rejected = reviews.admit_review_decision(
            candidate_id=self.candidate.identity.value,
            decision_kind="reject",
            actor="reviewer:lee",
        )
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

    # -- Review checks (GOAL-028) -------------------------------------------------------------

    def test_review_decision_identity_mismatch_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_review_decisions SET actor = 'reviewer:someone_else' "
            "WHERE identity = ?",
            (self.accepted.decision.identity.value,),
        )
        self._assert_flags("LECTURE_REVIEW_DECISION_IDENTITY_MISMATCH")

    def test_review_decision_anchor_missing_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_review_decisions SET candidate_id = ? WHERE identity = ?",
            ("lecture-analysis-edit-candidate:" + "9" * 64,
             self.accepted.decision.identity.value),
        )
        self._assert_flags("LECTURE_REVIEW_DECISION_ANCHOR_MISSING")

    def test_an_approving_decision_without_its_approval_is_flagged(self):
        """`§7.4`'s creation rule is structural: accept must own exactly one approval."""

        self._corrupt("DELETE FROM lecture_approved_edit_decisions")
        self._assert_flags("LECTURE_REVIEW_APPROVAL_CARDINALITY_INVALID")

    def test_a_reject_owning_an_approval_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_approved_edit_decisions SET review_decision_id = ?",
            (self.rejected.decision.identity.value,),
        )
        self._assert_flags("LECTURE_REVIEW_APPROVAL_CARDINALITY_INVALID")

    def test_approved_edit_decision_identity_mismatch_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_approved_edit_decisions SET approved_label = 'other_label'"
        )
        self._assert_flags("LECTURE_APPROVED_EDIT_DECISION_IDENTITY_MISMATCH")

    def test_approved_label_malformed_is_flagged(self):
        # The schema only requires a non-empty label, so a non-canonical token reaches the
        # validator: this is a real guard, not defence-in-depth.
        self._corrupt(
            "UPDATE lecture_approved_edit_decisions SET approved_label = 'Bad Label'"
        )
        self._assert_flags("LECTURE_APPROVED_EDIT_DECISION_LABEL_MALFORMED")

    def test_approved_range_not_canonical_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_approved_edit_decisions SET approved_range_end = 'x'"
        )
        self._assert_flags("LECTURE_APPROVED_EDIT_DECISION_RANGE_NOT_CANONICAL")

    def test_coexisting_contradictory_judgments_are_never_corruption(self):
        """R-9's recorded consequence: accept and reject on one candidate coexist as history.

        The validator must not adjudicate them, because current-selection is `§15.4`-deferred.
        """

        health, codes = self._codes()
        self.assertEqual(health, "healthy", codes)
        connection = sqlite3.connect(self.database, isolation_level=None)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM lecture_review_decisions WHERE candidate_id = ?",
                    (self.candidate.identity.value,),
                ).fetchone()[0],
                2,
            )
        finally:
            connection.close()

    def test_a_cross_generation_anchor_collision_is_flagged(self):
        """The legacy-leak probe is a real guard, not defence-in-depth.

        Legacy `edit_candidates` declares no foreign key and its identity is caller-owned free
        text, so one identity string can name a row in both generations while the v51 foreign key
        is still satisfied. Only the hash-derived prefix normally keeps them apart.
        """

        self._corrupt(
            """
            INSERT INTO edit_candidates VALUES (?, 'dr', 'f', 'm', 't', 'run', 'ue', 0,
                                                'legacy_type', 'legacy rationale', 0.0, 1.0)
            """,
            (self.candidate.identity.value,),
        )
        self._assert_flags("LECTURE_REVIEW_DECISION_LEGACY_ANCHOR_LEAK")

    def test_the_review_schema_refuses_these_corruptions_outright(self):
        """Defence-in-depth accounting: a CHECK refuses the write before any validator runs."""

        cases = (
            ("unknown decision kind",
             "UPDATE lecture_review_decisions SET decision_kind = 'approve'"),
            ("blank actor",
             "UPDATE lecture_review_decisions SET actor = '   '"),
            ("decision contract version",
             "UPDATE lecture_review_decisions SET review_contract_version = 2"),
            ("approved kind outside accept/modify",
             "UPDATE lecture_approved_edit_decisions SET approved_decision_kind = 'reject'"),
            ("empty approved label",
             "UPDATE lecture_approved_edit_decisions SET approved_label = ''"),
            ("blank approved rationale",
             "UPDATE lecture_approved_edit_decisions SET approved_rationale = '  '"),
            ("inverted approved range",
             "UPDATE lecture_approved_edit_decisions SET approved_range_start = 9.0, "
             "approved_range_end = 1.0"),
            ("negative approved bound",
             "UPDATE lecture_approved_edit_decisions SET approved_range_start = -1.0"),
            ("approved contract version",
             "UPDATE lecture_approved_edit_decisions SET approved_contract_version = 2"),
        )
        for label, statement in cases:
            with self.subTest(case=label):
                with self.assertRaises(sqlite3.IntegrityError):
                    self._corrupt(statement)
        health, codes = self._codes()
        self.assertEqual(health, "healthy", codes)

    # -- Review authority history checks (GOAL-029) -------------------------------------------

    def _position_id(self, sequence, actor="reviewer:lee"):
        return derive_authority_position_identity(
            self.candidate.identity, HumanActorReference(actor), sequence
        ).value

    def _other_actor_decision(self, actor="reviewer:park"):
        """A valid `reject` record for a second person — no approval, so nothing else flags."""

        identity = derive_review_decision_identity(
            self.candidate.identity, ReviewDecisionKind.REJECT, HumanActorReference(actor)
        ).value
        self._corrupt(
            "INSERT INTO lecture_review_decisions VALUES (?, ?, 'reject', ?, 1)",
            (identity, self.candidate.identity.value, actor),
        )
        return identity

    def test_the_recorded_authority_history_is_healthy(self):
        """setUp's accept → reject is two positions in one (candidate, actor) history."""

        health, codes = self._codes()
        self.assertEqual(health, "healthy", codes)
        connection = sqlite3.connect(self.database, isolation_level=None)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT sequence, review_decision_id FROM "
                    "lecture_review_authority_positions ORDER BY sequence"
                ).fetchall(),
                [(0, self.accepted.decision.identity.value),
                 (1, self.rejected.decision.identity.value)],
            )
        finally:
            connection.close()

    def test_authority_position_identity_mismatch_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_review_authority_positions SET identity = ? WHERE sequence = 1",
            ("lecture-review-authority-position:" + "9" * 64,),
        )
        self._assert_flags("LECTURE_REVIEW_AUTHORITY_POSITION_IDENTITY_MISMATCH")

    def test_authority_position_referencing_a_missing_decision_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_review_authority_positions SET review_decision_id = ? "
            "WHERE sequence = 1",
            ("lecture-review-decision:" + "9" * 64,),
        )
        self._assert_flags("LECTURE_REVIEW_AUTHORITY_POSITION_DECISION_MISSING")

    def test_a_position_recording_another_persons_judgment_is_flagged(self):
        """The scope probe is a real guard: the foreign key only requires the row to exist."""

        self._corrupt(
            "UPDATE lecture_review_authority_positions SET review_decision_id = ? "
            "WHERE sequence = 1",
            (self._other_actor_decision(),),
        )
        self._assert_flags("LECTURE_REVIEW_AUTHORITY_POSITION_SCOPE_MISMATCH")

    def test_a_previous_link_outside_its_own_scope_is_flagged(self):
        self._corrupt(
            "UPDATE lecture_review_authority_positions SET previous_position_id = ? "
            "WHERE sequence = 1",
            ("lecture-review-authority-position:" + "9" * 64,),
        )
        self._assert_flags("LECTURE_REVIEW_AUTHORITY_PREVIOUS_LINK_INVALID")

    def test_a_history_with_a_hole_in_its_sequence_is_flagged(self):
        self._corrupt(
            "DELETE FROM lecture_review_authority_positions WHERE sequence = 0"
        )
        self._assert_flags("LECTURE_REVIEW_AUTHORITY_SEQUENCE_NONCONTIGUOUS")

    def test_a_judgment_without_any_position_is_never_flagged(self):
        """AH-12: absence means 'no recorded authority history', never corruption."""

        self._corrupt("DELETE FROM lecture_review_authority_positions")
        health, codes = self._codes()
        self.assertEqual(health, "healthy", codes)

    def test_several_positions_referencing_one_decision_are_never_corruption(self):
        """AH-6's reversal case: position 0 and position 2 hold the same `accept`."""

        self._corrupt(
            "INSERT INTO lecture_review_authority_positions VALUES (?, ?, ?, 2, ?, ?, 1)",
            (self._position_id(2), self.candidate.identity.value, "reviewer:lee",
             self.accepted.decision.identity.value, self._position_id(1)),
        )
        health, codes = self._codes()
        self.assertEqual(health, "healthy", codes)

    def test_contradictory_cross_actor_histories_are_never_corruption(self):
        """AH-9 makes that a surfaced Conflict, not a repository defect."""

        decision = self._other_actor_decision()
        self._corrupt(
            "INSERT INTO lecture_review_authority_positions VALUES (?, ?, ?, 0, ?, NULL, 1)",
            (self._position_id(0, "reviewer:park"), self.candidate.identity.value,
             "reviewer:park", decision),
        )
        health, codes = self._codes()
        self.assertEqual(health, "healthy", codes)

    def test_a_superseded_chain_never_flags_its_authority_history(self):
        self.connection = sqlite3.connect(self.database, isolation_level=None)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.selection = compose_sqlite_corrected_revision_selection_service(
            self.connection
        )
        self._revise("c3", "교정 3")
        self.connection.close()
        health, codes = self._codes()
        self.assertEqual(health, "healthy", codes)

    def test_the_authority_schema_refuses_these_corruptions_outright(self):
        """Defence-in-depth accounting: a CHECK refuses the write before any validator runs."""

        cases = (
            ("position contract version",
             "UPDATE lecture_review_authority_positions SET position_contract_version = 2"),
            ("blank actor",
             "UPDATE lecture_review_authority_positions SET actor = '   '"),
            ("negative sequence",
             "UPDATE lecture_review_authority_positions SET sequence = -1 "
             "WHERE sequence = 0"),
            ("first position superseding something",
             "UPDATE lecture_review_authority_positions SET previous_position_id = "
             "'lecture-review-authority-position:x' WHERE sequence = 0"),
            ("later position without a previous link",
             "UPDATE lecture_review_authority_positions SET previous_position_id = NULL "
             "WHERE sequence = 1"),
            ("self-superseding position",
             "UPDATE lecture_review_authority_positions SET previous_position_id = identity"),
        )
        for label, statement in cases:
            with self.subTest(case=label):
                with self.assertRaises(sqlite3.IntegrityError):
                    self._corrupt(statement)
        health, codes = self._codes()
        self.assertEqual(health, "healthy", codes)

    def test_every_new_analysis_diagnostic_code_is_either_reached_or_schema_guarded(self):
        """Guard against a silently dead diagnostic.

        Each code added by GOAL-025/026/027/028/029 must be either exercised by a corruption test in
        this module or explicitly accounted for as schema-guarded / defence-in-depth. The list
        below is the accounting; adding a code without updating it fails this test.
        """

        from lectureos.validation import repository_validator as validator

        source = Path(validator.__file__).read_text(encoding="utf-8")
        declared = {
            code for code in
            __import__("re").findall(
                r"\"(LECTURE_(?:ANALYSIS_(?:FINDING|SEGMENT|EDIT_CANDIDATE)|REVIEW|APPROVED_EDIT_DECISION)_[A-Z_]+)\"",
                source,
            )
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
            "LECTURE_REVIEW_DECISION_IDENTITY_MISMATCH",
            "LECTURE_REVIEW_DECISION_ANCHOR_MISSING",
            "LECTURE_REVIEW_APPROVAL_CARDINALITY_INVALID",
            "LECTURE_APPROVED_EDIT_DECISION_IDENTITY_MISMATCH",
            "LECTURE_APPROVED_EDIT_DECISION_LABEL_MALFORMED",
            "LECTURE_APPROVED_EDIT_DECISION_RANGE_NOT_CANONICAL",
            "LECTURE_REVIEW_DECISION_LEGACY_ANCHOR_LEAK",
            "LECTURE_REVIEW_AUTHORITY_POSITION_IDENTITY_MISMATCH",
            "LECTURE_REVIEW_AUTHORITY_POSITION_DECISION_MISSING",
            "LECTURE_REVIEW_AUTHORITY_POSITION_SCOPE_MISMATCH",
            "LECTURE_REVIEW_AUTHORITY_PREVIOUS_LINK_INVALID",
            "LECTURE_REVIEW_AUTHORITY_SEQUENCE_NONCONTIGUOUS",
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
            "LECTURE_REVIEW_DECISION_CONTRACT_VERSION_MISMATCH",
            "LECTURE_REVIEW_DECISION_KIND_UNKNOWN",
            "LECTURE_REVIEW_DECISION_ACTOR_MISSING",
            "LECTURE_APPROVED_EDIT_DECISION_CONTRACT_VERSION_MISMATCH",
            "LECTURE_APPROVED_EDIT_DECISION_KIND_INVALID",
            "LECTURE_APPROVED_EDIT_DECISION_RATIONALE_EMPTY",
            "LECTURE_APPROVED_EDIT_DECISION_RANGE_INVALID",
            "LECTURE_REVIEW_AUTHORITY_POSITION_CONTRACT_VERSION_MISMATCH",
        }
        self.assertEqual(
            declared - reached_by_test - schema_guarded,
            set(),
            "a new analysis diagnostic code is neither exercised nor accounted for",
        )


if __name__ == "__main__":
    unittest.main()
