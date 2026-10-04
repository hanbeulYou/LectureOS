"""Same-Source Text + Timing Composition (040 §19 `PATCH-0050`, TX-1…TX-39).

One explicit pair request applies one currently Accepted text candidate and one currently Accepted
timing candidate on the same original source into one composed replacement inside one complete
immutable revision. These tests drive the released chain end to end — real admission, real `§18`
Decisions, real SQLite files, separate connections where concurrency is the subject — and never
weaken a production guard to pass.
"""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.same_source_composition_generation import (
    CompositionCandidateNotAcceptedError,
    CompositionCombinedValidityError,
    CompositionIntegrityError,
    CompositionNotApplicableError,
    CompositionRoleError,
    CompositionStaleAuthorityError,
    SameSourceCompositionGeneration,
    SameSourceCompositionGenerationService,
    derive_composition_digest,
)
from lectureos.application.corrected_revision_selection import RevisionNotEligibleError
from lectureos.application.timing_correction_candidate_admission import (
    build_timing_correction_candidate_input,
)
from lectureos.application.timing_correction_revision_generation import (
    TimingCorrectionGenerationError,
    TimingCorrectionSetError,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_effective_srt_materialization_service,
    compose_sqlite_effective_subtitle_final_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_effective_subtitle_srt_artifact_service,
    compose_sqlite_same_source_composition_generation_service,
    compose_sqlite_timing_correction_candidate_admission_service,
    compose_sqlite_timing_correction_decision_service,
    compose_sqlite_timing_correction_revision_generation_service,
)
from lectureos.persistence import (
    SQLiteCorrectedTranscriptRevisionRepository,
    SQLiteCorrectionCandidateAdmissionRepository,
    SQLiteCorrectionCandidateDecisionRepository,
    SQLiteRawTranscriptRepository,
    SQLiteRawTranscriptSelectionRepository,
    SQLiteTranscriptSegmentRepository,
    open_sqlite_database,
)
from lectureos.persistence.same_source_composition_generation import (
    SQLiteSameSourceCompositionCommandPersistence,
    SQLiteSameSourceCompositionRepository,
)
from lectureos.persistence.timing_correction_candidate import (
    SQLiteTimingCorrectionCandidateRepository,
)
from lectureos.persistence.timing_correction_candidate_decision import (
    SQLiteTimingCorrectionDecisionRepository,
)
from lectureos.persistence.timing_correction_revision_generation import (
    SQLiteTimingCorrectionGenerationRepository,
)
from lectureos.validation import validate_database, validate_repository

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import TimingCorrectionFixture, temporary_fixture  # noqa: E402


class _Base(unittest.TestCase):
    """A released-chain repository with helpers that author and accept both candidate kinds."""

    def setUp(self) -> None:
        self._directory, self.fixture = temporary_fixture()
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.fixture.close)
        self.connection = self.fixture.connection
        self.composer = compose_sqlite_same_source_composition_generation_service(self.connection)
        self.compositions = SQLiteSameSourceCompositionRepository(self.connection)
        self.segments = SQLiteTranscriptSegmentRepository(self.connection)
        self.revisions = SQLiteCorrectedTranscriptRevisionRepository(self.connection)
        self.text_decisions = compose_sqlite_correction_candidate_decision_service(self.connection)
        self.timing_decisions = compose_sqlite_timing_correction_decision_service(self.connection)

    def _text(self, *, segment=None, ref="c1", text="둘째 문장입니다", accept=True, connection=None):
        connection = connection or self.connection
        source = segment or self.fixture.target
        candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=self.fixture.intake_id,
            candidate=build_correction_candidate_input(
                {
                    "raw_transcript_id": self.fixture.raw_transcript_id,
                    "segment_id": source.identity.value,
                    "candidate_ref": ref,
                    "source_type": "manual",
                    "source_reference": "human:editor-1",
                    "proposed_text": text,
                    "source_text_snapshot": source.text,
                    "rationale": "표현 교정",
                }
            ),
        ).candidate
        if accept:
            compose_sqlite_correction_candidate_decision_service(connection).decide(
                candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
            )
        return candidate

    def _timing(self, *, segment=None, ref="t1", start=18.0, end=24.0, accept=True, connection=None):
        connection = connection or self.connection
        source = segment or self.fixture.target
        candidate = compose_sqlite_timing_correction_candidate_admission_service(
            connection
        ).admit(
            intake_id=self.fixture.intake_id,
            candidate=build_timing_correction_candidate_input(
                self.fixture.proposal(
                    segment_id=source.identity.value,
                    candidate_ref=ref,
                    source_start_snapshot=source.start,
                    source_end_snapshot=source.end,
                    proposed_start=start,
                    proposed_end=end,
                )
            ),
        ).candidate
        if accept:
            compose_sqlite_timing_correction_decision_service(connection).decide(
                candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:lee"
            )
        return candidate

    def _compose(self, text, timing, composer=None):
        return (composer or self.composer).generate(
            text_candidate_id=text.identity.value, timing_candidate_id=timing.identity.value
        )

    def _counts(self, connection=None):
        connection = connection or self.connection
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "same_source_composition_generations",
                "corrected_transcript_revisions",
                "transcript_segments",
                "corrected_revision_generations",
                "timing_correction_revision_generations",
                "corrected_revision_selections",
            )
        }


