import json
import unittest
from pathlib import Path

from lectureos.effective_materialize_demo import (
    _golden,
    run_effective_materialize_demo,
)

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "effective-materialize"
    / "expected"
    / "materialize-summary.json"
)


class EffectiveMaterializeDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_effective_materialize_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "first_write_exact_canonical_bytes",
            "replay_reuses_without_rewrite",
            "different_file_refuses_without_overwrite",
            "explicit_overwrite_replaces_as_new_event",
            "deleted_file_never_mutates_records",
            "historical_artifact_still_materializable",
            "escaping_path_refused",
            "no_legacy_materialization_rows",
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
