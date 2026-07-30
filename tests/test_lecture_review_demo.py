import json
import unittest
from pathlib import Path

from lectureos.lecture_review_demo import _golden, run_lecture_review_demo

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "lecture-review"
    / "expected"
    / "lecture-review-summary.json"
)


class LectureReviewDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_lecture_review_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "accept_owns_inherited_approved_snapshot",
            "reject_records_a_durable_decision_with_no_approval",
            "modify_owns_the_replacement_and_never_touches_the_candidate",
            "exact_replay_reused_no_new_rows",
            "a_different_human_actor_is_a_distinct_judgment",
            "integral_and_negative_zero_approved_bounds_converge",
            "differing_second_modify_is_an_explicit_conflict_nothing_written",
            "invalid_judgments_refused_nothing_written",
            "superseded_chain_refused_history_untouched",
            "returning_authority_restores_admissibility",
            "reversed_judgments_coexist_unadjudicated",
            "restart_reconstructs_identically",
            "execution_free_and_legacy_isolated",
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
