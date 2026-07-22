import unittest

from lectureos.application import (
    RULE_ORDERING_NON_MONOTONIC,
    RULE_OVERLAP_ADJACENT,
    SubtitleReviewPreparationError,
    SubtitleReviewPreparationIdentityPlan,
    SubtitleReviewPreparationService,
    SubtitleReviewTargetIdentityPlan,
    SubtitleValidation,
    SubtitleValidationCategory,
    SubtitleValidationFinding,
)
from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
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
    ReviewContextId,
    ReviewItemId,
)
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)

MEDIA = SourceMediaId("media")
TIMELINE = SourceTimelineId("timeline")


class _FakeValidationQuery:
    def __init__(self, validation, findings) -> None:
        self._validation = validation
        self._findings = {finding.identity: finding for finding in findings}

    def get(self, identity):
        return self._validation if identity == self._validation.identity else None

    def get_finding(self, identity):
        return self._findings.get(identity)


class SubtitleReviewPreparationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="review-preparation",
                capabilities=(CapabilityReference("subtitle.review"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("review-preparation"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )

    def _finding(self, name, rule, category, target="timed-0") -> SubtitleValidationFinding:
        return SubtitleValidationFinding(
            identity=SubtitleValidationFindingId(name),
            validation_id=SubtitleValidationId("validation"),
            rule=rule,
            category=category,
            blocking=True,
            description=f"{rule} finding",
            target_timed_unit_id=SubtitleTimedUnitId(target) if target else None,
        )

    def _validation(self, finding_ids, structural_valid=False) -> SubtitleValidation:
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
            structural_valid=structural_valid,
            provenance_complete=True,
            timeline_traceable=True,
            ordering_consistent=structural_valid,
            time_consistent=structural_valid,
            finding_ids=tuple(SubtitleValidationFindingId(f) for f in finding_ids),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="validation",
        )

    def _service(self, validation, findings):
        return SubtitleReviewPreparationService(
            _FakeValidationQuery(validation, findings), self.execution
        )

    def _plan(self, count, name="prep"):
        return SubtitleReviewPreparationIdentityPlan(
            preparation_id=SubtitleReviewPreparationId(name),
            preparation_result_id=DomainResultId(f"{name}-result"),
            context_id=ReviewContextId(f"{name}-context"),
            targets=tuple(
                SubtitleReviewTargetIdentityPlan(
                    candidate_reference_id=CandidateReferenceId(f"{name}-ref-{i}"),
                    review_item_id=ReviewItemId(f"{name}-item-{i}"),
                )
                for i in range(count)
            ),
        )

    def _prepare(self, service, plan):
        return service.prepare_review(
            source_validation_id=SubtitleValidationId("validation"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=plan,
        )

    def test_one_review_item_per_finding_open_and_traced(self) -> None:
        findings = [
            self._finding("f-0", RULE_ORDERING_NON_MONOTONIC, SubtitleValidationCategory.ORDERING),
            self._finding("f-1", RULE_OVERLAP_ADJACENT, SubtitleValidationCategory.OVERLAP, "timed-1"),
        ]
        validation = self._validation(["f-0", "f-1"])
        prepared = self._prepare(self._service(validation, findings), self._plan(2))

        self.assertEqual(prepared.preparation.item_count, 2)
        self.assertEqual(len(prepared.review_items), 2)
        self.assertEqual(len(prepared.candidate_references), 2)
        # review items are OPEN in the common lifecycle (no decisions yet)
        self.assertTrue(all(item.decision_references == () for item in prepared.review_items))
        # each item references its candidate reference + the shared context
        for item, reference in zip(prepared.review_items, prepared.candidate_references):
            self.assertEqual(item.candidate_id, reference.identity)
            self.assertEqual(item.context_id, prepared.context.identity)
            self.assertEqual(reference.kind, "subtitle_validation_finding")
            self.assertEqual(reference.source_domain, "subtitle")
            self.assertEqual(reference.domain_result_id, DomainResultId("validation-result"))
        # links trace each item to its source finding + stable rule, in finding order
        self.assertEqual(
            [link.source_finding_id for link in prepared.preparation.item_links],
            [SubtitleValidationFindingId("f-0"), SubtitleValidationFindingId("f-1")],
        )
        self.assertEqual(
            [link.rule for link in prepared.preparation.item_links],
            [RULE_ORDERING_NON_MONOTONIC, RULE_OVERLAP_ADJACENT],
        )
        self.assertEqual(
            prepared.preparation.item_links[1].target_timed_unit_id,
            SubtitleTimedUnitId("timed-1"),
        )
        self.assertEqual(
            prepared.preparation_result.upstream_results,
            (DomainResultId("validation-result"),),
        )
        self.assertEqual(prepared.preparation_result.kind, "subtitle_review_preparation")
        self.assertEqual(
            prepared.preparation.source_validation_id, SubtitleValidationId("validation")
        )

    def test_clean_validation_yields_empty_preparation(self) -> None:
        validation = self._validation([], structural_valid=True)
        prepared = self._prepare(self._service(validation, []), self._plan(0))
        self.assertEqual(prepared.preparation.item_count, 0)
        self.assertEqual(prepared.review_items, ())
        self.assertEqual(prepared.candidate_references, ())
        # a context is still materialized for the empty preparation
        self.assertEqual(prepared.context.identity, ReviewContextId("prep-context"))
        self.assertTrue(prepared.preparation.source_structural_valid)

    def test_target_count_must_match_findings(self) -> None:
        findings = [self._finding("f-0", RULE_OVERLAP_ADJACENT, SubtitleValidationCategory.OVERLAP)]
        validation = self._validation(["f-0"])
        with self.assertRaises(SubtitleReviewPreparationError):
            self._prepare(self._service(validation, findings), self._plan(2))

    def test_unknown_validation_raises(self) -> None:
        service = self._service(self._validation([]), [])
        with self.assertRaises(KeyError):
            service.prepare_review(
                source_validation_id=SubtitleValidationId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(0),
            )

    def test_unknown_finding_raises(self) -> None:
        validation = self._validation(["f-0"])
        service = self._service(validation, [])
        with self.assertRaises(KeyError):
            self._prepare(service, self._plan(1))

    def test_requires_running_execution(self) -> None:
        validation = self._validation([], structural_valid=True)
        service = self._service(validation, [])
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(SubtitleReviewPreparationError):
            self._prepare(service, self._plan(0))

    def test_deterministic_construction(self) -> None:
        findings = [self._finding("f-0", RULE_OVERLAP_ADJACENT, SubtitleValidationCategory.OVERLAP)]
        validation = self._validation(["f-0"])
        service = self._service(validation, findings)
        self.assertEqual(self._prepare(service, self._plan(1)), self._prepare(service, self._plan(1)))

    def test_record_without_persistence_raises(self) -> None:
        validation = self._validation([], structural_valid=True)
        service = self._service(validation, [])
        with self.assertRaises(RuntimeError):
            service.generate_review(
                source_validation_id=SubtitleValidationId("validation"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(0),
            )


if __name__ == "__main__":
    unittest.main()
