import unittest

from lectureos.lecture_segment_acceptance import run_lecture_segment_acceptance


class LectureSegmentAcceptanceTests(unittest.TestCase):
    def test_pipeline_records_persists_and_replays_lecture_segments(self) -> None:
        summary = run_lecture_segment_acceptance()

        self.assertEqual(summary["segment_count"], 2)
        # every Segment anchors to exactly one ELIGIBLE Eligible Analysis Input
        self.assertTrue(summary["anchored_to_input"])
        self.assertTrue(summary["eligibility_ok"])
        # provenance + DomainResult chaining to the eligible analysis input
        self.assertTrue(summary["provenance_linked"])
        # each Segment carries a required single Source Timeline Time Range
        self.assertTrue(summary["ranges_present"])
        self.assertTrue(summary["sequences_ordered"])
        # recording mutates no existing canonical artifact
        self.assertTrue(summary["upstream_unmutated"])
        # reconstructs and replays deterministically
        self.assertTrue(summary["restart_reconstructed"])
        self.assertTrue(summary["deterministic_replay"])
        # no Label / Candidate / Review table and no Analysis Finding row is produced
        self.assertTrue(summary["no_downstream_tables"])


if __name__ == "__main__":
    unittest.main()
