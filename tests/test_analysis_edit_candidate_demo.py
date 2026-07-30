import json
import unittest
from pathlib import Path

from lectureos.analysis_edit_candidate_demo import (
    _golden,
    run_analysis_edit_candidate_demo,
)

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "analysis-edit-candidate"
    / "expected"
    / "edit-candidate-summary.json"
)


class AnalysisEditCandidateDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_analysis_edit_candidate_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "candidate_anchors_finding_without_segment_or_execution",
            "exact_replay_reused_no_new_row",
            "integral_and_negative_zero_converge",
            "distinct_content_creates_distinct_candidates",
            "invalid_payloads_refused_nothing_written",
            "superseded_chain_refused_no_row",
            "existing_candidates_are_immutable_history",
            "returning_authority_restores_admissibility",
            "restart_reconstructs_identically",
            "segmentation_independence_and_legacy_isolation",
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