class ExplicitPairAndScopeTests(_Base):
    """TX-1…TX-4, TX-10…TX-13: scope, roles, applicability, field ownership."""

    def test_the_pair_composes_both_accepted_values_into_one_replacement(self) -> None:
        text, timing = self._text(), self._timing()
        result = self._compose(text, timing)
        self.assertEqual(result.outcome, "created")
        generation = result.generation
        replacement = self.segments.get(generation.replacement_segment_id)
        source = self.fixture.target
        # Text from the text candidate, interval from the timing candidate, exactly (TX-12).
        self.assertEqual(replacement.text, "둘째 문장입니다")
        self.assertEqual(replacement.start, 18.0)
        self.assertEqual(replacement.end, 24.0)
        # Carried fields from the original source; nothing fabricated.
        self.assertEqual(replacement.transcript_id, source.transcript_id)
        self.assertEqual(replacement.source_timeline_id, source.source_timeline_id)
        self.assertEqual(replacement.source_order, source.source_order)
        self.assertEqual(replacement.speaker_label, source.speaker_label)
        self.assertIsNone(replacement.confidence)
        self.assertIsNone(replacement.uncertainty)
        self.assertEqual(replacement.replaces_segment_id, source.identity)
        # Complete revision: every other source by identity, in released order (TX-20).
        revision = self.revisions.get(generation.corrected_revision_id)
        expected = tuple(
            replacement.identity if sid == source.identity else sid
            for sid in self.fixture.raw_transcript.segment_ids
        )
        self.assertEqual(tuple(revision.segment_ids), expected)
        self.assertEqual(revision.parent_raw_transcript_id, self.fixture.raw_transcript.identity)
        # The released text-only reference carries exactly the applied text candidate (TX-19).
        self.assertEqual(tuple(revision.correction_candidate_ids), (text.identity,))
        # Both roles' provenance on the single owner (TX-18).
        self.assertEqual(generation.text_correction_candidate_id, text.identity)
        self.assertEqual(generation.timing_correction_candidate_id, timing.identity)
        self.assertEqual(
            generation.text_authorizing_decision_id,
            self.text_decisions.authority(text.identity.value).current_decision_id,
        )
        self.assertEqual(
            generation.timing_authorizing_decision_id,
            self.timing_decisions.authority(timing.identity.value).current_decision_id,
        )
        self.assertEqual(generation.replaced_segment_id, source.identity)
        # Source, candidates and Decisions untouched; no selection happened (TX-13, TX-38).
        self.assertEqual(self.segments.get(source.identity).text, source.text)
        self.assertEqual(self._counts()["corrected_revision_selections"], 0)
        report = validate_repository(self.connection)
        self.assertEqual([d.code for d in report.diagnostics], [])

    def test_option_order_is_irrelevant_but_roles_are_not(self) -> None:
        text, timing = self._text(), self._timing()
        first = self._compose(text, timing)
        # Passing the same pair "the other way round" is the same request only when the roles are
        # still right; the service is keyword-based, so the order of keyword arguments cannot matter.
        again = self.composer.generate(
            timing_candidate_id=timing.identity.value, text_candidate_id=text.identity.value
        )
        self.assertEqual(again.outcome, "reused")
        self.assertEqual(again.generation.identity, first.generation.identity)
        # A text identity in the timing role (and vice versa) is a malformed request (TX-2).
        with self.assertRaises(CompositionRoleError):
            self.composer.generate(
                text_candidate_id=timing.identity.value, timing_candidate_id=text.identity.value
            )
        with self.assertRaises(CompositionRoleError):
            self.composer.generate(
                text_candidate_id=text.identity.value, timing_candidate_id=text.identity.value
            )

    def test_a_missing_role_is_refused(self) -> None:
        text = self._text()
        with self.assertRaises(CompositionRoleError):
            self.composer.generate(text_candidate_id=text.identity.value, timing_candidate_id="")
        with self.assertRaises(CompositionRoleError):
            self.composer.generate(text_candidate_id="", timing_candidate_id="timing-correction-candidate:" + "0" * 64)
        self.assertEqual(self._counts()["same_source_composition_generations"], 0)

    def test_an_unknown_candidate_in_either_role_is_refused(self) -> None:
        text, timing = self._text(), self._timing()
        with self.assertRaises(Exception) as unknown_timing:
            self.composer.generate(
                text_candidate_id=text.identity.value,
                timing_candidate_id="timing-correction-candidate:" + "a" * 64,
            )
        self.assertIn("unknown timing", str(unknown_timing.exception))
        with self.assertRaises(Exception) as unknown_text:
            self.composer.generate(
                text_candidate_id="correction-candidate:" + "a" * 64,
                timing_candidate_id=timing.identity.value,
            )
        self.assertIn("unknown text", str(unknown_text.exception))

    def test_candidates_on_different_source_segments_are_refused(self) -> None:
        text = self._text()
        other = self.fixture.segments[2]
        timing = self._timing(segment=other, start=26.0, end=29.0)
        with self.assertRaises(CompositionNotApplicableError) as raised:
            self._compose(text, timing)
        self.assertIn("different source segments", str(raised.exception))
        self.assertEqual(self._counts()["same_source_composition_generations"], 0)

    def test_candidates_on_different_raw_transcripts_are_refused(self) -> None:
        # A second intake/raw in another repository is not reachable here, so the cross-base case is
        # exercised with a candidate pair whose admissions disagree on the raw transcript: build the
        # timing candidate, then switch the intake's current Raw and admit the text candidate there.
        timing = self._timing()
        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_current_raw_transcript_selection_service,
            compose_sqlite_provider_transcript_admission_service,
        )

        second = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.fixture.intake_id,
            document=build_provider_transcript_document(
                {
                    "provider": "fake-asr",
                    "model": "tiny",
                    "language": "ko",
                    "provider_result_ref": "B",
                    "segments": [
                        {"start": 0.0, "end": 2.5, "text": "첫 문장"},
                        {"start": 10.0, "end": 20.0, "text": "둘째 문장"},
                        {"start": 25.0, "end": 30.0, "text": "셋째 문장"},
                    ],
                }
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.fixture.intake_id, second.raw_transcript_id.value
        )
        raw_b = SQLiteRawTranscriptRepository(self.connection).get(second.raw_transcript_id)
        target_b = self.segments.get(raw_b.segment_ids[1])
        text = compose_sqlite_correction_candidate_admission_service(self.connection).admit(
            intake_id=self.fixture.intake_id,
            candidate=build_correction_candidate_input(
                {
                    "raw_transcript_id": raw_b.identity.value,
                    "segment_id": target_b.identity.value,
                    "candidate_ref": "cb",
                    "source_type": "manual",
                    "source_reference": "human:editor-1",
                    "proposed_text": "둘째 문장입니다",
                    "source_text_snapshot": target_b.text,
                    "rationale": "표현 교정",
                }
            ),
        ).candidate
        self.text_decisions.decide(candidate_id=text.identity.value, kind="accept", reviewer="reviewer:kim")
        with self.assertRaises(CompositionNotApplicableError) as raised:
            self._compose(text, timing)
        self.assertIn("different intakes or raw transcripts", str(raised.exception))

    def test_a_replacement_segment_is_never_a_valid_source(self) -> None:
        # Chaining stays closed: neither admission accepts a replacement as a target (TX-4), so a
        # composition can never be anchored on one. Verified through the released admissions.
        text, timing = self._text(), self._timing()
        replacement = self.segments.get(self._compose(text, timing).generation.replacement_segment_id)
        with self.assertRaises(Exception):
            compose_sqlite_correction_candidate_admission_service(self.connection).admit(
                intake_id=self.fixture.intake_id,
                candidate=build_correction_candidate_input(
                    {
                        "raw_transcript_id": self.fixture.raw_transcript_id,
                        "segment_id": replacement.identity.value,
                        "candidate_ref": "chain",
                        "source_type": "manual",
                        "source_reference": "human:editor-1",
                        "proposed_text": "또 교정",
                        "source_text_snapshot": replacement.text,
                        "rationale": "연쇄",
                    }
                ),
            )
        with self.assertRaises(Exception):
            compose_sqlite_timing_correction_candidate_admission_service(self.connection).admit(
                intake_id=self.fixture.intake_id,
                candidate=build_timing_correction_candidate_input(
                    self.fixture.proposal(
                        segment_id=replacement.identity.value,
                        candidate_ref="chain",
                        source_start_snapshot=replacement.start,
                        source_end_snapshot=replacement.end,
                        proposed_start=18.5,
                        proposed_end=23.5,
                    )
                ),
            )

    def test_un_named_competitors_neither_participate_nor_block(self) -> None:
        text, timing = self._text(), self._timing()
        self._text(ref="c2", text="둘째 문장이에요")  # a second accepted text candidate on the source
        self._timing(ref="t2", start=17.0, end=23.0)  # a second accepted timing candidate
        result = self._compose(text, timing)
        self.assertEqual(result.outcome, "created")
        self.assertEqual(result.generation.text_correction_candidate_id, text.identity)
        self.assertEqual(result.generation.timing_correction_candidate_id, timing.identity)
        self.assertEqual(self.segments.get(result.generation.replacement_segment_id).text, "둘째 문장입니다")
        # Naming this pair changed nobody else's Decision.
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM correction_candidate_decisions").fetchone()[0], 2)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM timing_correction_candidate_decisions").fetchone()[0], 2)

    def test_the_corrected_interval_need_not_be_a_subset_of_the_original(self) -> None:
        # Target is [10, 20]; next segment starts at 25. An end past the original end but before the
        # neighbour is admissible under the released TC-6/TC-7 (TX-11).
        text = self._text()
        timing = self._timing(start=19.0, end=24.5)
        result = self._compose(text, timing)
        replacement = self.segments.get(result.generation.replacement_segment_id)
        self.assertEqual((replacement.start, replacement.end), (19.0, 24.5))

    def test_same_reviewer_or_session_is_not_a_guard(self) -> None:
        # Text accepted by one reviewer, timing by another, at different moments: still composable.
        text, timing = self._text(), self._timing()
        text_reviewer = self.connection.execute(
            "SELECT reviewer FROM correction_candidate_decisions WHERE correction_candidate_id = ?",
            (text.identity.value,),
        ).fetchone()[0]
        timing_reviewer = self.connection.execute(
            "SELECT reviewer FROM timing_correction_candidate_decisions WHERE timing_correction_candidate_id = ?",
            (timing.identity.value,),
        ).fetchone()[0]
        self.assertNotEqual(text_reviewer, timing_reviewer)
        self.assertEqual(self._compose(text, timing).outcome, "created")

    def test_the_timing_set_still_refuses_a_text_identity(self) -> None:
        text, timing = self._text(), self._timing()
        timing_service = compose_sqlite_timing_correction_revision_generation_service(self.connection)
        with self.assertRaises(TimingCorrectionGenerationError):
            timing_service.generate_set(candidate_ids=(timing.identity.value, text.identity.value))
        with self.assertRaises(TimingCorrectionSetError):
            timing_service.generate_set(candidate_ids=())

    def test_text_only_and_timing_only_paths_still_do_not_compose(self) -> None:
        text, timing = self._text(), self._timing()
        text_revision = compose_sqlite_corrected_revision_generation_service(self.connection).generate(
            candidate_id=text.identity.value
        ).revision
        timing_revision = compose_sqlite_timing_correction_revision_generation_service(
            self.connection
        ).generate(candidate_id=timing.identity.value).revision
        composed = self._compose(text, timing).revision
        self.assertEqual(len({text_revision.identity, timing_revision.identity, composed.identity}), 3)
        self.assertEqual(self._counts()["same_source_composition_generations"], 1)


