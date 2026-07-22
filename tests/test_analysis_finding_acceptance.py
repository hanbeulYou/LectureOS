import unittest

from lectureos.analysis_finding_acceptance import run_analysis_finding_acceptance


class AnalysisFindingAcceptanceTests(unittest.TestCase):
    def test_pipeline_records_persists_and_replays_analysis_findings(self) -> None:
        summary = run_analysis_finding_acceptance()

        self.assertEqual(summary["finding_count"], 2)
        # every Finding anchors to exactly one ELIGIBLE Eligible Analysis Input
        self.assertTrue(summary["anchored_to_input"])
        self.assertTrue(summary["eligibility_ok"])
        # provenance + DomainResult chaining to the eligible analysis input
        self.assertTrue(summary["provenance_linked"])
        self.assertTrue(summary["sequences_ordered"])
        # recording mutates no existing canonical artifact
        self.assertTrue(summary["upstream_unmutated"])
        # reconstructs and replays deterministically
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no Segment / Segment Label / Edit Candidate / Review table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
