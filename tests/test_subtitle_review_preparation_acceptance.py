import unittest

from lectureos.subtitle_review_preparation_acceptance import (
    run_subtitle_review_preparation_acceptance,
)


class SubtitleReviewPreparationAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_prepares_persists_and_replays_review(self) -> None:
        summary = run_subtitle_review_preparation_acceptance()

        # a clean validation yields a valid empty preparation
        self.assertTrue(summary["empty_valid"])
        # a defective validation yields exactly one OPEN review item per finding
        self.assertTrue(summary["one_item_per_finding"])
        self.assertTrue(summary["items_open"])
        # each item is traced to its source finding + stable rule
        self.assertTrue(summary["finding_traced"])
        self.assertTrue(summary["candidate_reference_kind"])
        self.assertTrue(summary["result_upstream_linked"])
        # preparation mutates no upstream validation and records no decision
        self.assertTrue(summary["idempotent_upstream"])
        self.assertTrue(summary["no_decision"])
        # reconstructs and replays deterministically
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no downstream final / artifact table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
