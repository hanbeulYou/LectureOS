import dataclasses
import unittest

from lectureos.application import (
    ApprovedEditExportIdentityPlan,
    ApprovedEditExportRepresentation,
    ApprovedEditExportService,
    EditExportError,
    EditReviewDecisionKind,
    require_canonical_candidate_type,
)
from lectureos.application.edit_export import (
    APPROVED_EDIT_EXPORT_REPRESENTATION_RESULT_KIND,
)
from lectureos.application.edit_candidate import EditCandidate
from lectureos.application.edit_review import (
    ApprovedEditDecision,
    EditReviewDecision,
)
from lectureos.application.identities import (
    AnalysisFindingId,
    ApprovedEditDecisionId,
    ApprovedEditExportRepresentationId,
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
from lectureos.execution.service import ExecutionService
from lectureos.review.identities import HumanActorReference

_MEDIA = SourceMediaId("media")
_TIMELINE = SourceTimelineId("timeline")
_ACTOR = HumanActorReference("reviewer:alice")
_CANDIDATE = EditCandidateId("candidate")
_REVIEW = EditReviewDecisionId("review")
_APPROVED = ApprovedEditDecisionId("approved")


def _candidate():
    return EditCandidate(
        identity=_CANDIDATE,
        domain_result_id=DomainResultId("candidate-result"),
        source_finding_id=AnalysisFindingId("finding"),
        source_media_id=_MEDIA,
        source_timeline_id=_TIMELINE,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        candidate_type="non_lecture_region",
        rationale="original candidate rationale",
        range_start=0.5,
        range_end=1.5,
    )


def _review(kind=EditReviewDecisionKind.ACCEPT):
    return EditReviewDecision(
        identity=_REVIEW,
        domain_result_id=DomainResultId("review-result"),
        source_candidate_id=_CANDIDATE,
        decision_kind=kind,
        actor=_ACTOR,
        source_media_id=_MEDIA,
        source_timeline_id=_TIMELINE,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
    )


def _approved(kind=EditReviewDecisionKind.ACCEPT, **overrides):
    base = dict(
        identity=_APPROVED,
        domain_result_id=DomainResultId("approved-result"),
        source_decision_id=_REVIEW,
        source_candidate_id=_CANDIDATE,
        decision_kind=kind,
        approved_range_start=0.5 if kind is EditReviewDecisionKind.ACCEPT else 0.75,
        approved_range_end=1.5 if kind is EditReviewDecisionKind.ACCEPT else 1.25,
        approved_candidate_type="non_lecture_region"
        if kind is EditReviewDecisionKind.ACCEPT
        else "condense_repetition",
        approved_rationale="approved rationale",
        source_media_id=_MEDIA,
        source_timeline_id=_TIMELINE,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
    )
    base.update(overrides)
    return ApprovedEditDecision(**base)


class _Query:
    def __init__(self, record):
        self._record = record

    def get(self, identity):
        if self._record is not None and identity == self._record.identity:
            return self._record
        return None


def _plan(name="e"):
    return ApprovedEditExportIdentityPlan(
        representation_id=ApprovedEditExportRepresentationId(f"rep-{name}"),
        representation_result_id=DomainResultId(f"rep-{name}-result"),
    )


class EditExportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="edit-export",
                capabilities=(CapabilityReference("lecture.export"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("edit-export"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.candidate = _candidate()

    def _service(self, *, approved=None, review=None, candidate=None):
        return ApprovedEditExportService(
            _Query(approved if approved is not None else _approved()),
            _Query(review if review is not None else _review()),
            _Query(candidate if candidate is not None else self.candidate),
            self.execution,
        )

    def _evaluate(self, service, **overrides):
        base = dict(
            source_approved_decision_id=_APPROVED,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=_plan(),
        )
        base.update(overrides)
        return service.evaluate_representation(**base)

    def test_accept_snapshot_copied_from_approved(self) -> None:
        prepared = self._evaluate(self._service())
        rep = prepared.representation
        approved = _approved()
        self.assertEqual(rep.approved_range_start, approved.approved_range_start)
        self.assertEqual(rep.approved_candidate_type, approved.approved_candidate_type)
        self.assertEqual(rep.approved_rationale, approved.approved_rationale)
        self.assertIs(rep.decision_kind, EditReviewDecisionKind.ACCEPT)
        self.assertEqual(rep.actor, _ACTOR)
        self.assertEqual(rep.source_approved_decision_id, _APPROVED)
        self.assertEqual(rep.source_review_decision_id, _REVIEW)
        self.assertEqual(rep.source_candidate_id, _CANDIDATE)
        self.assertEqual(prepared.representation_result.kind, APPROVED_EDIT_EXPORT_REPRESENTATION_RESULT_KIND)
        self.assertEqual(prepared.representation_result.upstream_results, (approved.domain_result_id,))

    def test_modify_snapshot_copied_from_approved_not_candidate(self) -> None:
        service = self._service(
            approved=_approved(kind=EditReviewDecisionKind.MODIFY),
            review=_review(kind=EditReviewDecisionKind.MODIFY),
        )
        rep = self._evaluate(service).representation
        # comes from the approved decision, not the candidate's original values
        self.assertEqual(rep.approved_candidate_type, "condense_repetition")
        self.assertNotEqual(rep.approved_candidate_type, self.candidate.candidate_type)
        self.assertEqual(rep.approved_range_start, 0.75)
        self.assertIs(rep.decision_kind, EditReviewDecisionKind.MODIFY)

    def test_open_candidate_type_outside_generation_registry(self) -> None:
        self.assertEqual(require_canonical_candidate_type("terminology_drift"), "terminology_drift")
        service = self._service(
            approved=_approved(kind=EditReviewDecisionKind.MODIFY, approved_candidate_type="terminology_drift"),
            review=_review(kind=EditReviewDecisionKind.MODIFY),
        )
        rep = self._evaluate(service).representation
        self.assertEqual(rep.approved_candidate_type, "terminology_drift")

    def test_unknown_approved_decision_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._evaluate(self._service(), source_approved_decision_id=ApprovedEditDecisionId("missing"))

    def test_missing_review_lineage_raises(self) -> None:
        service = ApprovedEditExportService(
            _Query(_approved()), _Query(None), _Query(self.candidate), self.execution
        )
        with self.assertRaises(KeyError):
            self._evaluate(service)

    def test_missing_candidate_lineage_raises(self) -> None:
        service = ApprovedEditExportService(
            _Query(_approved()), _Query(_review()), _Query(None), self.execution
        )
        with self.assertRaises(KeyError):
            self._evaluate(service)

    def test_lineage_candidate_mismatch_rejected(self) -> None:
        other_review = EditReviewDecision(
            identity=_REVIEW,
            domain_result_id=DomainResultId("review-result"),
            source_candidate_id=EditCandidateId("other-candidate"),
            decision_kind=EditReviewDecisionKind.ACCEPT,
            actor=_ACTOR,
            source_media_id=_MEDIA,
            source_timeline_id=_TIMELINE,
            run_id=ProcessingRunId("run"),
            unit_execution_id=UnitExecutionId("execution"),
            sequence=0,
        )
        with self.assertRaises(EditExportError):
            self._evaluate(self._service(review=other_review))

    def test_lineage_kind_mismatch_rejected(self) -> None:
        # approved says accept, review says modify -> inconsistent
        with self.assertRaises(EditExportError):
            self._evaluate(self._service(review=_review(kind=EditReviewDecisionKind.MODIFY)))

    def test_lineage_timeline_mismatch_rejected(self) -> None:
        approved = _approved(source_timeline_id=SourceTimelineId("other-timeline"))
        with self.assertRaises(EditExportError):
            self._evaluate(self._service(approved=approved))

    def test_non_running_execution_rejected(self) -> None:
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(EditExportError):
            self._evaluate(self._service())

    def test_deterministic_construction(self) -> None:
        self.assertEqual(self._evaluate(self._service()), self._evaluate(self._service()))

    def test_record_immutable_and_no_deferred_fields(self) -> None:
        rep = self._evaluate(self._service()).representation
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rep.approved_rationale = "x"  # type: ignore[misc]
        fields = set(ApprovedEditExportRepresentation.__dataclass_fields__)
        for forbidden in (
            "status", "state", "profile", "format", "mime_type", "filename", "path",
            "url", "checksum", "payload", "serialized", "artifact_id", "materialization",
            "current", "superseded",
        ):
            self.assertNotIn(forbidden, fields)

    def test_reject_kind_cannot_construct_record(self) -> None:
        with self.assertRaises(ValueError):
            ApprovedEditExportRepresentation(
                identity=ApprovedEditExportRepresentationId("r"),
                domain_result_id=DomainResultId("r-result"),
                source_approved_decision_id=_APPROVED,
                source_review_decision_id=_REVIEW,
                source_candidate_id=_CANDIDATE,
                decision_kind=EditReviewDecisionKind.REJECT,
                approved_range_start=0.0,
                approved_range_end=1.0,
                approved_candidate_type="non_lecture_region",
                approved_rationale="r",
                actor=_ACTOR,
                source_media_id=_MEDIA,
                source_timeline_id=_TIMELINE,
                run_id=ProcessingRunId("run"),
                unit_execution_id=UnitExecutionId("execution"),
                sequence=0,
            )

    def test_record_without_persistence_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            self._service().record_representation(
                source_approved_decision_id=_APPROVED,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=_plan(),
            )


if __name__ == "__main__":
    unittest.main()
