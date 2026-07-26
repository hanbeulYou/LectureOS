import json
import unittest
from pathlib import Path

from lectureos.corrected_revision_demo import _golden, run_corrected_revision_demo

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "corrected-revision"
    / "expected"
    / "revision-summary.json"
)


class CorrectedRevisionDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_corrected_revision_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "undecided_blocked",
            "acceptance_alone_created_nothing",
            "generation_created",
            "correction_applied",
            "timing_preserved",
            "unaffected_segment_identical",
            "raw_transcript_unchanged",
            "revision_not_current",
            "authorizing_decision_referenced",
            "replay_reused",
            "later_reject_blocks_new_generation",
            "revision_survives_reject",
            "decision_history_intact",
            "repository_validates_healthy",
        ):
            with self.subTest(check=key):
                self.assertTrue(self.summary[key], key)

    def test_golden_reproduces_byte_for_byte(self):
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(_golden(self.summary), expected)

    def test_golden_file_is_canonical(self):
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        rendered = json.dumps(expected, indent=2, sort_keys=True) + "\n"
        self.assertEqual(_EXPECTED.read_text(encoding="utf-8"), rendered)


if __name__ == "__main__":
    unittest.main()
