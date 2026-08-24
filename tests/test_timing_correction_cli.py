"""The Human Timing Correction CLI (040 §17/§18/§19, PATCH-0047).

Pins that the interval always comes from the person — the CLI offers no way to ask the system for one —
that each subcommand states plainly what has *not* happened, and that failures leave the repository
unchanged and return non-zero.
"""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from lectureos.timing_correction_cli import main

# `tests/` is not a package, so a single-module invocation does not put it on sys.path the way
# discovery does; this keeps both `unittest discover` and `unittest tests.<module>` working.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import temporary_fixture


class TimingCorrectionCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory, self.fixture = temporary_fixture()
        self.addCleanup(self._directory.cleanup)
        self.fixture.close()  # the CLI opens its own connection
        self.database = str(self.fixture.database_path)
        self.proposal_path = Path(self._directory.name) / "proposal.json"

    def _write_proposal(self, **overrides) -> str:
        self.proposal_path.write_text(
            json.dumps(self.fixture.proposal(**overrides), ensure_ascii=False),
            encoding="utf-8",
        )
        return str(self.proposal_path)

    def _run(self, *argv) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def _admit(self, **overrides) -> str:
        code, output, _ = self._run(
            "admit",
            "--intake", self.fixture.intake_id,
            "--input", self._write_proposal(**overrides),
            "--database", self.database,
        )
        self.assertEqual(code, 0, output)
        line = next(
            line
            for line in output.splitlines()
            if line.startswith(("created timing", "reused timing"))
        )
        tokens = line.split()
        return tokens[tokens.index("candidate") + 1]

    def test_admit_reports_the_interval_and_that_nothing_was_applied(self) -> None:
        code, output, _ = self._run(
            "admit",
            "--intake", self.fixture.intake_id,
            "--input", self._write_proposal(),
            "--database", self.database,
        )
        self.assertEqual(code, 0)
        self.assertIn("created timing correction candidate", output)
        self.assertIn("proposed interval: [18.0, 24.0]", output)
        self.assertIn("NOT applied", output)

    def test_admit_requires_the_person_to_supply_the_interval(self) -> None:
        # There is no flag that asks the system to propose one, and a payload without an interval
        # is refused rather than completed.
        payload = self.fixture.proposal()
        payload.pop("proposed_start")
        self.proposal_path.write_text(json.dumps(payload), encoding="utf-8")
        code, _, error = self._run(
            "admit",
            "--intake", self.fixture.intake_id,
            "--input", str(self.proposal_path),
            "--database", self.database,
        )
        self.assertEqual(code, 1)
        self.assertIn("proposed_start", error)

    def test_cli_offers_no_automatic_proposal_surface(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src" / "lectureos" / "timing_correction_cli.py"
        ).read_text(encoding="utf-8")
        for forbidden in ("--suggest", "--auto", "--from-diagnostic", "--estimate", "--drift"):
            self.assertNotIn(forbidden, source)

    def test_list_reports_candidates_without_ranking(self) -> None:
        self._admit(candidate_ref="t1")
        self._admit(candidate_ref="t2", proposed_end=23.0)
        code, output, _ = self._run(
            "list", "--intake", self.fixture.intake_id, "--database", self.database
        )
        self.assertEqual(code, 0)
        self.assertIn("timing correction candidates: 2 (not ranked)", output)
        self.assertNotIn("best", output.lower())

    def test_decide_accept_states_that_generation_has_not_happened(self) -> None:
        candidate = self._admit()
        code, output, _ = self._run(
            "decide", "--candidate", candidate, "--kind", "accept",
            "--reviewer", "reviewer:kim", "--database", self.database,
        )
        self.assertEqual(code, 0)
        self.assertIn("current authority: accepted", output)
        self.assertIn("NOT happened", output)

    def test_decide_reject_is_reported_as_a_normal_outcome(self) -> None:
        candidate = self._admit()
        code, output, _ = self._run(
            "decide", "--candidate", candidate, "--kind", "reject",
            "--reviewer", "reviewer:kim", "--database", self.database,
        )
        self.assertEqual(code, 0)
        self.assertIn("current authority: rejected", output)
        self.assertIn("reject is a normal outcome", output)

    def test_decide_rejects_modify(self) -> None:
        candidate = self._admit()
        with self.assertRaises(SystemExit):
            self._run(
                "decide", "--candidate", candidate, "--kind", "modify",
                "--reviewer", "reviewer:kim", "--database", self.database,
            )

    def test_generate_reports_text_preservation_and_non_selection(self) -> None:
        candidate = self._admit()
        self._run(
            "decide", "--candidate", candidate, "--kind", "accept",
            "--reviewer", "reviewer:kim", "--database", self.database,
        )
        code, output, _ = self._run(
            "generate", "--candidate", candidate, "--database", self.database
        )
        self.assertEqual(code, 0)
        self.assertIn("created corrected revision", output)
        self.assertIn("text is preserved exactly", output)
        self.assertIn("NOT selected as current", output)

    def test_generate_on_a_rejected_candidate_fails_without_writing(self) -> None:
        candidate = self._admit()
        self._run(
            "decide", "--candidate", candidate, "--kind", "reject",
            "--reviewer", "reviewer:kim", "--database", self.database,
        )
        code, _, error = self._run(
            "generate", "--candidate", candidate, "--database", self.database
        )
        self.assertEqual(code, 1)
        self.assertIn("rejected", error)

        from lectureos.persistence import open_sqlite_database

        connection = open_sqlite_database(self.database)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM corrected_transcript_revisions"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_no_op_proposal_fails_with_an_explicit_error(self) -> None:
        code, _, error = self._run(
            "admit",
            "--intake", self.fixture.intake_id,
            "--input", self._write_proposal(
                proposed_start=self.fixture.target.start,
                proposed_end=self.fixture.target.end,
            ),
            "--database", self.database,
        )
        self.assertEqual(code, 1)
        self.assertIn("no-op", error)

    def test_overlapping_proposal_fails_with_an_explicit_error(self) -> None:
        code, _, error = self._run(
            "admit",
            "--intake", self.fixture.intake_id,
            "--input", self._write_proposal(proposed_start=18.0, proposed_end=26.0),
            "--database", self.database,
        )
        self.assertEqual(code, 1)
        self.assertIn("next segment", error)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
