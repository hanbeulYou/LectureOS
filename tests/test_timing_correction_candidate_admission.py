"""Human Timing Correction Candidate admission (040 §17 sibling subsection, PATCH-0047 TC-1…TC-9).

Pins the structural admission contract and, just as importantly, what admission refuses to be: it
checks structure and never acoustic truth, it consults no diagnostic, it reads no media, it invents
no threshold, and it leaves the released text-correction path byte-identical.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.provider_transcript_admission import (
    TIMING_BOUNDARY_TOLERANCE_SECONDS,
)
from lectureos.application.timing_correction_candidate_admission import (
    TimingCorrectionCandidateConflictError,
    TimingCorrectionCandidateError,
    TimingProposalNoOpError,
    TimingProposalOverlapError,
    TimingRawTranscriptNotCurrentError,
    TimingSegmentLineageError,
    TimingSourceSnapshotMismatchError,
    build_timing_correction_candidate_input,
)
from lectureos.composition import (
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_timing_correction_candidate_admission_service,
)
from lectureos.transcript.identities import TranscriptSegmentId

# `tests/` is not a package, so a single-module invocation does not put it on sys.path the way
# discovery does; this keeps both `unittest discover` and `unittest tests.<module>` working.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import temporary_fixture

_ADMISSION_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "lectureos"
    / "application"
    / "timing_correction_candidate_admission.py"
)


class TimingCorrectionCandidateAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory, self.fixture = temporary_fixture()
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.fixture.close)
        self.service = compose_sqlite_timing_correction_candidate_admission_service(
            self.fixture.connection
        )

    def _admit(self, **overrides):
        return self.service.admit(
            intake_id=self.fixture.intake_id,
            candidate=build_timing_correction_candidate_input(
                self.fixture.proposal(**overrides)
            ),
        )

    # -- the proposal itself ------------------------------------------------------------------

    def test_valid_human_authored_interval_is_admitted(self) -> None:
        result = self._admit()
        self.assertTrue(result.created)
        candidate = result.candidate
        self.assertEqual(candidate.proposed_start, 18.0)
        self.assertEqual(candidate.proposed_end, 24.0)
        self.assertEqual(candidate.author.value, "human:editor-1")
        self.assertTrue(
            candidate.identity.value.startswith("timing-correction-candidate:")
        )

    def test_admission_does_not_apply_the_correction(self) -> None:
        self._admit()
        segment = self.fixture.segment(self.fixture.target.identity)
        self.assertEqual(segment.start, self.fixture.target.start)
        self.assertEqual(segment.end, self.fixture.target.end)
        self.assertEqual(segment.text, self.fixture.target.text)

    def test_proposal_carries_no_text(self) -> None:
        # TC-2/TC-3: the record proposes an interval; there is no text vocabulary to smuggle through.
        fields = set(
            build_timing_correction_candidate_input(self.fixture.proposal()).__dataclass_fields__
        )
        self.assertNotIn("proposed_text", fields)
        self.assertNotIn("source_text_snapshot", fields)

    def test_start_only_proposal_cannot_be_expressed(self) -> None:
        # TC-3: a complete replacement interval is required; omitting the end is a malformed payload.
        payload = self.fixture.proposal()
        payload.pop("proposed_end")
        with self.assertRaises(TimingCorrectionCandidateError):
            build_timing_correction_candidate_input(payload)

    def test_machine_source_vocabulary_does_not_exist(self) -> None:
        # TC-4: only a human-authored proposal can be expressed — there is no source_type to say
        # "rule" or "external", so a machine-generated proposal has no representation at all.
        payload = self.fixture.proposal()
        payload["source_type"] = "rule"
        with self.assertRaises(TimingCorrectionCandidateError):
            build_timing_correction_candidate_input(payload)

    def test_blank_author_is_rejected(self) -> None:
        with self.assertRaises(TimingCorrectionCandidateError):
            build_timing_correction_candidate_input(self.fixture.proposal(author="  "))

    # -- structural admission (TC-6) ----------------------------------------------------------

    def test_missing_segment_is_rejected(self) -> None:
        unknown = TranscriptSegmentId(f"transcript-segment:{'a' * 64}:0")
        with self.assertRaises(TimingSegmentLineageError):
            self._admit(segment_id=unknown.value)

    def test_segment_of_another_transcript_is_rejected(self) -> None:
        directory, other = temporary_fixture(provider_result_ref="B")
        self.addCleanup(directory.cleanup)
        self.addCleanup(other.close)
        with self.assertRaises(TimingSegmentLineageError):
            self._admit(segment_id=other.target.identity.value)

    def test_raw_transcript_that_is_not_current_is_rejected(self) -> None:
        with self.assertRaises(TimingRawTranscriptNotCurrentError):
            self._admit(raw_transcript_id=f"raw-transcript:{'b' * 64}")

    def test_non_finite_timing_is_rejected(self) -> None:
        for value in (float("inf"), float("nan"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(TimingCorrectionCandidateError):
                    build_timing_correction_candidate_input(
                        self.fixture.proposal(proposed_start=value)
                    )

    def test_non_numeric_timing_is_rejected(self) -> None:
        for value in ("18.0", None, True):
            with self.subTest(value=value):
                with self.assertRaises(TimingCorrectionCandidateError):
                    build_timing_correction_candidate_input(
                        self.fixture.proposal(proposed_start=value)
                    )

    def test_end_not_after_start_is_rejected(self) -> None:
        for start, end in ((18.0, 18.0), (18.0, 17.0)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(TimingCorrectionCandidateError):
                    build_timing_correction_candidate_input(
                        self.fixture.proposal(proposed_start=start, proposed_end=end)
                    )

    def test_negative_start_is_rejected(self) -> None:
        with self.assertRaises(TimingCorrectionCandidateError):
            build_timing_correction_candidate_input(
                self.fixture.proposal(proposed_start=-0.5, proposed_end=1.0)
            )

    def test_untimed_segment_has_no_interval_to_correct(self) -> None:
        """A segment with no timing is refused, because there is no interval to replace.

        Released provider admission requires start/end on every segment (A-10), so this state is not
        reachable through the released chain; the guard is driven directly against a stubbed segment
        query so the refusal is asserted rather than assumed.
        """

        from dataclasses import replace

        from lectureos.application.timing_correction_candidate_admission import (
            TimingCorrectionCandidateAdmissionService,
        )
        from lectureos.persistence import (
            SQLiteRawTranscriptRepository,
            SQLiteTranscriptSourceIntakeRepository,
            SQLiteRawTranscriptSelectionRepository,
        )
        from lectureos.persistence.timing_correction_candidate import (
            SQLiteTimingCorrectionCandidateRepository,
        )

        untimed = replace(self.fixture.target, start=None, end=None, source_timeline_id=None)

        class _UntimedSegments:
            def get(self, identity):
                return untimed if identity == untimed.identity else None

        service = TimingCorrectionCandidateAdmissionService(
            SQLiteTranscriptSourceIntakeRepository(self.fixture.connection),
            SQLiteRawTranscriptSelectionRepository(self.fixture.connection),
            _UntimedSegments(),
            SQLiteRawTranscriptRepository(self.fixture.connection),
            SQLiteTimingCorrectionCandidateRepository(self.fixture.connection),
        )
        with self.assertRaises(TimingSegmentLineageError):
            service.admit(
                intake_id=self.fixture.intake_id,
                candidate=build_timing_correction_candidate_input(
                    self.fixture.proposal()
                ),
            )

    # -- no-op and staleness (TC-8, TC-9) -----------------------------------------------------

    def test_timing_no_op_is_rejected(self) -> None:
        with self.assertRaises(TimingProposalNoOpError):
            self._admit(
                proposed_start=self.fixture.target.start,
                proposed_end=self.fixture.target.end,
            )

    def test_no_op_within_the_released_epsilon_is_rejected(self) -> None:
        eps = TIMING_BOUNDARY_TOLERANCE_SECONDS
        with self.assertRaises(TimingProposalNoOpError):
            self._admit(
                proposed_start=self.fixture.target.start + eps / 2,
                proposed_end=self.fixture.target.end - eps / 2,
            )

    def test_stale_source_timing_snapshot_is_rejected(self) -> None:
        with self.assertRaises(TimingSourceSnapshotMismatchError):
            self._admit(source_start_snapshot=9.0)
        with self.assertRaises(TimingSourceSnapshotMismatchError):
            self._admit(source_end_snapshot=21.0)

    # -- neighbour non-overlap (TC-7) ---------------------------------------------------------

    def test_overlapping_the_previous_neighbour_is_rejected(self) -> None:
        # The previous segment ends at 2.5; starting at 2.0 would overlap it.
        with self.assertRaises(TimingProposalOverlapError):
            self._admit(proposed_start=2.0, proposed_end=8.0)

    def test_overlapping_the_next_neighbour_is_rejected(self) -> None:
        # The next segment starts at 25.0; ending at 26.0 would overlap it.
        with self.assertRaises(TimingProposalOverlapError):
            self._admit(proposed_start=18.0, proposed_end=26.0)

    def test_touching_neighbour_boundaries_is_allowed(self) -> None:
        result = self._admit(proposed_start=2.5, proposed_end=25.0)
        self.assertTrue(result.created)

    def test_overlap_uses_the_released_epsilon_and_no_new_tolerance(self) -> None:
        eps = TIMING_BOUNDARY_TOLERANCE_SECONDS
        # Within ε of the neighbour boundary counts as the same instant — still allowed.
        self.assertTrue(self._admit(proposed_start=2.5 - eps / 2, proposed_end=24.0).created)
        # A visible overlap, far smaller than any drift figure, is still refused: no duration
        # threshold participates.
        with self.assertRaises(TimingProposalOverlapError):
            self._admit(candidate_ref="t2", proposed_start=2.4, proposed_end=24.0)

    def test_admission_source_holds_no_numeric_threshold(self) -> None:
        """TC-6: no drift, anchor-gap, or readability constant may hide in the admission logic."""

        module = ast.parse(_ADMISSION_SOURCE.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                if isinstance(node.value, bool):
                    continue
                self.assertIn(
                    node.value,
                    {0, 1, 2, 64},  # ordinal/index arithmetic and the SHA-256 digest length
                    f"unexpected numeric constant {node.value!r} in timing admission",
                )

    def test_admission_consults_no_diagnostic_and_no_media(self) -> None:
        source = _ADMISSION_SOURCE.read_text(encoding="utf-8")
        for forbidden in (
            "TIMING_ALIGNMENT_REVIEW_REQUIRED",
            "transcript_quality_diagnostic",
            "avg_logprob",
            "no_speech_prob",
            "compression_ratio",
            "ffmpeg",
            "librosa",
            "soundfile",
            "wave",
        ):
            self.assertNotIn(forbidden, source)

    # -- identity and idempotency (TC-15, K-5…K-8) --------------------------------------------

    def test_replay_of_the_same_proposal_is_idempotent(self) -> None:
        first = self._admit()
        second = self._admit()
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.candidate.identity, second.candidate.identity)

    def test_same_anchor_with_a_different_interval_is_a_conflict(self) -> None:
        self._admit()
        with self.assertRaises(TimingCorrectionCandidateConflictError):
            self._admit(proposed_end=23.0)

    def test_distinct_proposals_for_one_segment_have_distinct_identities(self) -> None:
        first = self._admit(candidate_ref="t1", proposed_end=24.0)
        second = self._admit(candidate_ref="t2", proposed_end=23.0)
        self.assertNotEqual(first.candidate.identity, second.candidate.identity)

    def test_timing_and_text_candidate_identities_cannot_collide(self) -> None:
        timing = self._admit().candidate
        text = compose_sqlite_correction_candidate_admission_service(
            self.fixture.connection
        ).admit(
            intake_id=self.fixture.intake_id,
            candidate=build_correction_candidate_input(
                {
                    "raw_transcript_id": self.fixture.raw_transcript_id,
                    "segment_id": self.fixture.target.identity.value,
                    "candidate_ref": "t1",
                    "source_type": "manual",
                    "source_reference": "human:editor-1",
                    "proposed_text": "둘째 문장!",
                    "source_text_snapshot": self.fixture.target.text,
                    "rationale": "구두점",
                }
            ),
        ).candidate
        self.assertNotEqual(timing.identity.value, text.identity.value)
        self.assertTrue(text.identity.value.startswith("correction-candidate:"))
        self.assertTrue(timing.identity.value.startswith("timing-correction-candidate:"))

    # -- the diagnostic is not a prerequisite (TC-5) -------------------------------------------

    def test_candidate_is_admitted_with_no_timing_finding_present(self) -> None:
        from lectureos.composition import (
            compose_sqlite_transcript_timing_diagnostic_service,
        )

        diagnostic = compose_sqlite_transcript_timing_diagnostic_service(
            self.fixture.connection
        )
        # This fixture's provider result preserves no decode-window anchor, so the diagnostic can
        # report nothing at all — and admission proceeds regardless.
        self.assertIsNotNone(diagnostic)
        self.assertTrue(self._admit().created)

    def test_no_code_path_turns_a_finding_into_a_candidate(self) -> None:
        source = _ADMISSION_SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names]
                if isinstance(node, ast.ImportFrom):
                    names.append(node.module or "")
                for name in names:
                    self.assertNotIn("quality_diagnostic", name)

    # -- the released text path is untouched (TC-2) --------------------------------------------

    def test_released_text_candidate_admission_still_works(self) -> None:
        result = compose_sqlite_correction_candidate_admission_service(
            self.fixture.connection
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
        )
        self.assertTrue(result.created)
        self.assertEqual(result.candidate.proposed_text, "둘째 문장입니다")

    def test_text_candidate_still_rejects_a_text_no_op(self) -> None:
        with self.assertRaises(Exception) as caught:
            build_correction_candidate_input(
                {
                    "raw_transcript_id": self.fixture.raw_transcript_id,
                    "segment_id": self.fixture.target.identity.value,
                    "candidate_ref": "c2",
                    "source_type": "manual",
                    "source_reference": "human:editor-1",
                    "proposed_text": self.fixture.target.text,
                    "source_text_snapshot": self.fixture.target.text,
                    "rationale": "…",
                }
            )
        self.assertIn("no-op", str(caught.exception))

    def test_timing_candidates_are_stored_in_their_own_relation(self) -> None:
        self._admit()
        rows = self.fixture.connection.execute(
            "SELECT COUNT(*) FROM correction_candidates"
        ).fetchone()[0]
        self.assertEqual(rows, 0, "a timing proposal must never land in the text relation")
        self.assertEqual(
            self.fixture.connection.execute(
                "SELECT COUNT(*) FROM timing_correction_candidates"
            ).fetchone()[0],
            1,
        )

    def test_listing_reports_applicability_without_ranking(self) -> None:
        self._admit(candidate_ref="t1")
        self._admit(candidate_ref="t2", proposed_end=23.0)
        views = self.service.candidates(self.fixture.intake_id)
        self.assertEqual(len(views), 2)
        self.assertTrue(all(view.applicable_to_current_selection for view in views))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
