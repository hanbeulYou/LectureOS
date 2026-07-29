import json
import unittest
from pathlib import Path

from lectureos.analysis_finding_demo import _golden, run_analysis_finding_demo

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "analysis-finding"
    / "expected"
    / "finding-summary.json"
)


class AnalysisFindingDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_analysis_finding_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "finding_anchors_admission_without_duplicating_provenance",
            "exact_replay_reused_no_new_row",
            "divergent_payload_conflicts_nothing_written",
            "distinct_content_creates_distinct_findings",
            "superseded_anchor_refused_no_row",
            "existing_findings_are_immutable_history",
            "returning_authority_restores_admissibility",
            "restart_reconstructs_identically",
            "legacy_execution_and_downstream_isolation",
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
