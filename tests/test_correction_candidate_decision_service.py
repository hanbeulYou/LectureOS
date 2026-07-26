"""Domain and application tests for the first Human Authority Decision (040 §18)."""

import unittest

from lectureos.application.correction_candidate_decision import (
    CorrectionCandidateDecision,
    CorrectionCandidateDecisionConflictError,
    CorrectionCandidateDecisionError,
    CorrectionCandidateDecisionService,
    HumanDecisionStatus,
    derive_decision_identity,
    require_canonical_correction_candidate_id,
    require_decision_kind,
)
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.review.identities import HumanActorReference
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import CorrectionCandidateId

_CAND = "correction-candidate:" + "1" * 64
_CAND2 = "correction-candidate:" + "2" * 64


class _FakeAdmissionQuery:
    def __init__(self, admitted=(_CAND,)):
        self._admitted = set(admitted)

    def is_admitted_candidate(self, candidate_id):
        return candidate_id.value in self._admitted


class _FakeDecisionStore:
    def __init__(self):
        self.by_identity = {}
        self.by_candidate = {}

    def get(self, identity):
        return self.by_identity.get(identity.value)

    def get_current(self, candidate_id):
        rows = self.by_candidate.get(candidate_id.value)
        return max(rows, key=lambda d: d.sequence) if rows else None

    def history(self, candidate_id):
        rows = self.by_candidate.get(candidate_id.value, [])
        return tuple(sorted(rows, key=lambda d: d.sequence))

    def persist_decision(self, *, decision):
        if decision.identity.value in self.by_identity:
            raise PersistenceIdentityCollisionError("identity exists")
        rows = self.by_candidate.setdefault(decision.correction_candidate_id.value, [])
        if any(r.sequence == decision.sequence for r in rows):
            raise PersistenceIdentityCollisionError("sequence exists")
        self.by_identity[decision.identity.value] = decision
        rows.append(decision)


def _service(*, admitted=(_CAND,), store=None):
    store = store if store is not None else _FakeDecisionStore()
    return CorrectionCandidateDecisionService(_FakeAdmissionQuery(admitted), store, store), store


class HelperTests(unittest.TestCase):
    def test_candidate_id_validation(self):
        self.assertEqual(require_canonical_correction_candidate_id(_CAND).value, _CAND)
        for bad in ("nope", "correction-candidate:xyz", "correction-candidate:" + "1" * 63, "raw-transcript:x"):
            with self.assertRaises(CorrectionCandidateDecisionError):
                require_canonical_correction_candidate_id(bad)

    def test_kind_validation(self):
        self.assertIs(require_decision_kind("accept"), DecisionKind.ACCEPT)
        self.assertIs(require_decision_kind("reject"), DecisionKind.REJECT)
        for bad in ("modify", "approve", ""):
            with self.assertRaises(CorrectionCandidateDecisionError):
                require_decision_kind(bad)

    def test_identity_is_deterministic_and_sequence_sensitive(self):
        cid = CorrectionCandidateId(_CAND)
        self.assertEqual(
            derive_decision_identity(cid, DecisionKind.ACCEPT, 0),
            derive_decision_identity(cid, DecisionKind.ACCEPT, 0),
        )
        self.assertNotEqual(
            derive_decision_identity(cid, DecisionKind.ACCEPT, 0),
            derive_decision_identity(cid, DecisionKind.REJECT, 0),
        )
        self.assertNotEqual(
            derive_decision_identity(cid, DecisionKind.ACCEPT, 0),
            derive_decision_identity(cid, DecisionKind.ACCEPT, 1),
        )

    def test_decision_record_rejects_modify_and_bad_derivation(self):
        cid = CorrectionCandidateId(_CAND)
        with self.assertRaises(ValueError):
            CorrectionCandidateDecision(
                identity=derive_decision_identity(cid, DecisionKind.ACCEPT, 0),
                correction_candidate_id=cid, kind=DecisionKind.MODIFY,
                reviewer=HumanActorReference("r"), sequence=0, content_fingerprint="0" * 64,
            )
        with self.assertRaises(ValueError):
            CorrectionCandidateDecision(
                identity=derive_decision_identity(cid, DecisionKind.ACCEPT, 5),
                correction_candidate_id=cid, kind=DecisionKind.ACCEPT,
                reviewer=HumanActorReference("r"), sequence=0, content_fingerprint="0" * 64,
            )


