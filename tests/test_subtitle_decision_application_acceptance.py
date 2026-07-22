import unittest

from lectureos.subtitle_decision_application_acceptance import (
    run_subtitle_decision_application_acceptance,
)


class SubtitleDecisionApplicationAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_applies_persists_and_replays_revisions(self) -> None:
        summary = run_subtitle_decision_application_acceptance()

        self.assertEqual(summary["revision_count"], 3)
        # Accept→ACCEPTED, Reject→REJECTED, Modify→MODIFIED with the applied text
        self.assertTrue(summary["outcomes_correct"])
        self.assertTrue(summary["modify_applied_text"])
        self.assertTrue(summary["accept_reject_no_text"])
        # each revision carries subtitle provenance + DomainResult chaining, traced to its finding/rule
        self.assertTrue(summary["provenance_linked"])
        self.assertTrue(summary["target_traced"])
        # application mutates no existing canonical artifact
        self.assertTrue(summary["no_upstream_mutation"])
        # reconstructs and replays deterministically
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no downstream final / artifact table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
