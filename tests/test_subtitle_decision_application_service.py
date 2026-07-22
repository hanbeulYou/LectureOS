import unittest
from datetime import datetime, timezone

from lectureos.application import (
    RULE_OVERLAP_ADJACENT,
    SubtitleAppliedOutcome,
    SubtitleDecisionApplicationError,
    SubtitleDecisionRevisionIdentityPlan,
    SubtitleDecisionRevisionService,
    SubtitleReviewDecision,
    SubtitleValidation,
    SubtitleValidationCategory,
    SubtitleValidationFinding,
)
from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleDecisionRevisionId,
    SubtitleReadingRevisionId,
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleTranscriptIntakeId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
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
from lectureos.review.identities import (
    CandidateReferenceId,
    HumanActorReference,
    ReviewItemId,
)
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)

WHEN = datetime(2026, 7, 22, 21, 0, tzinfo=timezone.utc)
MEDIA = SourceMediaId("media")
TIMELINE = SourceTimelineId("timeline")


class _FakeDecisionQuery:
    def __init__(self, decision) -> None:
        self._decision = decision

    def get(self, identity):
        return self._decision if identity == self._decision.identity else None


class _FakeValidationQuery:
    def __init__(self, validation, findings) -> None:
        self._validation = validation
        self._findings = {finding.identity: finding for finding in findings}

    def get(self, identity):
        return self._validation if identity == self._validation.identity else None

    def get_finding(self, identity):
        return self._findings.get(identity)


class SubtitleDecisionApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="decision-application",
                capabilities=(CapabilityReference("subtitle.decision"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("decision-application"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.finding = SubtitleValidationFinding(
            identity=SubtitleValidationFindingId("finding"),
            validation_id=SubtitleValidationId("validation"),
            rule=RULE_OVERLAP_ADJACENT,
            category=SubtitleValidationCategory.OVERLAP,
            blocking=True,
            description="overlap",
            target_timed_unit_id=SubtitleTimedUnitId("timed-1"),
        )
        self.validation = self._validation()

    def _validation(self) -> SubtitleValidation:
        return SubtitleValidation(
            identity=SubtitleValidationId("validation"),
            domain_result_id=DomainResultId("validation-result"),
            source_time_revision_id=SubtitleTimeRevisionId("time"),
            source_reading_revision_id=SubtitleReadingRevisionId("reading"),
            source_candidate_id=SubtitleCandidateId("candidate"),
            source_intake_id=SubtitleTranscriptIntakeId("intake"),
            source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
            source_selection_id=TranscriptCurrentSelectionId("selection"),
            source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
            source_decision_id=TranscriptReviewDecisionId("decision"),
            review_item_id=ReviewItemId("source-item"),
            candidate_reference_id=CandidateReferenceId("source-reference"),
            source_transcript_id=TranscriptId("raw"),
            source_revision_id=TranscriptRevisionId("revision"),
            source_media_id=MEDIA,
            source_timeline_id=TIMELINE,
            source_transcript_validation_id=TranscriptValidationId("transcript-validation"),
            structural_valid=False,
            provenance_complete=True,
            timeline_traceable=True,
            ordering_consistent=True,
            time_consistent=False,
            finding_ids=(self.finding.identity,),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="validation",
        )

    def _decision(self, kind=DecisionKind.ACCEPT, modified_text=None) -> SubtitleReviewDecision:
        return SubtitleReviewDecision(
            identity=SubtitleReviewDecisionId("decision"),
            domain_result_id=DomainResultId("decision-result"),
            review_item_id=ReviewItemId("item"),
            candidate_reference_id=CandidateReferenceId("reference"),
            source_preparation_id=SubtitleReviewPreparationId("preparation"),
            source_validation_id=SubtitleValidationId("validation"),
            source_time_revision_id=SubtitleTimeRevisionId("time"),
            source_finding_id=SubtitleValidationFindingId("finding"),
            rule=RULE_OVERLAP_ADJACENT,
            reviewer=HumanActorReference("reviewer"),
            kind=kind,
            decided_at=WHEN,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            modified_text=modified_text,
        )

    def _service(self, decision):
        return SubtitleDecisionRevisionService(
            _FakeDecisionQuery(decision),
            _FakeValidationQuery(self.validation, [self.finding]),
            self.execution,
        )

    def _plan(self, name="revision"):
        return SubtitleDecisionRevisionIdentityPlan(
            revision_id=SubtitleDecisionRevisionId(name),
            revision_result_id=DomainResultId(f"{name}-result"),
        )

    def _apply(self, service, plan=None):
        return service.apply_decision(
            source_review_decision_id=SubtitleReviewDecisionId("decision"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=plan or self._plan(),
        )

    def test_accept_produces_accepted_revision_with_lineage(self) -> None:
        prepared = self._apply(self._service(self._decision(DecisionKind.ACCEPT)))
        revision = prepared.revision
        self.assertIs(revision.outcome, SubtitleAppliedOutcome.ACCEPTED)
        self.assertIs(revision.decision_kind, DecisionKind.ACCEPT)
        self.assertIsNone(revision.applied_text)
        self.assertEqual(revision.source_review_decision_id, SubtitleReviewDecisionId("decision"))
        self.assertEqual(revision.target_timed_unit_id, SubtitleTimedUnitId("timed-1"))
        self.assertEqual(revision.rule, RULE_OVERLAP_ADJACENT)
        # lineage carried from the validation (read-only)
        self.assertEqual(revision.source_reading_revision_id, SubtitleReadingRevisionId("reading"))
        self.assertEqual(revision.source_candidate_id, SubtitleCandidateId("candidate"))
        self.assertEqual(revision.source_transcript_id, TranscriptId("raw"))
        self.assertEqual(revision.source_media_id, MEDIA)
        self.assertEqual(prepared.revision_result.kind, "subtitle_decision_revision")
        self.assertEqual(
            prepared.revision_result.upstream_results, (DomainResultId("decision-result"),)
        )

    def test_reject_produces_rejected_revision(self) -> None:
        revision = self._apply(self._service(self._decision(DecisionKind.REJECT))).revision
        self.assertIs(revision.outcome, SubtitleAppliedOutcome.REJECTED)
        self.assertIsNone(revision.applied_text)

    def test_modify_produces_modified_revision_with_applied_text(self) -> None:
        decision = self._decision(DecisionKind.MODIFY, modified_text="corrected line")
        revision = self._apply(self._service(decision)).revision
        self.assertIs(revision.outcome, SubtitleAppliedOutcome.MODIFIED)
        self.assertEqual(revision.applied_text, "corrected line")

    def test_unknown_decision_raises(self) -> None:
        service = self._service(self._decision())
        with self.assertRaises(KeyError):
            service.apply_decision(
                source_review_decision_id=SubtitleReviewDecisionId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_unknown_finding_raises(self) -> None:
        service = SubtitleDecisionRevisionService(
            _FakeDecisionQuery(self._decision()),
            _FakeValidationQuery(self.validation, []),
            self.execution,
        )
        with self.assertRaises(KeyError):
            self._apply(service)

    def test_requires_running_execution(self) -> None:
        service = self._service(self._decision())
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(SubtitleDecisionApplicationError):
            self._apply(service)

    def test_deterministic_construction(self) -> None:
        service = self._service(self._decision())
        self.assertEqual(self._apply(service), self._apply(service))

    def test_record_without_persistence_raises(self) -> None:
        service = self._service(self._decision())
        with self.assertRaises(RuntimeError):
            service.record_application(
                source_review_decision_id=SubtitleReviewDecisionId("decision"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
