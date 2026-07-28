import json
import unittest
from pathlib import Path

from lectureos.effective_publish_demo import (
    _golden,
    run_effective_publish_demo,
)

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "effective-publish"
    / "expected"
    / "publish-summary.json"
)


class EffectivePublishDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_effective_publish_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "publish_records_current_available",
            "exact_replay_reused",
            "same_target_other_actor_converges",
            "replacement_publish_supersedes",
            "withdraw_appends_and_deletes_nothing",
            "republish_after_withdraw_appends",
            "filesystem_never_mutates_authority",
            "historical_artifact_delivery_publishable",
            "failed_delivery_not_publishable",
            "concurrent_identical_publish_converges",
            "divergent_concurrent_command_conflicts",
            "publication_isolation",
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
