"""K-1 target membership for text Correction Candidate Admission (040 §17).

`§17` K-1 requires a candidate's target to be *one immutable Raw Transcript segment* that **belongs
to** that transcript. A `§19` replacement segment carries its parent Raw Transcript's identity (V-1's
revision-scoped segment) while living only in a corrected revision, so a `transcript_id` comparison
alone lets it through. Admitting one produced a candidate V-4 could never apply, and treating it as a
valid target would be revision-on-revision chaining — deferred by V-14, S2-14, and `PATCH-0048` RC-3.

These tests pin the guard and, just as importantly, its narrowness: normal Raw-segment admission,
K-9's non-applicable history, and the timing path are all unchanged.
"""

from __future__ import annotations

import unittest

from lectureos.application.correction_candidate_admission import (
    SegmentLineageError,
    build_correction_candidate_input,
)
from lectureos.application.corrected_revision_generation import (
    CandidateNotApplicableError,
)
from lectureos.application.timing_correction_candidate_admission import (
    TimingSegmentLineageError,
    build_timing_correction_candidate_input,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_timing_correction_candidate_admission_service,
)
from lectureos.persistence import (
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
)

# `tests/` is not a package, so a single-module invocation does not put it on sys.path the way
# discovery does; this keeps both `unittest discover` and `unittest tests.<module>` working.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import temporary_fixture


class ReplacementSegmentTargetGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory, self.fixture = temporary_fixture()
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.fixture.close)
        self.connection = self.fixture.connection
        self.segments = SQLiteTranscriptSegmentRepository(self.connection)
        self.admissions = compose_sqlite_correction_candidate_admission_service(
            self.connection
        )
        self.decisions = compose_sqlite_correction_candidate_decision_service(
            self.connection
        )
        self.generator = compose_sqlite_corrected_revision_generation_service(
            self.connection
        )

    def _admit_text(self, segment, ref, proposed, snapshot=None):
        return self.admissions.admit(
            intake_id=self.fixture.intake_id,
            candidate=build_correction_candidate_input(
                {
                    "raw_transcript_id": self.fixture.raw_transcript_id,
                    "segment_id": segment.identity.value,
                    "candidate_ref": ref,
                    "source_type": "manual",
                    "source_reference": "human:editor-1",
                    "proposed_text": proposed,
                    "source_text_snapshot": (
                        segment.text if snapshot is None else snapshot
                    ),
                    "rationale": "교정",
                }
            ),
        ).candidate

    def _replacement_segment(self):
        """Generate a corrected revision from the target segment and return its replacement."""

        candidate = self._admit_text(self.fixture.target, "c1", "둘째 문장입니다")
        self.decisions.decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        generation = self.generator.generate(
            candidate_id=candidate.identity.value
        ).generation
        return self.segments.get(generation.replacement_segment_id)

    # -- Test A: the normal path is untouched --------------------------------------------------

    def test_original_raw_segment_is_still_admitted(self) -> None:
        for index, segment in enumerate(self.fixture.segments):
            with self.subTest(ordinal=index):
                candidate = self._admit_text(segment, f"ok{index}", f"교정 {index}")
                self.assertTrue(
                    candidate.identity.value.startswith("correction-candidate:")
                )

    # -- Test B: the replacement segment is refused at admission -------------------------------

    def test_replacement_segment_is_rejected_at_admission(self) -> None:
        replacement = self._replacement_segment()
        with self.assertRaises(SegmentLineageError) as caught:
            self._admit_text(replacement, "chain", "둘째 문장이에요")
        self.assertIn("not part of the target raw transcript", str(caught.exception))

    def test_rejection_happens_before_any_row_is_written(self) -> None:
        replacement = self._replacement_segment()
        before = self.connection.execute(
            "SELECT COUNT(*) FROM correction_candidates"
        ).fetchone()[0]
        with self.assertRaises(SegmentLineageError):
            self._admit_text(replacement, "chain", "둘째 문장이에요")
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM correction_candidates"
            ).fetchone()[0],
            before,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM correction_candidate_admissions "
                "WHERE segment_id = ?",
                (replacement.identity.value,),
            ).fetchone()[0],
            0,
        )

    def test_the_replacement_segment_looks_like_a_raw_segment_but_is_not(self) -> None:
        """Why the released check let it through — the fact this guard exists to catch."""

        replacement = self._replacement_segment()
        raw = SQLiteRawTranscriptRepository(self.connection).get(
            self.fixture.raw_transcript.identity
        )
        self.assertEqual(replacement.transcript_id, raw.identity)   # names the raw transcript
        self.assertNotIn(replacement.identity, raw.segment_ids)     # but is not a member of it
        self.assertEqual(replacement.replaces_segment_id, self.fixture.target.identity)

    # -- Test C: the immutable original stays targetable ---------------------------------------

    def test_original_segment_is_still_admissible_after_a_revision_exists(self) -> None:
        """K-8 permits several distinct candidates per segment, and Raw stays immutable."""

        self._replacement_segment()
        raw = SQLiteRawTranscriptRepository(self.connection).get(
            self.fixture.raw_transcript.identity
        )
        self.assertIn(self.fixture.target.identity, raw.segment_ids)
        second = self._admit_text(self.fixture.target, "c2", "둘째 문장이야")
        self.assertTrue(second.identity.value.startswith("correction-candidate:"))
        self.decisions.decide(
            candidate_id=second.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        self.assertEqual(
            self.generator.generate(candidate_id=second.identity.value).outcome, "created"
        )

    # -- Test D: the timing path is unchanged ---------------------------------------------------

    def test_timing_admission_behaviour_is_unchanged(self) -> None:
        replacement = self._replacement_segment()
        timing = compose_sqlite_timing_correction_candidate_admission_service(
            self.connection
        )
        # A Raw segment is still admitted…
        self.assertTrue(
            timing.admit(
                intake_id=self.fixture.intake_id,
                candidate=build_timing_correction_candidate_input(
                    self.fixture.proposal()
                ),
            ).created
        )
        # …and a replacement segment is still refused, by its own released check.
        with self.assertRaises(TimingSegmentLineageError):
            timing.admit(
                intake_id=self.fixture.intake_id,
                candidate=build_timing_correction_candidate_input(
                    {
                        "raw_transcript_id": self.fixture.raw_transcript_id,
                        "segment_id": replacement.identity.value,
                        "candidate_ref": "chain",
                        "author": "human:editor-1",
                        "source_start_snapshot": replacement.start,
                        "source_end_snapshot": replacement.end,
                        "proposed_start": 18.0,
                        "proposed_end": 24.0,
                        "rationale": "연쇄",
                    }
                ),
            )

    # -- Test E: no chaining path exists ---------------------------------------------------------

    def test_no_chaining_path_exists_through_either_correction_kind(self) -> None:
        """V-14 / S2-14 / `PATCH-0048` RC-3: a revision's segment is not correctable."""

        replacement = self._replacement_segment()
        with self.assertRaises(SegmentLineageError):
            self._admit_text(replacement, "chain-text", "또 교정")
        with self.assertRaises(TimingSegmentLineageError):
            compose_sqlite_timing_correction_candidate_admission_service(
                self.connection
            ).admit(
                intake_id=self.fixture.intake_id,
                candidate=build_timing_correction_candidate_input(
                    {
                        "raw_transcript_id": self.fixture.raw_transcript_id,
                        "segment_id": replacement.identity.value,
                        "candidate_ref": "chain-timing",
                        "author": "human:editor-1",
                        "source_start_snapshot": replacement.start,
                        "source_end_snapshot": replacement.end,
                        "proposed_start": 18.0,
                        "proposed_end": 24.0,
                        "rationale": "연쇄",
                    }
                ),
            )
        # No revision acquired a revision parent, so no chain was formed.
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM corrected_transcript_revisions "
                "WHERE parent_revision_id IS NOT NULL"
            ).fetchone()[0],
            0,
        )

    def test_generation_still_refuses_a_replacement_target_candidate(self) -> None:
        """V-4 is unchanged: it remains the second line, not the only one.

        A candidate persisted before this guard existed is still refused at generation, so an
        already-stored record keeps behaving exactly as it did — nothing is rewritten or deleted.
        """

        replacement = self._replacement_segment()
        # Reproduce a pre-guard record by driving the released persistence directly, exactly as the
        # weaker check would have produced it.
        candidate = self._admit_text(self.fixture.target, "legacy", "둘째 문장이야")
        self.connection.execute(
            "UPDATE correction_candidate_admissions SET segment_id = ? "
            "WHERE correction_candidate_id = ?",
            (replacement.identity.value, candidate.identity.value),
        )
        self.decisions.decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        with self.assertRaises(CandidateNotApplicableError):
            self.generator.generate(candidate_id=candidate.identity.value)

    # -- Test F: the released end-to-end path still works ---------------------------------------

    def test_normal_text_correction_end_to_end_still_works(self) -> None:
        candidate = self._admit_text(self.fixture.target, "e2e", "둘째 문장입니다")
        self.decisions.decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        result = self.generator.generate(candidate_id=candidate.identity.value)
        self.assertEqual(result.outcome, "created")
        selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        selection.select_revision(
            revision_id=result.revision.identity.value, reviewer="selector:kim"
        )
        effective = selection.resolve_effective_transcript(self.fixture.intake_id)
        self.assertEqual(effective.effective_kind.value, "corrected_revision")
        self.assertEqual(effective.corrected_revision_id, result.revision.identity)

    # -- K-9 is not narrowed --------------------------------------------------------------------

    def test_k9_non_applicable_history_is_untouched(self) -> None:
        """A validly admitted candidate that later stops applying is still legal history.

        This guard rejects only targets that never satisfied K-1. A candidate admitted against a
        genuine Raw segment survives a later current-Raw-Transcript switch as immutable evidence,
        exactly as K-9 requires.
        """

        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_current_raw_transcript_selection_service,
            compose_sqlite_provider_transcript_admission_service,
        )

        candidate = self._admit_text(self.fixture.target, "hist", "둘째 문장입니다")
        second_raw = compose_sqlite_provider_transcript_admission_service(
            self.connection
        ).admit(
            intake_id=self.fixture.intake_id,
            document=build_provider_transcript_document(
                {
                    "provider": "fake-asr",
                    "model": "tiny",
                    "language": "ko",
                    "provider_result_ref": "B",
                    "segments": [{"start": 0.0, "end": 1.0, "text": "다른 결과"}],
                }
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.fixture.intake_id, second_raw.raw_transcript_id.value
        )
        views = self.admissions.candidates(self.fixture.intake_id)
        historical = [
            view for view in views if view.correction_candidate_id == candidate.identity
        ]
        self.assertEqual(len(historical), 1, "the candidate must be preserved, not deleted")
        self.assertFalse(historical[0].applicable_to_current_selection)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
