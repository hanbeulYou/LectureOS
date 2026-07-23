import unittest

from lectureos.edit_candidate_generation_acceptance import (
    run_edit_candidate_generation_acceptance,
)


class EditCandidateGenerationAcceptanceTests(unittest.TestCase):
    def test_first_slice_generation_to_admission_vertical_flow(self) -> None:
        summary = run_edit_candidate_generation_acceptance()

        # partial-success outcome: two valid proposals admitted, one invalid surfaced
        self.assertTrue(summary["partial_success"])
        self.assertEqual(summary["admitted_count"], 2)
        self.assertTrue(summary["rejected_surfaced"])
        # bounded provider context, only registry keys offered
        self.assertTrue(summary["bounded_context"])
        self.assertTrue(summary["registry_offered"])
        # existing admission produces canonical Candidates anchored to the Finding
        self.assertTrue(summary["anchored_to_finding"])
        self.assertTrue(summary["provenance_linked"])
        self.assertTrue(summary["ranges_within_context"])
        self.assertTrue(summary["types_from_registry"])
        # no upstream mutation, no Review artifacts, no provider metadata persisted
        self.assertTrue(summary["upstream_unmutated"])
        self.assertTrue(summary["no_review_tables"])
        self.assertTrue(summary["no_provider_columns"])
        # durable and deterministically replayable through the fake Port
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])


if __name__ == "__main__":
    unittest.main()
