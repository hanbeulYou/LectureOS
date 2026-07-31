"""Application and persistence tests for effective-generation Review (043 §7.5, GOAL-028)."""

import ast
import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.lecture_analysis_input_admission import (
    AdmissionAuthorityMatch,
)
from lectureos.application.lecture_review_decision import (
    LectureReviewApplicationService,
    LectureReviewError,
    ReviewAnchorNotAdmissibleError,
    ReviewApprovalConflictError,
    ReviewConflictError,
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
    compose_sqlite_lecture_review_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.persistence.lecture_review_decision import (
    SQLiteLectureReviewCommandPersistence,
    SQLiteLectureReviewRepository,
)
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository
from lectureos.review.identities import HumanActorReference

_ACTOR = "reviewer:lee"
_OTHER_ACTOR = "reviewer:park"
_APPROVED_RATIONALE = "앞부분만 잘라내는 것으로 승인한다"
_CANDIDATE_RATIONALE = "이 구간은 사람이 검토할 만하다"


class _Chain(unittest.TestCase):
    """One real released upstream chain down to a current-generation Edit Candidate."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"review \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(
            str(source)
        ).record
        self.intake = compose_sqlite_transcript_source_intake_service(
            self.connection
        ).admit(media.identity.value).intake.identity.value
        self.raw = compose_sqlite_provider_transcript_admission_service(
            self.connection
        ).admit(
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
        self.selection = compose_sqlite_corrected_revision_selection_service(
            self.connection
        )
        self.revision_1 = self._revise("c1", "교정 1")
        self.admission = compose_sqlite_lecture_analysis_input_admission_service(
            self.connection
        ).admit(intake_id=self.intake).admission
        self.finding = compose_sqlite_lecture_analysis_finding_service(
            self.connection
        ).admit(
            admission_id=self.admission.identity.value,
            finding_type="non_lecture_speech",
            evidence="수업과 무관한 발화가 관찰된다",
        ).finding
        self.candidate_service = compose_sqlite_lecture_analysis_edit_candidate_service(
            self.connection
        )
        self.candidate = self.candidate_service.admit_edit_candidate(
            finding_id=self.finding.identity.value,
            candidate_type="non_lecture_region",
            range_start=0.0,
            range_end=1.0,
            rationale=_CANDIDATE_RATIONALE,
        ).candidate
        self.reviews = compose_sqlite_lecture_review_service(self.connection)

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
        source_text = SQLiteTranscriptSegmentRepository(self.connection).get(
            segment_id
        ).text
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

    def _judge(self, **overrides):
        payload = {
            "candidate_id": self.candidate.identity.value,
            "decision_kind": "accept",
            "actor": _ACTOR,
        }
        payload.update(overrides)
        return self.reviews.admit_review_decision(**payload)

    def _modify(self, **overrides):
        payload = {
            "decision_kind": "modify",
            "approved_range_start": 0.0,
            "approved_range_end": 0.5,
            "approved_label": "trim_intro",
            "approved_rationale": _APPROVED_RATIONALE,
        }
        payload.update(overrides)
        return self._judge(**payload)

    def _counts(self):
        return (
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_review_decisions"
            ).fetchone()[0],
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_approved_edit_decisions"
            ).fetchone()[0],
        )


class AdmissionTests(_Chain):
    def test_accept_records_one_decision_and_one_inherited_approval(self):
        result = self._judge()
        self.assertEqual(result.outcome.value, "recorded")
        self.assertEqual(result.decision.candidate_id, self.candidate.identity)
        self.assertIs(result.decision.decision_kind, ReviewDecisionKind.ACCEPT)
        self.assertEqual(result.decision.actor, HumanActorReference(_ACTOR))
        approved = result.approved
        self.assertIsNotNone(approved)
        self.assertEqual(approved.review_decision_id, result.decision.identity)
        self.assertEqual(approved.candidate_id, self.candidate.identity)
        self.assertEqual(approved.approved_range_start, self.candidate.range_start)
        self.assertEqual(approved.approved_range_end, self.candidate.range_end)
        self.assertEqual(approved.approved_label, self.candidate.candidate_type)
        self.assertEqual(approved.approved_rationale, self.candidate.rationale)
        self.assertEqual(self._counts(), (1, 1))

    def test_reject_records_a_durable_decision_and_no_approval(self):
        result = self._judge(decision_kind="reject")
        self.assertEqual(result.outcome.value, "recorded")
        self.assertIsNone(result.approved)
        self.assertEqual(self._counts(), (1, 0))

    def test_modify_records_the_complete_approved_replacement(self):
        result = self._modify()
        self.assertIs(result.approved.approved_decision_kind, ReviewDecisionKind.MODIFY)
        self.assertEqual(result.approved.approved_range_end, 0.5)
        self.assertEqual(result.approved.approved_label, "trim_intro")
        self.assertEqual(result.approved.approved_rationale, _APPROVED_RATIONALE)
        self.assertEqual(self._counts(), (1, 1))

    def test_modify_never_mutates_the_candidate(self):
        before = self.candidate_service.get(self.candidate.identity.value)
        self._modify()
        self.assertEqual(
            self.candidate_service.get(self.candidate.identity.value), before
        )

    def test_all_three_kinds_coexist_as_distinct_records(self):
        accepted = self._judge()
        rejected = self._judge(decision_kind="reject")
        modified = self._modify()
        self.assertEqual(
            len({accepted.decision.identity, rejected.decision.identity,
                 modified.decision.identity}),
            3,
        )
        self.assertEqual(self._counts(), (3, 2))

    def test_a_different_actor_is_a_distinct_judgment(self):
        first = self._judge()
        second = self._judge(actor=_OTHER_ACTOR)
        self.assertNotEqual(first.decision.identity, second.decision.identity)
        self.assertNotEqual(first.approved.identity, second.approved.identity)
        self.assertEqual(self._counts(), (2, 2))

    def test_the_actor_is_stored_verbatim(self):
        result = self._judge(actor="  reviewer:lee  ")
        self.assertEqual(result.decision.actor.value, "  reviewer:lee  ")
        self.assertNotEqual(
            result.decision.identity, self._judge().decision.identity
        )


class PayloadValidationTests(_Chain):
    def test_accept_refuses_supplied_approved_values(self):
        for extra in ({"approved_label": "trim_intro"},
                      {"approved_rationale": _APPROVED_RATIONALE},
                      {"approved_range_start": 0.0},
                      {"approved_range_end": 1.0}):
            with self.subTest(extra=tuple(extra)):
                with self.assertRaises(LectureReviewError):
                    self._judge(**extra)
        self.assertEqual(self._counts(), (0, 0))

    def test_reject_refuses_supplied_approved_values(self):
        with self.assertRaises(LectureReviewError):
            self._judge(decision_kind="reject", approved_label="trim_intro")
        self.assertEqual(self._counts(), (0, 0))

    def test_modify_requires_the_complete_replacement(self):
        complete = {
            "decision_kind": "modify",
            "approved_range_start": 0.0,
            "approved_range_end": 0.5,
            "approved_label": "trim_intro",
            "approved_rationale": _APPROVED_RATIONALE,
        }
        for missing in ("approved_range_start", "approved_range_end",
                        "approved_label", "approved_rationale"):
            with self.subTest(missing=missing):
                partial = dict(complete)
                partial[missing] = None
                with self.assertRaises(LectureReviewError):
                    self._judge(**partial)
        self.assertEqual(self._counts(), (0, 0))

    def test_unknown_kinds_are_refused_before_anything_is_read(self):
        for bad in ("Accept", "approve", "", None, "modify_all"):
            with self.subTest(bad=bad):
                with self.assertRaises(LectureReviewError):
                    self._judge(decision_kind=bad)
        self.assertEqual(self._counts(), (0, 0))

    def test_an_empty_actor_is_refused(self):
        for bad in ("", "   ", None):
            with self.subTest(bad=bad):
                with self.assertRaises(LectureReviewError):
                    self._judge(actor=bad)
        self.assertEqual(self._counts(), (0, 0))

    def test_invalid_approved_ranges_and_labels_are_refused(self):
        for override in ({"approved_range_start": 1.0, "approved_range_end": 0.0},
                         {"approved_range_start": -1.0},
                         {"approved_range_end": float("inf")},
                         {"approved_range_end": float("nan")},
                         {"approved_label": "Bad Label"},
                         {"approved_label": ""},
                         {"approved_rationale": "   "}):
            with self.subTest(override=tuple(override)):
                with self.assertRaises(LectureReviewError):
                    self._modify(**override)
        self.assertEqual(self._counts(), (0, 0))

    def test_no_containment_or_media_duration_validation_is_applied(self):
        """R-8: the approved range need not sit inside the candidate's range."""

        result = self._modify(approved_range_start=0.0, approved_range_end=99999.0)
        self.assertEqual(result.approved.approved_range_end, 99999.0)

    def test_a_zero_duration_approved_range_is_valid(self):
        result = self._modify(approved_range_start=1.0, approved_range_end=1.0)
        self.assertEqual(result.approved.approved_range_start, 1.0)


class AnchorAndStandingTests(_Chain):
    def test_a_malformed_candidate_reference_is_refused_in_this_error_family(self):
        for bad in ("", "nope", "lecture-analysis-edit-candidate:short",
                    "lecture-analysis-finding:" + "a" * 64,
                    self.candidate.identity.value.upper()):
            with self.subTest(bad=bad):
                with self.assertRaises(LectureReviewError):
                    self._judge(candidate_id=bad)

    def test_an_unknown_candidate_is_refused(self):
        with self.assertRaises(LectureReviewError):
            self._judge(candidate_id="lecture-analysis-edit-candidate:" + "f" * 64)

    def test_a_finding_or_admission_identity_is_never_an_acceptable_anchor(self):
        """R-2: Review anchors to the Candidate, never to a Finding or the Admission."""

        for other in (self.finding.identity.value, self.admission.identity.value):
            with self.subTest(other=other):
                with self.assertRaises(LectureReviewError):
                    self._judge(candidate_id=other)

    def test_a_superseded_chain_refuses_new_admission(self):
        self._revise("c2", "교정 2")
        with self.assertRaises(ReviewAnchorNotAdmissibleError):
            self._judge()
        self.assertEqual(self._counts(), (0, 0))

    def test_existing_records_survive_an_authority_change_untouched(self):
        accepted = self._judge()
        self._revise("c2", "교정 2")
        self.assertEqual(
            self.reviews.get(accepted.decision.identity.value), accepted.decision
        )
        self.assertEqual(
            self.reviews.get_approved(accepted.decision.identity.value),
            accepted.approved,
        )
        self.assertIs(
            self.reviews.anchor_status(accepted.decision),
            AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE,
        )

    def test_returning_authority_restores_admissibility_and_converges(self):
        accepted = self._judge()
        self._revise("c2", "교정 2")
        self.selection.select_revision(revision_id=self.revision_1, reviewer="s:kim")
        self.assertIs(
            self.reviews.anchor_status(accepted.decision), AdmissionAuthorityMatch.CURRENT
        )
        again = self._judge()
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(again.decision.identity, accepted.decision.identity)

    def test_the_derived_vocabulary_is_never_extended(self):
        self.assertIs(
            self.reviews.anchor_status(self._judge().decision),
            AdmissionAuthorityMatch.CURRENT,
        )
        self.assertEqual(
            {match.value for match in AdmissionAuthorityMatch},
            {"current", "superseded_by_authority_change", "current_authority_ineligible"},
        )

    def test_no_standing_is_ever_stored(self):
        self._judge()
        columns = {
            row[1] for row in self.connection.execute(
                "PRAGMA table_info(lecture_review_decisions)"
            ).fetchall()
        } | {
            row[1] for row in self.connection.execute(
                "PRAGMA table_info(lecture_approved_edit_decisions)"
            ).fetchall()
        }
        for forbidden in ("current", "stale", "selected", "status", "state",
                          "authority_match", "sequence", "previous_decision_id",
                          "domain_result_id", "processing_run_id", "unit_execution_id",
                          "source_media_id", "source_timeline_id", "created_at"):
            with self.subTest(column=forbidden):
                self.assertNotIn(forbidden, columns)


class ReplayAndConflictTests(_Chain):
    def test_exact_replay_of_each_kind_reuses_and_writes_nothing_new(self):
        first_accept = self._judge()
        first_reject = self._judge(decision_kind="reject")
        first_modify = self._modify()
        before = self._counts()
        again_accept = self._judge()
        again_reject = self._judge(decision_kind="reject")
        again_modify = self._modify()
        self.assertEqual(
            [again_accept.outcome.value, again_reject.outcome.value,
             again_modify.outcome.value],
            ["reused"] * 3,
        )
        self.assertEqual(again_accept.decision.identity, first_accept.decision.identity)
        self.assertEqual(again_accept.approved.identity, first_accept.approved.identity)
        self.assertIsNone(again_reject.approved)
        self.assertEqual(again_modify.approved.identity, first_modify.approved.identity)
        self.assertEqual(self._counts(), before)

    def test_integral_and_negative_zero_approved_bounds_converge(self):
        first = self._modify()
        for override in ({"approved_range_start": 0}, {"approved_range_start": -0.0},
                         {"approved_range_end": 0.50}):
            with self.subTest(override=tuple(override)):
                again = self._modify(**override)
                self.assertEqual(again.outcome.value, "reused")
                self.assertEqual(again.approved.identity, first.approved.identity)
        self.assertEqual(self._counts(), (1, 1))

    def test_a_second_differing_modify_is_an_explicit_conflict(self):
        """R-11's reachable conflict arm: the approved snapshot is Option A at admission level."""

        self._modify()
        before = self._counts()
        for override in ({"approved_range_end": 0.9},
                         {"approved_label": "other_label"},
                         {"approved_rationale": "다른 이유"}):
            with self.subTest(override=tuple(override)):
                with self.assertRaises(ReviewApprovalConflictError):
                    self._modify(**override)
        self.assertEqual(self._counts(), before)

    def test_the_approval_conflict_is_a_review_conflict(self):
        self._modify()
        with self.assertRaises(ReviewConflictError):
            self._modify(approved_range_end=0.9)

    def test_the_stored_snapshot_is_never_overwritten_by_a_conflicting_submission(self):
        original = self._modify()
        with self.assertRaises(ReviewApprovalConflictError):
            self._modify(approved_range_end=0.9)
        self.assertEqual(
            self.reviews.get_approved(original.decision.identity.value),
            original.approved,
        )

    def test_a_partially_recorded_admission_is_never_treated_as_valid(self):
        """R-11's all-or-nothing requirement, probed by deleting the approved row."""

        accepted = self._judge()
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute("DELETE FROM lecture_approved_edit_decisions")
        self.connection.execute("PRAGMA foreign_keys = ON")
        with self.assertRaises(ReviewConflictError):
            self._judge()
        self.assertIsNotNone(self.reviews.get(accepted.decision.identity.value))

    def test_an_approval_repointed_to_another_decision_fails_re_derivation(self):
        """The approved identity binds its originating decision, so re-pointing breaks it."""

        rejected = self._judge(decision_kind="reject")
        accepted = self._judge()
        self.connection.execute(
            "UPDATE lecture_approved_edit_decisions SET review_decision_id = ? "
            "WHERE review_decision_id = ?",
            (rejected.decision.identity.value, accepted.decision.identity.value),
        )
        with self.assertRaises(LectureReviewError):
            self._judge(decision_kind="reject")
        self.assertIsNotNone(self.reviews.get(accepted.decision.identity.value))

    def test_a_reject_that_owns_an_approval_is_refused_as_a_conflict(self):
        """The cardinality guard itself: unreachable through this command, so a stub is used."""

        accepted = self._judge()
        rejected = self._judge(decision_kind="reject")

        class _Stub:
            def get_decision(self, identity):
                return rejected.decision

            def get_approved_for_decision(self, identity):
                return accepted.approved

            def list_decisions_for_candidate(self, candidate_id):
                return ()

            def head_position(self, candidate_id, actor):
                return None

            def list_positions(self, candidate_id, actor):
                return ()

            def actors_with_history(self, candidate_id):
                return ()

        service = LectureReviewApplicationService(
            self.candidate_service,
            _Stub(),
            SQLiteLectureReviewCommandPersistence(self.connection),
        )
        with self.assertRaises(ReviewConflictError):
            service.admit_review_decision(
                candidate_id=self.candidate.identity.value,
                decision_kind="reject",
                actor=_ACTOR,
            )

    def test_a_divergent_stored_decision_is_refused(self):
        """The Option-B guard: structurally unreachable, so a query stub is required."""

        accepted = self._judge()
        other = self._judge(actor=_OTHER_ACTOR)

        class _Stub:
            def get_decision(self, identity):
                return other.decision

            def get_approved_for_decision(self, identity):
                return other.approved

            def list_decisions_for_candidate(self, candidate_id):
                return ()

            def head_position(self, candidate_id, actor):
                return None

            def list_positions(self, candidate_id, actor):
                return ()

            def actors_with_history(self, candidate_id):
                return ()

        service = LectureReviewApplicationService(
            self.candidate_service,
            _Stub(),
            SQLiteLectureReviewCommandPersistence(self.connection),
        )
        with self.assertRaises(ReviewConflictError):
            service.admit_review_decision(
                candidate_id=self.candidate.identity.value,
                decision_kind="accept",
                actor=_ACTOR,
            )
        self.assertIsNotNone(self.reviews.get(accepted.decision.identity.value))

    def test_reversed_judgments_coexist_without_adjudication(self):
        """R-9's recorded consequence: accept → reject → accept converges on the first."""

        accepted = self._judge()
        self._judge(decision_kind="reject")
        again = self._judge()
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(again.decision.identity, accepted.decision.identity)
        recorded = self.reviews.list_for_candidate(self.candidate.identity.value)
        self.assertEqual(
            sorted(decision.decision_kind.value for decision in recorded),
            ["accept", "reject"],
        )
        self.assertFalse(hasattr(recorded[0], "sequence"))


class QueryTests(_Chain):
    def test_listing_is_deterministic_and_not_an_ordinal(self):
        self._judge()
        self._judge(decision_kind="reject")
        self._modify()
        first = self.reviews.list_for_candidate(self.candidate.identity.value)
        self.assertEqual(
            [decision.identity.value for decision in first],
            sorted(decision.identity.value for decision in first),
        )
        self.assertEqual(
            first, self.reviews.list_for_candidate(self.candidate.identity.value)
        )

    def test_listing_an_unreviewed_candidate_is_empty(self):
        self.assertEqual(
            self.reviews.list_for_candidate(self.candidate.identity.value), ()
        )

    def test_get_refuses_a_malformed_identity_and_returns_none_for_unknown(self):
        with self.assertRaises(LectureReviewError):
            self.reviews.get("nope")
        self.assertIsNone(
            self.reviews.get("lecture-review-decision:" + "e" * 64)
        )

    def test_get_approved_returns_none_for_a_reject(self):
        rejected = self._judge(decision_kind="reject")
        self.assertIsNone(self.reviews.get_approved(rejected.decision.identity.value))

    def test_anchor_status_reports_a_missing_anchor_as_an_integrity_failure(self):
        accepted = self._judge()
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute("DELETE FROM lecture_analysis_edit_candidates")
        self.connection.execute("PRAGMA foreign_keys = ON")
        with self.assertRaises(LectureReviewError):
            self.reviews.anchor_status(accepted.decision)

    def test_restart_reconstructs_identically(self):
        accepted = self._judge()
        modified = self._modify()
        self.connection.close()
        reopened = open_sqlite_database(self.database)
        try:
            service = compose_sqlite_lecture_review_service(reopened)
            self.assertEqual(
                service.get(accepted.decision.identity.value), accepted.decision
            )
            self.assertEqual(
                service.get_approved(accepted.decision.identity.value),
                accepted.approved,
            )
            self.assertEqual(
                service.get_approved(modified.decision.identity.value),
                modified.approved,
            )
            self.assertIs(
                service.anchor_status(accepted.decision), AdmissionAuthorityMatch.CURRENT
            )
        finally:
            reopened.close()


class PersistenceContractTests(_Chain):
    def test_the_repository_exposes_no_mutation_method(self):
        repository = SQLiteLectureReviewRepository(self.connection)
        for forbidden in ("update", "delete", "remove", "save", "upsert", "replace"):
            with self.subTest(method=forbidden):
                self.assertFalse(hasattr(repository, forbidden))

    def test_at_most_one_approval_per_decision_is_a_schema_constraint(self):
        """R-12: `§7.4`'s at-most-one rule is contract-backed, so it may be a constraint."""

        accepted = self._judge()
        row = self.connection.execute(
            "SELECT identity, candidate_id, approved_decision_kind, approved_range_start, "
            "approved_range_end, approved_label, approved_rationale, "
            "approved_contract_version FROM lecture_approved_edit_decisions"
        ).fetchone()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO lecture_approved_edit_decisions(
                    identity, review_decision_id, candidate_id, approved_decision_kind,
                    approved_range_start, approved_range_end, approved_label,
                    approved_rationale, approved_contract_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("lecture-approved-edit-decision:" + "c" * 64,
                 accepted.decision.identity.value, row[1], row[2], row[3], row[4],
                 row[5], row[6], row[7]),
            )

    def test_the_schema_refuses_an_unknown_decision_kind(self):
        accepted = self._judge()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO lecture_review_decisions VALUES (?, ?, ?, ?, ?)",
                ("lecture-review-decision:" + "d" * 64,
                 accepted.decision.candidate_id.value, "approve", _ACTOR, 1),
            )

    def test_the_schema_refuses_an_unknown_candidate_anchor(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO lecture_review_decisions VALUES (?, ?, ?, ?, ?)",
                ("lecture-review-decision:" + "d" * 64,
                 "lecture-analysis-edit-candidate:" + "9" * 64, "accept", _ACTOR, 1),
            )

    def test_the_schema_refuses_an_empty_actor_and_a_bad_contract_version(self):
        candidate = self.candidate.identity.value
        for kind, actor, version in (("accept", "   ", 1), ("accept", _ACTOR, 2)):
            with self.subTest(actor=actor, version=version):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        "INSERT INTO lecture_review_decisions VALUES (?, ?, ?, ?, ?)",
                        ("lecture-review-decision:" + "d" * 64, candidate, kind,
                         actor, version),
                    )

    def test_the_schema_refuses_an_inverted_or_negative_approved_range(self):
        accepted = self._judge()
        for start, end in ((1.0, 0.0), (-1.0, 1.0)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        """
                        INSERT INTO lecture_approved_edit_decisions VALUES
                        (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        ("lecture-approved-edit-decision:" + "c" * 64,
                         accepted.decision.identity.value,
                         self.candidate.identity.value, "modify", start, end,
                         "trim_intro", "이유", 1),
                    )

    def test_persistence_requires_the_released_schema_version(self):
        legacy = self.base / "legacy.sqlite3"
        connection = sqlite3.connect(legacy, isolation_level=None)
        connection.execute(
            "CREATE TABLE schema_metadata (singleton INTEGER PRIMARY KEY, version INTEGER)"
        )
        connection.execute("INSERT INTO schema_metadata VALUES (1, 50)")
        connection.close()
        opened = sqlite3.connect(legacy, isolation_level=None)
        try:
            with self.assertRaises(Exception):
                SQLiteLectureReviewRepository(opened)
        finally:
            opened.close()

    def test_an_approving_admission_is_atomic(self):
        """A failure while writing the approval must leave no decision row behind."""

        class _Failing(SQLiteLectureReviewCommandPersistence):
            def persist_review(self, *, decision, approved, position=None):
                broken = None
                if approved is not None:
                    broken = object.__new__(type(approved))
                    for field in type(approved).__slots__:
                        object.__setattr__(broken, field, getattr(approved, field))
                    object.__setattr__(broken, "approved_label", None)
                super().persist_review(
                    decision=decision, approved=broken, position=position
                )

        service = LectureReviewApplicationService(
            self.candidate_service,
            SQLiteLectureReviewRepository(self.connection),
            _Failing(self.connection),
        )
        with self.assertRaises(Exception):
            service.admit_review_decision(
                candidate_id=self.candidate.identity.value,
                decision_kind="accept",
                actor=_ACTOR,
            )
        self.assertEqual(self._counts(), (0, 0))
        self.assertFalse(self.connection.in_transaction)


class IsolationTests(_Chain):
    def test_no_execution_legacy_or_domain_result_row_is_created(self):
        before = self.connection.execute(
            "SELECT COUNT(*) FROM domain_result_references"
        ).fetchone()[0]
        self._judge()
        self._judge(decision_kind="reject")
        self._modify()
        for table in ("edit_review_decisions", "approved_edit_decisions",
                      "edit_candidates", "processing_runs", "unit_executions",
                      "lecture_analysis_segments", "lecture_segments"):
            with self.subTest(table=table):
                self.assertEqual(
                    self.connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0],
                    0,
                )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM domain_result_references"
            ).fetchone()[0],
            before,
        )

    def test_the_application_module_never_imports_the_legacy_execution_boundary(self):
        """R-6/R-12: this generation carries no source-level dependency on the legacy boundary.

        Asserted over the module's actual import graph, not its prose: the docstring necessarily
        names ProcessingRun, UnitExecution, and DomainResult to record that they are *not*
        required here.
        """

        module = ast.parse(
            (
                Path(__file__).resolve().parents[1]
                / "src" / "lectureos" / "application" / "lecture_review_decision.py"
            ).read_text(encoding="utf-8")
        )
        modules, symbols = set(), set()
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module or "")
                symbols.update(alias.name for alias in node.names)
        for forbidden in ("edit_review", "analysis_finding", "edit_candidate",
                          "lectureos.execution", "lectureos.application.edit_review"):
            with self.subTest(module=forbidden):
                self.assertNotIn(forbidden, modules)
        for forbidden in ("ExecutionQueryBoundary", "ProcessingRunId", "UnitExecutionId",
                          "ProcessingState", "DomainResultReference",
                          "EditReviewDecisionKind", "EditReviewApplicationService"):
            with self.subTest(symbol=forbidden):
                self.assertNotIn(forbidden, symbols)

    def test_the_identity_prefixes_never_collide_with_the_legacy_generation(self):
        accepted = self._judge()
        self.assertTrue(
            accepted.decision.identity.value.startswith("lecture-review-decision:")
        )
        self.assertTrue(
            accepted.approved.identity.value.startswith(
                "lecture-approved-edit-decision:"
            )
        )

    def test_a_decision_identity_re_derives_from_its_stored_row(self):
        accepted = self._judge()
        candidate_id, kind, actor = self.connection.execute(
            "SELECT candidate_id, decision_kind, actor FROM lecture_review_decisions"
        ).fetchone()
        self.assertEqual(
            derive_review_decision_identity(
                type(self.candidate.identity)(candidate_id),
                ReviewDecisionKind(kind),
                HumanActorReference(actor),
            ),
            accepted.decision.identity,
        )


if __name__ == "__main__":
    unittest.main()
