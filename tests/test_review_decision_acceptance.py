import unittest

from lectureos.review_decision_acceptance import run_review_decision_acceptance


class ReviewDecisionAcceptanceTests(unittest.TestCase):
    def test_fake_review_records_reconstructs_and_replays_decisions(self) -> None:
        summary = run_review_decision_acceptance()
        self.assertEqual(summary["reviewer"], "fake:reviewer")
        self.assertEqual(summary["decision_count"], 3)
        self.assertEqual(summary["kinds"], ["accept", "modify", "reject"])
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["review_item_linked"])
        self.assertTrue(summary["candidate_linked"])
        self.assertTrue(summary["revision_linked"])
        self.assertTrue(summary["reviewer_provenance"])
        self.assertTrue(summary["execution_provenance"])
        self.assertTrue(summary["append_only_lineage"])
        self.assertTrue(summary["deterministic_replay"])


if __name__ == "__main__":
    unittest.main()
