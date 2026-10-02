"""The same-source composition CLI, driven as a real subprocess (040 §19 `PATCH-0050`, IR 4/18)."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.timing_correction_candidate_admission import (
    build_timing_correction_candidate_input,
)
from lectureos.composition import (
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_timing_correction_candidate_admission_service,
    compose_sqlite_timing_correction_decision_service,
)
from lectureos.persistence import open_sqlite_database

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import temporary_fixture  # noqa: E402

SRC = str(Path(__file__).resolve().parents[1] / "src")


def _cli(module: str, *argv: str) -> tuple[int, str, str]:
    env = dict(os.environ, PYTHONPATH=SRC)
    completed = subprocess.run(
        [sys.executable, "-m", f"lectureos.{module}", *argv],
        capture_output=True, text=True, env=env, timeout=120,
    )
    return completed.returncode, completed.stdout, completed.stderr


class SameSourceCompositionCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory, self.fixture = temporary_fixture()
        self.addCleanup(self._directory.cleanup)
        connection = self.fixture.connection
        self.database = str(self.fixture.database_path)
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

    def _generate(self, text=None, timing=None, swap_option_order=False):
        text = text or self.text.identity.value
        timing = timing or self.timing.identity.value
        options = ["--text-candidate", text, "--timing-candidate", timing]
        if swap_option_order:
            options = ["--timing-candidate", timing, "--text-candidate", text]
        return _cli("same_source_composition_cli", "generate", *options, "--database", self.database)

    def test_generate_with_explicit_roles_then_show(self) -> None:
        code, out, err = self._generate()
        self.assertEqual(code, 0, err)
        self.assertIn("created composed corrected revision corrected-revision:", out)
        self.assertIn(f"text candidate: {self.text.identity.value}", out)
        self.assertIn(f"timing candidate: {self.timing.identity.value}", out)
        self.assertIn("text authorizing decision: correction-candidate-decision:", out)
        self.assertIn("timing authorizing decision: timing-correction-candidate-decision:", out)
        self.assertIn("text: '둘째 문장입니다'", out)
        self.assertIn("interval: [18.0, 24.0]", out)
        self.assertIn("NOT selected", out)
        generation = next(line.split(": ", 1)[1] for line in out.splitlines() if line.startswith("generation: "))
        code, shown, err = _cli("same_source_composition_cli", "show", "--generation", generation, "--database", self.database)
        self.assertEqual(code, 0, err)
        self.assertIn(f"replaced source segment: {self.fixture.target.identity.value}", shown)
        # Option order does not matter; the same request is reused.
        code, again, _ = self._generate(swap_option_order=True)
        self.assertEqual(code, 0)
        self.assertIn("reused composed corrected revision", again)
        self.assertIn(f"generation: {generation}", again)

    def test_wrong_role_missing_role_and_non_accepted_fail_explicitly(self) -> None:
        code, _, err = self._generate(text=self.timing.identity.value, timing=self.text.identity.value)
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertIn("text role", err)
        code, _, err = _cli(
            "same_source_composition_cli", "generate",
            "--text-candidate", self.text.identity.value, "--database", self.database,
        )
        self.assertEqual(code, 2)  # argparse: the timing role is required
        connection = open_sqlite_database(self.database)
        compose_sqlite_timing_correction_decision_service(connection).decide(
            candidate_id=self.timing.identity.value, kind="reject", reviewer="reviewer:lee"
        )
        connection.close()
        code, _, err = self._generate()
        self.assertEqual(code, 1)
        self.assertIn("rejected", err)
        connection = open_sqlite_database(self.database)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM same_source_composition_generations").fetchone()[0], 0
            )
        finally:
            connection.close()

    def test_generation_only_then_existing_selection_command_accepts_the_revision(self) -> None:
        code, out, err = self._generate()
        self.assertEqual(code, 0, err)
        revision = next(
            line.split(": ", 1)[1] for line in out.splitlines() if line.startswith("corrected revision: ")
        )
        code, status, _ = _cli(
            "corrected_selection_cli", "status", "--intake", self.fixture.intake_id, "--database", self.database
        )
        self.assertEqual(code, 0)
        self.assertNotIn(revision, status)  # generation selected nothing
        code, out, err = _cli(
            "corrected_selection_cli", "select",
            "--revision", revision, "--reviewer", "selector:kim", "--database", self.database,
        )
        self.assertEqual(code, 0, err)
        code, resolved, _ = _cli(
            "corrected_selection_cli", "resolve", "--intake", self.fixture.intake_id, "--database", self.database
        )
        self.assertEqual(code, 0)
        self.assertIn(revision, resolved)

    def test_released_single_kind_commands_are_unchanged(self) -> None:
        code, out, err = _cli(
            "corrected_revision_cli", "generate", "--candidate", self.text.identity.value, "--database", self.database
        )
        self.assertEqual(code, 0, err)
        code, out, err = _cli(
            "timing_correction_cli", "generate", "--candidate", self.timing.identity.value, "--database", self.database
        )
        self.assertEqual(code, 0, err)
        self.assertIn("segment text is preserved exactly", out)
        code, _, err = _cli(
            "timing_correction_cli", "generate", "--candidate", self.timing.identity.value,
            "--candidate", self.text.identity.value, "--database", self.database,
        )
        self.assertEqual(code, 1)
        # The text candidate's history lists both the singleton and the composition once composed.
        self.assertEqual(self._generate()[0], 0)
        code, listed, _ = _cli(
            "corrected_revision_cli", "list", "--candidate", self.text.identity.value, "--database", self.database
        )
        self.assertEqual(code, 0)
        self.assertIn("generations for candidate", listed)
        self.assertIn(": 2", listed.splitlines()[0])
        self.assertIn("composition", listed)
        self.assertIn(f"timing-candidate={self.timing.identity.value}", listed)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
