import json
import unittest
from pathlib import Path

from lectureos.media_import_demo import _golden, run_media_import_demo

_GOLDEN = (
    Path(__file__).resolve().parent.parent
    / "examples"
    / "media-import"
    / "expected"
    / "import-summary.json"
)


class MediaImportDemoTests(unittest.TestCase):
    def test_demo_behavioral_checks_all_true(self) -> None:
        summary = run_media_import_demo()
        for key, value in summary.items():
            if isinstance(value, bool):
                with self.subTest(check=key):
                    self.assertTrue(value, f"demo check failed: {key}")

    def test_demo_is_deterministic(self) -> None:
        self.assertEqual(
            _golden(run_media_import_demo()), _golden(run_media_import_demo())
        )

    def test_demo_matches_golden_fixture(self) -> None:
        produced = json.dumps(_golden(run_media_import_demo()), indent=2, sort_keys=True) + "\n"
        self.assertEqual(
            produced,
            _GOLDEN.read_text(encoding="utf-8"),
            "media import demo golden drifted; regenerate only after an intentional, reviewed change",
        )

    def test_identical_fixtures_share_identity(self) -> None:
        summary = run_media_import_demo()
        # sample-a and sample-a-copy are byte-identical -> same content identity, and only 4 distinct records.
        self.assertTrue(summary["same_content_other_name_reused"])
        self.assertEqual(summary["distinct_media_records"], 4)


if __name__ == "__main__":
    unittest.main()
