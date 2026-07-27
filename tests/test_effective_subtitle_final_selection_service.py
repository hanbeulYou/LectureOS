"""Application tests for Effective Subtitle Final Selection (GOAL-016)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_subtitle_final_selection import (
    EffectiveSubtitleFinalSelectionError,
    EffectiveSubtitleFinalSelectionService,
    EligibilityBlockingReason,
    FinalSelectionConflictError,
    ReviewSubjectNotEligibleError,
    SelectionApplicability,
    derive_final_selection_identity,
)
from lectureos.application.identities import (
    EffectiveSubtitleCandidateId,
    EffectiveSubtitleReviewDecisionId,
    EffectiveSubtitleReviewSubjectId,
    TranscriptSourceIntakeId,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_final_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteEffectiveSubtitleFinalSelectionCommandPersistence,
    SQLiteEffectiveSubtitleFinalSelectionRepository,
    initialize_sqlite_database,
)

_INTAKE = TranscriptSourceIntakeId("transcript-source-intake:sha256:" + "a" * 64)
_CAND = EffectiveSubtitleCandidateId("subtitle-effective-candidate:" + "a" * 64)
_SUBJ = EffectiveSubtitleReviewSubjectId("subtitle-effective-review-subject:" + "a" * 64)
_DEC = EffectiveSubtitleReviewDecisionId("subtitle-effective-review-decision:" + "a" * 64)


class IdentityTests(unittest.TestCase):
    def test_identity_deterministic_and_input_sensitive(self):
        base = derive_final_selection_identity(_INTAKE, _CAND, _SUBJ, _DEC, 0)
        self.assertEqual(base, derive_final_selection_identity(_INTAKE, _CAND, _SUBJ, _DEC, 0))
        self.assertTrue(base.value.startswith("subtitle-effective-final-selection:"))
        other_cand = EffectiveSubtitleCandidateId("subtitle-effective-candidate:" + "b" * 64)
        other_subj = EffectiveSubtitleReviewSubjectId(
            "subtitle-effective-review-subject:" + "b" * 64
        )
        other_dec = EffectiveSubtitleReviewDecisionId(
            "subtitle-effective-review-decision:" + "b" * 64
        )
        self.assertNotEqual(base, derive_final_selection_identity(_INTAKE, other_cand, _SUBJ, _DEC, 0))
        self.assertNotEqual(base, derive_final_selection_identity(_INTAKE, _CAND, other_subj, _DEC, 0))
        self.assertNotEqual(base, derive_final_selection_identity(_INTAKE, _CAND, _SUBJ, other_dec, 0))
        self.assertNotEqual(base, derive_final_selection_identity(_INTAKE, _CAND, _SUBJ, _DEC, 1))


class EffectiveSubtitleFinalSelectionServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.connection = initialize_sqlite_database(self.base / "lectureos.sqlite3")
        source = self.base / "a.bin"
        source.write_bytes(b"final-selection \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        self.provider = compose_sqlite_provider_transcript_admission_service(self.connection)
        self.raw_selection = compose_sqlite_current_raw_transcript_selection_service(self.connection)
        self.revision_selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        self.generation = compose_sqlite_effective_subtitle_generation_service(self.connection)
        self.preparation = compose_sqlite_effective_subtitle_review_preparation_service(self.connection)
        self.decisions = compose_sqlite_effective_subtitle_review_decision_service(self.connection)
        self.selection = compose_sqlite_effective_subtitle_final_selection_service(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _admit_raw(self, ref: str) -> str:
        return self.provider.admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": ref,
                 "segments": [{"start": 0.0, "end": 1.0, "text": "원본"}]}
            ),
        ).admission.raw_transcript_id.value

    def _subject(self, ref="A"):
        raw = self._admit_raw(ref)
        self.raw_selection.select(self.intake, raw)
        if ref != "A":
            self.revision_selection.select_raw_fallback(
                intake_id=self.intake, reviewer="s:kim"
            )
        candidate = self.generation.generate(intake_id=self.intake).candidate
        return candidate, self.preparation.prepare_review(
            candidate_id=candidate.identity.value
        ).subject

    def _accept(self, subject):
        return self.decisions.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        ).decision

    # -- eligibility (derived, never persisted) -------------------------------------------------------

    def test_eligibility_states(self):
        _, subject = self._subject()
        report = self.selection.eligibility(subject.identity.value)
        self.assertFalse(report.eligible)
        self.assertIs(report.blocking_reason, EligibilityBlockingReason.NO_DECISION)
        self.decisions.decide(
            review_subject_id=subject.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        report = self.selection.eligibility(subject.identity.value)
        self.assertFalse(report.eligible)
        self.assertIs(report.blocking_reason, EligibilityBlockingReason.DECISION_NOT_ACCEPT)
        self.decisions.decide(
            review_subject_id=subject.identity.value, kind="modify", reviewer="reviewer:kim"
        )
        self.assertFalse(self.selection.eligibility(subject.identity.value).eligible)
        self._accept(subject)
        report = self.selection.eligibility(subject.identity.value)
        self.assertTrue(report.eligible)
        self.assertIsNone(report.blocking_reason)

    def test_stale_subject_ineligible_for_new_selection(self):
        _, subject = self._subject()
        self._accept(subject)
        raw2 = self._admit_raw("B")
        self.raw_selection.select(self.intake, raw2)  # candidate source now stale
        report = self.selection.eligibility(subject.identity.value)
        self.assertFalse(report.eligible)
        self.assertIs(report.blocking_reason, EligibilityBlockingReason.DECISION_NOT_APPLICABLE)
        with self.assertRaises(ReviewSubjectNotEligibleError):
            self.selection.select_final(
                review_subject_id=subject.identity.value, selector="selector:park"
            )
        self.assertEqual(self.selection.history(self.intake), ())

    # -- explicit selection with exact lineage --------------------------------------------------------

    def test_select_binds_exact_lineage(self):
        candidate, subject = self._subject()
        accept = self._accept(subject)
        result = self.selection.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        )
        selection = result.selection
        self.assertEqual(result.outcome.value, "recorded")
        self.assertEqual(selection.candidate_id, candidate.identity)
        self.assertEqual(selection.review_subject_id, subject.identity)
        self.assertEqual(selection.supporting_decision_id, accept.identity)
        self.assertEqual(selection.selector.value, "selector:park")
        self.assertEqual(
            selection.transcript_source_intake_id.value, self.intake
        )
        self.assertIs(
            self.selection.applicability(selection), SelectionApplicability.APPLICABLE
        )
        current = self.selection.current(self.intake)
        self.assertEqual(current.identity, selection.identity)

    def test_selector_explicit_and_may_differ_from_reviewer(self):
        _, subject = self._subject()
        self._accept(subject)
        with self.assertRaises(EffectiveSubtitleFinalSelectionError):
            self.selection.select_final(
                review_subject_id=subject.identity.value, selector="  "
            )
        result = self.selection.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        )
        self.assertNotEqual(result.selection.selector.value, "reviewer:kim")

    def test_exact_subject_required(self):
        with self.assertRaises(EffectiveSubtitleFinalSelectionError):
            self.selection.select_final(
                review_subject_id="subtitle-effective-review-subject:" + "0" * 64,
                selector="selector:park",
            )
        candidate, subject = self._subject()
        with self.assertRaises(EffectiveSubtitleFinalSelectionError):
            self.selection.select_final(
                review_subject_id=candidate.identity.value, selector="selector:park"
            )

    # -- replay and reselection ----------------------------------------------------------------------

    def test_exact_replay_reuses(self):
        _, subject = self._subject()
        self._accept(subject)
        first = self.selection.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        )
        replay = self.selection.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        )
        self.assertEqual(replay.outcome.value, "reused")
        self.assertEqual(replay.selection, first.selection)
        self.assertEqual(len(self.selection.history(self.intake)), 1)

    def test_new_supporting_accept_appends_new_selection(self):
        _, subject = self._subject()
        accept_1 = self._accept(subject)
        first = self.selection.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        )
        self.decisions.decide(
            review_subject_id=subject.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        accept_2 = self._accept(subject)
        self.assertNotEqual(accept_1.identity, accept_2.identity)
        second = self.selection.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        )
        self.assertEqual(second.outcome.value, "changed")
        self.assertNotEqual(second.selection.identity, first.selection.identity)
        self.assertEqual(second.selection.supporting_decision_id, accept_2.identity)
        self.assertIs(
            self.selection.applicability(first.selection),
            SelectionApplicability.SUPERSEDED,
        )

    def test_changed_candidate_appends_and_supersedes(self):
        _, subject_a = self._subject()
        self._accept(subject_a)
        first = self.selection.select_final(
            review_subject_id=subject_a.identity.value, selector="selector:park"
        )
        _, subject_b = self._subject("B")
        self._accept(subject_b)
        second = self.selection.select_final(
            review_subject_id=subject_b.identity.value, selector="selector:park"
        )
        self.assertEqual(second.outcome.value, "changed")
        current = self.selection.current(self.intake)
        self.assertEqual(current.identity, second.selection.identity)
        history = self.selection.history(self.intake)
        self.assertEqual([s.sequence for s in history], [0, 1])
        self.assertEqual(
            self.selection.get(first.selection.identity.value), first.selection
        )
        self.assertIs(
            self.selection.applicability(first.selection),
            SelectionApplicability.SUPERSEDED,
        )

    # -- applicability -------------------------------------------------------------------------------

    def test_supporting_decision_superseded_derives_inapplicable(self):
        _, subject = self._subject()
        self._accept(subject)
        result = self.selection.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        )
        self.decisions.decide(
            review_subject_id=subject.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        self.assertIs(
            self.selection.applicability(result.selection),
            SelectionApplicability.SUPPORTING_DECISION_SUPERSEDED,
        )
        # History remains immutable.
        self.assertEqual(
            self.selection.get(result.selection.identity.value), result.selection
        )

    def test_stale_candidate_source_derives_stale(self):
        _, subject = self._subject()
        self._accept(subject)
        result = self.selection.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        )
        raw2 = self._admit_raw("B")
        self.raw_selection.select(self.intake, raw2)
        self.assertIs(
            self.selection.applicability(result.selection),
            SelectionApplicability.STALE_DUE_TO_CANDIDATE_SOURCE,
        )

    # -- concurrency ---------------------------------------------------------------------------------

    def test_near_concurrent_identical_selection_converges(self):
        _, subject = self._subject()
        self._accept(subject)
        self.selection.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        )

        class _StaleCurrentView:
            def __init__(self, inner):
                self._inner = inner

            def get(self, identity):
                return self._inner.get(identity)

            def get_current(self, intake_id):
                calls = getattr(self, "_calls", 0)
                self._calls = calls + 1
                if calls == 0:
                    return None  # raced ahead of the competitor's insert
                return self._inner.get_current(intake_id)

            def history(self, intake_id):
                return self._inner.history(intake_id)

        racing = EffectiveSubtitleFinalSelectionService(
            self.preparation,
            self.decisions,
            _StaleCurrentView(
                SQLiteEffectiveSubtitleFinalSelectionRepository(self.connection)
            ),
            SQLiteEffectiveSubtitleFinalSelectionCommandPersistence(self.connection),
        )
        result = racing.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        )
        self.assertEqual(result.outcome.value, "reused")
        self.assertEqual(len(self.selection.history(self.intake)), 1)

    def test_competing_divergent_selection_raises_explicit_conflict(self):
        _, subject_a = self._subject()
        self._accept(subject_a)
        _, subject_b = self._subject("B")
        self._accept(subject_b)
        # subject_a's candidate source is now stale (raw switched for B) — re-point authority
        # back so both are decided; instead simulate the race directly: a competitor selects B
        # while our reader for a fresh A-selection still observes no current selection.
        self.selection.select_final(
            review_subject_id=subject_b.identity.value, selector="selector:park"
        )

        class _StaleCurrentView:
            def __init__(self, inner):
                self._inner = inner

            def get(self, identity):
                return self._inner.get(identity)

            def get_current(self, intake_id):
                calls = getattr(self, "_calls", 0)
                self._calls = calls + 1
                if calls == 0:
                    return None
                return self._inner.get_current(intake_id)

            def history(self, intake_id):
                return self._inner.history(intake_id)

        racing = EffectiveSubtitleFinalSelectionService(
            self.preparation,
            self.decisions,
            _StaleCurrentView(
                SQLiteEffectiveSubtitleFinalSelectionRepository(self.connection)
            ),
            SQLiteEffectiveSubtitleFinalSelectionCommandPersistence(self.connection),
        )
        with self.assertRaises(FinalSelectionConflictError):
            racing.select_final(
                review_subject_id=subject_b.identity.value, selector="selector:other"
            )
        self.assertEqual(len(self.selection.history(self.intake)), 1)


if __name__ == "__main__":
    unittest.main()
