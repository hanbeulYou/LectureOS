import unittest

from lectureos.subtitle_srt_materialization_acceptance import (
    run_subtitle_srt_materialization_acceptance,
)


class SrtMaterializationAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_materializes_reconciles_and_replays(self) -> None:
        summary = run_subtitle_srt_materialization_acceptance()

        # a real file is written with the exact artifact payload bytes
        self.assertTrue(summary["exact_bytes"])
        self.assertTrue(summary["materialized"])
        # provenance + DomainResult chaining to the artifact
        self.assertTrue(summary["provenance_linked"])
        # generation mutates no existing canonical artifact; the Artifact carries no materialization status
        self.assertTrue(summary["no_upstream_mutation"])
        self.assertTrue(summary["no_materialization_status"])
        # rematerialization is a new act with a new identity; idempotent repeat returns the same record
        self.assertTrue(summary["rematerialized"])
        self.assertTrue(summary["idempotent"])
        # different bytes -> FAILED, never overwritten
        self.assertTrue(summary["collision_failed"])
        # a durable PENDING with no file reconciles deterministically to MATERIALIZED
        self.assertTrue(summary["reconciled"])
        # reconstructs after restart and replays deterministically
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no Delivery / URL table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
