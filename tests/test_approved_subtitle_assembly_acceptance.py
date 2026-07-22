import unittest

from lectureos.subtitle_approved_assembly_acceptance import (
    run_subtitle_approved_assembly_acceptance,
)


class ApprovedSubtitleAssemblyAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_assembles_persists_and_replays_documents(self) -> None:
        summary = run_subtitle_approved_assembly_acceptance()

        self.assertEqual(summary["document_count"], 3)
        # Modify->applied_text (included), Reject->omitted
        self.assertTrue(summary["a_modified"])
        # Accept->original text, Untouched->original text
        self.assertTrue(summary["b_accept_untouched"])
        # an included unit with unresolved timing -> INELIGIBLE, no units
        self.assertTrue(summary["c_ineligible"])
        # order comes from the canonical timed units
        self.assertTrue(summary["ordering_preserved"])
        # provenance + DomainResult chaining to the time revision
        self.assertTrue(summary["provenance_linked"])
        # assembly mutates no existing canonical artifact
        self.assertTrue(summary["no_upstream_mutation"])
        # reconstructs and replays deterministically
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no downstream artifact / export table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
