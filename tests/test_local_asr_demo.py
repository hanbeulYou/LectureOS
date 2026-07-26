import json
import unittest
from pathlib import Path

from lectureos.local_asr_demo import _golden, run_local_asr_demo

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "local-asr"
    / "expected"
    / "local-asr-summary.json"
)


class LocalAsrDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_local_asr_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "first_execution_created_and_ran",
            "replay_reused_without_rerun",
            "adapter_used_source_lineage",
            "raw_transcript_created",
            "provider_evidence_distinct",
            "source_changed_rejected",
            "failure_before_admission_wrote_nothing",
            "repository_validates_healthy",
        ):
            with self.subTest(check=key):
                self.assertTrue(self.summary[key], key)

    def test_identities_are_content_derived(self):
        digest = self.summary["admission_id"].split(":")[-1]
        self.assertEqual(
            self.summary["provider_transcript_result_id"], f"provider-transcript-result:{digest}"
        )
        self.assertEqual(self.summary["raw_transcript_id"], f"raw-transcript:{digest}")

    def test_golden_reproduces_byte_for_byte(self):
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(_golden(self.summary), expected)

    def test_golden_file_is_canonical(self):
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        rendered = json.dumps(expected, indent=2, sort_keys=True) + "\n"
        self.assertEqual(_EXPECTED.read_text(encoding="utf-8"), rendered)


if __name__ == "__main__":
    unittest.main()
