"""Record-level contracts of the Review authority history (043 §7.6, GOAL-029).

Pure model, identity, and append-rule behaviour: no repository, no schema, no service.
"""

import hashlib
import json
import unittest

from lectureos.application.identities import (
    LectureAnalysisEditCandidateId,
    LectureReviewAuthorityPositionId,
    LectureReviewDecisionId,
)
from lectureos.application.lecture_review_authority import (
    AUTHORITY_POSITION_CONTRACT_KIND,
    AUTHORITY_POSITION_CONTRACT_VERSION,
    AuthorityPositionOutcome,
    CandidateAuthorityStatus,
    LectureReviewAuthorityError,
    LectureReviewAuthorityPosition,
    derive_authority_position_identity,
    plan_authority_position,
    require_authority_actor,
    require_canonical_authority_position_id,
    require_sequence,
)
from lectureos.review.identities import HumanActorReference

_CANDIDATE = LectureAnalysisEditCandidateId(
    "lecture-analysis-edit-candidate:" + "a" * 64
)
_OTHER_CANDIDATE = LectureAnalysisEditCandidateId(
    "lecture-analysis-edit-candidate:" + "b" * 64
)
_ACTOR = HumanActorReference("reviewer:lee")
_OTHER_ACTOR = HumanActorReference("reviewer:park")
_ACCEPT = LectureReviewDecisionId("lecture-review-decision:" + "c" * 64)
_REJECT = LectureReviewDecisionId("lecture-review-decision:" + "d" * 64)


def _position(sequence=0, candidate=_CANDIDATE, actor=_ACTOR, decision=_ACCEPT,
              previous=None):
    if sequence > 0 and previous is None:
        previous = derive_authority_position_identity(candidate, actor, sequence - 1)
    return LectureReviewAuthorityPosition(
        identity=derive_authority_position_identity(candidate, actor, sequence),
        candidate_id=candidate,
        actor=actor,
        sequence=sequence,
        review_decision_id=decision,
        previous_position_id=previous,
    )


class ScopeFieldTests(unittest.TestCase):
    def test_a_non_empty_actor_is_stored_verbatim(self):
        self.assertEqual(require_authority_actor(" reviewer:lee ").value,
                         " reviewer:lee ")

    def test_empty_blank_or_non_string_actors_are_refused(self):
        for value in ("", "   ", None, 7, HumanActorReference):
            with self.subTest(value=value):
                with self.assertRaises(LectureReviewAuthorityError):
                    require_authority_actor(value)

    def test_sequence_must_be_a_non_negative_integer(self):
        for value in (0, 1, 12):
            with self.subTest(value=value):
                self.assertEqual(require_sequence(value), value)
        for value in (-1, 1.0, "0", True, False, None):
            with self.subTest(value=value):
                with self.assertRaises(LectureReviewAuthorityError):
                    require_sequence(value)


