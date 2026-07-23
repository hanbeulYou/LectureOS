import unittest

from lectureos.edit_review_acceptance import run_edit_review_acceptance


class EditReviewAcceptanceTests(unittest.TestCase):
    def test_edit_pipeline_review_vertical_slice(self) -> None:
        summary = run_edit_review_acceptance()

        # the review target Candidate is never mutated
        self.assertTrue(summary["candidates_unmutated"])
        # Accept snapshots the Candidate; Modify carries the human-approved replacement
        self.assertTrue(summary["accept_snapshot_matches"])
        self.assertTrue(summary["modify_snapshot_matches"])
        # Reject records only the decision
        self.assertTrue(summary["reject_has_no_approved"])
        # ApprovedEditDecision -> ReviewDecision -> EditCandidate provenance
        self.assertTrue(summary["provenance_linked"])
        # no status field and no deferred Review Session/History tables
        self.assertTrue(summary["no_status_column"])
        self.assertTrue(summary["no_deferred_tables"])
        # durable and deterministically replayable
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])


if __name__ == "__main__":
    unittest.main()
