import json
import unittest
from pathlib import Path

from lectureos.transcript_consumption_demo import (
    _golden,
    run_transcript_consumption_demo,
)

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "transcript-consumption"
    / "expected"
    / "consumption-summary.json"
)


class TranscriptConsumptionDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_transcript_consumption_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "first_consumption_no_history_raw",
            "same_source_replay_reused",
            "corrected_consumption_created",
            "corrected_replay_reused",
            "distinct_sources_distinct_bindings",
            "fallback_converges_on_r1_binding",
            "provenance_distinguishes_no_history_and_fallback",
            "later_reject_blocks_new_consumption",
            "later_reject_keeps_bindings",
            "later_reject_derives_stale_not_mutates",
            "raw_switch_blocks_corrected_consumption",
            "raw_switch_derives_r1_stale",
            "new_source_gets_new_binding",
            "all_bindings_preserved",
            "source_segments_immutable",
            "repository_validates_healthy",
        ):
            with self.subTest(check=key):
                self.assertTrue(self.summary[key], key)

    def test_golden_reproduces_byte_for_byte(self):
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(_golden(self.summary), expected)

    def test_golden_file_is_canonical(self):
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        rendered = json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self.assertEqual(_EXPECTED.read_text(encoding="utf-8"), rendered)


if __name__ == "__main__":
    unittest.main()
