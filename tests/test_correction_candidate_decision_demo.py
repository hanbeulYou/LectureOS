import json
import unittest
from pathlib import Path

from lectureos.correction_candidate_decision_demo import (
    _golden,
    run_correction_candidate_decision_demo,
)

_EXPECTED = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "correction-decision"
    / "expected"
    / "decision-summary.json"
)


class CorrectionCandidateDecisionDemoTests(unittest.TestCase):
    def setUp(self):
        self.summary = run_correction_candidate_decision_demo()

    def test_all_behavioral_checks_pass(self):
        for key in (
            "undecided_before_any_decision",
            "accept_recorded",
            "accepted_eligible_for_revision",
            "replay_reused",
            "reject_changed_authority",
            "re_accept_appends_history",
            "history_is_append_only",
            "current_authority_accepted",
            "modify_rejected",
            "unknown_candidate_rejected",
            "candidate_immutable",
            "raw_transcript_immutable",
            "repository_validates_healthy",
        ):
            with self.subTest(check=key):
                self.assertTrue(self.summary[key], key)

    def test_golden_reproduces_byte_for_byte(self):
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(_golden(self.summary), expected)

    def test_golden_file_is_canonical(self):
        expected = json.loads(_EXPECTED.read_text(encoding="utf-8"))
        rendered = json.dumps(expected, indent=2, sort_keys=True) + "\n"
        self.assertEqual(_EXPECTED.read_text(encoding="utf-8"), rendered)


if __name__ == "__main__":
    unittest.main()
