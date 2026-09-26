"""Timing candidate generation history completeness (OI-1 from the PATCH-0049 implementation review).

`generations_for_candidate()` used to query only the released singleton relation, so a candidate
applied as a member of an aggregate generation reported no history at all. These tests pin what the
answer must contain: the candidate's singleton **and** every aggregate it is an explicit member of,
each generation exactly once, with complete member provenance, in a deterministic order, and
without the query writing anything or filtering by current authority.

This is a read completeness fix. Nothing about admission, authority, identity, persistence,
selection or effective consumption changes, and no schema or migration is involved.
"""

from __future__ import annotations

import unittest

from lectureos.application.timing_correction_candidate_admission import (
    build_timing_correction_candidate_input,
)
from lectureos.application.timing_correction_revision_generation import (
    TimingCorrectionGenerationError,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_timing_correction_candidate_admission_service,
    compose_sqlite_timing_correction_decision_service,
    compose_sqlite_timing_correction_revision_generation_service,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.persistence import open_sqlite_database
from lectureos.persistence.timing_correction_revision_generation import (
    SQLiteTimingCorrectionGenerationRepository,
)

# `tests/` is not a package, so a single-module invocation does not put it on sys.path the way
# discovery does; this keeps both `unittest discover` and `unittest tests.<module>` working.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import temporary_fixture  # noqa: E402

# Four well-separated segments, so several corrections coexist without forcing a conflict.
SEGMENTS = (
    {"start": 0.0, "end": 2.5, "text": "첫 문장"},
    {"start": 10.0, "end": 20.0, "text": "둘째 문장"},
    {"start": 25.0, "end": 30.0, "text": "셋째 문장"},
    {"start": 40.0, "end": 44.0, "text": "넷째 문장"},
)


class TimingCandidateGenerationHistoryTests(unittest.TestCase):
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

    # -- helpers ------------------------------------------------------------------------------

    def _accepted(self, index: int, start: float, end: float, ref: str = "t"):
        source = self.fixture.segments[index]
        candidate = self.admissions.admit(
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
        self.decisions.decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        return candidate

    def _history(self, candidate) -> tuple:
        return self.generator.generations_for_candidate(candidate.identity.value)

    def _snapshot(self) -> dict:
        return {
            table: self.connection.execute(
                f"SELECT * FROM {table} ORDER BY 1"
            ).fetchall()
            for table in (
                "timing_correction_revision_generations",
                "timing_correction_revision_aggregate_generations",
                "timing_correction_revision_generation_members",
                "timing_correction_candidates",
                "timing_correction_candidate_decisions",
                "corrected_transcript_revisions",
                "corrected_transcript_revision_segments",
                "transcript_segments",
                "corrected_revision_selections",
            )
        }

    # -- the released singleton case is unchanged ------------------------------------------------

    def test_a_singleton_only_candidate_reports_its_singleton(self) -> None:
        candidate = self._accepted(1, 12.0, 21.0)
        created = self.generator.generate(candidate_id=candidate.identity.value)
        history = self._history(candidate)
        self.assertEqual(len(history), 1)
        entry = history[0]
        self.assertEqual(entry.identity, created.generation.identity)
        self.assertEqual(entry.corrected_revision_id, created.revision.identity)
        self.assertTrue(entry.is_legacy_singleton)
        self.assertEqual(entry.candidate_ids, (candidate.identity,))
        # The released record's provenance survives the projection intact.
        member = entry.members[0]
        self.assertEqual(member.authorizing_decision_id, created.generation.authorizing_decision_id)
        self.assertEqual(member.replaced_segment_id, created.generation.replaced_segment_id)
        self.assertEqual(member.replacement_segment_id, created.generation.replacement_segment_id)
        self.assertEqual(entry.content_fingerprint, created.generation.content_fingerprint)

    # -- the defect OI-1 names -------------------------------------------------------------------

    def test_a_candidate_applied_only_in_an_aggregate_reports_that_aggregate(self) -> None:
        first = self._accepted(1, 12.0, 21.0)
        second = self._accepted(3, 41.0, 45.0)
        created = self.generator.generate_set(
            candidate_ids=(first.identity.value, second.identity.value)
        )
        for candidate in (first, second):
            history = self._history(candidate)
            self.assertEqual(
                len(history), 1, "aggregate participation must appear in the candidate's history"
            )
            self.assertEqual(history[0].identity, created.view.identity)
            self.assertFalse(history[0].is_legacy_singleton)

    def test_a_candidate_reports_its_singleton_and_every_aggregate_exactly_once(self) -> None:
        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        c = self._accepted(2, 26.0, 31.0)
        s_a = self.generator.generate(candidate_id=a.identity.value)
        g_ab = self.generator.generate_set(candidate_ids=(a.identity.value, b.identity.value))
        g_ac = self.generator.generate_set(candidate_ids=(a.identity.value, c.identity.value))
        g_bc = self.generator.generate_set(candidate_ids=(b.identity.value, c.identity.value))

        identities = [entry.identity for entry in self._history(a)]
        self.assertEqual(
            sorted(identity.value for identity in identities),
            sorted(
                identity.value
                for identity in (s_a.generation.identity, g_ab.view.identity, g_ac.view.identity)
            ),
        )
        self.assertNotIn(g_bc.view.identity, identities)
        self.assertEqual(len(identities), len(set(identities)), "one entry per generation")

    def test_the_queried_candidate_filters_generations_not_members(self) -> None:
        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        created = self.generator.generate_set(
            candidate_ids=(a.identity.value, b.identity.value)
        )
        from_a = next(e for e in self._history(a) if e.identity == created.view.identity)
        from_b = next(e for e in self._history(b) if e.identity == created.view.identity)
        # Querying by one member must not trim the other out of the generation.
        self.assertEqual(from_a.members, created.view.members)
        self.assertEqual(from_a.members, from_b.members)
        self.assertEqual(set(from_a.candidate_ids), {a.identity, b.identity})

    def test_aggregates_sharing_a_replacement_stay_distinct_history_entries(self) -> None:
        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        c = self._accepted(2, 26.0, 31.0)
        g_ab = self.generator.generate_set(candidate_ids=(a.identity.value, b.identity.value))
        g_ac = self.generator.generate_set(candidate_ids=(a.identity.value, c.identity.value))
        shared = {
            m.replacement_segment_id
            for view in (g_ab.view, g_ac.view)
            for m in view.members
            if m.timing_correction_candidate_id == a.identity
        }
        self.assertEqual(len(shared), 1, "the shared replacement is one entity")
        history = self._history(a)
        self.assertEqual(len(history), 2, "a shared replacement must not merge two generations")
        self.assertEqual(
            {entry.identity for entry in history}, {g_ab.view.identity, g_ac.view.identity}
        )

    # -- a source-identity boundary the query must not blur --------------------------------------

    def test_an_equally_timed_candidate_on_another_segment_is_not_reported(self) -> None:
        # Same proposed interval shape, different source segment: a different authority fact that
        # must never be folded into this candidate's history.
        a = self._accepted(1, 12.0, 21.0)
        other = self._accepted(2, 26.0, 31.0)
        mine = self.generator.generate(candidate_id=a.identity.value)
        theirs = self.generator.generate(candidate_id=other.identity.value)
        self.assertNotEqual(mine.generation.identity, theirs.generation.identity)
        self.assertEqual([e.identity for e in self._history(a)], [mine.generation.identity])
        self.assertEqual([e.identity for e in self._history(other)], [theirs.generation.identity])

    # -- lifecycle: history is not applicability --------------------------------------------------

    def test_replay_does_not_add_a_history_entry(self) -> None:
        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        self.generator.generate_set(candidate_ids=(a.identity.value, b.identity.value))
        before = self._history(a)
        replay = self.generator.generate_set(
            candidate_ids=(b.identity.value, a.identity.value)
        )
        self.assertEqual(replay.outcome, "reused")
        self.assertEqual(self._history(a), before)

    def test_history_survives_a_member_reject(self) -> None:
        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        created = self.generator.generate_set(
            candidate_ids=(a.identity.value, b.identity.value)
        )
        self.decisions.decide(
            candidate_id=b.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        for candidate in (a, b):
            self.assertIn(
                created.view.identity, [e.identity for e in self._history(candidate)]
            )

    def test_history_survives_a_current_raw_transcript_switch(self) -> None:
        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        created = self.generator.generate_set(
            candidate_ids=(a.identity.value, b.identity.value)
        )
        other = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.fixture.intake_id,
            document=build_provider_transcript_document(
                {
                    "provider": "fake-asr",
                    "model": "tiny",
                    "language": "ko",
                    "provider_result_ref": "B",
                    "segments": [dict(segment) for segment in SEGMENTS],
                }
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.fixture.intake_id, other.raw_transcript_id.value
        )
        self.assertIn(created.view.identity, [e.identity for e in self._history(a)])

    def test_reject_then_re_accept_yields_two_distinct_retained_entries(self) -> None:
        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        first = self.generator.generate_set(
            candidate_ids=(a.identity.value, b.identity.value)
        )
        self.decisions.decide(
            candidate_id=b.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        self.decisions.decide(
            candidate_id=b.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        second = self.generator.generate_set(
            candidate_ids=(a.identity.value, b.identity.value)
        )
        self.assertNotEqual(second.view.identity, first.view.identity)
        identities = [e.identity for e in self._history(b)]
        self.assertIn(first.view.identity, identities)
        self.assertIn(second.view.identity, identities)
        # Each keeps the Decision that actually authorized it; nothing is rewritten forward.
        authorizing = {
            e.identity: next(
                m.authorizing_decision_id
                for m in e.members
                if m.timing_correction_candidate_id == b.identity
            )
            for e in self._history(b)
        }
        self.assertNotEqual(
            authorizing[first.view.identity], authorizing[second.view.identity]
        )

    # -- ordering and restart ----------------------------------------------------------------------

    def test_ordering_is_deterministic_and_stable_across_restart(self) -> None:
        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        c = self._accepted(2, 26.0, 31.0)
        self.generator.generate(candidate_id=a.identity.value)
        self.generator.generate_set(candidate_ids=(a.identity.value, b.identity.value))
        self.generator.generate_set(candidate_ids=(a.identity.value, c.identity.value))
        first = [e.identity.value for e in self._history(a)]
        self.assertEqual(first, sorted(first), "ordered by generation identity")
        self.assertEqual(first, [e.identity.value for e in self._history(a)])
        self.connection.close()
        connection = open_sqlite_database(self.fixture.database_path)
        self.addCleanup(connection.close)
        after_restart = compose_sqlite_timing_correction_revision_generation_service(
            connection
        ).generations_for_candidate(a.identity.value)
        self.assertEqual([e.identity.value for e in after_restart], first)

    def test_singleton_only_ordering_keeps_the_released_meaning(self) -> None:
        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        self.generator.generate(candidate_id=a.identity.value)
        self.generator.generate(candidate_id=b.identity.value)
        for candidate in (a, b):
            values = [e.identity.value for e in self._history(candidate)]
            self.assertEqual(values, sorted(values))

    # -- empty history and unknown identities --------------------------------------------------

    def test_a_candidate_with_no_history_returns_empty(self) -> None:
        candidate = self._accepted(1, 12.0, 21.0)
        self.assertEqual(self._history(candidate), ())

    def test_an_unknown_but_well_formed_identity_returns_empty(self) -> None:
        unknown = "timing-correction-candidate:" + "0" * 64
        self.assertEqual(self.generator.generations_for_candidate(unknown), ())

    def test_a_malformed_identity_is_rejected(self) -> None:
        with self.assertRaises(TimingCorrectionGenerationError):
            self.generator.generations_for_candidate("not-a-candidate")

    # -- the query writes nothing -------------------------------------------------------------

    def test_the_query_is_read_only(self) -> None:
        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        self.generator.generate(candidate_id=a.identity.value)
        self.generator.generate_set(candidate_ids=(a.identity.value, b.identity.value))
        compose_sqlite_corrected_revision_selection_service(self.connection)
        version = self.connection.execute(
            "SELECT version FROM schema_metadata"
        ).fetchone()[0]
        before = self._snapshot()
        for _ in range(3):
            self._history(a)
            self._history(b)
        self.assertEqual(before, self._snapshot())
        self.assertEqual(
            self.connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
            version,
        )
        # A legacy singleton is projected, never back-filled into the member relation.
        member_rows = self.connection.execute(
            "SELECT COUNT(*) FROM timing_correction_revision_generation_members"
        ).fetchone()[0]
        self.assertEqual(member_rows, 2, "only the aggregate's own two members exist")

    # -- corruption is surfaced, not silently dropped ------------------------------------------

    def test_a_member_referencing_a_missing_aggregate_is_surfaced(self) -> None:
        from lectureos.persistence.errors import PersistenceError

        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        created = self.generator.generate_set(
            candidate_ids=(a.identity.value, b.identity.value)
        )
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute(
            "DELETE FROM timing_correction_revision_aggregate_generations WHERE identity = ?",
            (created.view.identity.value,),
        )
        self.connection.execute("PRAGMA foreign_keys = ON")
        with self.assertRaises(PersistenceError):
            self._history(a)

    def test_an_incomplete_aggregate_membership_is_surfaced(self) -> None:
        from lectureos.persistence.errors import PersistenceError

        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        created = self.generator.generate_set(
            candidate_ids=(a.identity.value, b.identity.value)
        )
        self.connection.execute(
            "DELETE FROM timing_correction_revision_generation_members "
            "WHERE aggregate_generation_id = ? AND member_ordinal = 1",
            (created.view.identity.value,),
        )
        with self.assertRaises(PersistenceError):
            # A damaged aggregate must not be reported as a healthy one-member history entry.
            self._history(a)

    # -- both layers ----------------------------------------------------------------------------

    def test_the_repository_layer_returns_the_same_complete_history(self) -> None:
        a = self._accepted(1, 12.0, 21.0)
        b = self._accepted(3, 41.0, 45.0)
        self.generator.generate(candidate_id=a.identity.value)
        self.generator.generate_set(candidate_ids=(a.identity.value, b.identity.value))
        through_repository = self.generations.generations_for_candidate(a.identity)
        through_application = self._history(a)
        self.assertEqual(len(through_repository), 2)
        self.assertEqual(
            [e.identity for e in through_repository],
            [e.identity for e in through_application],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
