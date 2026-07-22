import unittest

from lectureos.subtitle_final_subtitle_acceptance import (
    run_subtitle_final_subtitle_acceptance,
)


class SubtitleFinalSubtitleAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_selects_persists_and_replays_final_subtitles(self) -> None:
        summary = run_subtitle_final_subtitle_acceptance()

        self.assertEqual(summary["final_count"], 3)
        # Accept→FINAL, Modify→FINAL (with applied text), Reject→NOT_FINAL
        self.assertTrue(summary["outcomes_correct"])
        self.assertTrue(summary["modify_applied_text"])
        self.assertTrue(summary["accept_reject_no_text"])
        # each final carries decision-revision provenance + DomainResult chaining, traced to its finding
        self.assertTrue(summary["provenance_linked"])
        self.assertTrue(summary["target_traced"])
        # selection mutates no existing canonical artifact
        self.assertTrue(summary["no_upstream_mutation"])
        # reconstructs and replays deterministically
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no downstream export / artifact table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
