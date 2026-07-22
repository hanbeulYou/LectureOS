import unittest

from lectureos.subtitle_reading_acceptance import run_subtitle_reading_acceptance


class SubtitleReadingAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_composes_persists_and_replays_reading(self) -> None:
        summary = run_subtitle_reading_acceptance()

        self.assertEqual(summary["reading_revision_count"], 1)
        self.assertEqual(summary["unit_count"], 2)
        # deterministic, meaning-preserving normalization (not a pure copy) into ordered units
        self.assertTrue(summary["normalized_lines"])
        self.assertTrue(summary["source_cue_lineage"])
        self.assertTrue(summary["unit_ordering"])
        # timing is inherited metadata only — nothing computed or inferred
        self.assertTrue(summary["timing_inherited"])
        # revision carries the full candidate lineage and source media/timeline
        self.assertTrue(summary["revision_linked"])
        self.assertTrue(summary["execution_provenance"])
        self.assertTrue(summary["result_upstream_linked"])
        # composition mutates no upstream candidate and reconstructs / replays deterministically
        self.assertTrue(summary["idempotent_upstream"])
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no downstream time / validation / review / final / artifact table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
