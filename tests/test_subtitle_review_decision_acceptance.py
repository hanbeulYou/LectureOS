import unittest

from lectureos.subtitle_review_decision_acceptance import (
    run_subtitle_review_decision_acceptance,
)


class SubtitleReviewDecisionAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_records_persists_and_replays_decisions(self) -> None:
        summary = run_subtitle_review_decision_acceptance()

        self.assertEqual(summary["decision_count"], 3)
        # Accept, Reject, and an append-only Modify are recorded
        self.assertTrue(summary["kinds_recorded"])
        self.assertTrue(summary["append_only"])
        # each decision carries subtitle provenance + DomainResult chaining, traced to its finding
        self.assertTrue(summary["provenance_linked"])
        self.assertTrue(summary["finding_traced"])
        # recording mutates no upstream preparation/items and applies nothing (items stay OPEN)
        self.assertTrue(summary["idempotent_upstream"])
        self.assertTrue(summary["items_still_open"])
        # reconstructs and replays deterministically
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no downstream final / artifact table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
