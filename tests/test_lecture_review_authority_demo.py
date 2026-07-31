import json
import unittest
from pathlib import Path

from lectureos.lecture_review_authority_demo import (
    _golden,
    run_lecture_review_authority_demo,
)

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "lecture-review-authority"
    / "expected"
    / "review-authority-summary.json"
)


class LectureReviewAuthorityDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_lecture_review_authority_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "first_judgment_starts_the_history_at_zero",
            "a_reversal_appends_and_supersedes",
            "reversing_back_reuses_the_decision_and_opens_a_new_position",
            "one_decision_occupies_several_positions",
            "replaying_the_head_writes_nothing",
            "current_is_derived_from_the_highest_position",
            "superseded_positions_remain_immutable_history",
            "a_second_actor_keeps_a_separate_history",
            "cross_actor_derives_no_current_and_reports_a_conflict",
            "per_actor_currents_stay_derivable_during_the_conflict",
            "a_scope_without_history_derives_nothing",
            "superseded_chain_refused_history_untouched",
            "returning_authority_appends_nothing_for_the_same_judgment",
            "restart_reconstructs_identically",
            "execution_free_and_canonical_records_untouched",
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

    def test_the_demo_is_deterministic_across_runs(self):
        self.assertEqual(_golden(run_lecture_review_authority_demo()),
                         _golden(self.summary))


if __name__ == "__main__":
    unittest.main()
