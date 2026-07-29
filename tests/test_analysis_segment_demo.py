import json
import unittest
from pathlib import Path

from lectureos.analysis_segment_demo import _golden, run_analysis_segment_demo

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "analysis-segment"
    / "expected"
    / "segment-summary.json"
)


class AnalysisSegmentDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_analysis_segment_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "batch_recorded_without_finding_or_execution",
            "exact_replay_reused_no_new_row",
            "integral_ranges_converge_on_same_identities",
            "distinct_batch_records_distinct_segments_sharing_sequence",
            "partial_pre_existence_records_only_new",
            "invalid_batches_refused_nothing_written",
            "superseded_anchor_refused_no_row",
            "existing_segments_are_immutable_history",
            "returning_authority_restores_admissibility",
            "restart_reconstructs_identically",
            "finding_independence_and_legacy_isolation",
            "repository_validates_healthy",
        ):
            with self.subTest(check=key):
                self.assertTrue(self.summary[key], key)

    def test_golden_reproduces_byte_for_byte(self):
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(_golden(self.summary), expected)

    def test_golden_file_is_canonical_and_free_of_machine_paths(self):
        text = _EXPECTED.read_text(encoding="utf-8")
        expected = json.loads(text)
        rendered = json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self.assertEqual(text, rendered)
        for fragment in ("/tmp", "/var", "/Users", "/home", "C:\\"):
            self.assertNotIn(fragment, text)


if __name__ == "__main__":
    unittest.main()
