import unittest

from lectureos.subtitle_srt_artifact_acceptance import (
    run_subtitle_srt_artifact_acceptance,
)


class SrtArtifactAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_generates_persists_and_replays_artifact(self) -> None:
        summary = run_subtitle_srt_artifact_acceptance()

        # exact serialized SRT payload from the eligible approved document
        self.assertTrue(summary["payload_exact"])
        self.assertTrue(summary["metadata_correct"])
        # ineligible document yields no artifact
        self.assertTrue(summary["ineligible_rejected"])
        # provenance + DomainResult chaining to the approved document
        self.assertTrue(summary["provenance_linked"])
        # generation mutates no existing canonical artifact
        self.assertTrue(summary["no_upstream_mutation"])
        # reconstructs (payload byte-equal) and replays deterministically
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no physical-file / materialization / delivery table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
