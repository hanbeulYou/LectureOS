import unittest

from lectureos.applicability_acceptance import run_applicability_acceptance


class ApplicabilityAcceptanceTests(unittest.TestCase):
    def test_fake_review_derives_persists_and_replays_applicability(self) -> None:
        summary = run_applicability_acceptance()
        self.assertEqual(summary["reviewer"], "fake:reviewer")
        self.assertEqual(summary["evaluation_count"], 3)
        self.assertEqual(
            summary["outcomes"],
            ["applicable", "not_applicable", "superseded_by_modification"],
        )
        self.assertTrue(summary["deterministic_evaluation"])
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["decision_linked"])
        self.assertTrue(summary["review_item_linked"])
        self.assertTrue(summary["candidate_linked"])
        self.assertTrue(summary["revision_linked"])
        self.assertTrue(summary["execution_provenance"])
        self.assertTrue(summary["deterministic_replay"])


if __name__ == "__main__":
    unittest.main()
