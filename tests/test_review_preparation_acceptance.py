import unittest

from lectureos.review_preparation_acceptance import run_review_preparation_acceptance


class ReviewPreparationAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_prepares_and_reconstructs_review(self) -> None:
        summary = run_review_preparation_acceptance()
        self.assertEqual(summary["provider"], "fake:transcript.correction")
        self.assertEqual(summary["proposal_count"], 2)
        self.assertEqual(summary["review_item_count"], 2)
        self.assertEqual(summary["group_count"], 2)
        self.assertTrue(summary["deterministic"])
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["structural_valid"])
        self.assertTrue(summary["provenance_complete"])
        self.assertTrue(summary["ordering_valid"])
        self.assertTrue(summary["lineage_immutable"])
        self.assertTrue(summary["parent_revision_linked"])
        self.assertTrue(summary["candidates_linked"])
        self.assertTrue(summary["execution_provenance"])


if __name__ == "__main__":
    unittest.main()
