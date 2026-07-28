import json
import unittest
from pathlib import Path

from lectureos.analysis_input_admission_demo import (
    _golden,
    run_analysis_input_admission_demo,
)

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "analysis-input-admission"
    / "expected"
    / "admission-summary.json"
)


class AnalysisInputAdmissionDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_analysis_input_admission_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "ineligible_admission_refused_nothing_persisted",
            "admission_binds_exact_authority_snapshot",
            "exact_replay_reused_no_new_row",
            "authority_change_appends_immutable_history",
            "returning_authority_converges",
            "restart_reconstructs_identically",
            "legacy_and_execution_isolation",
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
