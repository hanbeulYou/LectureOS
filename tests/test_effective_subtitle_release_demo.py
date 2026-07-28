import json
import unittest
from pathlib import Path

from lectureos.effective_subtitle_release_demo import (
    _golden,
    run_effective_subtitle_release_demo,
)

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "effective-subtitle-v1"
    / "expected"
    / "release-summary.json"
)
_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "effective-subtitle-v1"
    / "release-manifest.json"
)


class EffectiveSubtitleReleaseDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_effective_subtitle_release_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "every_stage_requires_explicit_command",
            "typed_lineage_connects_every_stage",
            "exact_bytes_end_to_end",
            "exactly_one_record_per_stage",
            "no_legacy_rows_written",
            "repository_validates_healthy",
        ):
            with self.subTest(check=key):
                self.assertTrue(self.summary[key], key)

    def test_golden_reproduces_byte_for_byte(self):
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(_golden(self.summary), expected)

    def test_golden_file_is_canonical_and_free_of_machine_paths(self):
        text = _EXPECTED.read_text(encoding="utf-8")
        expected = json.loads(text)
        rendered = json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self.assertEqual(text, rendered)
        for fragment in ("/tmp", "/var", "/Users", "/home", "C:\\"):
            self.assertNotIn(fragment, text)

    def test_release_manifest_is_deterministic_and_consistent(self):
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["release"], self.summary["release"])
        self.assertEqual(
            manifest["schema_range"]["latest_version"], self.summary["schema_version"]
        )
        self.assertEqual(len(manifest["included_goals"]), 8)
        self.assertEqual(len(manifest["stages"]), 8)
        for stage in manifest["stages"]:
            completion = Path(_MANIFEST).resolve().parents[2] / stage["completion_document"]
            self.assertTrue(completion.is_file(), stage["completion_document"])
        text = _MANIFEST.read_text(encoding="utf-8")
        for fragment in ("/tmp", "/var", "/Users", "/home", "C:\\", "http://", "https://"):
            self.assertNotIn(fragment, text)


if __name__ == "__main__":
    unittest.main()
