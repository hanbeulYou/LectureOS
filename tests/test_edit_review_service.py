import dataclasses
import unittest

from lectureos.application import (
    ApprovedEditDecision,
    EditReviewApplicationService,
    EditReviewDecision,
    EditReviewDecisionKind,
    EditReviewError,
    EditReviewIdentityPlan,
    NormalizedModification,
    require_canonical_candidate_type,
    require_decision_kind,
)
from lectureos.application.edit_review import (
    APPROVED_EDIT_DECISION_RESULT_KIND,
    EDIT_REVIEW_DECISION_RESULT_KIND,
)
from lectureos.application.edit_candidate import EditCandidate
from lectureos.application.identities import (
    AnalysisFindingId,
    ApprovedEditDecisionId,
    EditCandidateId,
    EditReviewDecisionId,
)
from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    ProcessingUnitId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import ExecutionIntent, ProcessingUnit
from lectureos.execution.repositories import InMemoryRepository
from lectureos.execution.service import ExecutionService
from lectureos.review.identities import HumanActorReference

_MEDIA = SourceMediaId("media")
_TIMELINE = SourceTimelineId("timeline")
_ACTOR = HumanActorReference("reviewer:alice")


class _FakeCandidateQuery:
    def __init__(self, candidate):
        self._candidate = candidate

    def get(self, identity):
        if self._candidate is not None and identity == self._candidate.identity:
            return self._candidate
        return None


def _candidate(name="candidate"):
    return EditCandidate(
        identity=EditCandidateId(name),
        domain_result_id=DomainResultId(f"{name}-result"),
        source_finding_id=AnalysisFindingId("finding"),
        source_media_id=_MEDIA,
        source_timeline_id=_TIMELINE,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        candidate_type="non_lecture_region",
        rationale="propose review of a possible non-lecture region",
        range_start=0.5,
        range_end=1.5,
    )


def _plan(name="d", *, approved=True):
    return EditReviewIdentityPlan(
        decision_id=EditReviewDecisionId(f"decision-{name}"),
        decision_result_id=DomainResultId(f"decision-{name}-result"),
        approved_id=ApprovedEditDecisionId(f"approved-{name}") if approved else None,
        approved_result_id=DomainResultId(f"approved-{name}-result") if approved else None,
    )


def _modification(**overrides):
    base = dict(
        approved_range_start=0.75,
        approved_range_end=1.25,
        approved_candidate_type="condense_repetition",
        approved_rationale="approved: condense",
    )
    base.update(overrides)
    return NormalizedModification(**base)


class EditReviewServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="edit-review",
                capabilities=(CapabilityReference("lecture.review"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("edit-review"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.candidate = _candidate()
        self.service = EditReviewApplicationService(
            _FakeCandidateQuery(self.candidate), self.execution
        )

    def _evaluate(self, **overrides):
        base = dict(
            source_candidate_id=self.candidate.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            decision_kind="accept",
            actor=_ACTOR,
            identities=_plan(),
        )
        base.update(overrides)
        return self.service.evaluate_decision(**base)

    # -- decision kind ---------------------------------------------------
    def test_decision_kind_closed_set(self) -> None:
        self.assertEqual({k.value for k in EditReviewDecisionKind}, {"accept", "reject", "modify"})

    def test_unknown_decision_kind_rejected(self) -> None:
        for junk in ("Accept", "APPROVE", "acccept", "keep", "", "delete"):
            with self.subTest(junk=junk):
                with self.assertRaises(ValueError):
                    require_decision_kind(junk)

    def test_decision_kind_not_coerced(self) -> None:
        with self.assertRaises(ValueError):
            self._evaluate(decision_kind="Accept")

    def test_candidate_type_remains_open(self) -> None:
        # A canonical open key outside the generation registry is valid for a Modify approval.
        self.assertEqual(require_canonical_candidate_type("terminology_drift"), "terminology_drift")
        prepared = self._evaluate(
            decision_kind="modify",
            identities=_plan("m"),
            modification=_modification(approved_candidate_type="terminology_drift"),
        )
        self.assertEqual(prepared.approved.approved_candidate_type, "terminology_drift")

    # -- accept ----------------------------------------------------------
    def test_accept_snapshots_candidate(self) -> None:
        prepared = self._evaluate(decision_kind="accept")
        self.assertIs(prepared.decision.decision_kind, EditReviewDecisionKind.ACCEPT)
        approved = prepared.approved
        self.assertIsNotNone(approved)
        self.assertEqual(approved.approved_range_start, self.candidate.range_start)
        self.assertEqual(approved.approved_range_end, self.candidate.range_end)
        self.assertEqual(approved.approved_candidate_type, self.candidate.candidate_type)
        self.assertEqual(approved.approved_rationale, self.candidate.rationale)
        self.assertEqual(approved.source_decision_id, prepared.decision.identity)
        self.assertEqual(approved.source_candidate_id, self.candidate.identity)
        self.assertEqual(prepared.decision_result.kind, EDIT_REVIEW_DECISION_RESULT_KIND)
        self.assertEqual(prepared.decision_result.upstream_results, (self.candidate.domain_result_id,))
        self.assertEqual(prepared.approved_result.kind, APPROVED_EDIT_DECISION_RESULT_KIND)
        self.assertEqual(prepared.approved_result.upstream_results, (prepared.decision.domain_result_id,))
        self.assertEqual(prepared.decision.source_media_id, _MEDIA)
        self.assertEqual(prepared.decision.source_timeline_id, _TIMELINE)

    def test_accept_may_not_override_candidate_values(self) -> None:
        with self.assertRaises(EditReviewError):
            self._evaluate(decision_kind="accept", modification=_modification())

    # -- modify ----------------------------------------------------------
    def test_modify_uses_modification(self) -> None:
        prepared = self._evaluate(
            decision_kind="modify", identities=_plan("m"), modification=_modification()
        )
        approved = prepared.approved
        self.assertEqual(approved.approved_range_start, 0.75)
        self.assertEqual(approved.approved_candidate_type, "condense_repetition")
        self.assertNotEqual(approved.approved_candidate_type, self.candidate.candidate_type)

    def test_modify_requires_modification(self) -> None:
        with self.assertRaises(EditReviewError):
            self._evaluate(decision_kind="modify", identities=_plan("m"))

    def test_modify_invalid_range_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _modification(approved_range_start=2.0, approved_range_end=1.0)

    def test_modify_blank_rationale_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _modification(approved_rationale="  ")

    def test_modify_non_canonical_type_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _modification(approved_candidate_type="Remove This")

    # -- reject ----------------------------------------------------------
    def test_reject_creates_no_approved(self) -> None:
        prepared = self._evaluate(decision_kind="reject", identities=_plan("r", approved=False))
        self.assertIs(prepared.decision.decision_kind, EditReviewDecisionKind.REJECT)
        self.assertIsNone(prepared.approved)
        self.assertIsNone(prepared.approved_result)

    def test_reject_rejects_approved_plan(self) -> None:
        with self.assertRaises(EditReviewError):
            self._evaluate(decision_kind="reject", identities=_plan("r"))

    def test_reject_rejects_modification(self) -> None:
        with self.assertRaises(EditReviewError):
            self._evaluate(
                decision_kind="reject",
                identities=_plan("r", approved=False),
                modification=_modification(),
            )

    def test_accept_requires_approved_plan(self) -> None:
        with self.assertRaises(EditReviewError):
            self._evaluate(decision_kind="accept", identities=_plan("d", approved=False))

    # -- preconditions ---------------------------------------------------
    def test_unknown_candidate_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._evaluate(source_candidate_id=EditCandidateId("missing"))

    def test_non_running_execution_rejected(self) -> None:
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(EditReviewError):
            self._evaluate()

    def test_missing_actor_rejected(self) -> None:
        with self.assertRaises(TypeError):
            self.service.evaluate_decision(
                source_candidate_id=self.candidate.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                decision_kind="accept",
                identities=_plan(),
            )

    def test_deterministic_construction(self) -> None:
        self.assertEqual(self._evaluate(), self._evaluate())

    def test_records_are_immutable(self) -> None:
        prepared = self._evaluate()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            prepared.decision.decision_kind = EditReviewDecisionKind.REJECT  # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            prepared.approved.approved_rationale = "x"  # type: ignore[misc]

    def test_no_status_or_deferred_fields(self) -> None:
        for cls in (EditReviewDecision, ApprovedEditDecision):
            fields = set(cls.__dataclass_fields__)
            for forbidden in (
                "status", "state", "current", "stale", "superseded", "withdrawn",
                "revoked", "confidence", "priority", "severity", "quality",
                "review_session_id", "review_history_id", "note",
            ):
                self.assertNotIn(forbidden, fields)
        # ReviewDecision carries no modify payload
        self.assertNotIn("modification", set(EditReviewDecision.__dataclass_fields__))
        self.assertNotIn("approved_range_start", set(EditReviewDecision.__dataclass_fields__))

    def test_record_without_persistence_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            self.service.record_decision(
                source_candidate_id=self.candidate.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                decision_kind="accept",
                actor=_ACTOR,
                identities=_plan(),
            )


if __name__ == "__main__":
    unittest.main()
