"""`timing_correction_cli inspect` — the operational read that closes the SQLite gap (040 §17).

`implementation/142` found that authoring a timing proposal required reading the database by hand:
TC-9 makes the source-timing snapshot caller-supplied, and no released command printed a segment's
persisted interval. This command reports the canonical snapshot so a person does not have to.

These tests pin what it reports, and just as firmly what it refuses to become: it proposes no
interval, reads no media, consults no diagnostic, persists nothing, and re-implements no admission
rule. The values it prints must round-trip into `admit` without precision loss, which is the whole
point of the command existing.
"""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.timing_correction_candidate_admission import (
    build_timing_correction_candidate_input,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_timing_correction_candidate_admission_service,
    compose_sqlite_timing_correction_decision_service,
    compose_sqlite_timing_correction_revision_generation_service,
)
from lectureos.persistence import SQLiteTranscriptSegmentRepository
from lectureos.timing_correction_cli import main

# `tests/` is not a package, so a single-module invocation does not put it on sys.path the way
# discovery does; this keeps both `unittest discover` and `unittest tests.<module>` working.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import temporary_fixture

_CLI_SOURCE = (
    Path(__file__).resolve().parents[1] / "src" / "lectureos" / "timing_correction_cli.py"
)


class TimingCorrectionInspectCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory, self.fixture = temporary_fixture()
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.fixture.close)
        self.connection = self.fixture.connection
        self.database = str(self.fixture.database_path)

    def _run(self, *argv) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def _inspect(self, segment, fmt="text", raw=None):
        return self._run(
            "inspect",
            "--raw-transcript", raw or self.fixture.raw_transcript_id,
            "--segment", segment.identity.value,
            "--format", fmt,
            "--database", self.database,
        )

    def _replacement_segment(self):
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
                    "rationale": "교정",
                }
            ),
        ).candidate
        compose_sqlite_correction_candidate_decision_service(self.connection).decide(
            candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        generation = compose_sqlite_corrected_revision_generation_service(
            self.connection
        ).generate(candidate_id=candidate.identity.value).generation
        return SQLiteTranscriptSegmentRepository(self.connection).get(
            generation.replacement_segment_id
        )

    # -- what it reports -----------------------------------------------------------------------

    def test_reports_the_canonical_snapshot(self) -> None:
        code, output, _ = self._inspect(self.fixture.target)
        self.assertEqual(code, 0)
        self.assertIn(self.fixture.raw_transcript_id, output)
        self.assertIn(self.fixture.target.identity.value, output)
        self.assertIn("ordinal: 1 of 3", output)
        self.assertIn(self.fixture.target.text, output)
        self.assertIn(f"[{self.fixture.target.start}, {self.fixture.target.end}]", output)

    def test_reports_the_intake_the_admit_command_requires(self) -> None:
        code, output, _ = self._inspect(self.fixture.target)
        self.assertEqual(code, 0)
        self.assertIn(self.fixture.intake_id, output)

    def test_reports_both_neighbour_intervals(self) -> None:
        _, output, _ = self._inspect(self.fixture.target)
        previous, following = self.fixture.segments[0], self.fixture.segments[2]
        self.assertIn(f"previous: [{previous.start}, {previous.end}]", output)
        self.assertIn(f"next: [{following.start}, {following.end}]", output)

    def test_first_segment_has_no_previous(self) -> None:
        _, output, _ = self._inspect(self.fixture.segments[0])
        self.assertIn("previous: none (this is the first segment)", output)
        self.assertIn(f"next: [{self.fixture.segments[1].start}", output)

    def test_last_segment_has_no_next(self) -> None:
        _, output, _ = self._inspect(self.fixture.segments[-1])
        self.assertIn("next: none (this is the last segment)", output)
        self.assertIn(f"previous: [{self.fixture.segments[-2].start}", output)

    def test_prints_the_snapshot_fields_to_carry(self) -> None:
        _, output, _ = self._inspect(self.fixture.target)
        self.assertIn(
            f'"source_start_snapshot": {self.fixture.target.start}, '
            f'"source_end_snapshot": {self.fixture.target.end}',
            output,
        )
        self.assertIn("proposes nothing", output)

    # -- errors --------------------------------------------------------------------------------

    def test_unknown_raw_transcript_is_an_error(self) -> None:
        code, _, error = self._run(
            "inspect", "--raw-transcript", f"raw-transcript:{'0' * 64}",
            "--segment", self.fixture.target.identity.value, "--database", self.database,
        )
        self.assertEqual(code, 1)
        self.assertIn("unknown raw transcript", error)

    def test_unknown_segment_is_an_error(self) -> None:
        code, _, error = self._run(
            "inspect", "--raw-transcript", self.fixture.raw_transcript_id,
            "--segment", f"transcript-segment:{'0' * 64}:0", "--database", self.database,
        )
        self.assertEqual(code, 1)
        self.assertIn("not part of this raw transcript", error)

    def test_segment_of_another_transcript_is_an_error(self) -> None:
        directory, other = temporary_fixture(provider_result_ref="B")
        self.addCleanup(directory.cleanup)
        self.addCleanup(other.close)
        code, _, error = self._inspect(other.target)
        self.assertEqual(code, 1)
        self.assertIn("not part of this raw transcript", error)

    def test_a_replacement_segment_is_not_reported_as_a_raw_member(self) -> None:
        """It carries the Raw Transcript's identity but is not in its membership (K-1)."""

        replacement = self._replacement_segment()
        self.assertEqual(replacement.transcript_id.value, self.fixture.raw_transcript_id)
        code, _, error = self._inspect(replacement)
        self.assertEqual(code, 1)
        self.assertIn("replacement segment is not a Raw Transcript segment", error)

    # -- machine-readable output and precision --------------------------------------------------

    def test_json_output_round_trips_into_a_working_proposal(self) -> None:
        """The reason this command exists: paste its values and admission must accept them."""

        code, output, _ = self._inspect(self.fixture.target, fmt="json")
        self.assertEqual(code, 0)
        snapshot = json.loads(output)
        self.assertEqual(snapshot["start"], self.fixture.target.start)
        self.assertEqual(snapshot["end"], self.fixture.target.end)

        candidate = compose_sqlite_timing_correction_candidate_admission_service(
            self.connection
        ).admit(
            intake_id=snapshot["transcript_source_intake_id"],
            candidate=build_timing_correction_candidate_input(
                {
                    "raw_transcript_id": snapshot["raw_transcript_id"],
                    "segment_id": snapshot["segment_id"],
                    "candidate_ref": "from-inspect",
                    "author": "human:editor-1",
                    # carried verbatim from the inspect output — TC-9's snapshot must match exactly
                    "source_start_snapshot": snapshot["start"],
                    "source_end_snapshot": snapshot["end"],
                    # the person's own judgement, bounded by the neighbours inspect reported
                    "proposed_start": 18.0,
                    "proposed_end": 24.0,
                    "rationale": "청취 후 판단",
                }
            ),
        ).candidate
        self.assertTrue(candidate.identity.value.startswith("timing-correction-candidate:"))

    def test_json_carries_the_neighbours_that_bound_a_proposal(self) -> None:
        _, output, _ = self._inspect(self.fixture.target, fmt="json")
        snapshot = json.loads(output)
        self.assertEqual(snapshot["previous"]["end"], self.fixture.segments[0].end)
        self.assertEqual(snapshot["next"]["start"], self.fixture.segments[2].start)
        edge = json.loads(self._inspect(self.fixture.segments[0], fmt="json")[1])
        self.assertIsNone(edge["previous"])

    def test_json_preserves_awkward_float_precision(self) -> None:
        directory, fixture = temporary_fixture(
            segments=(
                {"start": 0.0, "end": 2.5, "text": "첫"},
                {"start": 4276.139999999999, "end": 4300.1, "text": "둘"},
            ),
            provider_result_ref="C",
        )
        self.addCleanup(directory.cleanup)
        self.addCleanup(fixture.close)
        out = io.StringIO()
        with redirect_stdout(out):
            main([
                "inspect", "--raw-transcript", fixture.raw_transcript_id,
                "--segment", fixture.segments[1].identity.value,
                "--format", "json", "--database", str(fixture.database_path),
            ])
        self.assertEqual(json.loads(out.getvalue())["start"], 4276.139999999999)

    # -- what it must not do ---------------------------------------------------------------------

    def test_inspection_writes_nothing(self) -> None:
        def _counts():
            return {
                table: self.connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                for table in (
                    "timing_correction_candidates",
                    "timing_correction_candidate_decisions",
                    "timing_correction_revision_generations",
                    "correction_candidates",
                    "corrected_transcript_revisions",
                    "transcript_segments",
                )
            }

        before = _counts()
        self._inspect(self.fixture.target)
        self._inspect(self.fixture.target, fmt="json")
        self.assertEqual(before, _counts())

    def test_raw_transcript_segment_is_unchanged_by_inspection(self) -> None:
        before = self.connection.execute(
            'SELECT identity, text, "start", "end" FROM transcript_segments ORDER BY identity'
        ).fetchall()
        self._inspect(self.fixture.target)
        self.assertEqual(
            before,
            self.connection.execute(
                'SELECT identity, text, "start", "end" FROM transcript_segments ORDER BY identity'
            ).fetchall(),
        )

    def test_inspect_consults_no_diagnostic_and_proposes_nothing(self) -> None:
        source = _CLI_SOURCE.read_text(encoding="utf-8")
        for forbidden in (
            "TIMING_ALIGNMENT_REVIEW_REQUIRED",
            "transcript_quality_diagnostic",
            "anchor",
            "drift",
            "proposed_start\":",
            "ffmpeg",
        ):
            self.assertNotIn(forbidden, source)

    def test_inspect_offers_no_proposal_flags(self) -> None:
        source = _CLI_SOURCE.read_text(encoding="utf-8")
        for forbidden in ("--suggest", "--auto", "--from-diagnostic", "--estimate", "--propose"):
            self.assertNotIn(forbidden, source)

    # -- the loop it enables ---------------------------------------------------------------------

    def test_inspect_output_reaches_decision_and_generation(self) -> None:
        """inspect → admit → decide → generate, using only values the command printed."""

        snapshot = json.loads(self._inspect(self.fixture.target, fmt="json")[1])
        candidate = compose_sqlite_timing_correction_candidate_admission_service(
            self.connection
        ).admit(
            intake_id=snapshot["transcript_source_intake_id"],
            candidate=build_timing_correction_candidate_input(
                {
                    "raw_transcript_id": snapshot["raw_transcript_id"],
                    "segment_id": snapshot["segment_id"],
                    "candidate_ref": "loop",
                    "author": "human:editor-1",
                    "source_start_snapshot": snapshot["start"],
                    "source_end_snapshot": snapshot["end"],
                    "proposed_start": 18.0,
                    "proposed_end": 24.0,
                    "rationale": "청취 후 판단",
                }
            ),
        ).candidate
        code, output, _ = self._run(
            "decide", "--candidate", candidate.identity.value, "--kind", "accept",
            "--reviewer", "reviewer:kim", "--database", self.database,
        )
        self.assertEqual(code, 0, output)
        code, output, _ = self._run(
            "generate", "--candidate", candidate.identity.value, "--database", self.database
        )
        self.assertEqual(code, 0, output)
        self.assertIn("created corrected revision", output)

    def test_a_rejected_candidate_needs_no_extra_tooling(self) -> None:
        snapshot = json.loads(self._inspect(self.fixture.target, fmt="json")[1])
        candidate = compose_sqlite_timing_correction_candidate_admission_service(
            self.connection
        ).admit(
            intake_id=snapshot["transcript_source_intake_id"],
            candidate=build_timing_correction_candidate_input(
                {
                    "raw_transcript_id": snapshot["raw_transcript_id"],
                    "segment_id": snapshot["segment_id"],
                    "candidate_ref": "rej",
                    "author": "human:editor-1",
                    "source_start_snapshot": snapshot["start"],
                    "source_end_snapshot": snapshot["end"],
                    "proposed_start": 18.0,
                    "proposed_end": 24.0,
                    "rationale": "청취 후 판단",
                }
            ),
        ).candidate
        code, output, _ = self._run(
            "decide", "--candidate", candidate.identity.value, "--kind", "reject",
            "--reviewer", "reviewer:kim", "--database", self.database,
        )
        self.assertEqual(code, 0)
        self.assertIn("reject is a normal outcome", output)

    def test_admission_rules_still_belong_to_the_service(self) -> None:
        """A no-op is refused by admission, not by anything inspect taught the CLI."""

        from lectureos.application.timing_correction_candidate_admission import (
            TimingProposalNoOpError,
        )

        snapshot = json.loads(self._inspect(self.fixture.target, fmt="json")[1])
        with self.assertRaises(TimingProposalNoOpError):
            compose_sqlite_timing_correction_candidate_admission_service(
                self.connection
            ).admit(
                intake_id=snapshot["transcript_source_intake_id"],
                candidate=build_timing_correction_candidate_input(
                    {
                        "raw_transcript_id": snapshot["raw_transcript_id"],
                        "segment_id": snapshot["segment_id"],
                        "candidate_ref": "noop",
                        "author": "human:editor-1",
                        "source_start_snapshot": snapshot["start"],
                        "source_end_snapshot": snapshot["end"],
                        "proposed_start": snapshot["start"],
                        "proposed_end": snapshot["end"],
                        "rationale": "…",
                    }
                ),
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
