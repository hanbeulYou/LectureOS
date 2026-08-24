"""Repository validation over the timing-correction relations (040 §17/§18/§19, PATCH-0047).

Two things are asserted, and the second matters as much as the first: the new integrity diagnostics
fire on genuinely corrupt lineage, and **application-level product policy is not moved into the
validator** — staleness, inapplicability and a later Reject are query semantics (K-9, H-12, S2-9) and
must keep a repository healthy.
"""

from __future__ import annotations

import unittest

from lectureos.application.timing_correction_candidate_admission import (
    build_timing_correction_candidate_input,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_timing_correction_candidate_admission_service,
    compose_sqlite_timing_correction_decision_service,
    compose_sqlite_timing_correction_revision_generation_service,
)
from lectureos.validation import validate_database

# `tests/` is not a package, so a single-module invocation does not put it on sys.path the way
# discovery does; this keeps both `unittest discover` and `unittest tests.<module>` working.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import temporary_fixture


class TimingCorrectionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory, self.fixture = temporary_fixture()
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.fixture.close)
        self.connection = self.fixture.connection

    def _codes(self):
        report = validate_database(self.fixture.database_path)
        return [diagnostic.code for diagnostic in report.diagnostics]

    def _accepted_generation(self):
        candidate = compose_sqlite_timing_correction_candidate_admission_service(
            self.connection
        ).admit(
            intake_id=self.fixture.intake_id,
            candidate=build_timing_correction_candidate_input(self.fixture.proposal()),
        ).candidate
        compose_sqlite_timing_correction_decision_service(self.connection).decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        return compose_sqlite_timing_correction_revision_generation_service(
            self.connection
        ).generate(candidate_id=candidate.identity.value)

    # -- healthy states -----------------------------------------------------------------------

    def test_a_complete_timing_correction_lineage_is_healthy(self) -> None:
        self._accepted_generation()
        self.assertEqual(self._codes(), [])

    def test_a_rejected_candidate_is_not_corruption(self) -> None:
        candidate = compose_sqlite_timing_correction_candidate_admission_service(
            self.connection
        ).admit(
            intake_id=self.fixture.intake_id,
            candidate=build_timing_correction_candidate_input(self.fixture.proposal()),
        ).candidate
        compose_sqlite_timing_correction_decision_service(self.connection).decide(
            candidate_id=candidate.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        self.assertEqual(self._codes(), [])

    def test_accept_generate_then_reject_stays_healthy(self) -> None:
        """V-11/H-12: a later Reject blocks new generation and never makes history corruption."""

        result = self._accepted_generation()
        compose_sqlite_timing_correction_decision_service(self.connection).decide(
            candidate_id=result.generation.timing_correction_candidate_id.value,
            kind="reject",
            reviewer="reviewer:kim",
        )
        self.assertEqual(self._codes(), [])

    def test_an_inapplicable_selection_stays_healthy(self) -> None:
        result = self._accepted_generation()
        compose_sqlite_corrected_revision_selection_service(self.connection).select_revision(
            revision_id=result.revision.identity.value, reviewer="selector:kim"
        )
        compose_sqlite_timing_correction_decision_service(self.connection).decide(
            candidate_id=result.generation.timing_correction_candidate_id.value,
            kind="reject",
            reviewer="reviewer:kim",
        )
        self.assertEqual(self._codes(), [])

    def test_a_repository_with_no_timing_rows_is_unaffected(self) -> None:
        self.assertEqual(self._codes(), [])

    # -- genuine corruption -------------------------------------------------------------------

    def test_a_segment_outside_the_named_transcript_is_flagged(self) -> None:
        """A candidate whose segment does not belong to the transcript it names is corruption."""

        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_provider_transcript_admission_service,
        )

        self._accepted_generation()
        # A-7: one intake may hold several provider results. Point the candidate at a real second
        # Raw Transcript of the same intake, which does not contain its target segment.
        second = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
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
        self.connection.execute(
            "UPDATE timing_correction_candidates SET raw_transcript_id = ?",
            (second.raw_transcript_id.value,),
        )
        self.assertIn("TIMING_CORRECTION_SEGMENT_NOT_IN_RAW_TRANSCRIPT", self._codes())

    def test_a_dangling_segment_reference_is_flagged(self) -> None:
        self._accepted_generation()
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute(
            "UPDATE timing_correction_candidates SET segment_id = ?",
            (f"transcript-segment:{'f' * 64}:0",),
        )
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.assertIn("TIMING_CORRECTION_DANGLING_SEGMENT", self._codes())

    def test_a_broken_decision_history_is_flagged(self) -> None:
        result = self._accepted_generation()
        candidate = result.generation.timing_correction_candidate_id.value
        decisions = compose_sqlite_timing_correction_decision_service(self.connection)
        decisions.decide(candidate_id=candidate, kind="reject", reviewer="reviewer:kim")
        # Detach the superseding record from its predecessor.
        self.connection.execute(
            "UPDATE timing_correction_candidate_decisions SET previous_decision_id = ? "
            "WHERE sequence = 1",
            (f"timing-correction-candidate-decision:{'d' * 64}",),
        )
        self.assertIn("TIMING_CORRECTION_DECISION_BROKEN_HISTORY", self._codes())

    def test_a_generation_authorized_by_a_reject_is_flagged(self) -> None:
        result = self._accepted_generation()
        candidate = result.generation.timing_correction_candidate_id.value
        reject = compose_sqlite_timing_correction_decision_service(self.connection).decide(
            candidate_id=candidate, kind="reject", reviewer="reviewer:kim"
        ).decision
        self.connection.execute(
            "UPDATE timing_correction_revision_generations SET authorizing_decision_id = ?",
            (reject.identity.value,),
        )
        self.assertIn("TIMING_CORRECTION_GENERATION_UNAUTHORIZED", self._codes())

    def test_a_replacement_that_declares_nothing_is_flagged(self) -> None:
        result = self._accepted_generation()
        self.connection.execute(
            "UPDATE transcript_segments SET replaces_segment_id = NULL WHERE identity = ?",
            (result.generation.replacement_segment_id.value,),
        )
        self.assertIn("TIMING_CORRECTION_GENERATION_BROKEN_REPLACEMENT", self._codes())

    def test_a_revision_still_holding_its_replaced_segment_is_flagged(self) -> None:
        result = self._accepted_generation()
        self.connection.execute(
            "INSERT INTO corrected_transcript_revision_segments VALUES (?, ?, ?)",
            (
                result.revision.identity.value,
                99,
                result.generation.replaced_segment_id.value,
            ),
        )
        self.assertIn("TIMING_CORRECTION_GENERATION_BROKEN_MEMBERSHIP", self._codes())

    def test_a_revision_bound_to_both_correction_kinds_is_flagged(self) -> None:
        result = self._accepted_generation()
        # Fabricate a text generation row against the same revision — impossible through the
        # services, and a lineage collision if it ever appeared.
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute(
            "INSERT INTO corrected_revision_generations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "corrected-revision-generation:fabricated",
                result.revision.identity.value,
                "correction-candidate:fabricated",
                "correction-candidate-decision:fabricated",
                self.fixture.raw_transcript_id,
                result.generation.replaced_segment_id.value,
                result.generation.replacement_segment_id.value,
                "0" * 64,
            ),
        )
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.assertIn("TIMING_CORRECTION_GENERATION_KIND_COLLISION", self._codes())

    def test_a_selection_of_a_foreign_context_revision_is_still_flagged(self) -> None:
        """The released context check keeps working, and now covers the timing lineage too."""

        result = self._accepted_generation()
        compose_sqlite_corrected_revision_selection_service(self.connection).select_revision(
            revision_id=result.revision.identity.value, reviewer="selector:kim"
        )
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute(
            "UPDATE timing_correction_candidates SET transcript_source_intake_id = ?",
            (f"transcript-source-intake:{'e' * 64}",),
        )
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.assertIn("CORRECTED_SELECTION_CONTEXT_MISMATCH", self._codes())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
