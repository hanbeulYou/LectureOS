import unittest

from lectureos.readiness_acceptance import run_readiness_acceptance


class ReadinessAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_evaluates_persists_and_replays_readiness(self) -> None:
        summary = run_readiness_acceptance()
        self.assertEqual(summary["reviewer"], "fake:reviewer")
        self.assertEqual(summary["readiness_count"], 3)
        self.assertEqual(summary["outcomes"], ["ready", "not_ready", "not_ready"])
        self.assertEqual(
            summary["reason_codes"],
            ["all_conditions_met", "not_applicable", "superseded_by_modification"],
        )
        self.assertTrue(summary["deterministic_readiness"])
        self.assertTrue(summary["ready_structurally_valid"])
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["selection_linked"])
        self.assertTrue(summary["applicability_linked"])
        self.assertTrue(summary["decision_linked"])
        self.assertTrue(summary["review_item_linked"])
        self.assertTrue(summary["candidate_linked"])
        self.assertTrue(summary["revision_linked"])
        self.assertTrue(summary["validation_linked"])
        self.assertTrue(summary["execution_provenance"])
        self.assertTrue(summary["idempotent_upstream"])
        self.assertTrue(summary["no_downstream_tables"])
        self.assertTrue(summary["deterministic_replay"])


if __name__ == "__main__":
    unittest.main()
