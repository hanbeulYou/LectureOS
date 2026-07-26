import json
import unittest
from pathlib import Path

from lectureos.correction_candidate_demo import _golden, run_correction_candidate_demo

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "correction-candidate"
    / "expected"
    / "candidate-summary.json"
)


class CorrectionCandidateDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_correction_candidate_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "not_ready_rejected",
            "candidate_admitted",
            "raw_text_unchanged",
            "replay_idempotent",
            "two_distinct_candidates",
            "candidates_all_applicable_before_switch",
            "candidates_preserved_after_switch",
            "candidates_not_applicable_after_switch",
            "stale_rejected",
            "not_current_rejected",
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
