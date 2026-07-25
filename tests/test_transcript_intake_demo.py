import json
import unittest
from pathlib import Path

from lectureos.transcript_intake_demo import _golden, run_transcript_intake_demo

_GOLDEN = (
    Path(__file__).resolve().parent.parent
    / "examples"
    / "transcript-intake"
    / "expected"
    / "intake-summary.json"
)


class TranscriptIntakeDemoTests(unittest.TestCase):
    def test_demo_behavioral_checks_all_true(self) -> None:
        summary = run_transcript_intake_demo()
        for key, value in summary.items():
            if isinstance(value, bool):
                with self.subTest(check=key):
                    self.assertTrue(value, f"demo check failed: {key}")

    def test_demo_is_deterministic(self) -> None:
        self.assertEqual(
            _golden(run_transcript_intake_demo()), _golden(run_transcript_intake_demo())
        )

    def test_demo_matches_golden_fixture(self) -> None:
        produced = (
            json.dumps(_golden(run_transcript_intake_demo()), indent=2, sort_keys=True) + "\n"
        )
        self.assertEqual(
            produced,
            _GOLDEN.read_text(encoding="utf-8"),
            "transcript intake demo golden drifted; regenerate only after an intentional, reviewed change",
        )

    def test_intake_identity_is_derived_from_media(self) -> None:
        summary = run_transcript_intake_demo()
        self.assertEqual(
            summary["sample_a_intake_id"],
            "transcript-source-intake:" + summary["sample_a_media_id"],
        )
        self.assertEqual(summary["distinct_intakes"], 2)
        self.assertTrue(summary["no_transcript_content_created"])


if __name__ == "__main__":
    unittest.main()
