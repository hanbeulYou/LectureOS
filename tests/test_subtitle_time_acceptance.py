import unittest

from lectureos.subtitle_time_acceptance import run_subtitle_time_acceptance


class SubtitleTimeAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_anchors_persists_and_replays_timing(self) -> None:
        summary = run_subtitle_time_acceptance()

        self.assertEqual(summary["time_revision_count"], 1)
        self.assertEqual(summary["unit_count"], 2)
        # one-to-one units anchor to their own cue range on the source timeline
        self.assertTrue(summary["all_anchored"])
        self.assertTrue(summary["one_to_one_anchored"])
        # a merged reading unit anchors the minimal enclosing source-timeline span
        self.assertTrue(summary["merged_span_anchored"])
        # an untimed basis derives UNRESOLVED
        self.assertTrue(summary["unresolved_derivation"])
        # display order preserved; each timed unit references its reading unit
        self.assertTrue(summary["unit_ordering"])
        self.assertTrue(summary["reading_unit_linked"])
        # revision carries the candidate lineage and source media/timeline
        self.assertTrue(summary["revision_linked"])
        self.assertTrue(summary["execution_provenance"])
        self.assertTrue(summary["result_upstream_linked"])
        # composition mutates no upstream reading revision and reconstructs / replays deterministically
        self.assertTrue(summary["idempotent_upstream"])
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no downstream validation / review / final / artifact table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
