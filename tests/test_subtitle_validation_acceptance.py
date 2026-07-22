import unittest

from lectureos.subtitle_validation_acceptance import run_subtitle_validation_acceptance


class SubtitleValidationAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_diagnoses_persists_and_replays_validation(self) -> None:
        summary = run_subtitle_validation_acceptance()

        # a clean pipeline time revision is structurally valid with no findings
        self.assertTrue(summary["clean_valid"])
        # defective time revisions produce ordering / overlap / unresolved findings, invalid
        self.assertTrue(summary["defective_findings"])
        # findings carry stable rule identifiers independent of their descriptions
        self.assertTrue(summary["stable_rules"])
        # lineage carried; result upstream = time revision DomainResult
        self.assertTrue(summary["lineage_linked"])
        self.assertTrue(summary["result_upstream_linked"])
        # validation mutates no upstream time revision and reconstructs / replays deterministically
        self.assertTrue(summary["idempotent_upstream"])
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no downstream review / final / artifact table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
