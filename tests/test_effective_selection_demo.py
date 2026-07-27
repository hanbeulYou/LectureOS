import json
import unittest
from pathlib import Path

from lectureos.effective_selection_demo import _golden, run_effective_selection_demo

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "effective-selection"
    / "expected"
    / "selection-summary.json"
)


class EffectiveSelectionDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_effective_selection_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "eligible_accept_selects_current_applicable",
            "exact_replay_reused",
            "reject_and_modify_and_superseded_accept_block",
            "new_accept_appends_new_lineage",
            "changed_candidate_appends_and_supersedes",
            "same_content_distinct_candidates_distinct_selections",
            "authority_change_derives_not_mutates",
            "invalid_graph_blocks_selection",
            "no_export_or_legacy_records",
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
