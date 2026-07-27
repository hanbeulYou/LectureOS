import json
import unittest
from pathlib import Path

from lectureos.effective_deliver_demo import (
    _golden,
    run_effective_deliver_demo,
)

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "effective-deliver"
    / "expected"
    / "deliver-summary.json"
)


class EffectiveDeliverDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_effective_deliver_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "first_delivery_exact_verified_bytes",
            "replay_reuses_without_rewrite",
            "identical_destination_truthful_success",
            "different_destination_refuses_without_overwrite",
            "explicit_overwrite_replaces_as_new_attempt",
            "deleted_destination_never_mutates_history",
            "missing_source_blocks_pre_intent",
            "tampered_source_blocks_pre_intent",
            "historical_superseded_artifact_deliverable",
            "escaping_destination_refused",
            "reconcile_matching_appends_delivered",
            "reconcile_missing_or_differing_honest_failed",
            "concurrent_identical_requests_converge",
            "no_legacy_or_publication_rows",
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
