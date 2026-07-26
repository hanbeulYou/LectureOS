import json
import unittest
from pathlib import Path

from lectureos.corrected_selection_demo import _golden, run_corrected_selection_demo

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "corrected-selection"
    / "expected"
    / "selection-summary.json"
)


class CorrectedSelectionDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_corrected_selection_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "no_history_before_selection",
            "generation_did_not_auto_select",
            "select_recorded",
            "replay_reused",
            "resolve_returns_corrected",
            "transition_appends",
            "fallback_replay_reused",
            "fallback_resolves_raw",
            "history_preserves_all_transitions",
            "later_reject_keeps_selection",
            "later_reject_resolves_inapplicable",
            "reselect_rejected_blocked",
            "revision_a_persisted",
            "raw_transcript_immutable",
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
