import unittest

from lectureos.current_selection_acceptance import run_current_selection_acceptance


class CurrentSelectionAcceptanceTests(unittest.TestCase):
    def test_fake_review_derives_persists_and_replays_current_selection(self) -> None:
        summary = run_current_selection_acceptance()
        self.assertEqual(summary["reviewer"], "fake:reviewer")
        self.assertEqual(summary["selection_count"], 3)
        self.assertEqual(
            summary["outcomes"], ["selected", "not_selected", "not_selected"]
        )
        self.assertTrue(summary["deterministic_selection"])
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["applicability_linked"])
        self.assertTrue(summary["review_item_linked"])
        self.assertTrue(summary["candidate_linked"])
        self.assertTrue(summary["revision_linked"])
        self.assertTrue(summary["execution_provenance"])
        self.assertTrue(summary["deterministic_replay"])


if __name__ == "__main__":
    unittest.main()
