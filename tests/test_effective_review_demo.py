import json
import unittest
from pathlib import Path

from lectureos.effective_review_demo import _golden, run_effective_review_demo

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "effective-review"
    / "expected"
    / "review-summary.json"
)


class EffectiveReviewDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_effective_review_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "prepare_binds_exact_candidate",
            "identical_replay_reuses",
            "corrected_subject_distinct_with_lineage",
            "raw_round_trip_reuses_subject",
            "same_content_different_candidate_distinct",
            "authority_changes_keep_subjects_immutable",
            "staleness_is_derived_not_stored",
            "invalid_graph_blocks_preparation",
            "no_authority_records_created",
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
