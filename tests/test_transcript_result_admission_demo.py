import json
import unittest
from pathlib import Path

from lectureos.transcript_result_admission_demo import (
    _golden,
    run_transcript_result_admission_demo,
)

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "transcript-result-admission"
    / "expected"
    / "admission-summary.json"
)


class TranscriptResultAdmissionDemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.summary = run_transcript_result_admission_demo()

    def test_all_behavioral_checks_pass(self) -> None:
        for key in (
            "first_admission_created",
            "replay_is_idempotent",
            "conflicting_replay_rejected",
            "malformed_timing_rejected",
            "missing_intake_rejected",
            "raw_transcript_created",
            "provider_evidence_preserved",
            "provider_evidence_distinct_from_transcript",
            "single_admission",
            "source_media_unmutated",
            "repository_validates_healthy",
        ):
            with self.subTest(check=key):
                self.assertTrue(self.summary[key], key)

    def test_identities_are_content_derived(self) -> None:
        digest = self.summary["admission_id"].split(":")[-1]
        self.assertEqual(
            self.summary["provider_transcript_result_id"],
            f"provider-transcript-result:{digest}",
        )
        self.assertEqual(
            self.summary["raw_transcript_id"], f"raw-transcript:{digest}"
        )

    def test_golden_reproduces_byte_for_byte(self) -> None:
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(_golden(self.summary), expected)

    def test_golden_file_is_canonical(self) -> None:
        # The committed golden must equal a deterministic pretty-print of itself (stable formatting).
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        rendered = json.dumps(expected, indent=2, sort_keys=True) + "\n"
        self.assertEqual(_EXPECTED.read_text(encoding="utf-8"), rendered)


if __name__ == "__main__":
    unittest.main()
