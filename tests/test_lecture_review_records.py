"""Record-level contracts of effective-generation Review records (043 §7.5, GOAL-028).

Pure model and identity behaviour: no repository, no schema, no service.
"""

import unittest

from lectureos.application.identities import (
    LectureAnalysisEditCandidateId,
    LectureApprovedEditDecisionId,
    LectureReviewDecisionId,
)
from lectureos.application.lecture_review_decision import (
    APPROVED_EDIT_DECISION_CONTRACT_VERSION,
    REVIEW_DECISION_CONTRACT_VERSION,
    LectureApprovedEditDecision,
    LectureReviewDecision,
    LectureReviewError,
    ReviewDecisionKind,
    derive_approved_edit_decision_identity,
    derive_review_decision_identity,
    normalize_approved_range,
    require_approved_label,
    require_approved_rationale,
    require_canonical_approved_edit_decision_id,
    require_canonical_review_decision_id,
    require_decision_kind,
    require_human_actor,
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


def _decision(kind=ReviewDecisionKind.ACCEPT, candidate=_CANDIDATE, actor=_ACTOR):
    return LectureReviewDecision(
        identity=derive_review_decision_identity(candidate, kind, actor),
        candidate_id=candidate,
        decision_kind=kind,
        actor=actor,
    )


def _approved(decision=None, kind=ReviewDecisionKind.ACCEPT, start=0.0, end=1.0,
              label="non_lecture_region", rationale="승인한다"):
    decision = decision or _decision(kind)
    return LectureApprovedEditDecision(
        identity=derive_approved_edit_decision_identity(
            decision.identity, decision.candidate_id, kind, start, end, label, rationale
        ),
        review_decision_id=decision.identity,
        candidate_id=decision.candidate_id,
        approved_decision_kind=kind,
        approved_range_start=start,
        approved_range_end=end,
        approved_label=label,
        approved_rationale=rationale,
    )


class DecisionKindTests(unittest.TestCase):
    def test_the_closed_set_is_exactly_accept_reject_modify(self):
        self.assertEqual(
            {kind.value for kind in ReviewDecisionKind},
            {"accept", "reject", "modify"},
        )

    def test_the_vocabulary_never_drifts_from_the_released_legacy_generation(self):
        """`§7.4`'s closed set is inherited unchanged (R-8), so the two must stay identical.

        Asserted by value rather than by importing the legacy module, which would create a
        source-level dependency on its execution boundary.
        """

        from lectureos.application.edit_review import EditReviewDecisionKind

        self.assertEqual(
            {kind.value for kind in ReviewDecisionKind},
            {kind.value for kind in EditReviewDecisionKind},
        )

    def test_canonical_tokens_are_admitted(self):
        for token in ("accept", "reject", "modify"):
            with self.subTest(token=token):
                self.assertEqual(require_decision_kind(token).value, token)

    def test_enum_members_pass_through(self):
        self.assertIs(
            require_decision_kind(ReviewDecisionKind.MODIFY), ReviewDecisionKind.MODIFY
        )

    def test_unknown_values_are_refused_never_coerced(self):
        for bad in ("Accept", "ACCEPT", " accept", "accept ", "approve", "approved",
                    "acc", "", None, 0, 1, True, ["accept"], "accept\n"):
            with self.subTest(bad=bad):
                with self.assertRaises(LectureReviewError):
                    require_decision_kind(bad)


class HumanActorTests(unittest.TestCase):
    def test_a_non_empty_reference_is_stored_verbatim(self):
        self.assertEqual(require_human_actor("  reviewer:lee ").value, "  reviewer:lee ")

    def test_empty_or_blank_or_non_string_is_refused(self):
        for bad in ("", "   ", "\t\n", None, 7, HumanActorReference("x")):
            with self.subTest(bad=bad):
                with self.assertRaises(LectureReviewError):
                    require_human_actor(bad)


class ApprovedFieldTests(unittest.TestCase):
    def test_label_follows_the_released_open_application_key_rule(self):
        for token in ("trim_intro", "a", "non_lecture_region", "x9_y0"):
            with self.subTest(token=token):
                self.assertEqual(require_approved_label(token), token)

    def test_label_is_not_a_closed_enum(self):
        self.assertEqual(require_approved_label("some_label_no_registry_knows"),
                         "some_label_no_registry_knows")

    def test_malformed_labels_are_refused(self):
        for bad in ("Trim", "trim intro", "_trim", "9trim", "trim-intro", "", None, 3,
                    "trim\n", "TRIM_INTRO"):
            with self.subTest(bad=bad):
                with self.assertRaises(LectureReviewError):
                    require_approved_label(bad)

    def test_rationale_is_required_and_stored_verbatim(self):
        self.assertEqual(require_approved_rationale("  이유 "), "  이유 ")
        for bad in ("", "   ", None, 5):
            with self.subTest(bad=bad):
                with self.assertRaises(LectureReviewError):
                    require_approved_rationale(bad)


class ApprovedRangeTests(unittest.TestCase):
    def test_canonical_range_is_admitted(self):
        self.assertEqual(normalize_approved_range(0.0, 1.5), (0.0, 1.5))

    def test_zero_duration_is_structurally_valid(self):
        self.assertEqual(normalize_approved_range(2.0, 2.0), (2.0, 2.0))

    def test_integral_and_negative_zero_spellings_are_canonicalized(self):
        self.assertEqual(normalize_approved_range(0, 1), (0.0, 1.0))
        self.assertEqual(normalize_approved_range(-0.0, 1.0), (0.0, 1.0))
        start, _ = normalize_approved_range(-0.0, 1.0)
        self.assertEqual(str(start), "0.0")

    def test_invalid_ranges_are_refused(self):
        for start, end in ((1.0, 0.0), (-1.0, 1.0), (0.0, -1.0),
                           (float("nan"), 1.0), (0.0, float("inf")),
                           (0.0, float("-inf")), ("0", 1.0), (None, 1.0),
                           (True, 1.0), (0.0, 10**400)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(LectureReviewError):
                    normalize_approved_range(start, end)


class ReviewDecisionIdentityTests(unittest.TestCase):
    def test_identity_is_deterministic_and_prefixed(self):
        first = derive_review_decision_identity(
            _CANDIDATE, ReviewDecisionKind.ACCEPT, _ACTOR
        )
        second = derive_review_decision_identity(
            _CANDIDATE, ReviewDecisionKind.ACCEPT, _ACTOR
        )
        self.assertEqual(first, second)
        self.assertTrue(first.value.startswith("lecture-review-decision:"))
        self.assertEqual(len(first.value), len("lecture-review-decision:") + 64)

    def test_the_human_actor_participates_in_identity(self):
        """R-10: without it, two people's identical-kind judgments would not be distinct."""

        self.assertNotEqual(
            derive_review_decision_identity(_CANDIDATE, ReviewDecisionKind.ACCEPT, _ACTOR),
            derive_review_decision_identity(
                _CANDIDATE, ReviewDecisionKind.ACCEPT, _OTHER_ACTOR
            ),
        )

    def test_the_candidate_and_the_kind_participate_in_identity(self):
        base = derive_review_decision_identity(
            _CANDIDATE, ReviewDecisionKind.ACCEPT, _ACTOR
        )
        self.assertNotEqual(
            base,
            derive_review_decision_identity(
                _OTHER_CANDIDATE, ReviewDecisionKind.ACCEPT, _ACTOR
            ),
        )
        for kind in (ReviewDecisionKind.REJECT, ReviewDecisionKind.MODIFY):
            with self.subTest(kind=kind):
                self.assertNotEqual(
                    base, derive_review_decision_identity(_CANDIDATE, kind, _ACTOR)
                )

    def test_identity_is_a_hash_and_not_caller_owned(self):
        """R-10: `§7.4`'s caller-owned identity is legacy-only."""

        digest = derive_review_decision_identity(
            _CANDIDATE, ReviewDecisionKind.ACCEPT, _ACTOR
        ).value.split(":", 1)[1]
        self.assertTrue(all(character in "0123456789abcdef" for character in digest))

    def test_malformed_identities_are_refused(self):
        for bad in ("", "lecture-review-decision:", "lecture-review-decision:short",
                    "review-decision:" + "a" * 64, "lecture-review-decision:" + "a" * 63,
                    "lecture-review-decision:" + "a" * 65, None, 3):
            with self.subTest(bad=bad):
                with self.assertRaises(LectureReviewError):
                    require_canonical_review_decision_id(bad)

    def test_a_canonical_identity_round_trips(self):
        value = derive_review_decision_identity(
            _CANDIDATE, ReviewDecisionKind.ACCEPT, _ACTOR
        ).value
        self.assertEqual(require_canonical_review_decision_id(value).value, value)


class ApprovedEditDecisionIdentityTests(unittest.TestCase):
    def test_every_owned_snapshot_field_participates(self):
        decision = _decision(ReviewDecisionKind.MODIFY)
        base = derive_approved_edit_decision_identity(
            decision.identity, decision.candidate_id, ReviewDecisionKind.MODIFY,
            0.0, 1.0, "trim_intro", "이유",
        )
        variants = (
            (0.5, 1.0, "trim_intro", "이유"),
            (0.0, 2.0, "trim_intro", "이유"),
            (0.0, 1.0, "other_label", "이유"),
            (0.0, 1.0, "trim_intro", "다른 이유"),
        )
        for start, end, label, rationale in variants:
            with self.subTest(label=label, rationale=rationale, start=start, end=end):
                self.assertNotEqual(
                    base,
                    derive_approved_edit_decision_identity(
                        decision.identity, decision.candidate_id,
                        ReviewDecisionKind.MODIFY, start, end, label, rationale,
                    ),
                )

    def test_the_originating_decision_participates(self):
        accept = _decision(ReviewDecisionKind.ACCEPT)
        modify = _decision(ReviewDecisionKind.MODIFY)
        self.assertNotEqual(
            derive_approved_edit_decision_identity(
                accept.identity, _CANDIDATE, ReviewDecisionKind.ACCEPT,
                0.0, 1.0, "x_label", "이유",
            ),
            derive_approved_edit_decision_identity(
                modify.identity, _CANDIDATE, ReviewDecisionKind.ACCEPT,
                0.0, 1.0, "x_label", "이유",
            ),
        )

    def test_integral_and_negative_zero_bounds_produce_one_identity(self):
        decision = _decision(ReviewDecisionKind.MODIFY)
        canonical = derive_approved_edit_decision_identity(
            decision.identity, _CANDIDATE, ReviewDecisionKind.MODIFY,
            0.0, 1.0, "trim_intro", "이유",
        )
        for start, end in ((0, 1), (-0.0, 1.0), (-0.0, 1)):
            with self.subTest(start=start, end=end):
                self.assertEqual(
                    canonical,
                    derive_approved_edit_decision_identity(
                        decision.identity, _CANDIDATE, ReviewDecisionKind.MODIFY,
                        start, end, "trim_intro", "이유",
                    ),
                )

    def test_malformed_identities_are_refused(self):
        for bad in ("", "lecture-approved-edit-decision:", "approved:" + "a" * 64,
                    "lecture-approved-edit-decision:" + "a" * 63, None):
            with self.subTest(bad=bad):
                with self.assertRaises(LectureReviewError):
                    require_canonical_approved_edit_decision_id(bad)


class ReviewDecisionModelTests(unittest.TestCase):
    def test_a_canonical_decision_is_constructed_and_frozen(self):
        decision = _decision()
        self.assertEqual(decision.candidate_id, _CANDIDATE)
        self.assertIs(decision.decision_kind, ReviewDecisionKind.ACCEPT)
        self.assertEqual(decision.actor, _ACTOR)
        self.assertEqual(
            decision.review_contract_version, REVIEW_DECISION_CONTRACT_VERSION
        )
        with self.assertRaises(Exception):
            decision.decision_kind = ReviewDecisionKind.REJECT

    def test_a_tampered_identity_is_refused(self):
        with self.assertRaises(LectureReviewError):
            LectureReviewDecision(
                identity=LectureReviewDecisionId("lecture-review-decision:" + "0" * 64),
                candidate_id=_CANDIDATE,
                decision_kind=ReviewDecisionKind.ACCEPT,
                actor=_ACTOR,
            )

    def test_swapping_any_canonical_field_breaks_re_derivation(self):
        decision = _decision()
        for overrides in (
            {"candidate_id": _OTHER_CANDIDATE},
            {"decision_kind": ReviewDecisionKind.REJECT},
            {"actor": _OTHER_ACTOR},
        ):
            with self.subTest(overrides=tuple(overrides)):
                payload = {
                    "identity": decision.identity,
                    "candidate_id": decision.candidate_id,
                    "decision_kind": decision.decision_kind,
                    "actor": decision.actor,
                }
                payload.update(overrides)
                with self.assertRaises(LectureReviewError):
                    LectureReviewDecision(**payload)

    def test_an_unsupported_contract_version_is_refused(self):
        for version in (0, 2, -1, None):
            with self.subTest(version=version):
                with self.assertRaises(LectureReviewError):
                    LectureReviewDecision(
                        identity=derive_review_decision_identity(
                            _CANDIDATE, ReviewDecisionKind.ACCEPT, _ACTOR
                        ),
                        candidate_id=_CANDIDATE,
                        decision_kind=ReviewDecisionKind.ACCEPT,
                        actor=_ACTOR,
                        review_contract_version=version,
                    )

    def test_a_plain_string_actor_is_refused_by_the_model(self):
        with self.assertRaises(LectureReviewError):
            LectureReviewDecision(
                identity=derive_review_decision_identity(
                    _CANDIDATE, ReviewDecisionKind.ACCEPT, _ACTOR
                ),
                candidate_id=_CANDIDATE,
                decision_kind=ReviewDecisionKind.ACCEPT,
                actor="reviewer:lee",
            )

    def test_the_record_carries_no_forbidden_field(self):
        """R-4, R-6, R-7, R-9 and `§7.4`'s "does not have" list, asserted structurally."""

        decision = _decision()
        for forbidden in (
            "sequence", "ordinal", "previous_decision_id", "status", "state",
            "current", "stale", "selected", "domain_result_id", "processing_run_id",
            "unit_execution_id", "execution_id", "note", "decision_note",
            "modification", "modify_payload", "approved_range_start", "approved_label",
            "review_session_id", "review_history_id", "review_item_id",
            "source_media_id", "source_timeline_id", "created_at", "timestamp",
        ):
            with self.subTest(field=forbidden):
                self.assertFalse(hasattr(decision, forbidden))

    def test_approval_creation_is_derived_from_the_kind_alone(self):
        self.assertTrue(_decision(ReviewDecisionKind.ACCEPT).creates_approved_edit_decision)
        self.assertTrue(_decision(ReviewDecisionKind.MODIFY).creates_approved_edit_decision)
        self.assertFalse(_decision(ReviewDecisionKind.REJECT).creates_approved_edit_decision)


class ApprovedEditDecisionModelTests(unittest.TestCase):
    def test_a_canonical_approved_record_is_constructed(self):
        approved = _approved()
        self.assertIs(approved.approved_decision_kind, ReviewDecisionKind.ACCEPT)
        self.assertEqual(approved.approved_range_start, 0.0)
        self.assertEqual(approved.approved_range_end, 1.0)
        self.assertEqual(
            approved.approved_contract_version, APPROVED_EDIT_DECISION_CONTRACT_VERSION
        )

    def test_reject_can_never_own_an_approved_record(self):
        decision = _decision(ReviewDecisionKind.REJECT)
        with self.assertRaises(LectureReviewError):
            LectureApprovedEditDecision(
                identity=derive_approved_edit_decision_identity(
                    decision.identity, _CANDIDATE, ReviewDecisionKind.ACCEPT,
                    0.0, 1.0, "x_label", "이유",
                ),
                review_decision_id=decision.identity,
                candidate_id=_CANDIDATE,
                approved_decision_kind=ReviewDecisionKind.REJECT,
                approved_range_start=0.0,
                approved_range_end=1.0,
                approved_label="x_label",
                approved_rationale="이유",
            )

    def test_a_tampered_identity_is_refused(self):
        decision = _decision()
        with self.assertRaises(LectureReviewError):
            LectureApprovedEditDecision(
                identity=LectureApprovedEditDecisionId(
                    "lecture-approved-edit-decision:" + "0" * 64
                ),
                review_decision_id=decision.identity,
                candidate_id=_CANDIDATE,
                approved_decision_kind=ReviewDecisionKind.ACCEPT,
                approved_range_start=0.0,
                approved_range_end=1.0,
                approved_label="x_label",
                approved_rationale="이유",
            )

    def test_bounds_are_canonicalized_on_construction(self):
        decision = _decision(ReviewDecisionKind.MODIFY)
        approved = LectureApprovedEditDecision(
            identity=derive_approved_edit_decision_identity(
                decision.identity, _CANDIDATE, ReviewDecisionKind.MODIFY,
                -0.0, 1, "trim_intro", "이유",
            ),
            review_decision_id=decision.identity,
            candidate_id=_CANDIDATE,
            approved_decision_kind=ReviewDecisionKind.MODIFY,
            approved_range_start=-0.0,
            approved_range_end=1,
            approved_label="trim_intro",
            approved_rationale="이유",
        )
        self.assertEqual(str(approved.approved_range_start), "0.0")
        self.assertIsInstance(approved.approved_range_end, float)

    def test_an_unsupported_contract_version_is_refused(self):
        decision = _decision()
        with self.assertRaises(LectureReviewError):
            LectureApprovedEditDecision(
                identity=derive_approved_edit_decision_identity(
                    decision.identity, _CANDIDATE, ReviewDecisionKind.ACCEPT,
                    0.0, 1.0, "x_label", "이유",
                ),
                review_decision_id=decision.identity,
                candidate_id=_CANDIDATE,
                approved_decision_kind=ReviewDecisionKind.ACCEPT,
                approved_range_start=0.0,
                approved_range_end=1.0,
                approved_label="x_label",
                approved_rationale="이유",
                approved_contract_version=2,
            )

    def test_the_record_carries_no_executable_edit_or_execution_field(self):
        approved = _approved()
        for forbidden in (
            "sequence", "ordinal", "status", "current", "selected",
            "domain_result_id", "processing_run_id", "unit_execution_id",
            "cut", "operation", "nle_operation", "rendered", "export_format",
            "artifact_path", "applied", "source_media_id", "source_timeline_id",
            "created_at",
        ):
            with self.subTest(field=forbidden):
                self.assertFalse(hasattr(approved, forbidden))


if __name__ == "__main__":
    unittest.main()