class PositionIdentityTests(unittest.TestCase):
    def test_identity_is_deterministic_and_prefixed(self):
        first = derive_authority_position_identity(_CANDIDATE, _ACTOR, 0)
        self.assertEqual(first, derive_authority_position_identity(_CANDIDATE, _ACTOR, 0))
        self.assertTrue(
            first.value.startswith("lecture-review-authority-position:")
        )
        self.assertEqual(len(first.value.split(":", 1)[1]), 64)

    def test_the_candidate_the_actor_and_the_position_all_participate(self):
        base = derive_authority_position_identity(_CANDIDATE, _ACTOR, 0)
        self.assertNotEqual(
            base, derive_authority_position_identity(_OTHER_CANDIDATE, _ACTOR, 0)
        )
        self.assertNotEqual(
            base, derive_authority_position_identity(_CANDIDATE, _OTHER_ACTOR, 0)
        )
        self.assertNotEqual(
            base, derive_authority_position_identity(_CANDIDATE, _ACTOR, 1)
        )

    def test_the_referenced_decision_and_previous_link_do_not_participate(self):
        """AH-11 Option A: the recorded facts stay out, so a competing append collides."""

        accepted = _position(decision=_ACCEPT)
        rejected = _position(decision=_REJECT)
        self.assertEqual(accepted.identity, rejected.identity)
        self.assertNotEqual(accepted.review_decision_id, rejected.review_decision_id)

    def test_identity_re_derives_from_the_recorded_contract_and_scope(self):
        expected = hashlib.sha256(
            json.dumps(
                {
                    "contract": AUTHORITY_POSITION_CONTRACT_KIND,
                    "contract_version": AUTHORITY_POSITION_CONTRACT_VERSION,
                    "candidate": _CANDIDATE.value,
                    "actor": _ACTOR.value,
                    "sequence": 3,
                },
                ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(
            derive_authority_position_identity(_CANDIDATE, _ACTOR, 3).value,
            f"lecture-review-authority-position:{expected}",
        )

    def test_no_wall_clock_uuid_or_rowid_can_reach_the_identity(self):
        """AH-11: the derivation is a pure function of the scope and the position."""

        repeated = {
            derive_authority_position_identity(_CANDIDATE, _ACTOR, 2).value
            for _ in range(5)
        }
        self.assertEqual(len(repeated), 1)

    def test_malformed_identities_are_refused(self):
        for value in (
            "nope",
            "lecture-review-authority-position:",
            "lecture-review-authority-position:" + "a" * 63,
            "lecture-review-authority-position:" + "a" * 65,
            "lecture-review-decision:" + "a" * 64,
            None,
        ):
            with self.subTest(value=value):
                with self.assertRaises(LectureReviewAuthorityError):
                    require_canonical_authority_position_id(value)

    def test_a_canonical_identity_round_trips(self):
        identity = derive_authority_position_identity(_CANDIDATE, _ACTOR, 1)
        self.assertEqual(
            require_canonical_authority_position_id(identity.value), identity
        )

    def test_the_prefix_never_collides_with_the_records_it_references(self):
        identity = derive_authority_position_identity(_CANDIDATE, _ACTOR, 0).value
        self.assertFalse(identity.startswith("lecture-review-decision:"))
        self.assertFalse(identity.startswith("lecture-approved-edit-decision:"))


class PositionModelTests(unittest.TestCase):
    def test_a_canonical_first_position_is_constructed_and_frozen(self):
        position = _position()
        self.assertEqual(position.sequence, 0)
        self.assertIsNone(position.previous_position_id)
        self.assertEqual(position.review_decision_id, _ACCEPT)
        self.assertEqual(
            position.position_contract_version, AUTHORITY_POSITION_CONTRACT_VERSION
        )
        with self.assertRaises(Exception):
            position.sequence = 4

    def test_sequence_zero_carries_no_previous_and_later_positions_require_one(self):
        with self.assertRaises(LectureReviewAuthorityError):
            LectureReviewAuthorityPosition(
                identity=derive_authority_position_identity(_CANDIDATE, _ACTOR, 0),
                candidate_id=_CANDIDATE,
                actor=_ACTOR,
                sequence=0,
                review_decision_id=_ACCEPT,
                previous_position_id=derive_authority_position_identity(
                    _CANDIDATE, _ACTOR, 1
                ),
            )
        with self.assertRaises(LectureReviewAuthorityError):
            LectureReviewAuthorityPosition(
                identity=derive_authority_position_identity(_CANDIDATE, _ACTOR, 1),
                candidate_id=_CANDIDATE,
                actor=_ACTOR,
                sequence=1,
                review_decision_id=_ACCEPT,
            )

    def test_a_position_never_supersedes_itself(self):
        identity = derive_authority_position_identity(_CANDIDATE, _ACTOR, 1)
        with self.assertRaises(LectureReviewAuthorityError):
            LectureReviewAuthorityPosition(
                identity=identity,
                candidate_id=_CANDIDATE,
                actor=_ACTOR,
                sequence=1,
                review_decision_id=_ACCEPT,
                previous_position_id=identity,
            )

    def test_a_tampered_identity_is_refused(self):
        with self.assertRaises(LectureReviewAuthorityError):
            LectureReviewAuthorityPosition(
                identity=LectureReviewAuthorityPositionId(
                    "lecture-review-authority-position:" + "f" * 64
                ),
                candidate_id=_CANDIDATE,
                actor=_ACTOR,
                sequence=0,
                review_decision_id=_ACCEPT,
            )

    def test_swapping_any_scope_field_breaks_re_derivation(self):
        identity = derive_authority_position_identity(_CANDIDATE, _ACTOR, 0)
        for candidate, actor in ((_OTHER_CANDIDATE, _ACTOR), (_CANDIDATE, _OTHER_ACTOR)):
            with self.subTest(candidate=candidate.value, actor=actor.value):
                with self.assertRaises(LectureReviewAuthorityError):
                    LectureReviewAuthorityPosition(
                        identity=identity,
                        candidate_id=candidate,
                        actor=actor,
                        sequence=0,
                        review_decision_id=_ACCEPT,
                    )

    def test_a_plain_string_actor_is_refused_by_the_model(self):
        with self.assertRaises(LectureReviewAuthorityError):
            LectureReviewAuthorityPosition(
                identity=derive_authority_position_identity(_CANDIDATE, _ACTOR, 0),
                candidate_id=_CANDIDATE,
                actor="reviewer:lee",
                sequence=0,
                review_decision_id=_ACCEPT,
            )

    def test_an_empty_actor_never_reaches_the_model(self):
        """The released reference type refuses it first; the model re-checks regardless."""

        with self.assertRaises(ValueError):
            HumanActorReference("")
        self.assertIn(
            "require_authority_actor",
            LectureReviewAuthorityPosition.__post_init__.__code__.co_names,
        )

    def test_a_negative_sequence_is_refused(self):
        with self.assertRaises(LectureReviewAuthorityError):
            LectureReviewAuthorityPosition(
                identity=derive_authority_position_identity(_CANDIDATE, _ACTOR, -1),
                candidate_id=_CANDIDATE,
                actor=_ACTOR,
                sequence=-1,
                review_decision_id=_ACCEPT,
            )

    def test_an_unsupported_contract_version_is_refused(self):
        with self.assertRaises(LectureReviewAuthorityError):
            LectureReviewAuthorityPosition(
                identity=derive_authority_position_identity(_CANDIDATE, _ACTOR, 0),
                candidate_id=_CANDIDATE,
                actor=_ACTOR,
                sequence=0,
                review_decision_id=_ACCEPT,
                position_contract_version=AUTHORITY_POSITION_CONTRACT_VERSION + 1,
            )

    def test_the_record_duplicates_no_referenced_payload_and_carries_no_status(self):
        """AH-5: kind, approved values, currentness, wall clock, and execution stay out."""

        fields = set(LectureReviewAuthorityPosition.__slots__)
        self.assertEqual(
            fields,
            {
                "identity", "candidate_id", "actor", "sequence", "review_decision_id",
                "previous_position_id", "position_contract_version",
            },
        )
        for forbidden in (
            "decision_kind", "approved_range_start", "approved_range_end",
            "approved_label", "approved_rationale", "status", "current", "is_current",
            "stale", "selected", "created_at", "timestamp", "domain_result_id",
            "processing_run_id", "unit_execution_id", "rowid",
        ):
            with self.subTest(field=forbidden):
                self.assertNotIn(forbidden, fields)


class AppendRuleTests(unittest.TestCase):
    def test_no_history_starts_at_sequence_zero(self):
        plan = plan_authority_position(
            candidate_id=_CANDIDATE, actor=_ACTOR, decision_id=_ACCEPT, head=None
        )
        self.assertIs(plan.outcome, AuthorityPositionOutcome.RECORDED)
        self.assertTrue(plan.appends)
        self.assertEqual(plan.position.sequence, 0)
        self.assertIsNone(plan.position.previous_position_id)
        self.assertEqual(plan.position.review_decision_id, _ACCEPT)

    def test_the_head_recording_this_judgment_is_reused_and_writes_nothing(self):
        head = _position(decision=_ACCEPT)
        plan = plan_authority_position(
            candidate_id=_CANDIDATE, actor=_ACTOR, decision_id=_ACCEPT, head=head
        )
        self.assertIs(plan.outcome, AuthorityPositionOutcome.REUSED)
        self.assertFalse(plan.appends)
        self.assertIs(plan.position, head)

    def test_a_different_judgment_appends_and_supersedes_the_head(self):
        head = _position(decision=_ACCEPT)
        plan = plan_authority_position(
            candidate_id=_CANDIDATE, actor=_ACTOR, decision_id=_REJECT, head=head
        )
        self.assertIs(plan.outcome, AuthorityPositionOutcome.RECORDED)
        self.assertEqual(plan.position.sequence, 1)
        self.assertEqual(plan.position.previous_position_id, head.identity)
        self.assertEqual(plan.position.review_decision_id, _REJECT)

    def test_a_reversal_lets_one_decision_occupy_several_positions(self):
        """AH-6: `accept` → `reject` → `accept` is two decisions across three positions."""

        first = plan_authority_position(
            candidate_id=_CANDIDATE, actor=_ACTOR, decision_id=_ACCEPT, head=None
        ).position
        second = plan_authority_position(
            candidate_id=_CANDIDATE, actor=_ACTOR, decision_id=_REJECT, head=first
        ).position
        third = plan_authority_position(
            candidate_id=_CANDIDATE, actor=_ACTOR, decision_id=_ACCEPT, head=second
        ).position
        self.assertEqual(
            [position.sequence for position in (first, second, third)], [0, 1, 2]
        )
        self.assertEqual(first.review_decision_id, third.review_decision_id)
        self.assertNotEqual(first.identity, third.identity)
        self.assertEqual(third.previous_position_id, second.identity)
        self.assertEqual(len({first.identity, second.identity, third.identity}), 3)

    def test_the_next_position_derives_only_from_the_supplied_head(self):
        """AH-7: never a row count, wall clock, insertion order, or rowid."""

        head = _position(sequence=7, decision=_ACCEPT)
        plan = plan_authority_position(
            candidate_id=_CANDIDATE, actor=_ACTOR, decision_id=_REJECT, head=head
        )
        self.assertEqual(plan.position.sequence, 8)
        self.assertEqual(
            plan.position,
            plan_authority_position(
                candidate_id=_CANDIDATE, actor=_ACTOR, decision_id=_REJECT, head=head
            ).position,
        )

    def test_each_actor_plans_inside_its_own_scope(self):
        head = _position(actor=_OTHER_ACTOR, decision=_REJECT)
        plan = plan_authority_position(
            candidate_id=_CANDIDATE, actor=_ACTOR, decision_id=_ACCEPT, head=None
        )
        other = plan_authority_position(
            candidate_id=_CANDIDATE, actor=_OTHER_ACTOR, decision_id=_ACCEPT, head=head
        )
        self.assertEqual(plan.position.sequence, 0)
        self.assertEqual(other.position.sequence, 1)
        self.assertNotEqual(plan.position.identity, other.position.identity)


class VocabularyTests(unittest.TestCase):
    def test_the_position_outcome_vocabulary_is_closed(self):
        self.assertEqual(
            {member.value for member in AuthorityPositionOutcome},
            {"recorded", "reused"},
        )

    def test_the_candidate_observation_vocabulary_is_closed(self):
        """AH-9 defines three observations and no automatic authority ranking."""

        self.assertEqual(
            {member.value for member in CandidateAuthorityStatus},
            {"no_history", "single_actor", "cross_actor_conflict"},
        )
        for forbidden in ("resolved", "winner", "priority", "latest", "ranked"):
            with self.subTest(value=forbidden):
                self.assertNotIn(
                    forbidden, {member.value for member in CandidateAuthorityStatus}
                )


if __name__ == "__main__":
    unittest.main()
