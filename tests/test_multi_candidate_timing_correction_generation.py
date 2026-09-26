"""Multi-candidate Timing Correction Revision Generation (040 §19, PATCH-0049 MG-1…MG-38).

Pins the explicit-set contract at both cardinalities: what the caller must name, what is refused,
canonical ordering and order independence, combined validity that individual TC-7 admission cannot
imply, singleton legacy compatibility, per-member replacement identity and verified reuse,
complete-result integrity (and that a matching content fingerprint never substitutes for it),
authority snapshot and staleness, atomic rollback, and the generation/selection boundary.
"""

from __future__ import annotations

import sqlite3
import unittest

from lectureos.application.corrected_revision_selection import (
    RevisionNotEligibleError,
    SelectionApplicability,
)
from lectureos.application.timing_correction_candidate_admission import (
    build_timing_correction_candidate_input,
)
from lectureos.application.timing_correction_revision_generation import (
    TimingCandidateNotAcceptedError,
    TimingCandidateNotApplicableError,
    TimingCorrectionCombinedValidityError,
    TimingCorrectionCompetingCandidatesError,
    TimingCorrectionGenerationError,
    TimingCorrectionRevisionIntegrityError,
    TimingCorrectionSetError,
    TimingCorrectionStaleAuthorityError,
    derive_timing_generation_digest,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_timing_correction_candidate_admission_service,
    compose_sqlite_timing_correction_decision_service,
    compose_sqlite_timing_correction_revision_generation_service,
)
from lectureos.persistence import (
    SQLiteCorrectedTranscriptRevisionRepository,
    SQLiteTranscriptSegmentRepository,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError
from lectureos.persistence.timing_correction_revision_generation import (
    SQLiteTimingCorrectionGenerationRepository,
)
from lectureos.validation.repository_validator import validate_repository

# `tests/` is not a package, so a single-module invocation does not put it on sys.path the way
# discovery does; this keeps both `unittest discover` and `unittest tests.<module>` working.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import temporary_fixture  # noqa: E402

# Four well-separated segments, so several corrections can be admitted independently and applied
# together without the fixture itself forcing a conflict.
SEGMENTS = (
    {"start": 0.0, "end": 2.5, "text": "첫 문장"},
    {"start": 10.0, "end": 20.0, "text": "둘째 문장"},
    {"start": 25.0, "end": 30.0, "text": "셋째 문장"},
    {"start": 40.0, "end": 44.0, "text": "넷째 문장"},
)


class MultiCandidateTimingGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory, self.fixture = temporary_fixture(segments=SEGMENTS)
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.fixture.close)
        self.connection = self.fixture.connection
        self.admissions = compose_sqlite_timing_correction_candidate_admission_service(
            self.connection
        )
        self.decisions = compose_sqlite_timing_correction_decision_service(self.connection)
        self.generator = compose_sqlite_timing_correction_revision_generation_service(
            self.connection
        )
        self.generations = SQLiteTimingCorrectionGenerationRepository(self.connection)
        self.segments = SQLiteTranscriptSegmentRepository(self.connection)
        self.revisions = SQLiteCorrectedTranscriptRevisionRepository(self.connection)

    # -- helpers ------------------------------------------------------------------------------

    def _candidate(self, index: int, start: float, end: float, ref: str = "t"):
        source = self.fixture.segments[index]
        return self.admissions.admit(
            intake_id=self.fixture.intake_id,
            candidate=build_timing_correction_candidate_input(
                {
                    "raw_transcript_id": self.fixture.raw_transcript_id,
                    "segment_id": source.identity.value,
                    "candidate_ref": f"{ref}{index}",
                    "author": "human:editor-1",
                    "source_start_snapshot": source.start,
                    "source_end_snapshot": source.end,
                    "proposed_start": start,
                    "proposed_end": end,
                    "rationale": "사람이 실제 발화를 듣고 측정했다",
                }
            ),
        ).candidate

    def _accepted(self, index: int, start: float, end: float, ref: str = "t"):
        candidate = self._candidate(index, start, end, ref)
        self.decisions.decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        return candidate

    def _pair(self):
        """Two accepted corrections on different source segments, safe together."""

        return (
            self._accepted(1, 12.0, 21.0),
            self._accepted(3, 41.0, 45.0),
        )

    # -- explicit set (MG-7/MG-8/MG-9) ----------------------------------------------------------

    def test_an_empty_set_is_refused(self) -> None:
        with self.assertRaises(TimingCorrectionSetError):
            self.generator.generate_set(candidate_ids=())

    def test_a_repeated_identity_is_refused_rather_than_deduplicated(self) -> None:
        first, _ = self._pair()
        with self.assertRaises(TimingCorrectionSetError) as raised:
            self.generator.generate_set(
                candidate_ids=(first.identity.value, first.identity.value)
            )
        self.assertIn("repeat", str(raised.exception))

    def test_a_bare_string_is_not_silently_treated_as_a_set(self) -> None:
        first, _ = self._pair()
        with self.assertRaises(TimingCorrectionSetError):
            self.generator.generate_set(candidate_ids=first.identity.value)

    def test_an_unnamed_accepted_candidate_never_joins_the_set(self) -> None:
        first, second = self._pair()
        result = self.generator.generate_set(candidate_ids=(first.identity.value,))
        self.assertEqual(len(result.view.members), 1)
        self.assertNotIn(second.identity, result.view.candidate_ids)
        # ...and naming one never changes the other's Decision.
        self.assertEqual(
            self.decisions.authority(second.identity.value).status.value, "accepted"
        )

    def test_an_explicit_subset_is_permitted(self) -> None:
        first, second = self._pair()
        third = self._accepted(2, 26.0, 31.0)
        result = self.generator.generate_set(
            candidate_ids=(first.identity.value, third.identity.value)
        )
        self.assertEqual(len(result.view.members), 2)
        self.assertNotIn(second.identity, result.view.candidate_ids)

    def test_an_unknown_identity_refuses_the_whole_set(self) -> None:
        first, _ = self._pair()
        unknown = "timing-correction-candidate:" + "0" * 64
        with self.assertRaises(TimingCorrectionGenerationError):
            self.generator.generate_set(candidate_ids=(first.identity.value, unknown))
        self.assertEqual(self._generation_count(), (0, 0))

    # -- one candidate per source segment (MG-3/MG-14/MG-15) ------------------------------------

    def test_two_candidates_on_one_source_segment_are_refused_by_name(self) -> None:
        first = self._accepted(1, 12.0, 21.0, ref="a")
        competitor = self._accepted(1, 13.0, 22.0, ref="b")
        with self.assertRaises(TimingCorrectionCompetingCandidatesError):
            self.generator.generate_set(
                candidate_ids=(first.identity.value, competitor.identity.value)
            )
        self.assertEqual(self._generation_count(), (0, 0))

    def test_a_stored_competitor_does_not_block_the_named_choice(self) -> None:
        first = self._accepted(1, 12.0, 21.0, ref="a")
        competitor = self._accepted(1, 13.0, 22.0, ref="b")
        other = self._accepted(3, 41.0, 45.0)
        result = self.generator.generate_set(
            candidate_ids=(first.identity.value, other.identity.value)
        )
        self.assertEqual(len(result.view.members), 2)
        self.assertNotIn(competitor.identity, result.view.candidate_ids)
        self.assertEqual(
            self.decisions.authority(competitor.identity.value).status.value, "accepted"
        )

    # -- one base (MG-2) ------------------------------------------------------------------------

    def test_a_set_spanning_two_raw_transcripts_is_refused(self) -> None:
        first, _ = self._pair()
        other_directory, other = temporary_fixture(
            segments=SEGMENTS, provider_result_ref="B"
        )
        self.addCleanup(other_directory.cleanup)
        self.addCleanup(other.close)
        # A foreign candidate cannot even be resolved here, but the set rule is what must refuse a
        # mixed base; assert through a second raw transcript admitted into THIS repository instead.
        foreign = "timing-correction-candidate:" + "1" * 64
        with self.assertRaises(TimingCorrectionGenerationError):
            self.generator.generate_set(candidate_ids=(first.identity.value, foreign))

    # -- authority (MG-12) ----------------------------------------------------------------------

    def test_one_undecided_member_refuses_the_whole_set(self) -> None:
        first, _ = self._pair()
        undecided = self._candidate(2, 26.0, 31.0)
        with self.assertRaises(TimingCandidateNotAcceptedError):
            self.generator.generate_set(
                candidate_ids=(first.identity.value, undecided.identity.value)
            )
        self.assertEqual(self._generation_count(), (0, 0))

    def test_one_rejected_member_refuses_the_whole_set(self) -> None:
        first, second = self._pair()
        self.decisions.decide(
            candidate_id=second.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        with self.assertRaises(TimingCandidateNotAcceptedError):
            self.generator.generate_set(
                candidate_ids=(first.identity.value, second.identity.value)
            )
        self.assertEqual(self._generation_count(), (0, 0))

    def test_a_past_acceptance_never_authorizes_under_a_current_reject(self) -> None:
        first, second = self._pair()
        created = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        self.decisions.decide(
            candidate_id=second.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        # The past result stays queryable (MG-27)...
        stored = self.generations.view(created.view.identity)
        self.assertIsNotNone(stored)
        self.assertEqual(len(stored.members), 2)
        # ...but re-issuing the generation command is refused, existing result or not (MG-28).
        with self.assertRaises(TimingCandidateNotAcceptedError):
            self.generator.generate_set(
                candidate_ids=(first.identity.value, second.identity.value)
            )

    def test_re_accept_is_a_new_anchor_not_a_replay(self) -> None:
        first, second = self._pair()
        original = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        self.decisions.decide(
            candidate_id=second.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        self.decisions.decide(
            candidate_id=second.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        regenerated = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        self.assertEqual(regenerated.outcome, "created")
        self.assertNotEqual(regenerated.view.identity, original.view.identity)
        self.assertNotEqual(
            regenerated.revision.identity, original.revision.identity
        )
        # The original keeps its own authorizing provenance, untouched.
        self.assertIsNotNone(self.generations.view(original.view.identity))

    # -- staleness (MG-13) ----------------------------------------------------------------------

    def test_a_stale_source_snapshot_refuses_the_whole_set(self) -> None:
        first, second = self._pair()
        self.connection.execute(
            "UPDATE transcript_segments SET end = end + 1.0 WHERE identity = ?",
            (self.fixture.segments[3].identity.value,),
        )
        with self.assertRaises(TimingCandidateNotApplicableError):
            self.generator.generate_set(
                candidate_ids=(first.identity.value, second.identity.value)
            )
        self.assertEqual(self._generation_count(), (0, 0))

    def test_authority_moving_inside_the_write_transaction_fails_the_request(self) -> None:
        # MG-13 must hold at persist time, not merely at guard time: a revalidation raising inside
        # the transaction must leave no new record behind.
        first, second = self._pair()
        service = self.generator
        original = service._require_snapshot_unchanged

        def moved(snapshot):
            original(snapshot)
            raise TimingCorrectionStaleAuthorityError("authority moved during generation")

        service._require_snapshot_unchanged = moved
        with self.assertRaises(TimingCorrectionStaleAuthorityError):
            service.generate_set(
                candidate_ids=(first.identity.value, second.identity.value)
            )
        service._require_snapshot_unchanged = original
        self.assertEqual(self._generation_count(), (0, 0))
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM corrected_transcript_revisions"
            ).fetchone()[0],
            0,
        )

    # -- canonical ordering and order independence (MG-16/MG-17) --------------------------------

    def test_members_are_ordered_by_source_segment_ordinal(self) -> None:
        early = self._accepted(1, 12.0, 21.0)
        late = self._accepted(3, 41.0, 45.0)
        result = self.generator.generate_set(
            candidate_ids=(late.identity.value, early.identity.value)
        )
        self.assertEqual(
            [member.timing_correction_candidate_id for member in result.view.members],
            [early.identity, late.identity],
        )

    def test_input_order_does_not_change_identity_or_content(self) -> None:
        first, second = self._pair()
        forward = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        reverse = self.generator.generate_set(
            candidate_ids=(second.identity.value, first.identity.value)
        )
        self.assertEqual(reverse.outcome, "reused")
        self.assertEqual(reverse.view.identity, forward.view.identity)
        self.assertEqual(reverse.revision.identity, forward.revision.identity)
        self.assertEqual(
            reverse.view.content_fingerprint, forward.view.content_fingerprint
        )

    # -- complete snapshot and combined validation (MG-4/MG-18) ---------------------------------

    def test_the_result_is_a_complete_snapshot_with_every_correction_applied(self) -> None:
        first, second = self._pair()
        result = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        revision = self.revisions.get(result.revision.identity)
        self.assertEqual(
            len(revision.segment_ids), len(self.fixture.raw_transcript.segment_ids)
        )
        applied = {
            member.replaced_segment_id: member.replacement_segment_id
            for member in result.view.members
        }
        for ordinal, source_id in enumerate(self.fixture.raw_transcript.segment_ids):
            expected = applied.get(source_id, source_id)
            self.assertEqual(revision.segment_ids[ordinal], expected)
        # Unchanged segments keep their identity; corrected ones carry the accepted intervals only.
        for member, candidate in zip(result.view.members, (first, second)):
            replacement = self.segments.get(member.replacement_segment_id)
            source = self.segments.get(member.replaced_segment_id)
            self.assertEqual(replacement.text, source.text)
            self.assertEqual(replacement.start, candidate.proposed_start)
            self.assertEqual(replacement.end, candidate.proposed_end)

    def test_individually_admissible_corrections_that_overlap_together_are_refused(self) -> None:
        # The constructed counterexample: TC-7 judges each proposal against the ORIGINAL neighbours,
        # so both are admitted, yet applied together they overlap.
        first = self._accepted(0, 0.0, 8.0)
        second = self._accepted(1, 4.0, 20.0)
        with self.assertRaises(TimingCorrectionCombinedValidityError) as raised:
            self.generator.generate_set(
                candidate_ids=(first.identity.value, second.identity.value)
            )
        self.assertIn("overlap", str(raised.exception))
        self.assertEqual(self._generation_count(), (0, 0))

    def test_a_combined_validity_failure_clamps_nothing(self) -> None:
        first = self._accepted(0, 0.0, 8.0)
        second = self._accepted(1, 4.0, 20.0)
        with self.assertRaises(TimingCorrectionCombinedValidityError):
            self.generator.generate_set(
                candidate_ids=(first.identity.value, second.identity.value)
            )
        for candidate, start, end in ((first, 0.0, 8.0), (second, 4.0, 20.0)):
            stored = self.connection.execute(
                "SELECT proposed_start, proposed_end FROM timing_correction_candidates "
                "WHERE identity = ?",
                (candidate.identity.value,),
            ).fetchone()
            self.assertEqual(stored, (start, end))

    def test_touching_boundaries_stay_allowed(self) -> None:
        # The released contract allows an interval to end exactly where the next begins.
        first = self._accepted(1, 12.0, 25.0)
        second = self._accepted(3, 41.0, 45.0)
        result = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        self.assertEqual(result.outcome, "created")

    # -- identity (MG-21/MG-22/MG-24) -----------------------------------------------------------

    def test_a_one_member_set_uses_the_released_singleton_identity_and_relation(self) -> None:
        first, _ = self._pair()
        through_set = self.generator.generate_set(candidate_ids=(first.identity.value,))
        authority = self.decisions.authority(first.identity.value)
        expected_digest = derive_timing_generation_digest(
            first.identity, authority.current_decision_id
        )
        self.assertTrue(
            through_set.view.identity.value.endswith(expected_digest),
            "a singleton keeps the released identity encoding",
        )
        self.assertTrue(through_set.view.is_legacy_singleton)
        self.assertEqual(self._generation_count(), (1, 0))

    def test_the_released_single_candidate_call_is_unchanged(self) -> None:
        first, _ = self._pair()
        released = self.generator.generate(candidate_id=first.identity.value)
        self.assertEqual(released.outcome, "created")
        replay = self.generator.generate(candidate_id=first.identity.value)
        self.assertEqual(replay.outcome, "reused")
        self.assertEqual(replay.generation.identity, released.generation.identity)
        self.assertEqual(self._generation_count(), (1, 0))

    def test_changing_the_membership_is_a_different_anchor(self) -> None:
        first, second = self._pair()
        third = self._accepted(2, 26.0, 31.0)
        pair = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        triple = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value, third.identity.value)
        )
        self.assertNotEqual(pair.view.identity, triple.view.identity)
        self.assertNotEqual(pair.revision.identity, triple.revision.identity)

    def test_a_member_replacement_is_shared_across_aggregates_and_the_singleton(self) -> None:
        shared = self._accepted(1, 12.0, 21.0)
        second = self._accepted(3, 41.0, 45.0)
        third = self._accepted(2, 26.0, 31.0)
        singleton = self.generator.generate(candidate_id=shared.identity.value)
        first_pair = self.generator.generate_set(
            candidate_ids=(shared.identity.value, second.identity.value)
        )
        other_pair = self.generator.generate_set(
            candidate_ids=(shared.identity.value, third.identity.value)
        )
        shared_id = singleton.generation.replacement_segment_id
        for result in (first_pair, other_pair):
            member = next(
                m
                for m in result.view.members
                if m.timing_correction_candidate_id == shared.identity
            )
            self.assertEqual(member.replacement_segment_id, shared_id)
        # One entity, reused — not three near-duplicates.
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM transcript_segments WHERE identity = ?",
                (shared_id.value,),
            ).fetchone()[0],
            1,
        )
        # ...and the three revisions are distinct results that all reference it.
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(DISTINCT transcript_revision_id) "
                "FROM corrected_transcript_revision_segments WHERE transcript_segment_id = ?",
                (shared_id.value,),
            ).fetchone()[0],
            3,
        )

    def test_a_corrupted_existing_replacement_refuses_the_whole_generation(self) -> None:
        shared = self._accepted(1, 12.0, 21.0)
        second = self._accepted(3, 41.0, 45.0)
        singleton = self.generator.generate(candidate_id=shared.identity.value)
        # Corrupt the shared entity's payload, then require it from a new aggregate.
        self.connection.execute(
            "UPDATE transcript_segments SET text = '다른 본문' WHERE identity = ?",
            (singleton.generation.replacement_segment_id.value,),
        )
        with self.assertRaises(PersistenceError) as raised:
            self.generator.generate_set(
                candidate_ids=(shared.identity.value, second.identity.value)
            )
        self.assertIn("does not match", str(raised.exception))
        self.assertEqual(self._generation_count(), (1, 0))

    # -- complete-result integrity (MG-29/MG-31) ------------------------------------------------

    def test_an_identical_request_is_reused(self) -> None:
        first, second = self._pair()
        created = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        replay = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        self.assertEqual(created.outcome, "created")
        self.assertEqual(replay.outcome, "reused")
        self.assertEqual(replay.view.identity, created.view.identity)
        self.assertEqual(self._generation_count(), (0, 1))

    def test_reuse_is_refused_when_member_provenance_differs(self) -> None:
        first, second = self._pair()
        created = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        # Rebind a member to a different candidate: the CONTENT is untouched, so the fingerprint
        # still matches — provenance integrity must catch it anyway.
        other = self._accepted(2, 26.0, 31.0)
        self.connection.execute(
            "UPDATE timing_correction_revision_generation_members "
            "SET timing_correction_candidate_id = ? "
            "WHERE aggregate_generation_id = ? AND member_ordinal = 1",
            (other.identity.value, created.view.identity.value),
        )
        with self.assertRaises(TimingCorrectionRevisionIntegrityError) as raised:
            self.generator.generate_set(
                candidate_ids=(first.identity.value, second.identity.value)
            )
        self.assertIn("different candidate", str(raised.exception))

    def test_reuse_is_refused_when_a_member_is_missing(self) -> None:
        first, second = self._pair()
        created = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        self.connection.execute(
            "DELETE FROM timing_correction_revision_generation_members "
            "WHERE aggregate_generation_id = ? AND member_ordinal = 1",
            (created.view.identity.value,),
        )
        with self.assertRaises(PersistenceError):
            # The projection refuses an incomplete aggregate before reuse is even considered.
            self.generator.generate_set(
                candidate_ids=(first.identity.value, second.identity.value)
            )

    def test_reuse_is_refused_when_the_revision_membership_order_differs(self) -> None:
        first, second = self._pair()
        created = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        revision_id = created.revision.identity.value
        # A genuine REORDER, not corruption: the ordinals stay a dense sequence and every expected
        # replacement is still present, only arranged differently. Content equality cannot see this.
        rows = self.connection.execute(
            "SELECT ordinal, transcript_segment_id FROM corrected_transcript_revision_segments "
            "WHERE transcript_revision_id = ? ORDER BY ordinal",
            (revision_id,),
        ).fetchall()
        self.connection.execute(
            "DELETE FROM corrected_transcript_revision_segments WHERE transcript_revision_id = ?",
            (revision_id,),
        )
        swapped = [rows[1][1], rows[0][1], *[row[1] for row in rows[2:]]]
        self.connection.executemany(
            "INSERT INTO corrected_transcript_revision_segments("
            "transcript_revision_id, ordinal, transcript_segment_id) VALUES (?, ?, ?)",
            [(revision_id, ordinal, value) for ordinal, value in enumerate(swapped)],
        )
        with self.assertRaises(TimingCorrectionRevisionIntegrityError) as raised:
            self.generator.generate_set(
                candidate_ids=(first.identity.value, second.identity.value)
            )
        self.assertIn("ordered segment membership", str(raised.exception))

    def test_corrupt_revision_ordering_is_refused_by_the_repository_reader_first(self) -> None:
        # Distinguished from the case above: a non-dense ordinal is repository corruption, and the
        # released reader refuses it before reuse is considered. The guard is not weakened to let
        # the integrity check "win" the race to report it.
        first, second = self._pair()
        created = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        self.connection.execute(
            "UPDATE corrected_transcript_revision_segments SET ordinal = 99 "
            "WHERE transcript_revision_id = ? AND ordinal = 0",
            (created.revision.identity.value,),
        )
        with self.assertRaises(PersistenceError):
            self.generator.generate_set(
                candidate_ids=(first.identity.value, second.identity.value)
            )

    def test_reuse_is_refused_when_a_member_replacement_is_swapped(self) -> None:
        first, second = self._pair()
        created = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        # Point member 0 at a real but unrelated segment: the revision, the content, and every
        # other relationship are untouched, so only the mapping condition can catch it.
        self.connection.execute(
            "UPDATE timing_correction_revision_generation_members "
            "SET replacement_segment_id = ? "
            "WHERE aggregate_generation_id = ? AND member_ordinal = 0",
            (self.fixture.segments[2].identity.value, created.view.identity.value),
        )
        with self.assertRaises(TimingCorrectionRevisionIntegrityError) as raised:
            self.generator.generate_set(
                candidate_ids=(first.identity.value, second.identity.value)
            )
        self.assertIn("different replacement segment", str(raised.exception))

    # -- atomicity (MG-19/MG-20) ----------------------------------------------------------------

    def test_a_persistence_failure_leaves_no_partial_result(self) -> None:
        first, second = self._pair()
        third = self._accepted(2, 26.0, 31.0)
        keeper = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        before = self._snapshot()
        # Block the aggregate insert, then attempt a different, valid aggregate.
        self.connection.execute(
            "CREATE TRIGGER block_aggregate "
            "BEFORE INSERT ON timing_correction_revision_aggregate_generations "
            "BEGIN SELECT RAISE(ABORT, 'blocked'); END"
        )
        try:
            with self.assertRaises(PersistenceError):
                self.generator.generate_set(
                    candidate_ids=(first.identity.value, third.identity.value)
                )
        finally:
            self.connection.execute("DROP TRIGGER block_aggregate")
        self.assertEqual(before, self._snapshot())
        # The pre-existing aggregate and its shared replacement survived untouched.
        self.assertIsNotNone(self.generations.view(keeper.view.identity))

    # -- selection and downstream (MG-32…MG-38) -------------------------------------------------

    def test_generation_alone_selects_nothing(self) -> None:
        first, second = self._pair()
        self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        self.assertIsNone(selection.current(self.fixture.intake_id))

    def test_an_aggregate_revision_can_be_selected_and_resolves_effectively(self) -> None:
        first, second = self._pair()
        result = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        selection.select_revision(
            revision_id=result.revision.identity.value, reviewer="reviewer:kim"
        )
        effective = selection.resolve_effective_transcript(self.fixture.intake_id)
        self.assertEqual(effective.effective_kind.value, "corrected_revision")
        self.assertEqual(effective.corrected_revision_id, result.revision.identity)
        self.assertEqual(
            selection.applicability(self.fixture.intake_id),
            SelectionApplicability(applicable=True),
        )

    def test_one_member_reject_makes_the_whole_aggregate_inapplicable(self) -> None:
        first, second = self._pair()
        result = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        selection.select_revision(
            revision_id=result.revision.identity.value, reviewer="reviewer:kim"
        )
        self.decisions.decide(
            candidate_id=second.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        applicability = selection.applicability(self.fixture.intake_id)
        self.assertFalse(applicability.applicable)
        self.assertEqual(applicability.reason, "candidate_not_accepted")
        effective = selection.resolve_effective_transcript(self.fixture.intake_id)
        self.assertEqual(effective.effective_kind.value, "inapplicable_selection")
        # The selection record itself is preserved — never auto-deselected or rewritten.
        current = selection.current(self.fixture.intake_id)
        self.assertEqual(current.corrected_revision_id, result.revision.identity)

    def test_member_re_accept_makes_the_past_aggregate_applicable_again(self) -> None:
        first, second = self._pair()
        result = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        selection.select_revision(
            revision_id=result.revision.identity.value, reviewer="reviewer:kim"
        )
        self.decisions.decide(
            candidate_id=second.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        self.decisions.decide(
            candidate_id=second.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        # No agreement between the CURRENT Decision identity and the authorizing one is required.
        self.assertTrue(selection.applicability(self.fixture.intake_id).applicable)
        # ...and the aggregate's authorizing references were never rewritten to the new Decision.
        stored = self.generations.view(result.view.identity)
        self.assertEqual(stored.members, result.view.members)
        current = self.decisions.authority(second.identity.value).current_decision_id
        authorizing = next(
            m.authorizing_decision_id
            for m in stored.members
            if m.timing_correction_candidate_id == second.identity
        )
        self.assertNotEqual(current, authorizing)

    def test_a_revision_with_a_rejected_member_cannot_be_newly_selected(self) -> None:
        first, second = self._pair()
        result = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        self.decisions.decide(
            candidate_id=second.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        with self.assertRaises(RevisionNotEligibleError):
            selection.select_revision(
                revision_id=result.revision.identity.value, reviewer="reviewer:kim"
            )

    # -- restart and repository health ----------------------------------------------------------

    def test_an_aggregate_survives_restart_and_replays_as_reuse(self) -> None:
        first, second = self._pair()
        created = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        self.connection.close()
        connection = open_sqlite_database(self.fixture.database_path)
        self.addCleanup(connection.close)
        stored = SQLiteTimingCorrectionGenerationRepository(connection).view(
            created.view.identity
        )
        self.assertEqual(stored.members, created.view.members)
        replay = compose_sqlite_timing_correction_revision_generation_service(
            connection
        ).generate_set(candidate_ids=(second.identity.value, first.identity.value))
        self.assertEqual(replay.outcome, "reused")
        self.assertEqual(replay.revision.identity, created.revision.identity)

    def test_repository_validation_is_healthy_with_aggregates_present(self) -> None:
        first, second = self._pair()
        result = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        compose_sqlite_corrected_revision_selection_service(
            self.connection
        ).select_revision(
            revision_id=result.revision.identity.value, reviewer="reviewer:kim"
        )
        report = validate_repository(self.connection)
        self.assertEqual(report.schema_version, 55)
        self.assertEqual([d.code for d in report.diagnostics], [])

    def test_incomplete_member_provenance_is_reported_as_corruption(self) -> None:
        first, second = self._pair()
        created = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        self.connection.execute(
            "DELETE FROM timing_correction_revision_generation_members "
            "WHERE aggregate_generation_id = ? AND member_ordinal = 1",
            (created.view.identity.value,),
        )
        report = validate_repository(self.connection)
        self.assertIn(
            "TIMING_CORRECTION_AGGREGATE_INCOMPLETE_MEMBERSHIP",
            [d.code for d in report.diagnostics],
        )

    # -- scope guards ---------------------------------------------------------------------------

    def test_a_replacement_segment_is_never_a_valid_generation_target(self) -> None:
        # Revision-on-revision chaining stays closed: a replacement segment is not part of the Raw
        # Transcript, so a candidate against it is refused at admission.
        first, second = self._pair()
        result = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        replacement = result.view.members[0].replacement_segment_id
        with self.assertRaises(Exception):
            self.admissions.admit(
                intake_id=self.fixture.intake_id,
                candidate=build_timing_correction_candidate_input(
                    {
                        "raw_transcript_id": self.fixture.raw_transcript_id,
                        "segment_id": replacement.value,
                        "candidate_ref": "chain",
                        "author": "human:editor-1",
                        "source_start_snapshot": 12.0,
                        "source_end_snapshot": 21.0,
                        "proposed_start": 12.5,
                        "proposed_end": 21.5,
                        "rationale": "chaining must stay closed",
                    }
                ),
            )

    # -- helpers ------------------------------------------------------------------------------

    def _generation_count(self) -> tuple[int, int]:
        return (
            self.connection.execute(
                "SELECT COUNT(*) FROM timing_correction_revision_generations"
            ).fetchone()[0],
            self.connection.execute(
                "SELECT COUNT(*) FROM timing_correction_revision_aggregate_generations"
            ).fetchone()[0],
        )

    def _snapshot(self) -> dict:
        return {
            table: self.connection.execute(
                f"SELECT * FROM {table} ORDER BY 1"
            ).fetchall()
            for table in (
                "timing_correction_revision_generations",
                "timing_correction_revision_aggregate_generations",
                "timing_correction_revision_generation_members",
                "corrected_transcript_revisions",
                "corrected_transcript_revision_segments",
                "transcript_segments",
                "corrected_revision_selections",
                "timing_correction_candidate_decisions",
            )
        }


class ConcurrentAggregateGenerationTests(unittest.TestCase):
    """Two real connections racing on the same database file (MG-31), not mock call counting."""

    def setUp(self) -> None:
        self._directory, self.fixture = temporary_fixture(segments=SEGMENTS)
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.fixture.close)
        admissions = compose_sqlite_timing_correction_candidate_admission_service(
            self.fixture.connection
        )
        decisions = compose_sqlite_timing_correction_decision_service(
            self.fixture.connection
        )

        def accepted(index, start, end):
            source = self.fixture.segments[index]
            candidate = admissions.admit(
                intake_id=self.fixture.intake_id,
                candidate=build_timing_correction_candidate_input(
                    {
                        "raw_transcript_id": self.fixture.raw_transcript_id,
                        "segment_id": source.identity.value,
                        "candidate_ref": f"t{index}",
                        "author": "human:editor-1",
                        "source_start_snapshot": source.start,
                        "source_end_snapshot": source.end,
                        "proposed_start": start,
                        "proposed_end": end,
                        "rationale": "사람이 측정했다",
                    }
                ),
            ).candidate
            decisions.decide(
                candidate_id=candidate.identity.value,
                kind="accept",
                reviewer="reviewer:kim",
            )
            return candidate

        self.a = accepted(1, 12.0, 21.0)
        self.b = accepted(3, 41.0, 45.0)
        self.c = accepted(2, 26.0, 31.0)
        self.fixture.connection.close()

    def _service(self):
        connection = open_sqlite_database(self.fixture.database_path)
        self.addCleanup(connection.close)
        return connection, compose_sqlite_timing_correction_revision_generation_service(
            connection
        )

    def test_concurrent_identical_requests_converge_on_one_result(self) -> None:
        _, first = self._service()
        _, second = self._service()
        one = first.generate_set(candidate_ids=(self.a.identity.value, self.b.identity.value))
        two = second.generate_set(candidate_ids=(self.b.identity.value, self.a.identity.value))
        self.assertEqual(one.outcome, "created")
        self.assertEqual(two.outcome, "reused")
        self.assertEqual(two.view.identity, one.view.identity)
        connection, _ = self._service()
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM timing_correction_revision_aggregate_generations"
            ).fetchone()[0],
            1,
        )

    def test_two_aggregates_sharing_one_member_are_two_distinct_results(self) -> None:
        # G1 = {A, B} and G2 = {A, C}: A's replacement is verified-reused, and the shared entity is
        # never mistaken for a duplicate request on the same anchor.
        _, first = self._service()
        _, second = self._service()
        g1 = first.generate_set(candidate_ids=(self.a.identity.value, self.b.identity.value))
        g2 = second.generate_set(candidate_ids=(self.a.identity.value, self.c.identity.value))
        self.assertEqual(g1.outcome, "created")
        self.assertEqual(g2.outcome, "created")
        self.assertNotEqual(g1.view.identity, g2.view.identity)
        shared_in_g1 = next(
            m for m in g1.view.members if m.timing_correction_candidate_id == self.a.identity
        )
        shared_in_g2 = next(
            m for m in g2.view.members if m.timing_correction_candidate_id == self.a.identity
        )
        self.assertEqual(
            shared_in_g1.replacement_segment_id, shared_in_g2.replacement_segment_id
        )
        connection, _ = self._service()
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM transcript_segments WHERE identity = ?",
                (shared_in_g1.replacement_segment_id.value,),
            ).fetchone()[0],
            1,
        )
        report = validate_repository(connection)
        self.assertEqual([d.code for d in report.diagnostics], [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
