import unittest

from lectureos.lecture_analysis_input_acceptance import (
    run_lecture_analysis_input_acceptance,
)


class LectureAnalysisInputAcceptanceTests(unittest.TestCase):
    def test_fake_pipeline_records_persists_and_replays_analysis_inputs(self) -> None:
        summary = run_lecture_analysis_input_acceptance()

        self.assertEqual(summary["input_count"], 2)
        # READY -> ELIGIBLE, NOT_READY -> NOT_ELIGIBLE
        self.assertTrue(summary["eligibility_correct"])
        # provenance + DomainResult chaining to the readiness evaluation
        self.assertTrue(summary["provenance_linked"])
        self.assertTrue(summary["lineage_linked"])
        # recording mutates no existing canonical artifact
        self.assertTrue(summary["no_upstream_mutation"])
        # reconstructs and replays deterministically
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no analysis / Finding / Segment / Candidate table is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
