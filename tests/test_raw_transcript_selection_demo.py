import json
import unittest
from pathlib import Path

from lectureos.raw_transcript_selection_demo import (
    _golden,
    run_raw_transcript_selection_demo,
)

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "raw-transcript-selection"
    / "expected"
    / "selection-summary.json"
)


class RawTranscriptSelectionDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_raw_transcript_selection_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "two_distinct_candidates",
            "candidates_ordered_by_identity",
            "not_ready_before_selection",
            "initial_selection_created",
            "repeated_selection_idempotent",
            "ready_after_selection",
            "switch_changes_current",
            "switch_preserves_history",
            "unrelated_raw_transcript_rejected",
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
