import json
import unittest
from pathlib import Path

from lectureos.effective_srt_demo import _golden, run_effective_srt_demo

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "effective-srt"
    / "expected"
    / "srt-summary.json"
)


class EffectiveSrtDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_effective_srt_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "eligible_export_current_with_exact_payload",
            "exact_replay_reused",
            "superseded_selection_blocks_new_export",
            "current_selection_exports_distinct_artifact",
            "same_content_distinct_selections_distinct_artifacts",
            "invalid_graph_blocks_generation",
            "physical_isolation",
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
