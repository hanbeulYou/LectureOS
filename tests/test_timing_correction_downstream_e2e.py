"""Timing correction end to end: candidate → decision → revision → selection → SRT (PATCH-0047 TC-13/TC-17).

Drives the whole path over a real released chain with a fake provider result — no ASR, no network, no
media decoding — and asserts the two facts the contract turns on:

* a corrected revision's segment timing **is** that segment's canonical corrected timing, and reaches
  the delivered SRT through the released `§20`/`§21`/`041` path with no subtitle retiming logic added;
* nothing downstream moves on its own — the released Final Selection, SRT Artifact and Materialization
  stay exactly as they were until a person selects the corrected revision and materializes again.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lectureos.application.timing_correction_candidate_admission import (
    build_timing_correction_candidate_input,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_effective_srt_materialization_service,
    compose_sqlite_effective_subtitle_final_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_effective_subtitle_srt_artifact_service,
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

from timing_correction_fixture import TimingCorrectionFixture


class TimingCorrectionDownstreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.fixture = TimingCorrectionFixture(self._directory.name)
        self.addCleanup(self.fixture.close)
        self.connection = self.fixture.connection
        self.storage_root = Path(self._directory.name) / "out"
        self.storage_root.mkdir()

        self.subtitles = compose_sqlite_effective_subtitle_generation_service(self.connection)
        self.preparation = compose_sqlite_effective_subtitle_review_preparation_service(
            self.connection
        )
        self.review = compose_sqlite_effective_subtitle_review_decision_service(self.connection)
        self.final = compose_sqlite_effective_subtitle_final_selection_service(self.connection)
        self.export = compose_sqlite_effective_subtitle_srt_artifact_service(self.connection)
        self.materializer = compose_sqlite_effective_srt_materialization_service(
            self.connection, str(self.storage_root)
        )
        self.selection = compose_sqlite_corrected_revision_selection_service(self.connection)

    # -- the released downstream chain, driven exactly as its own demo does --------------------

    def _deliver(self):
        candidate = self.subtitles.generate(intake_id=self.fixture.intake_id).candidate
        subject = self.preparation.prepare_review(
            candidate_id=candidate.identity.value
        ).subject
        self.review.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        selection = self.final.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        ).selection
        artifact = self.export.generate_srt_artifact(
            final_selection_id=selection.identity.value
        ).artifact
        materialization = self.materializer.materialize(
            artifact_id=artifact.identity.value
        ).materialization
        path = self.storage_root / materialization.relative_location
        return artifact, path, path.read_text(encoding="utf-8")

    def _accept_timing_correction(self, **overrides):
        candidate = compose_sqlite_timing_correction_candidate_admission_service(
            self.connection
        ).admit(
            intake_id=self.fixture.intake_id,
            candidate=build_timing_correction_candidate_input(
                self.fixture.proposal(**overrides)
            ),
        ).candidate
        compose_sqlite_timing_correction_decision_service(self.connection).decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        return compose_sqlite_timing_correction_revision_generation_service(
            self.connection
        ).generate(candidate_id=candidate.identity.value)

    def test_corrected_timing_reaches_the_delivered_srt(self) -> None:
        self.selection.select_raw_fallback(
            intake_id=self.fixture.intake_id, reviewer="selector:kim"
        )
        before_artifact, before_path, before_srt = self._deliver()
        self.assertIn("00:00:10,000 --> 00:00:20,000", before_srt)

        result = self._accept_timing_correction()

        # Generation alone changes nothing downstream (TC-17).
        self.assertEqual(before_path.read_text(encoding="utf-8"), before_srt)
        self.assertIn("00:00:10,000 --> 00:00:20,000", before_path.read_text(encoding="utf-8"))

        # Only an explicit selection moves the effective transcript.
        self.selection.select_revision(
            revision_id=result.revision.identity.value, reviewer="selector:kim"
        )
        after_artifact, after_path, after_srt = self._deliver()

        self.assertIn("00:00:18,000 --> 00:00:24,000", after_srt)
        self.assertNotIn("00:00:10,000 --> 00:00:20,000", after_srt)
        # The corrected cue carries the source text unchanged.
        self.assertIn(self.fixture.target.text, after_srt)
        # Untouched segments keep their timing.
        self.assertIn("00:00:00,000 --> 00:00:02,500", after_srt)
        self.assertIn("00:00:25,000 --> 00:00:30,000", after_srt)

        # A new artifact under a new identity; the released one is untouched on disk.
        self.assertNotEqual(before_artifact.identity, after_artifact.identity)
        self.assertNotEqual(before_path, after_path)
        self.assertEqual(before_path.read_text(encoding="utf-8"), before_srt)

    def test_no_subtitle_retiming_logic_participates(self) -> None:
        """TC-13/TC-14: the cue timing equals the revision's segment timing, value for value."""

        self.selection.select_raw_fallback(
            intake_id=self.fixture.intake_id, reviewer="selector:kim"
        )
        self._deliver()
        result = self._accept_timing_correction()
        self.selection.select_revision(
            revision_id=result.revision.identity.value, reviewer="selector:kim"
        )
        candidate = self.subtitles.generate(intake_id=self.fixture.intake_id).candidate
        cues = self.subtitles.cues(candidate_id=candidate.identity.value)
        corrected = next(
            cue
            for cue in cues
            if result.generation.replacement_segment_id in cue.source_segment_ids
        )
        self.assertEqual(corrected.start, 18.0)
        self.assertEqual(corrected.end, 24.0)
        self.assertEqual(corrected.text, self.fixture.target.text)

    def test_generation_does_not_auto_select_or_auto_regenerate(self) -> None:
        result = self._accept_timing_correction()
        self.assertIsNone(self.selection.current(self.fixture.intake_id))
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_srt_artifacts"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM corrected_revision_selections"
            ).fetchone()[0],
            0,
        )
        self.assertIsNotNone(result.revision.identity)

    def test_selection_resolves_a_timing_revision_as_the_effective_transcript(self) -> None:
        result = self._accept_timing_correction()
        self.selection.select_revision(
            revision_id=result.revision.identity.value, reviewer="selector:kim"
        )
        effective = self.selection.resolve_effective_transcript(self.fixture.intake_id)
        self.assertEqual(effective.effective_kind.value, "corrected_revision")
        self.assertEqual(effective.corrected_revision_id, result.revision.identity)
        applicability = self.selection.applicability(self.fixture.intake_id)
        self.assertTrue(applicability.applicable)

    def test_rejecting_the_candidate_later_makes_the_selection_inapplicable(self) -> None:
        """S2-9 semantics, unchanged for the timing kind: never corruption, never silent fallback."""

        result = self._accept_timing_correction()
        candidate_id = result.generation.timing_correction_candidate_id.value
        self.selection.select_revision(
            revision_id=result.revision.identity.value, reviewer="selector:kim"
        )
        compose_sqlite_timing_correction_decision_service(self.connection).decide(
            candidate_id=candidate_id, kind="reject", reviewer="reviewer:kim"
        )
        effective = self.selection.resolve_effective_transcript(self.fixture.intake_id)
        self.assertEqual(effective.effective_kind.value, "inapplicable_selection")
        self.assertEqual(effective.inapplicability_reason, "candidate_not_accepted")
        # The selection history itself is untouched.
        self.assertEqual(len(self.selection.history(self.fixture.intake_id)), 1)

    def test_a_timing_revision_with_a_rejected_candidate_cannot_be_newly_selected(self) -> None:
        from lectureos.application.corrected_revision_selection import (
            RevisionNotEligibleError,
        )

        result = self._accept_timing_correction()
        compose_sqlite_timing_correction_decision_service(self.connection).decide(
            candidate_id=result.generation.timing_correction_candidate_id.value,
            kind="reject",
            reviewer="reviewer:kim",
        )
        with self.assertRaises(RevisionNotEligibleError):
            self.selection.select_revision(
                revision_id=result.revision.identity.value, reviewer="selector:kim"
            )

    def test_repository_validation_is_healthy_through_the_whole_flow(self) -> None:
        self.selection.select_raw_fallback(
            intake_id=self.fixture.intake_id, reviewer="selector:kim"
        )
        self._deliver()
        result = self._accept_timing_correction()
        self.selection.select_revision(
            revision_id=result.revision.identity.value, reviewer="selector:kim"
        )
        self._deliver()
        report = validate_database(self.fixture.database_path)
        self.assertEqual(
            [diagnostic.code for diagnostic in report.diagnostics],
            [],
        )
        self.assertEqual(report.health.value, "healthy")
        self.assertEqual(report.schema_version, 55)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
