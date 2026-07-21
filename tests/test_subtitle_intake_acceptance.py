import unittest

from lectureos.subtitle_intake_acceptance import run_subtitle_intake_acceptance


class SubtitleIntakeAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_evaluates_persists_and_replays_intake(self) -> None:
        summary = run_subtitle_intake_acceptance()
        self.assertEqual(summary["reviewer"], "fake:reviewer")
        self.assertEqual(summary["intake_count"], 2)
        self.assertEqual(summary["outcomes"], ["eligible", "not_eligible"])
        self.assertTrue(summary["deterministic_intake"])
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["readiness_linked"])
        self.assertTrue(summary["revision_linked"])
        self.assertTrue(summary["transcript_linked"])
        self.assertTrue(summary["media_timeline_linked"])
        self.assertTrue(summary["candidate_linked"])
        self.assertTrue(summary["review_item_linked"])
        self.assertTrue(summary["execution_provenance"])
        self.assertTrue(summary["idempotent_upstream"])
        self.assertTrue(summary["no_downstream_tables"])
        self.assertTrue(summary["deterministic_replay"])


if __name__ == "__main__":
    unittest.main()