class DecisionMatrixTests(unittest.TestCase):
    def test_none_accept_inserts(self):
        service, store = _service()
        result = service.decide(candidate_id=_CAND, kind="accept", reviewer="r:kim")
        self.assertEqual(result.outcome.value, "recorded")
        self.assertEqual(result.decision.sequence, 0)
        self.assertIsNone(result.decision.previous_decision_id)
        self.assertEqual(len(store.by_identity), 1)

    def test_none_reject_inserts(self):
        service, _ = _service()
        result = service.decide(candidate_id=_CAND, kind="reject", reviewer="r:kim")
        self.assertEqual(result.outcome.value, "recorded")
        self.assertEqual(service.authority(_CAND).status, HumanDecisionStatus.REJECTED)

    def test_accept_accept_reuses(self):
        service, store = _service()
        service.decide(candidate_id=_CAND, kind="accept", reviewer="r:kim")
        again = service.decide(candidate_id=_CAND, kind="accept", reviewer="r:lee")
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(len(store.by_identity), 1)

    def test_reject_reject_reuses(self):
        service, store = _service()
        service.decide(candidate_id=_CAND, kind="reject", reviewer="r:kim")
        again = service.decide(candidate_id=_CAND, kind="reject", reviewer="r:lee")
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(len(store.by_identity), 1)

    def test_accept_reject_appends(self):
        service, store = _service()
        service.decide(candidate_id=_CAND, kind="accept", reviewer="r:kim")
        changed = service.decide(candidate_id=_CAND, kind="reject", reviewer="r:kim")
        self.assertEqual(changed.outcome.value, "changed")
        self.assertEqual(changed.decision.sequence, 1)
        self.assertEqual(changed.previous.kind, DecisionKind.ACCEPT)
        self.assertEqual(len(store.by_identity), 2)
        self.assertEqual(service.authority(_CAND).status, HumanDecisionStatus.REJECTED)

    def test_reject_accept_appends(self):
        service, _ = _service()
        service.decide(candidate_id=_CAND, kind="reject", reviewer="r:kim")
        changed = service.decide(candidate_id=_CAND, kind="accept", reviewer="r:kim")
        self.assertEqual(changed.outcome.value, "changed")
        self.assertEqual(service.authority(_CAND).status, HumanDecisionStatus.ACCEPTED)

    def test_full_evolution_preserves_history(self):
        service, _ = _service()
        service.decide(candidate_id=_CAND, kind="accept", reviewer="r")
        service.decide(candidate_id=_CAND, kind="reject", reviewer="r")
        service.decide(candidate_id=_CAND, kind="accept", reviewer="r")
        history = service.history(_CAND)
        self.assertEqual([d.kind.value for d in history], ["accept", "reject", "accept"])
        self.assertEqual([d.sequence for d in history], [0, 1, 2])


class AuthorityTests(unittest.TestCase):
    def test_undecided_by_absence(self):
        service, _ = _service()
        authority = service.authority(_CAND)
        self.assertEqual(authority.status, HumanDecisionStatus.UNDECIDED)
        self.assertEqual(authority.decision_count, 0)
        self.assertIsNone(authority.current_decision_id)
        self.assertFalse(authority.eligible_for_revision)

    def test_accepted_is_eligible_rejected_is_not(self):
        service, _ = _service()
        service.decide(candidate_id=_CAND, kind="accept", reviewer="r")
        self.assertTrue(service.authority(_CAND).eligible_for_revision)
        service.decide(candidate_id=_CAND, kind="reject", reviewer="r")
        self.assertFalse(service.authority(_CAND).eligible_for_revision)


class RejectionTests(unittest.TestCase):
    def test_unknown_candidate_rejected(self):
        service, store = _service(admitted=())
        with self.assertRaises(CorrectionCandidateDecisionError):
            service.decide(candidate_id=_CAND, kind="accept", reviewer="r")
        self.assertEqual(len(store.by_identity), 0)

    def test_malformed_candidate_rejected(self):
        service, _ = _service()
        with self.assertRaises(CorrectionCandidateDecisionError):
            service.decide(candidate_id="nope", kind="accept", reviewer="r")

    def test_modify_rejected(self):
        service, _ = _service()
        with self.assertRaises(CorrectionCandidateDecisionError):
            service.decide(candidate_id=_CAND, kind="modify", reviewer="r")

    def test_blank_reviewer_rejected(self):
        service, _ = _service()
        with self.assertRaises(CorrectionCandidateDecisionError):
            service.decide(candidate_id=_CAND, kind="accept", reviewer="  ")

    def test_conflict_on_same_anchor_different_provenance(self):
        store = _FakeDecisionStore()
        service, _ = _service(store=store)
        # Pre-seed a sequence-0 accept with one reviewer; a different reviewer's accept at seq 0 would only be
        # reached via a stale read, and must conflict on differing content rather than overwrite.
        first = service.decide(candidate_id=_CAND, kind="accept", reviewer="r:kim")
        # Force the conflict path: a decision at the derived identity already exists with a different fingerprint.
        identity = derive_decision_identity(CorrectionCandidateId(_CAND), DecisionKind.REJECT, 1)
        conflicting = CorrectionCandidateDecision(
            identity=identity, correction_candidate_id=CorrectionCandidateId(_CAND),
            kind=DecisionKind.REJECT, reviewer=HumanActorReference("r:kim"), sequence=1,
            content_fingerprint="a" * 64,
            previous_decision_id=first.decision.identity, rationale="one",
        )
        # Placed in the identity index only: current authority stays Accept (seq 0), so deciding Reject derives
        # the seq-1 identity and finds this record with a differing fingerprint -> conflict (no overwrite).
        store.by_identity[identity.value] = conflicting
        with self.assertRaises(CorrectionCandidateDecisionConflictError):
            service.decide(candidate_id=_CAND, kind="reject", reviewer="r:kim", rationale="two")

    def test_near_concurrent_collision_converges(self):
        class _RacingStore(_FakeDecisionStore):
            def persist_decision(self, *, decision):
                _FakeDecisionStore.persist_decision(self, decision=decision)
                raise PersistenceIdentityCollisionError("won")

        racing = _RacingStore()
        service, _ = _service(store=racing)
        result = service.decide(candidate_id=_CAND, kind="accept", reviewer="r")
        self.assertEqual(result.outcome.value, "recorded")

    def test_persistence_required(self):
        service = CorrectionCandidateDecisionService(_FakeAdmissionQuery(), _FakeDecisionStore(), None)
        with self.assertRaises(RuntimeError):
            service.decide(candidate_id=_CAND, kind="accept", reviewer="r")


if __name__ == "__main__":
    unittest.main()
