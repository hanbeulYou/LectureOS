"""Human Authority over a Timing Correction Candidate (040 §18, PATCH-0047 TC-10/TC-11).

Pins that `§18`'s released semantics carry over unchanged, that rejection is a first-class normal
outcome introducing no new state, and that the released text decision path is unaffected.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.correction_candidate_decision import (
    DecisionOutcome,
    HumanDecisionStatus,
)
from lectureos.application.timing_correction_candidate_admission import (
    build_timing_correction_candidate_input,
)
from lectureos.application.timing_correction_candidate_decision import (
    TimingCorrectionDecisionError,
)
from lectureos.composition import (
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_timing_correction_candidate_admission_service,
    compose_sqlite_timing_correction_decision_service,
)
from lectureos.review.models import DecisionKind

# `tests/` is not a package, so a single-module invocation does not put it on sys.path the way
# discovery does; this keeps both `unittest discover` and `unittest tests.<module>` working.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from timing_correction_fixture import temporary_fixture

_DECISION_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "lectureos"
    / "application"
    / "timing_correction_candidate_decision.py"
)


class TimingCorrectionDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory, self.fixture = temporary_fixture()
        self.addCleanup(self._directory.cleanup)
        self.addCleanup(self.fixture.close)
        self.admissions = compose_sqlite_timing_correction_candidate_admission_service(
            self.fixture.connection
        )
        self.decisions = compose_sqlite_timing_correction_decision_service(
            self.fixture.connection
        )
        self.candidate = self.admissions.admit(
            intake_id=self.fixture.intake_id,
            candidate=build_timing_correction_candidate_input(self.fixture.proposal()),
        ).candidate

    def _decide(self, kind: str, reviewer: str = "reviewer:kim", **kwargs):
        return self.decisions.decide(
            candidate_id=self.candidate.identity.value,
            kind=kind,
            reviewer=reviewer,
            **kwargs,
        )

    # -- the three released states ------------------------------------------------------------

    def test_undecided_is_derived_from_absence(self) -> None:
        authority = self.decisions.authority(self.candidate.identity.value)
        self.assertIs(authority.status, HumanDecisionStatus.UNDECIDED)
        self.assertEqual(authority.decision_count, 0)
        self.assertFalse(authority.eligible_for_revision)
        self.assertIsNone(authority.current_decision_id)

    def test_accept_is_recorded_and_makes_the_candidate_eligible(self) -> None:
        result = self._decide("accept")
        self.assertIs(result.outcome, DecisionOutcome.RECORDED)
        self.assertIs(result.decision.kind, DecisionKind.ACCEPT)
        authority = self.decisions.authority(self.candidate.identity.value)
        self.assertIs(authority.status, HumanDecisionStatus.ACCEPTED)
        self.assertTrue(authority.eligible_for_revision)

    def test_reject_is_a_normal_first_class_outcome(self) -> None:
        # TC-11: "the source timing is correct" is a complete judgement, not an error or a
        # second-class result — it records cleanly and never becomes eligible.
        result = self._decide("reject", rationale="원래 타이밍이 맞다")
        self.assertIs(result.outcome, DecisionOutcome.RECORDED)
        authority = self.decisions.authority(self.candidate.identity.value)
        self.assertIs(authority.status, HumanDecisionStatus.REJECTED)
        self.assertFalse(authority.eligible_for_revision)
        self.assertEqual(authority.decision_count, 1)

    def test_no_state_beyond_the_released_three_exists(self) -> None:
        self.assertEqual(
            {status.value for status in HumanDecisionStatus},
            {"undecided", "accepted", "rejected"},
        )
        source = _DECISION_SOURCE.read_text(encoding="utf-8")
        for forbidden in ("ignored", "dismissed", "false_positive", "acknowledged", "auto_accept"):
            self.assertNotIn(f'"{forbidden}"', source)
            self.assertNotIn(f"'{forbidden}'", source)

    def test_modify_is_still_deferred(self) -> None:
        with self.assertRaises(TimingCorrectionDecisionError):
            self._decide("modify")

    def test_unknown_kind_is_rejected(self) -> None:
        with self.assertRaises(TimingCorrectionDecisionError):
            self._decide("maybe")

    def test_blank_reviewer_is_rejected(self) -> None:
        with self.assertRaises(TimingCorrectionDecisionError):
            self._decide("accept", reviewer="   ")

    def test_unknown_candidate_is_rejected(self) -> None:
        with self.assertRaises(TimingCorrectionDecisionError):
            self.decisions.decide(
                candidate_id=f"timing-correction-candidate:{'0' * 64}",
                kind="accept",
                reviewer="reviewer:kim",
            )

    def test_text_candidate_identity_is_not_accepted_here(self) -> None:
        text = compose_sqlite_correction_candidate_admission_service(
            self.fixture.connection
        ).admit(
            intake_id=self.fixture.intake_id,
            candidate=build_correction_candidate_input(
                {
                    "raw_transcript_id": self.fixture.raw_transcript_id,
                    "segment_id": self.fixture.target.identity.value,
                    "candidate_ref": "c1",
                    "source_type": "manual",
                    "source_reference": "human:editor-1",
                    "proposed_text": "둘째 문장!",
                    "source_text_snapshot": self.fixture.target.text,
                    "rationale": "구두점",
                }
            ),
        ).candidate
        with self.assertRaises(TimingCorrectionDecisionError):
            self.decisions.decide(
                candidate_id=text.identity.value, kind="accept", reviewer="reviewer:kim"
            )

    # -- append-only supersession (H-5, H-6, H-8) ---------------------------------------------

    def test_replay_of_the_current_kind_is_idempotent(self) -> None:
        first = self._decide("accept")
        replay = self._decide("accept", reviewer="reviewer:lee")
        self.assertIs(replay.outcome, DecisionOutcome.REUSED)
        self.assertEqual(replay.decision.identity, first.decision.identity)
        self.assertEqual(len(self.decisions.history(self.candidate.identity.value)), 1)

    def test_changing_authority_appends_and_preserves_history(self) -> None:
        first = self._decide("accept")
        changed = self._decide("reject")
        self.assertIs(changed.outcome, DecisionOutcome.CHANGED)
        self.assertEqual(changed.decision.sequence, 1)
        self.assertEqual(changed.decision.previous_decision_id, first.decision.identity)
        history = self.decisions.history(self.candidate.identity.value)
        self.assertEqual([d.kind for d in history], [DecisionKind.ACCEPT, DecisionKind.REJECT])
        self.assertEqual(history[0].identity, first.decision.identity)

    def test_history_is_insert_only(self) -> None:
        self._decide("accept")
        self._decide("reject")
        self._decide("accept")
        rows = self.fixture.connection.execute(
            "SELECT sequence, kind FROM timing_correction_candidate_decisions "
            "WHERE timing_correction_candidate_id = ? ORDER BY sequence",
            (self.candidate.identity.value,),
        ).fetchall()
        self.assertEqual(rows, [(0, "accept"), (1, "reject"), (2, "accept")])

    def test_identity_is_deterministic_from_candidate_kind_and_sequence(self) -> None:
        from lectureos.application.timing_correction_candidate_decision import (
            derive_timing_decision_identity,
        )

        decision = self._decide("accept").decision
        self.assertEqual(
            decision.identity,
            derive_timing_decision_identity(
                self.candidate.identity, DecisionKind.ACCEPT, 0
            ),
        )

    def test_timing_and_text_decision_identities_cannot_collide(self) -> None:
        from lectureos.application.correction_candidate_decision import (
            derive_decision_identity,
        )
        from lectureos.application.timing_correction_candidate_decision import (
            derive_timing_decision_identity,
        )
        from lectureos.transcript.identities import CorrectionCandidateId

        digest = self.candidate.identity.value.split(":", 1)[1]
        timing = derive_timing_decision_identity(
            self.candidate.identity, DecisionKind.ACCEPT, 0
        )
        text = derive_decision_identity(
            CorrectionCandidateId(f"correction-candidate:{digest}"), DecisionKind.ACCEPT, 0
        )
        self.assertNotEqual(timing.value, text.value)

    def test_decisions_are_stored_in_their_own_relation(self) -> None:
        self._decide("accept")
        self.assertEqual(
            self.fixture.connection.execute(
                "SELECT COUNT(*) FROM correction_candidate_decisions"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.fixture.connection.execute(
                "SELECT COUNT(*) FROM timing_correction_candidate_decisions"
            ).fetchone()[0],
            1,
        )

    def test_released_value_types_are_reused_rather_than_redefined(self) -> None:
        """TC-10: no new authority vocabulary — the released types are imported, not re-declared."""

        tree = ast.parse(_DECISION_SOURCE.read_text(encoding="utf-8"))
        declared = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        }
        self.assertNotIn("DecisionKind", declared)
        self.assertNotIn("HumanActorReference", declared)
        self.assertNotIn("HumanDecisionStatus", declared)

    # -- the released text decision path is untouched ------------------------------------------

    def test_released_text_decision_still_works(self) -> None:
        text = compose_sqlite_correction_candidate_admission_service(
            self.fixture.connection
        ).admit(
            intake_id=self.fixture.intake_id,
            candidate=build_correction_candidate_input(
                {
                    "raw_transcript_id": self.fixture.raw_transcript_id,
                    "segment_id": self.fixture.target.identity.value,
                    "candidate_ref": "c1",
                    "source_type": "manual",
                    "source_reference": "human:editor-1",
                    "proposed_text": "둘째 문장!",
                    "source_text_snapshot": self.fixture.target.text,
                    "rationale": "구두점",
                }
            ),
        ).candidate
        service = compose_sqlite_correction_candidate_decision_service(
            self.fixture.connection
        )
        result = service.decide(
            candidate_id=text.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        self.assertIs(result.outcome, DecisionOutcome.RECORDED)
        self.assertIs(
            service.authority(text.identity.value).status, HumanDecisionStatus.ACCEPTED
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
