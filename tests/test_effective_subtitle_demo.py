import json
import unittest
from pathlib import Path

from lectureos.effective_subtitle_demo import _golden, run_effective_subtitle_demo

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "effective-subtitle"
    / "expected"
    / "subtitle-summary.json"
)


class EffectiveSubtitleDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_effective_subtitle_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "raw_generation_passthrough",
            "identical_replay_reuses",
            "corrected_generation_distinct",
            "corrected_cue_uses_corrected_text",
            "replacement_lineage_preserved",
            "raw_round_trip_reuses_s1",
            "same_content_different_source_distinct",
            "inapplicable_blocks_generation",
            "candidates_immutable_after_authority_changes",
            "currentness_is_derived",
            "legacy_pipeline_untouched",
            "repository_validates_healthy",
        ):
            with self.subTest(check=key):
                self.assertTrue(self.summary[key], key)

    def test_golden_reproduces_byte_for_byte(self):
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(_golden(self.summary), expected)

    def test_golden_file_is_canonical(self):
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        rendered = json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self.assertEqual(_EXPECTED.read_text(encoding="utf-8"), rendered)


if __name__ == "__main__":
    unittest.main()
