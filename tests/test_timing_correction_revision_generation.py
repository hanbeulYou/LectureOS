"""Corrected revision generation from an accepted timing candidate (040 §19, PATCH-0047 TC-12/TC-15/TC-18).

Pins the replacement's text preservation and interval, the identity/lineage rules, Raw Transcript
immutability, atomicity, and the deliberately narrow composition boundary: two competing corrections
on one segment produce two independent revisions and are never merged or ordered by the implementation.
"""

from __future__ import annotations

import unittest

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.timing_correction_candidate_admission import (
    build_timing_correction_candidate_input,
)
from lectureos.application.timing_correction_revision_generation import (
    TimingCandidateNotAcceptedError,
    TimingCorrectionGenerationError,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_timing_correction_candidate_admission_service,
    compose_sqlite_timing_correction_decision_service,
    compose_sqlite_timing_correction_revision_generation_service,
)
from lectureos.persistence import (
    SQLiteCorrectedTranscriptRevisionRepository,
    SQLiteTranscriptSegmentRepository,
)
from lectureos.persistence.errors import PersistenceError

# `tests/` is not a package, so a single-module invocation does not put it on sys.path the way
# discovery does; this keeps both `unittest discover` and `unittest tests.<module>` working.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import temporary_fixture


class TimingCorrectionRevisionGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory, self.fixture = temporary_fixture()
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
        self.segments = SQLiteTranscriptSegmentRepository(self.connection)
        self.revisions = SQLiteCorrectedTranscriptRevisionRepository(self.connection)

    def _candidate(self, **overrides):
        return self.admissions.admit(
            intake_id=self.fixture.intake_id,
            candidate=build_timing_correction_candidate_input(
                self.fixture.proposal(**overrides)
            ),
        ).candidate

    def _accepted(self, **overrides):
        candidate = self._candidate(**overrides)
        self.decisions.decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        return candidate

    # -- the replacement segment (TC-12) -------------------------------------------------------

    def test_replacement_preserves_source_text_byte_identically(self) -> None:
        candidate = self._accepted()
        result = self.generator.generate(candidate_id=candidate.identity.value)
        replacement = self.segments.get(result.generation.replacement_segment_id)
        source = self.segments.get(self.fixture.target.identity)
        self.assertEqual(replacement.text, source.text)
        self.assertEqual(
            replacement.text.encode("utf-8"), source.text.encode("utf-8")
        )

    def test_replacement_carries_the_accepted_interval(self) -> None:
        candidate = self._accepted()
        result = self.generator.generate(candidate_id=candidate.identity.value)
        replacement = self.segments.get(result.generation.replacement_segment_id)
        self.assertEqual(replacement.start, candidate.proposed_start)
        self.assertEqual(replacement.end, candidate.proposed_end)

    def test_replacement_declares_its_source_and_has_a_distinct_identity(self) -> None:
        candidate = self._accepted()
        result = self.generator.generate(candidate_id=candidate.identity.value)
        replacement = self.segments.get(result.generation.replacement_segment_id)
        self.assertEqual(replacement.replaces_segment_id, self.fixture.target.identity)
        self.assertNotEqual(replacement.identity, self.fixture.target.identity)

    def test_replacement_preserves_order_timeline_and_speaker(self) -> None:
        candidate = self._accepted()
        result = self.generator.generate(candidate_id=candidate.identity.value)
        replacement = self.segments.get(result.generation.replacement_segment_id)
        source = self.fixture.target
        self.assertEqual(replacement.source_order, source.source_order)
        self.assertEqual(replacement.source_timeline_id, source.source_timeline_id)
        self.assertEqual(replacement.speaker_label, source.speaker_label)

    def test_revision_swaps_only_the_target_segment(self) -> None:
        candidate = self._accepted()
        result = self.generator.generate(candidate_id=candidate.identity.value)
        revision = self.revisions.get(result.revision.identity)
        expected = tuple(
            result.generation.replacement_segment_id
            if segment.identity == self.fixture.target.identity
            else segment.identity
            for segment in self.fixture.segments
        )
        self.assertEqual(revision.segment_ids, expected)
        self.assertNotIn(self.fixture.target.identity, revision.segment_ids)

    def test_revision_reuses_the_released_aggregate_and_names_no_text_candidate(self) -> None:
        candidate = self._accepted()
        revision = self.revisions.get(
            self.generator.generate(candidate_id=candidate.identity.value).revision.identity
        )
        self.assertEqual(revision.correction_candidate_ids, ())
        self.assertEqual(revision.parent_raw_transcript_id, self.fixture.raw_transcript.identity)
        self.assertIsNone(revision.parent_revision_id)

    # -- authority gating ----------------------------------------------------------------------

    def test_undecided_candidate_cannot_generate(self) -> None:
        candidate = self._candidate()
        with self.assertRaises(TimingCandidateNotAcceptedError):
            self.generator.generate(candidate_id=candidate.identity.value)

    def test_rejected_candidate_generates_nothing(self) -> None:
        candidate = self._candidate()
        self.decisions.decide(
            candidate_id=candidate.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        with self.assertRaises(TimingCandidateNotAcceptedError):
            self.generator.generate(candidate_id=candidate.identity.value)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM timing_correction_revision_generations"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM corrected_transcript_revisions"
            ).fetchone()[0],
            0,
        )

    def test_accept_then_reject_leaves_a_generated_revision_intact(self) -> None:
        candidate = self._accepted()
        revision_id = self.generator.generate(
            candidate_id=candidate.identity.value
        ).revision.identity
        self.decisions.decide(
            candidate_id=candidate.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        self.assertIsNotNone(self.revisions.get(revision_id))
        with self.assertRaises(TimingCandidateNotAcceptedError):
            self.generator.generate(candidate_id=candidate.identity.value)

    def test_unknown_candidate_is_rejected(self) -> None:
        with self.assertRaises(TimingCorrectionGenerationError):
            self.generator.generate(
                candidate_id=f"timing-correction-candidate:{'0' * 64}"
            )

    # -- identity and replay (TC-15) -----------------------------------------------------------

    def test_replay_reuses_the_same_revision(self) -> None:
        candidate = self._accepted()
        first = self.generator.generate(candidate_id=candidate.identity.value)
        second = self.generator.generate(candidate_id=candidate.identity.value)
        self.assertEqual(first.outcome, "created")
        self.assertEqual(second.outcome, "reused")
        self.assertEqual(first.revision.identity, second.revision.identity)

    def test_two_proposals_for_one_segment_do_not_collide(self) -> None:
        first = self._accepted(candidate_ref="t1", proposed_start=18.0, proposed_end=24.0)
        second = self._accepted(candidate_ref="t2", proposed_start=17.0, proposed_end=23.0)
        revision_a = self.generator.generate(candidate_id=first.identity.value)
        revision_b = self.generator.generate(candidate_id=second.identity.value)
        self.assertNotEqual(revision_a.revision.identity, revision_b.revision.identity)
        self.assertNotEqual(
            revision_a.generation.replacement_segment_id,
            revision_b.generation.replacement_segment_id,
        )

    def test_a_second_accepted_decision_yields_a_distinct_revision(self) -> None:
        candidate = self._accepted()
        first = self.generator.generate(candidate_id=candidate.identity.value)
        self.decisions.decide(
            candidate_id=candidate.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        self.decisions.decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        second = self.generator.generate(candidate_id=candidate.identity.value)
        self.assertNotEqual(first.revision.identity, second.revision.identity)

    def test_generation_digest_follows_the_released_anchor_recipe(self) -> None:
        from lectureos.application.corrected_revision_generation import (
            derive_generation_digest,
        )
        from lectureos.application.timing_correction_revision_generation import (
            derive_timing_generation_digest,
        )

        candidate = self._accepted()
        decision = self.decisions.decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        ).decision
        self.assertEqual(
            derive_timing_generation_digest(candidate.identity, decision.identity),
            derive_generation_digest(candidate.identity, decision.identity),
        )

    # -- Raw Transcript immutability (TC-16) ---------------------------------------------------

    def test_raw_transcript_and_provider_rows_are_unchanged(self) -> None:
        before = self.connection.execute(
            'SELECT identity, text, "start", "end" FROM transcript_segments ORDER BY identity'
        ).fetchall()
        provider_before = self.connection.execute(
            "SELECT * FROM provider_transcript_results ORDER BY identity"
        ).fetchall()
        raw_before = self.connection.execute(
            "SELECT * FROM raw_transcripts ORDER BY identity"
        ).fetchall()

        candidate = self._accepted()
        result = self.generator.generate(candidate_id=candidate.identity.value)

        after = self.connection.execute(
            'SELECT identity, text, "start", "end" FROM transcript_segments '
            'WHERE identity <> ? ORDER BY identity',
            (result.generation.replacement_segment_id.value,),
        ).fetchall()
        self.assertEqual(before, after)
        self.assertEqual(
            provider_before,
            self.connection.execute(
                "SELECT * FROM provider_transcript_results ORDER BY identity"
            ).fetchall(),
        )
        self.assertEqual(
            raw_before,
            self.connection.execute(
                "SELECT * FROM raw_transcripts ORDER BY identity"
            ).fetchall(),
        )

    # -- atomicity ------------------------------------------------------------------------------

    def test_a_failing_generation_leaves_no_partial_state(self) -> None:
        """Generation is one transaction: a linkage failure persists neither segment nor revision."""

        from lectureos.application.timing_correction_revision_generation import (
            TimingCorrectionRevisionGenerationService,
        )
        from lectureos.persistence import (
            SQLiteRawTranscriptRepository,
            SQLiteRawTranscriptSelectionRepository,
        )
        from lectureos.persistence.timing_correction_candidate import (
            SQLiteTimingCorrectionCandidateRepository,
        )
        from lectureos.persistence.timing_correction_candidate_decision import (
            SQLiteTimingCorrectionDecisionRepository,
        )
        from lectureos.persistence.timing_correction_revision_generation import (
            SQLiteTimingCorrectionGenerationCommandPersistence,
            SQLiteTimingCorrectionGenerationRepository,
        )
        from lectureos.transcript.models import CorrectedTranscriptRevision

        class _MislinkedRevision(SQLiteTimingCorrectionGenerationCommandPersistence):
            """Hands the transaction a revision that still references the replaced segment."""

            def persist_timing_correction_generation(self, **kwargs):
                revision: CorrectedTranscriptRevision = kwargs["revision"]
                kwargs["revision"] = CorrectedTranscriptRevision(
                    identity=revision.identity,
                    transcript_id=revision.transcript_id,
                    domain_result_id=revision.domain_result_id,
                    run_id=revision.run_id,
                    unit_execution_id=revision.unit_execution_id,
                    segment_ids=revision.segment_ids
                    + (kwargs["generation"].replaced_segment_id,),
                    parent_raw_transcript_id=revision.parent_raw_transcript_id,
                )
                return super().persist_timing_correction_generation(**kwargs)

        candidate = self._accepted()
        service = TimingCorrectionRevisionGenerationService(
            SQLiteTimingCorrectionCandidateRepository(self.connection),
            SQLiteTimingCorrectionDecisionRepository(self.connection),
            SQLiteRawTranscriptSelectionRepository(self.connection),
            SQLiteRawTranscriptRepository(self.connection),
            self.segments,
            SQLiteTimingCorrectionGenerationRepository(self.connection),
            _MislinkedRevision(self.connection),
        )
        with self.assertRaises(PersistenceError):
            service.generate(candidate_id=candidate.identity.value)

        for table in (
            "timing_correction_revision_generations",
            "corrected_transcript_revisions",
            "corrected_transcript_revision_segments",
        ):
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
                f"{table} must hold no partial state",
            )
        # The replacement segment inserted earlier in the same transaction is gone too.
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM transcript_segments WHERE replaces_segment_id IS NOT NULL"
            ).fetchone()[0],
            0,
        )
        # And the whole flow still works afterwards, so nothing was left locked or half-written.
        self.assertEqual(
            self.generator.generate(candidate_id=candidate.identity.value).outcome,
            "created",
        )

    # -- text + timing composition stays Deferred (TC-18) --------------------------------------

    def _accepted_text_candidate(self):
        candidate = compose_sqlite_correction_candidate_admission_service(
            self.connection
        ).admit(
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
        compose_sqlite_correction_candidate_decision_service(self.connection).decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        return candidate

    def test_competing_corrections_are_never_composed(self) -> None:
        """TC-18: each accepted correction yields its own revision; nothing merges them."""

        text = self._accepted_text_candidate()
        timing = self._accepted()

        text_revision = compose_sqlite_corrected_revision_generation_service(
            self.connection
        ).generate(candidate_id=text.identity.value).revision
        timing_result = self.generator.generate(candidate_id=timing.identity.value)

        self.assertNotEqual(text_revision.identity, timing_result.revision.identity)

        def _segment_of(revision_id):
            revision = self.revisions.get(revision_id)
            return next(
                self.segments.get(sid)
                for sid in revision.segment_ids
                if self.segments.get(sid).replaces_segment_id == self.fixture.target.identity
            )

        text_segment = _segment_of(text_revision.identity)
        timing_segment = _segment_of(timing_result.revision.identity)

        # The text revision changed only text; the timing revision changed only timing. Neither
        # carries the other's change — no automatic composition happened.
        self.assertEqual(text_segment.text, "둘째 문장입니다")
        self.assertEqual(text_segment.start, self.fixture.target.start)
        self.assertEqual(text_segment.end, self.fixture.target.end)
        self.assertEqual(timing_segment.text, self.fixture.target.text)
        self.assertEqual(timing_segment.start, timing.proposed_start)
        self.assertEqual(timing_segment.end, timing.proposed_end)

    def test_generation_order_does_not_change_either_result(self) -> None:
        """TC-18: the implementation chooses no ordering — both orders yield identical records."""

        def _run(timing_first: bool):
            directory, fixture = temporary_fixture(provider_result_ref="A")
            self.addCleanup(directory.cleanup)
            self.addCleanup(fixture.close)
            connection = fixture.connection
            text = compose_sqlite_correction_candidate_admission_service(connection).admit(
                intake_id=fixture.intake_id,
                candidate=build_correction_candidate_input(
                    {
                        "raw_transcript_id": fixture.raw_transcript_id,
                        "segment_id": fixture.target.identity.value,
                        "candidate_ref": "c1",
                        "source_type": "manual",
                        "source_reference": "human:editor-1",
                        "proposed_text": "둘째 문장입니다",
                        "source_text_snapshot": fixture.target.text,
                        "rationale": "표현 교정",
                    }
                ),
            ).candidate
            compose_sqlite_correction_candidate_decision_service(connection).decide(
                candidate_id=text.identity.value, kind="accept", reviewer="reviewer:kim"
            )
            timing = compose_sqlite_timing_correction_candidate_admission_service(
                connection
            ).admit(
                intake_id=fixture.intake_id,
                candidate=build_timing_correction_candidate_input(fixture.proposal()),
            ).candidate
            compose_sqlite_timing_correction_decision_service(connection).decide(
                candidate_id=timing.identity.value, kind="accept", reviewer="reviewer:kim"
            )
            text_gen = compose_sqlite_corrected_revision_generation_service(connection)
            timing_gen = compose_sqlite_timing_correction_revision_generation_service(
                connection
            )
            if timing_first:
                b = timing_gen.generate(candidate_id=timing.identity.value)
                a = text_gen.generate(candidate_id=text.identity.value)
            else:
                a = text_gen.generate(candidate_id=text.identity.value)
                b = timing_gen.generate(candidate_id=timing.identity.value)
            return a.revision.identity.value, b.revision.identity.value

        self.assertEqual(_run(timing_first=False), _run(timing_first=True))

    def test_independent_segments_are_not_blocked_by_each_other(self) -> None:
        first = self._accepted(
            segment_id=self.fixture.segments[0].identity.value,
            candidate_ref="s0",
            source_start_snapshot=self.fixture.segments[0].start,
            source_end_snapshot=self.fixture.segments[0].end,
            proposed_start=0.5,
            proposed_end=2.0,
        )
        second = self._accepted(candidate_ref="s1")
        self.assertEqual(
            self.generator.generate(candidate_id=first.identity.value).outcome, "created"
        )
        self.assertEqual(
            self.generator.generate(candidate_id=second.identity.value).outcome, "created"
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
