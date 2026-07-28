import json
import unittest
from pathlib import Path

from lectureos.analysis_input_eligibility_demo import (
    _golden,
    run_analysis_input_eligibility_demo,
)

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "analysis-input-eligibility"
    / "expected"
    / "eligibility-summary.json"
)


class AnalysisInputEligibilityDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_analysis_input_eligibility_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "corrected_authority_required",
            "eligible_exposes_exact_lineage",
            "eligibility_resolves_only_current_authority",
            "inapplicable_selection_never_falls_back",
            "unknown_intake_is_stable_ineligibility",
            "derived_only_nothing_persisted",
            "restart_produces_identical_result",
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
