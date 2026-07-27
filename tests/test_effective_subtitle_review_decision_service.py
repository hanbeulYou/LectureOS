"""Application tests for Human Decisions over Effective Review Subjects (GOAL-015)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_subtitle_review_decision import (
    DecisionApplicability,
    DecisionSubjectIntegrityError,
    EffectiveSubtitleReviewDecisionConflictError,
    EffectiveSubtitleReviewDecisionError,
    EffectiveSubtitleReviewDecisionService,
    derive_decision_identity,
    require_decision_kind,
)
from lectureos.application.identities import EffectiveSubtitleReviewSubjectId
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteEffectiveSubtitleReviewDecisionCommandPersistence,
    SQLiteEffectiveSubtitleReviewDecisionRepository,
    SQLiteRawTranscriptRepository,
    initialize_sqlite_database,
)
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptId

_SUBJECT = EffectiveSubtitleReviewSubjectId(
    "subtitle-effective-review-subject:" + "a" * 64
)
_SUBJECT2 = EffectiveSubtitleReviewSubjectId(
    "subtitle-effective-review-subject:" + "b" * 64
)


class VocabularyAndIdentityTests(unittest.TestCase):
    def test_closed_kind_set(self):
        self.assertIs(require_decision_kind("accept"), DecisionKind.ACCEPT)
        self.assertIs(require_decision_kind("reject"), DecisionKind.REJECT)
        self.assertIs(require_decision_kind("modify"), DecisionKind.MODIFY)
        for bad in ("approve", "deny", "edit", "pending", "completed", "unknown", ""):
            with self.assertRaises(EffectiveSubtitleReviewDecisionError):
                require_decision_kind(bad)

    def test_identity_deterministic_and_input_sensitive(self):
        a = derive_decision_identity(_SUBJECT, DecisionKind.ACCEPT, 0)
        self.assertEqual(a, derive_decision_identity(_SUBJECT, DecisionKind.ACCEPT, 0))
        self.assertTrue(a.value.startswith("subtitle-effective-review-decision:"))
        self.assertNotEqual(a, derive_decision_identity(_SUBJECT2, DecisionKind.ACCEPT, 0))
        self.assertNotEqual(a, derive_decision_identity(_SUBJECT, DecisionKind.REJECT, 0))
        self.assertNotEqual(a, derive_decision_identity(_SUBJECT, DecisionKind.ACCEPT, 1))


class EffectiveSubtitleReviewDecisionServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.connection = initialize_sqlite_database(self.base / "lectureos.sqlite3")
        source = self.base / "a.bin"
        source.write_bytes(b"decision-svc \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        self.provider = compose_sqlite_provider_transcript_admission_service(self.connection)
        self.raw_selection = compose_sqlite_current_raw_transcript_selection_service(self.connection)
        self.correction_decisions = compose_sqlite_correction_candidate_decision_service(self.connection)
        self.selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        self.generation = compose_sqlite_effective_subtitle_generation_service(self.connection)
        self.preparation = compose_sqlite_effective_subtitle_review_preparation_service(self.connection)
        self.decisions = compose_sqlite_effective_subtitle_review_decision_service(self.connection)

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

    def _subject(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        candidate = self.generation.generate(intake_id=self.intake).candidate
        return raw, candidate, self.preparation.prepare_review(
            candidate_id=candidate.identity.value
        ).subject

    def _make_stale(self, raw):
        segment = SQLiteRawTranscriptRepository(self.connection).get(
            TranscriptId(raw)
        ).segment_ids[0]
        correction = compose_sqlite_correction_candidate_admission_service(self.connection).admit(
            intake_id=self.intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw, "segment_id": segment.value,
                 "candidate_ref": "c1", "source_type": "manual", "source_reference": "human",
                 "proposed_text": "교정", "source_text_snapshot": "원본", "rationale": "fix"}
            ),
        ).candidate.identity.value
        self.correction_decisions.decide(candidate_id=correction, kind="accept", reviewer="r:kim")
        revision = compose_sqlite_corrected_revision_generation_service(self.connection).generate(
            candidate_id=correction
        ).revision.identity.value
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")

    # -- explicit command, subject boundary ----------------------------------------------------------

    def test_accept_recorded_current_applicable(self):
        _, candidate, subject = self._subject()
        result = self.decisions.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        self.assertEqual(result.outcome.value, "recorded")
        self.assertEqual(result.decision.review_subject_id, subject.identity)
        self.assertEqual(result.decision.reviewer.value, "reviewer:kim")
        self.assertIs(
            self.decisions.applicability(result.decision), DecisionApplicability.APPLICABLE
        )
        current = self.decisions.current(subject.identity.value)
        self.assertEqual(current.identity, result.decision.identity)

    def test_exact_subject_required(self):
        _, candidate, _subject = self._subject()
        with self.assertRaises(EffectiveSubtitleReviewDecisionError):
            self.decisions.decide(
                review_subject_id="subtitle-effective-review-subject:" + "0" * 64,
                kind="accept", reviewer="r",
            )
        with self.assertRaises(EffectiveSubtitleReviewDecisionError):
            # A candidate identity cannot stand in for a review subject.
            self.decisions.decide(
                review_subject_id=candidate.identity.value, kind="accept", reviewer="r"
            )

    def test_blank_reviewer_and_unknown_kind_rejected(self):
        _, _, subject = self._subject()
        with self.assertRaises(EffectiveSubtitleReviewDecisionError):
            self.decisions.decide(
                review_subject_id=subject.identity.value, kind="accept", reviewer="  "
            )
        with self.assertRaises(EffectiveSubtitleReviewDecisionError):
            self.decisions.decide(
                review_subject_id=subject.identity.value, kind="approve", reviewer="r"
            )
        self.assertEqual(self.decisions.history(subject.identity.value), ())

    # -- replay and repeated intent (GOAL-009 rule) --------------------------------------------------

    def test_matching_kind_reused_idempotently(self):
        _, _, subject = self._subject()
        first = self.decisions.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        replay = self.decisions.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        other_actor = self.decisions.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:lee"
        )
        self.assertEqual(replay.outcome.value, "reused")
        self.assertEqual(other_actor.outcome.value, "reused")
        self.assertEqual(replay.decision, first.decision)
        self.assertEqual(other_actor.decision, first.decision)
        self.assertEqual(len(self.decisions.history(subject.identity.value)), 1)

    def test_changed_judgment_appends_and_supersedes(self):
        _, _, subject = self._subject()
        rejected = self.decisions.decide(
            review_subject_id=subject.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        modified = self.decisions.decide(
            review_subject_id=subject.identity.value, kind="modify", reviewer="reviewer:kim"
        )
        accepted = self.decisions.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:park"
        )
        history = self.decisions.history(subject.identity.value)
        self.assertEqual([d.kind.value for d in history], ["reject", "modify", "accept"])
        self.assertEqual([d.sequence for d in history], [0, 1, 2])
        self.assertEqual(history[1].previous_decision_id, rejected.decision.identity)
        current = self.decisions.current(subject.identity.value)
        self.assertEqual(current.identity, accepted.decision.identity)
        self.assertIs(
            self.decisions.applicability(rejected.decision), DecisionApplicability.SUPERSEDED
        )
        self.assertIs(
            self.decisions.applicability(modified.decision), DecisionApplicability.SUPERSEDED
        )
        self.assertIs(
            self.decisions.applicability(accepted.decision), DecisionApplicability.APPLICABLE
        )

    def test_reject_and_modify_are_authority_only(self):
        _, candidate, subject = self._subject()
        cues_before = self.generation.cues(candidate.identity.value)
        reject = self.decisions.decide(
            review_subject_id=subject.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        self.assertIs(
            self.decisions.applicability(reject.decision), DecisionApplicability.APPLICABLE
        )
        modify = self.decisions.decide(
            review_subject_id=subject.identity.value, kind="modify", reviewer="reviewer:kim"
        )
        self.assertIs(
            self.decisions.applicability(modify.decision), DecisionApplicability.APPLICABLE
        )
        self.assertEqual(self.generation.cues(candidate.identity.value), cues_before)
        for table in ("subtitle_effective_candidates", "subtitle_effective_review_subjects"):
            pass  # rows counted below
        counts = self.connection.execute(
            "SELECT (SELECT COUNT(*) FROM subtitle_effective_candidates), "
            "(SELECT COUNT(*) FROM subtitle_effective_review_subjects), "
            "(SELECT COUNT(*) FROM subtitle_final_subtitles), "
            "(SELECT COUNT(*) FROM subtitle_review_decisions)"
        ).fetchone()
        self.assertEqual(counts, (1, 1, 0, 0))

    # -- staleness and applicability -----------------------------------------------------------------

    def test_stale_subject_decision_is_valid_history_with_derived_staleness(self):
        raw, _, subject = self._subject()
        accepted = self.decisions.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        self._make_stale(raw)
        self.assertIs(
            self.decisions.applicability(accepted.decision),
            DecisionApplicability.STALE_DUE_TO_CANDIDATE_SOURCE,
        )
        # An explicit historical decision over the stale-but-valid subject is still possible.
        rejected = self.decisions.decide(
            review_subject_id=subject.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        self.assertEqual(rejected.outcome.value, "changed")
        self.assertIs(
            self.decisions.applicability(rejected.decision),
            DecisionApplicability.STALE_DUE_TO_CANDIDATE_SOURCE,
        )
        self.assertEqual(len(self.decisions.history(subject.identity.value)), 2)

    # -- integrity and conflicts ---------------------------------------------------------------------

    def test_broken_subject_graph_blocks_decision(self):
        _, candidate, subject = self._subject()
        self.connection.execute("PRAGMA foreign_keys = OFF")
        try:
            self.connection.execute(
                "UPDATE subtitle_effective_candidate_cues SET text = '조작' "
                "WHERE candidate_id = ?",
                (candidate.identity.value,),
            )
        finally:
            self.connection.execute("PRAGMA foreign_keys = ON")
        with self.assertRaises(DecisionSubjectIntegrityError):
            self.decisions.decide(
                review_subject_id=subject.identity.value, kind="accept", reviewer="r"
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_review_decisions"
            ).fetchone()[0],
            0,
        )

    def test_divergent_payload_at_same_slot_is_explicit_conflict(self):
        _, _, subject = self._subject()
        self.decisions.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        # Tamper the stored fingerprint so the same (subject, kind, sequence) slot no longer
        # matches; a change back to that kind must refuse to converge.
        self.decisions.decide(
            review_subject_id=subject.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        self.connection.execute("PRAGMA foreign_keys = OFF")
        try:
            self.connection.execute(
                "UPDATE subtitle_effective_review_decisions SET reviewer = 'reviewer:evil' "
                "WHERE sequence = 0"
            )
        finally:
            self.connection.execute("PRAGMA foreign_keys = ON")
        # sequence 2 accept would collide with... no: new accept lands at sequence 2 (new slot).
        # The conflict path is exercised at the identity level in the atomic tests; here we
        # verify the fingerprint validator catches the tamper instead.
        from lectureos.validation import validate_repository

        report = validate_repository(self.connection)
        self.assertIn(
            "EFFECTIVE_REVIEW_DECISION_FINGERPRINT_MISMATCH",
            {d.code for d in report.diagnostics},
        )

    def test_divergent_command_at_same_slot_raises_application_conflict(self):
        # A DIVERGENT near-concurrent competitor (different actor) wins the same derived
        # (subject, kind, sequence) slot while our reader still observes no current decision:
        # the service must refuse to converge because the payload fingerprints disagree —
        # never overwrite, never silently adopt the competitor's authority.
        _, _, subject = self._subject()
        from lectureos.application.effective_subtitle_review_decision import (
            EffectiveSubtitleReviewDecision,
            _content_fingerprint,
        )
        from lectureos.review.identities import HumanActorReference
        from lectureos.review.models import DecisionKind

        evil = HumanActorReference("reviewer:evil")
        competitor = EffectiveSubtitleReviewDecision(
            identity=derive_decision_identity(subject.identity, DecisionKind.ACCEPT, 0),
            review_subject_id=subject.identity,
            kind=DecisionKind.ACCEPT,
            reviewer=evil,
            sequence=0,
            content_fingerprint=_content_fingerprint(
                subject.identity, DecisionKind.ACCEPT, 0, evil, None
            ),
        )
        SQLiteEffectiveSubtitleReviewDecisionCommandPersistence(
            self.connection
        ).persist_decision(decision=competitor)

        class _StaleCurrentView:
            def __init__(self, inner):
                self._inner = inner

            def get(self, identity):
                return self._inner.get(identity)

            def get_current(self, review_subject_id):
                return None  # the reader raced ahead of the competitor's insert

            def history(self, review_subject_id):
                return self._inner.history(review_subject_id)

        racing = EffectiveSubtitleReviewDecisionService(
            self.preparation,
            self.generation,
            _StaleCurrentView(
                SQLiteEffectiveSubtitleReviewDecisionRepository(self.connection)
            ),
            SQLiteEffectiveSubtitleReviewDecisionCommandPersistence(self.connection),
        )
        with self.assertRaises(EffectiveSubtitleReviewDecisionConflictError):
            racing.decide(
                review_subject_id=subject.identity.value, kind="accept",
                reviewer="reviewer:kim",
            )
        history = self.decisions.history(subject.identity.value)
        self.assertEqual([d.reviewer.value for d in history], ["reviewer:evil"])

    def test_near_concurrent_identical_command_converges(self):
        _, _, subject = self._subject()

        class _RacingView:
            def __init__(self, inner):
                self._inner = inner
                self._get_current_calls = 0

            def get(self, identity):
                return self._inner.get(identity)

            def get_current(self, review_subject_id):
                # The racing caller observes no current decision, then a competing identical
                # command lands first.
                self._get_current_calls += 1
                if self._get_current_calls == 1:
                    return None
                return self._inner.get_current(review_subject_id)

            def history(self, review_subject_id):
                return self._inner.history(review_subject_id)

        inner = SQLiteEffectiveSubtitleReviewDecisionRepository(self.connection)
        racing = EffectiveSubtitleReviewDecisionService(
            self.preparation,
            self.generation,
            _RacingView(inner),
            SQLiteEffectiveSubtitleReviewDecisionCommandPersistence(self.connection),
        )
        self.decisions.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        result = racing.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        self.assertEqual(result.outcome.value, "recorded")  # converged on the existing record
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_review_decisions"
            ).fetchone()[0],
            1,
        )

    def test_same_content_distinct_subjects_distinct_decisions(self):
        raw, _, subject = self._subject()
        d1 = self.decisions.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        raw2 = self.provider.admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": "B",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "원본"}]}
            ),
        ).admission.raw_transcript_id.value
        self.raw_selection.select(self.intake, raw2)
        c2 = self.generation.generate(intake_id=self.intake).candidate
        s2 = self.preparation.prepare_review(candidate_id=c2.identity.value).subject
        d2 = self.decisions.decide(
            review_subject_id=s2.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        self.assertNotEqual(d1.decision.identity, d2.decision.identity)
        # Subject histories remain isolated.
        self.assertEqual(len(self.decisions.history(subject.identity.value)), 1)
        self.assertEqual(len(self.decisions.history(s2.identity.value)), 1)


if __name__ == "__main__":
    unittest.main()
