import json
import unittest
from pathlib import Path

from lectureos.effective_decision_demo import _golden, run_effective_decision_demo

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "effective-decision"
    / "expected"
    / "decision-summary.json"
)


class EffectiveDecisionDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_effective_decision_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "explicit_accept_current_and_applicable",
            "identical_request_reused",
            "matching_intent_by_other_actor_reused",
            "reject_current_and_applicable",
            "modify_is_authority_only",
            "supersession_appends_and_derives_current",
            "stale_subject_keeps_history_and_derives",
            "same_content_distinct_subjects_distinct_decisions",
            "invalid_graph_blocks_decision",
            "no_downstream_records_created",
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
