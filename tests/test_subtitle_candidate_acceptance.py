import unittest

from lectureos.subtitle_candidate_acceptance import run_subtitle_candidate_acceptance


class SubtitleCandidateAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_generates_persists_and_replays_candidate(self) -> None:
        summary = run_subtitle_candidate_acceptance()

        self.assertEqual(summary["candidate_count"], 1)
        self.assertEqual(summary["cue_count"], 2)
        # only the ELIGIBLE intake yields a candidate; the NOT_ELIGIBLE intake is refused
        self.assertTrue(summary["refused_not_eligible"])
        # each cue traces to its ordered source segment(s), revision and transcript
        self.assertTrue(summary["cue_segment_lineage"])
        self.assertTrue(summary["cue_ordering"])
        self.assertTrue(summary["cue_revision_linked"])
        # candidate carries the full intake lineage and source media/timeline
        self.assertTrue(summary["candidate_linked"])
        self.assertTrue(summary["execution_provenance"])
        self.assertTrue(summary["result_upstream_linked"])
        # generation mutates no upstream intake and reconstructs / replays deterministically
        self.assertTrue(summary["idempotent_upstream"])
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no later subtitle-revision / subtitle-cue / artifact table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