class AuthorityAndStalenessTests(_Base):
    """TX-5…TX-9, TX-24: current authority per role, derived Decisions, stale detection."""

    def test_an_undecided_or_rejected_role_refuses_the_whole_request(self) -> None:
        text, timing = self._text(accept=False), self._timing()
        with self.assertRaises(CompositionCandidateNotAcceptedError):
            self._compose(text, timing)
        self.text_decisions.decide(candidate_id=text.identity.value, kind="accept", reviewer="reviewer:kim")
        self.timing_decisions.decide(candidate_id=timing.identity.value, kind="reject", reviewer="reviewer:lee")
        with self.assertRaises(CompositionCandidateNotAcceptedError):
            self._compose(text, timing)
        self.assertEqual(self._counts()["same_source_composition_generations"], 0)
        self.assertEqual(self._counts()["corrected_transcript_revisions"], 0)

    def test_a_past_accept_does_not_bypass_a_current_reject(self) -> None:
        text, timing = self._text(), self._timing()
        created = self._compose(text, timing)
        self.timing_decisions.decide(candidate_id=timing.identity.value, kind="reject", reviewer="reviewer:lee")
        with self.assertRaises(CompositionCandidateNotAcceptedError):
            self._compose(text, timing)
        # The past result is still readable — lookup grants no authority (TX-27).
        self.assertIsNotNone(self.compositions.get(created.generation.identity))

    def test_a_stale_text_snapshot_refuses_without_partial_result(self) -> None:
        text, timing = self._text(), self._timing()
        # Switch the intake to another Raw: both candidates become inapplicable (parent not current).
        from lectureos.application.provider_transcript_admission import build_provider_transcript_document
        from lectureos.composition import (
            compose_sqlite_current_raw_transcript_selection_service,
            compose_sqlite_provider_transcript_admission_service,
        )

        second = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.fixture.intake_id,
            document=build_provider_transcript_document(
                {"provider": "fake-asr", "model": "tiny", "language": "ko", "provider_result_ref": "B",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "다른 문장"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.fixture.intake_id, second.raw_transcript_id.value
        )
        with self.assertRaises(CompositionNotApplicableError):
            self._compose(text, timing)
        self.assertEqual(self._counts()["same_source_composition_generations"], 0)

    def test_authority_moving_between_verification_and_persist_is_a_stale_failure(self) -> None:
        # Controlled seam: the persistence wrapper performs a Reject on a SEPARATE connection right
        # before delegating, so the in-transaction revalidation sees authority that moved after the
        # snapshot was fixed (TX-24). Nothing is written and nothing is silently re-bound.
        text, timing = self._text(), self._timing()
        path = self.fixture.database_path
        real = SQLiteSameSourceCompositionCommandPersistence(self.connection)

        class _Racing:
            def persist_same_source_composition(inner, **kwargs):
                other = open_sqlite_database(path)
                try:
                    compose_sqlite_correction_candidate_decision_service(other).decide(
                        candidate_id=text.identity.value, kind="reject", reviewer="reviewer:kim"
                    )
                finally:
                    other.close()
                return real.persist_same_source_composition(**kwargs)

        service = SameSourceCompositionGenerationService(
            SQLiteCorrectionCandidateAdmissionRepository(self.connection),
            SQLiteCorrectionCandidateDecisionRepository(self.connection),
            SQLiteTimingCorrectionCandidateRepository(self.connection),
            SQLiteTimingCorrectionDecisionRepository(self.connection),
            SQLiteRawTranscriptSelectionRepository(self.connection),
            SQLiteRawTranscriptRepository(self.connection),
            self.segments,
            self.compositions,
            _Racing(),
        )
        with self.assertRaises(CompositionStaleAuthorityError):
            self._compose(text, timing, composer=service)
        self.assertEqual(self._counts()["same_source_composition_generations"], 0)
        self.assertEqual(self._counts()["corrected_transcript_revisions"], 0)
        self.assertFalse(self.connection.in_transaction)

    def test_a_different_accept_after_re_accept_is_a_different_anchor(self) -> None:
        text, timing = self._text(), self._timing()
        first = self._compose(text, timing)
        self.timing_decisions.decide(candidate_id=timing.identity.value, kind="reject", reviewer="reviewer:lee")
        self.timing_decisions.decide(candidate_id=timing.identity.value, kind="accept", reviewer="reviewer:lee")
        second = self._compose(text, timing)
        self.assertEqual(second.outcome, "created")
        self.assertNotEqual(second.generation.identity, first.generation.identity)
        self.assertNotEqual(second.generation.replacement_segment_id, first.generation.replacement_segment_id)
        # Same content, different authority: two entities, both persisted (TX-16/TX-17).
        self.assertEqual(second.generation.content_fingerprint, first.generation.content_fingerprint)
        self.assertEqual(self._counts()["same_source_composition_generations"], 2)
        self.assertIsNotNone(self.compositions.get(first.generation.identity))


class IdentityAndIntegrityTests(_Base):
    """TX-14…TX-17, TX-27…TX-30: role-tagged anchor, replay, complete-result integrity."""

    def test_replay_and_restart_converge_on_the_same_identities(self) -> None:
        text, timing = self._text(), self._timing()
        first = self._compose(text, timing)
        again = self._compose(text, timing)
        self.assertEqual(again.outcome, "reused")
        self.assertEqual(again.generation, first.generation)
        self.connection.close()
        reopened = open_sqlite_database(self.fixture.database_path)
        self.addCleanup(reopened.close)
        after_restart = compose_sqlite_same_source_composition_generation_service(reopened).generate(
            text_candidate_id=text.identity.value, timing_candidate_id=timing.identity.value
        )
        self.assertEqual(after_restart.outcome, "reused")
        self.assertEqual(after_restart.generation.identity, first.generation.identity)
        self.assertEqual(self._counts(reopened)["same_source_composition_generations"], 1)
        self.fixture.connection = reopened  # keep the fixture's cleanup consistent

    def test_the_anchor_is_role_tagged_and_order_independent(self) -> None:
        text, timing = self._text(), self._timing()
        t_dec = self.text_decisions.authority(text.identity.value).current_decision_id
        m_dec = self.timing_decisions.authority(timing.identity.value).current_decision_id
        raw, source = self.fixture.raw_transcript.identity, self.fixture.target.identity
        digest = derive_composition_digest(raw, source, text.identity, t_dec, timing.identity, m_dec)
        result = self._compose(text, timing)
        self.assertTrue(result.generation.identity.value.endswith(digest))
        # Swapping what sits in each role is a different digest — roles are keys, not positions.
        swapped = derive_composition_digest(raw, source, timing.identity, m_dec, text.identity, t_dec)
        self.assertNotEqual(digest, swapped)

    def test_pairs_sharing_one_candidate_are_distinct_and_share_no_replacement(self) -> None:
        text = self._text()
        timing_b = self._timing(ref="tb", start=18.0, end=24.0)
        timing_c = self._timing(ref="tc", start=17.0, end=23.0)
        ab = self._compose(text, timing_b)
        ac = self._compose(text, timing_c)
        self.assertEqual((ab.outcome, ac.outcome), ("created", "created"))
        self.assertNotEqual(ab.generation.identity, ac.generation.identity)
        self.assertNotEqual(ab.revision.identity, ac.revision.identity)
        self.assertNotEqual(ab.generation.replacement_segment_id, ac.generation.replacement_segment_id)
        self.assertEqual(self._counts()["same_source_composition_generations"], 2)
        self.assertEqual([d.code for d in validate_repository(self.connection).diagnostics], [])

    def test_the_composed_replacement_never_reuses_a_sibling_identity(self) -> None:
        text, timing = self._text(), self._timing()
        text_gen = compose_sqlite_corrected_revision_generation_service(self.connection).generate(
            candidate_id=text.identity.value
        ).generation
        timing_gen = compose_sqlite_timing_correction_revision_generation_service(self.connection).generate(
            candidate_id=timing.identity.value
        ).generation
        composed = self._compose(text, timing).generation
        self.assertNotIn(
            composed.replacement_segment_id,
            {text_gen.replacement_segment_id, timing_gen.replacement_segment_id},
        )
        # The siblings' payloads are untouched.
        self.assertEqual(self.segments.get(text_gen.replacement_segment_id).start, self.fixture.target.start)
        self.assertEqual(self.segments.get(timing_gen.replacement_segment_id).text, self.fixture.target.text)

    def _corrupt(self, sql, params=()):
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute(sql, params)
        self.connection.execute("PRAGMA foreign_keys = ON")

    def test_a_swapped_role_binding_is_an_integrity_failure_despite_equal_fingerprint(self) -> None:
        text, timing = self._text(), self._timing()
        created = self._compose(text, timing)
        other_text = self._text(ref="c2", text="둘째 문장입니다")  # same proposed text, other candidate
        # Rebind the stored text role to the other candidate: content identical, provenance wrong.
        self._corrupt(
            "UPDATE same_source_composition_generations SET text_correction_candidate_id = ? WHERE identity = ?",
            (other_text.identity.value, created.generation.identity.value),
        )
        with self.assertRaises(CompositionIntegrityError) as raised:
            self._compose(text, timing)
        self.assertIn("different candidate", str(raised.exception))

    def test_a_mismatched_replacement_payload_is_an_integrity_failure(self) -> None:
        text, timing = self._text(), self._timing()
        created = self._compose(text, timing)
        self._corrupt(
            "UPDATE transcript_segments SET speaker_label = 'ghost' WHERE identity = ?",
            (created.generation.replacement_segment_id.value,),
        )
        with self.assertRaises(CompositionIntegrityError) as raised:
            self._compose(text, timing)
        self.assertIn("canonical payload or lineage", str(raised.exception))

    def test_a_mispositioned_membership_is_an_integrity_failure(self) -> None:
        text, timing = self._text(), self._timing()
        created = self._compose(text, timing)
        revision_id = created.revision.identity.value
        # Swap ordinals 0 and 1 in the stored membership: same members, wrong order.
        self._corrupt(
            "UPDATE corrected_transcript_revision_segments SET ordinal = 99 WHERE transcript_revision_id = ? AND ordinal = 0",
            (revision_id,),
        )
        self._corrupt(
            "UPDATE corrected_transcript_revision_segments SET ordinal = 0 WHERE transcript_revision_id = ? AND ordinal = 1",
            (revision_id,),
        )
        self._corrupt(
            "UPDATE corrected_transcript_revision_segments SET ordinal = 1 WHERE transcript_revision_id = ? AND ordinal = 99",
            (revision_id,),
        )
        # The membership is still dense and references the right entities, so the released reader
        # loads it; complete-result integrity (TX-28 condition 4) is what refuses the wrong order.
        with self.assertRaises(CompositionIntegrityError) as raised:
            self._compose(text, timing)
        self.assertIn("ordered segment membership", str(raised.exception))

    def test_different_content_under_the_same_anchor_is_a_conflict_not_an_overwrite(self) -> None:
        text, timing = self._text(), self._timing()
        created = self._compose(text, timing)
        self._corrupt(
            "UPDATE same_source_composition_generations SET content_fingerprint = ? WHERE identity = ?",
            ("f" * 64, created.generation.identity.value),
        )
        from lectureos.application.same_source_composition_generation import (
            CompositionRevisionConflictError,
        )

        with self.assertRaises(CompositionRevisionConflictError):
            self._compose(text, timing)


class AtomicityAndConcurrencyTests(unittest.TestCase):
    """TX-25, IR 11–13: all-or-nothing, real concurrent connections, collision integrity."""

    def setUp(self) -> None:
        self._directory, self.fixture = temporary_fixture()
        self.addCleanup(self._directory.cleanup)
        connection = self.fixture.connection
        self.text = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=self.fixture.intake_id,
            candidate=build_correction_candidate_input(
                {
                    "raw_transcript_id": self.fixture.raw_transcript_id,
                    "segment_id": self.fixture.target.identity.value,
                    "candidate_ref": "c1",
                    "source_type": "manual",
                    "source_reference": "human:editor-1",
                    "proposed_text": "둘째 문장입니다",
                    "source_text_snapshot": self.fixture.target.text,
                    "rationale": "표현 교정",
                }
            ),
        ).candidate
        compose_sqlite_correction_candidate_decision_service(connection).decide(
            candidate_id=self.text.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        self.timing = compose_sqlite_timing_correction_candidate_admission_service(connection).admit(
            intake_id=self.fixture.intake_id,
            candidate=build_timing_correction_candidate_input(self.fixture.proposal()),
        ).candidate
        compose_sqlite_timing_correction_decision_service(connection).decide(
            candidate_id=self.timing.identity.value, kind="accept", reviewer="reviewer:lee"
        )
        connection.close()

    def _service(self, barrier=None, connection=None):
        if connection is None:
            connection = open_sqlite_database(self.fixture.database_path)
            self.addCleanup(connection.close)
        compositions = SQLiteSameSourceCompositionRepository(connection)
        if barrier is not None:
            real = compositions

            class _Gated:
                """Both requests pass the pre-persist lookup before either may write."""

                def get(inner, identity):
                    found = real.get(identity)
                    if found is None:
                        barrier.wait(timeout=10)
                    return found

                def revision(inner, revision_id):
                    return real.revision(revision_id)

            compositions = _Gated()
        service = SameSourceCompositionGenerationService(
            SQLiteCorrectionCandidateAdmissionRepository(connection),
            SQLiteCorrectionCandidateDecisionRepository(connection),
            SQLiteTimingCorrectionCandidateRepository(connection),
            SQLiteTimingCorrectionDecisionRepository(connection),
            SQLiteRawTranscriptSelectionRepository(connection),
            SQLiteRawTranscriptRepository(connection),
            SQLiteTranscriptSegmentRepository(connection),
            compositions,
            SQLiteSameSourceCompositionCommandPersistence(connection),
        )
        return connection, service

    def test_concurrent_identical_requests_converge_through_the_collision_path(self) -> None:
        # Two real connections, one file, a barrier placed after BOTH have found no stored result:
        # both race to BEGIN IMMEDIATE, the loser's insert collides, and it converges only after the
        # same complete-result integrity check the pre-persist lookup would have applied (TX-28).
        barrier = threading.Barrier(2)
        results, errors = {}, {}

        def run(name):
            # SQLite connections are thread-bound: each worker opens its own on the shared file.
            connection = open_sqlite_database(self.fixture.database_path)
            try:
                _, service = self._service(barrier, connection=connection)
                results[name] = service.generate(
                    text_candidate_id=self.text.identity.value,
                    timing_candidate_id=self.timing.identity.value,
                )
            except Exception as error:  # pragma: no cover - surfaced by the assertions below
                errors[name] = error
            finally:
                connection.close()

        threads = [threading.Thread(target=run, args=(n,)) for n in ("a", "b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(errors, {})
        outcomes = sorted(result.outcome for result in results.values())
        self.assertEqual(outcomes, ["created", "reused"])
        identities = {result.generation.identity for result in results.values()}
        self.assertEqual(len(identities), 1)
        connection, _ = self._service()
        self.assertEqual(
            connection.execute("SELECT COUNT(*) FROM same_source_composition_generations").fetchone()[0], 1
        )
        self.assertEqual(
            connection.execute("SELECT COUNT(*) FROM corrected_transcript_revisions").fetchone()[0], 1
        )
        self.assertEqual([d.code for d in validate_repository(connection).diagnostics], [])

    def test_a_persist_failure_leaves_no_partial_result_and_preserves_siblings(self) -> None:
        connection, _ = self._service()
        # Pre-existing siblings and a shared state that a failed composition must not disturb.
        text_rev = compose_sqlite_corrected_revision_generation_service(connection).generate(
            candidate_id=self.text.identity.value
        ).revision
        before = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in (
                "corrected_transcript_revisions", "corrected_transcript_revision_segments",
                "transcript_segments", "corrected_revision_generations",
                "correction_candidate_decisions", "timing_correction_candidate_decisions",
            )
        }
        real = SQLiteSameSourceCompositionCommandPersistence(connection)

        class _Failing:
            def persist_same_source_composition(inner, **kwargs):
                # Make the final INSERT fail by planting a conflicting replacement identity row
                # AFTER the replacement is verified absent: the whole transaction must roll back.
                kwargs = dict(kwargs)
                original = kwargs["revalidate"]

                def revalidate():
                    original()
                    connection.execute(
                        "INSERT INTO same_source_composition_generations VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (
                            "same-source-composition-generation:" + "e" * 64,
                            text_rev.identity.value,  # owned elsewhere -> collision inside the tx
                            kwargs["generation"].parent_raw_transcript_id.value,
                            kwargs["generation"].replaced_segment_id.value,
                            kwargs["generation"].text_correction_candidate_id.value,
                            kwargs["generation"].text_authorizing_decision_id.value,
                            kwargs["generation"].timing_correction_candidate_id.value,
                            kwargs["generation"].timing_authorizing_decision_id.value,
                            kwargs["generation"].replacement_segment_id.value,
                            "0" * 64,
                        ),
                    )

                kwargs["revalidate"] = revalidate
                return real.persist_same_source_composition(**kwargs)

        service = SameSourceCompositionGenerationService(
            SQLiteCorrectionCandidateAdmissionRepository(connection),
            SQLiteCorrectionCandidateDecisionRepository(connection),
            SQLiteTimingCorrectionCandidateRepository(connection),
            SQLiteTimingCorrectionDecisionRepository(connection),
            SQLiteRawTranscriptSelectionRepository(connection),
            SQLiteRawTranscriptRepository(connection),
            SQLiteTranscriptSegmentRepository(connection),
            SQLiteSameSourceCompositionRepository(connection),
            _Failing(),
        )
        with self.assertRaises(Exception):
            service.generate(
                text_candidate_id=self.text.identity.value, timing_candidate_id=self.timing.identity.value
            )
        self.assertFalse(connection.in_transaction)
        after = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in before
        }
        self.assertEqual(before, after)
        self.assertEqual(
            connection.execute("SELECT COUNT(*) FROM same_source_composition_generations").fetchone()[0], 0
        )


