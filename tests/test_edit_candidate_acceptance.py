import unittest

from lectureos.edit_candidate_acceptance import run_edit_candidate_acceptance


class EditCandidateAcceptanceTests(unittest.TestCase):
    def test_pipeline_records_persists_and_replays_edit_candidates(self) -> None:
        summary = run_edit_candidate_acceptance()

        self.assertEqual(summary["candidate_count"], 2)
        # every Candidate anchors to exactly one canonical Analysis Finding
        self.assertTrue(summary["anchored_to_finding"])
        self.assertTrue(summary["finding_is_canonical"])
        # provenance + DomainResult chaining directly to the Finding's Domain Result
        self.assertTrue(summary["provenance_linked"])
        # required Candidate Type + rationale + single range present
        self.assertTrue(summary["payload_present"])
        # the Candidate carries a required range even though the anchoring Finding had none
        self.assertTrue(summary["finding_had_no_range"])
        self.assertTrue(summary["sequences_ordered"])
        # recording mutates no existing canonical artifact
        self.assertTrue(summary["upstream_unmutated"])
        # reconstructs and replays deterministically
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no Segment Label / Review / Approved-Edit-Decision table and no Segment row is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