class SelectionLifecycleAndHistoryTests(_Base):
    """TX-31…TX-38 and IR 14–15, 18–19: `§20`, both-kind history, downstream delivery."""

    def setUp(self) -> None:
        super().setUp()
        self.selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        self.storage_root = Path(self._directory.name) / "out"
        self.storage_root.mkdir()

    def _deliver(self):
        subtitles = compose_sqlite_effective_subtitle_generation_service(self.connection)
        preparation = compose_sqlite_effective_subtitle_review_preparation_service(self.connection)
        review = compose_sqlite_effective_subtitle_review_decision_service(self.connection)
        final = compose_sqlite_effective_subtitle_final_selection_service(self.connection)
        export = compose_sqlite_effective_subtitle_srt_artifact_service(self.connection)
        materializer = compose_sqlite_effective_srt_materialization_service(
            self.connection, str(self.storage_root)
        )
        candidate = subtitles.generate(intake_id=self.fixture.intake_id).candidate
        subject = preparation.prepare_review(candidate_id=candidate.identity.value).subject
        review.decide(review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim")
        selection = final.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        ).selection
        artifact = export.generate_srt_artifact(final_selection_id=selection.identity.value).artifact
        materialization = materializer.materialize(artifact_id=artifact.identity.value).materialization
        return (self.storage_root / materialization.relative_location).read_text(encoding="utf-8")

    def test_a_composed_revision_is_selectable_and_applicable_when_both_roles_are_accepted(self) -> None:
        text, timing = self._text(), self._timing()
        result = self._compose(text, timing)
        self.selection.select_revision(revision_id=result.revision.identity.value, reviewer="reviewer:kim")
        effective = self.selection.resolve_effective_transcript(self.fixture.intake_id)
        self.assertEqual(effective.effective_kind.value, "corrected_revision")
        self.assertEqual(effective.corrected_revision_id, result.revision.identity)

    def test_generation_alone_changes_no_selection_or_artifact(self) -> None:
        text, timing = self._text(), self._timing()
        before_srt = self._deliver()  # raw delivery, before any composition
        self._compose(text, timing)
        self.assertEqual(self._counts()["corrected_revision_selections"], 0)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM subtitle_effective_srt_artifacts").fetchone()[0], 1
        )
        self.assertEqual(self._deliver(), before_srt)

    def test_explicit_selection_delivers_both_corrections_in_one_cue(self) -> None:
        text, timing = self._text(), self._timing()
        result = self._compose(text, timing)
        self.selection.select_revision(revision_id=result.revision.identity.value, reviewer="reviewer:kim")
        srt = self._deliver()
        self.assertIn("둘째 문장입니다", srt)
        self.assertIn("00:00:18,000 --> 00:00:24,000", srt)
        self.assertNotIn("둘째 문장\n", srt)

    def test_reject_of_either_role_blocks_new_generation_and_selection_but_keeps_history(self) -> None:
        text, timing = self._text(), self._timing()
        result = self._compose(text, timing)
        self.selection.select_revision(revision_id=result.revision.identity.value, reviewer="reviewer:kim")
        self.text_decisions.decide(candidate_id=text.identity.value, kind="reject", reviewer="reviewer:kim")
        # Existing selection record preserved; effective resolution reports inapplicability.
        self.assertEqual(self._counts()["corrected_revision_selections"], 1)
        effective = self.selection.resolve_effective_transcript(self.fixture.intake_id)
        self.assertEqual(effective.effective_kind.value, "inapplicable_selection")
        self.assertEqual(effective.inapplicability_reason, "candidate_not_accepted")
        # No new generation, no new selection; the past revision and its provenance are intact.
        with self.assertRaises(CompositionCandidateNotAcceptedError):
            self._compose(text, timing)
        with self.assertRaises(RevisionNotEligibleError):
            self.selection.select_revision(revision_id=result.revision.identity.value, reviewer="reviewer:kim")
        stored = self.compositions.get(result.generation.identity)
        self.assertEqual(stored, result.generation)
        # The timing role alone rejected is equally blocking.
        self.text_decisions.decide(candidate_id=text.identity.value, kind="accept", reviewer="reviewer:kim")
        self.timing_decisions.decide(candidate_id=timing.identity.value, kind="reject", reviewer="reviewer:lee")
        self.assertEqual(
            self.selection.resolve_effective_transcript(self.fixture.intake_id).inapplicability_reason,
            "candidate_not_accepted",
        )

    def test_re_accept_makes_the_past_composition_applicable_again_without_rewriting(self) -> None:
        text, timing = self._text(), self._timing()
        result = self._compose(text, timing)
        self.selection.select_revision(revision_id=result.revision.identity.value, reviewer="reviewer:kim")
        self.timing_decisions.decide(candidate_id=timing.identity.value, kind="reject", reviewer="reviewer:lee")
        self.timing_decisions.decide(candidate_id=timing.identity.value, kind="accept", reviewer="reviewer:lee")
        effective = self.selection.resolve_effective_transcript(self.fixture.intake_id)
        self.assertEqual(effective.effective_kind.value, "corrected_revision")
        stored = self.compositions.get(result.generation.identity)
        # Authorizing references are never rewritten to the new Decision (TX-34).
        self.assertEqual(stored.timing_authorizing_decision_id, result.generation.timing_authorizing_decision_id)
        self.assertNotEqual(
            stored.timing_authorizing_decision_id,
            self.timing_decisions.authority(timing.identity.value).current_decision_id,
        )

    def test_both_candidate_histories_list_the_composition_once_with_both_roles(self) -> None:
        text, timing = self._text(), self._timing()
        text_gen = compose_sqlite_corrected_revision_generation_service(self.connection).generate(
            candidate_id=text.identity.value
        ).generation
        timing_service = compose_sqlite_timing_correction_revision_generation_service(self.connection)
        timing_gen = timing_service.generate(candidate_id=timing.identity.value).generation
        composed = self._compose(text, timing).generation
        self._compose(text, timing)  # replay adds nothing
        text_history = compose_sqlite_corrected_revision_generation_service(
            self.connection
        ).generations_for_candidate(text.identity.value)
        timing_history = timing_service.generations_for_candidate(timing.identity.value)
        self.assertEqual({g.identity for g in text_history}, {text_gen.identity, composed.identity})
        self.assertEqual({g.identity for g in timing_history}, {timing_gen.identity, composed.identity})
        for history in (text_history, timing_history):
            entry = next(g for g in history if isinstance(g, SameSourceCompositionGeneration))
            self.assertEqual(entry.text_correction_candidate_id, text.identity)
            self.assertEqual(entry.timing_correction_candidate_id, timing.identity)
            self.assertEqual([g.identity.value for g in history], sorted(g.identity.value for g in history))
        # A current Reject hides nothing (TX-37).
        self.text_decisions.decide(candidate_id=text.identity.value, kind="reject", reviewer="reviewer:kim")
        self.assertEqual(
            {g.identity for g in compose_sqlite_corrected_revision_generation_service(
                self.connection).generations_for_candidate(text.identity.value)},
            {text_gen.identity, composed.identity},
        )

    def test_validator_flags_a_revision_owned_by_two_kinds_and_a_wrong_role_decision(self) -> None:
        text, timing = self._text(), self._timing()
        composed = self._compose(text, timing)
        timing_gen = compose_sqlite_timing_correction_revision_generation_service(self.connection).generate(
            candidate_id=timing.identity.value
        ).generation
        self.connection.execute("PRAGMA foreign_keys = OFF")
        # A timing singleton row claiming the composed revision: ownership collision in both directions.
        self.connection.execute(
            "INSERT INTO timing_correction_revision_generations VALUES (?,?,?,?,?,?,?,?)",
            (
                "timing-correction-revision-generation:" + "d" * 64,
                composed.revision.identity.value,
                "timing-correction-candidate:" + "d" * 64,
                "timing-correction-candidate-decision:" + "d" * 64,
                self.fixture.raw_transcript_id,
                timing_gen.replaced_segment_id.value,
                timing_gen.replacement_segment_id.value,
                "0" * 64,
            ),
        )
        self.connection.execute("PRAGMA foreign_keys = ON")
        codes = [d.code for d in validate_database(self.fixture.database_path).diagnostics]
        self.assertIn("SAME_SOURCE_COMPOSITION_OWNERSHIP_COLLISION", codes)
        self.assertIn("TIMING_CORRECTION_GENERATION_KIND_COLLISION", codes)
        # A timing Decision in the text role is unauthorized provenance.
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute(
            "UPDATE same_source_composition_generations SET text_authorizing_decision_id = ? WHERE identity = ?",
            (composed.generation.timing_authorizing_decision_id.value, composed.generation.identity.value),
        )
        self.connection.execute("PRAGMA foreign_keys = ON")
        codes = [d.code for d in validate_database(self.fixture.database_path).diagnostics]
        self.assertIn("SAME_SOURCE_COMPOSITION_DANGLING_TEXT_DECISION", codes)

    def test_existing_writers_refuse_a_revision_owned_by_a_composition(self) -> None:
        # Reverse-direction ownership: the released text and timing writers consult the composition
        # relation and refuse to adopt its revision (TX-21).
        from lectureos.persistence.corrected_revision_generation import (
            SQLiteCorrectedRevisionGenerationCommandPersistence,
        )
        from lectureos.persistence.timing_correction_revision_generation import (
            SQLiteTimingCorrectionGenerationCommandPersistence,
        )

        text, timing = self._text(), self._timing()
        composed = self._compose(text, timing)
        self.assertTrue(
            SQLiteCorrectedRevisionGenerationCommandPersistence(self.connection)._revision_owned_elsewhere(
                composed.revision.identity
            )
        )
        self.assertTrue(
            SQLiteTimingCorrectionGenerationCommandPersistence(self.connection)._revision_owned_elsewhere(
                composed.revision.identity
            )
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
