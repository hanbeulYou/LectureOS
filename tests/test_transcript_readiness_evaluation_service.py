import unittest

from lectureos.application import (
    ApplicabilityOutcome,
    CurrentSelectionOutcome,
    ReadinessEvaluationIdentityPlan,
    ReadinessOutcome,
    ReadinessReasonCode,
    TranscriptReadinessEvaluationError,
    TranscriptReadinessEvaluationService,
)
from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.application.transcript_applicability_evaluation import (
    TranscriptApplicabilityEvaluation,
    outcome_for_decision_kind,
)
from lectureos.application.transcript_current_selection import (
    TranscriptCurrentSelection,
    selection_for_applicability_outcome,
)
from lectureos.application.transcript_review_decision import TranscriptReviewDecision
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
from lectureos.review.identities import (
    CandidateReferenceId,
    HumanActorReference,
    ReviewItemId,
)
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import (
    CorrectedTranscriptRevision,
    CorrectionCandidate,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)
from lectureos.transcript.service import TranscriptService
from lectureos.transcript.validation import TranscriptValidationService

from datetime import datetime, timezone

WHEN = datetime(2026, 7, 22, 18, 0, tzinfo=timezone.utc)


class TranscriptReadinessEvaluationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.media_id = SourceMediaId("media")
        self.timeline_id = SourceTimelineId("timeline")
        capability = CapabilityReference("transcript.correction")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(identity=unit_id, purpose="ready", capabilities=(capability,))
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("ready"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.transcripts = TranscriptService(self.execution)
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("provider"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="provider:model",
            original_content="source",
        )
        self.raw = RawTranscript(
            identity=TranscriptId("raw"),
            domain_result_id=DomainResultId("raw-result"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=(TranscriptSegmentId("segment-0"),),
        )
        segment = TranscriptSegment(
            identity=self.raw.segment_ids[0],
            transcript_id=self.raw.identity,
            source_timeline_id=self.timeline_id,
            text="one",
            source_order=0,
            start=0.0,
            end=1.0,
        )
        self.transcripts.register_provider_result(provider)
        self.transcripts.create_raw_transcript(self.raw, (segment,))
        self.transcripts.create_correction_candidate(
            CorrectionCandidate(
                identity=CorrectionCandidateId("candidate-0"),
                domain_result_id=DomainResultId("candidate-result-0"),
                transcript_id=self.raw.identity,
                segment_id=segment.identity,
                proposed_text="corrected",
                rationale="recognition",
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
            )
        )
        self.revision = CorrectedTranscriptRevision(
            identity=TranscriptRevisionId("revision"),
            transcript_id=self.raw.identity,
            domain_result_id=DomainResultId("revision-result"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=self.raw.segment_ids,
            parent_raw_transcript_id=self.raw.identity,
            correction_candidate_ids=(CorrectionCandidateId("candidate-0"),),
        )
        self.transcripts.create_corrected_revision(self.revision, (segment,))
        self.validation = TranscriptValidationService(self.transcripts, self.execution)
        self.decisions = InMemoryRepository()
        self.applicabilities = InMemoryRepository()
        self.selections = InMemoryRepository()
        self.service = TranscriptReadinessEvaluationService(
            self.selections,
            self.applicabilities,
            self.decisions,
            self.transcripts,
            self.validation,
            self.execution,
        )

    def _build_lineage(self, kind=DecisionKind.ACCEPT):
        decision = TranscriptReviewDecision(
            identity=TranscriptReviewDecisionId("decision"),
            domain_result_id=DomainResultId("decision-result"),
            review_item_id=ReviewItemId("item-0"),
            candidate_reference_id=CandidateReferenceId("candidate-0"),
            source_revision_id=self.revision.identity,
            reviewer=HumanActorReference("reviewer"),
            kind=kind,
            decided_at=WHEN,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            modified_text="revised" if kind is DecisionKind.MODIFY else None,
        )
        self.decisions.save(decision)
        applicability_outcome = outcome_for_decision_kind(kind)
        applicability = TranscriptApplicabilityEvaluation(
            identity=TranscriptApplicabilityEvaluationId("evaluation"),
            domain_result_id=DomainResultId("evaluation-result"),
            source_decision_id=decision.identity,
            decision_kind=kind,
            outcome=applicability_outcome,
            review_item_id=ReviewItemId("item-0"),
            candidate_reference_id=CandidateReferenceId("candidate-0"),
            source_revision_id=self.revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="derived",
        )
        self.applicabilities.save(applicability)
        selection = TranscriptCurrentSelection(
            identity=TranscriptCurrentSelectionId("selection"),
            domain_result_id=DomainResultId("selection-result"),
            source_applicability_id=applicability.identity,
            applicability_outcome=applicability_outcome,
            outcome=selection_for_applicability_outcome(applicability_outcome),
            source_decision_id=decision.identity,
            review_item_id=ReviewItemId("item-0"),
            candidate_reference_id=CandidateReferenceId("candidate-0"),
            source_revision_id=self.revision.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="derived",
        )
        self.selections.save(selection)
        return selection

    def _plan(self, name="readiness") -> ReadinessEvaluationIdentityPlan:
        return ReadinessEvaluationIdentityPlan(
            readiness_id=TranscriptReadinessEvaluationId(name),
            readiness_result_id=DomainResultId(f"{name}-result"),
            validation_id=TranscriptValidationId(f"{name}-validation"),
        )

    def _evaluate(self, selection, **overrides):
        base = dict(
            source_selection_id=selection.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        base.update(overrides)
        return self.service.evaluate_readiness(**base)

    def test_accepted_selected_valid_is_ready(self) -> None:
        selection = self._build_lineage(DecisionKind.ACCEPT)
        prepared = self._evaluate(selection)
        readiness = prepared.readiness
        self.assertIs(readiness.outcome, ReadinessOutcome.READY)
        self.assertIs(readiness.reason_code, ReadinessReasonCode.ALL_CONDITIONS_MET)
        self.assertTrue(readiness.structural_valid)
        self.assertEqual(readiness.source_selection_id, selection.identity)
        self.assertEqual(readiness.source_revision_id, self.revision.identity)
        self.assertEqual(readiness.review_item_id, ReviewItemId("item-0"))
        self.assertEqual(
            readiness.candidate_reference_id, CandidateReferenceId("candidate-0")
        )
        self.assertEqual(
            readiness.validation_id, TranscriptValidationId("readiness-validation")
        )
        self.assertEqual(
            prepared.readiness_result.kind, "transcript_readiness_evaluation"
        )
        self.assertEqual(
            prepared.readiness_result.upstream_results,
            (selection.domain_result_id,),
        )

    def test_rejected_lineage_is_not_ready(self) -> None:
        selection = self._build_lineage(DecisionKind.REJECT)
        prepared = self._evaluate(selection)
        self.assertIs(prepared.readiness.outcome, ReadinessOutcome.NOT_READY)
        self.assertIs(
            prepared.readiness.reason_code, ReadinessReasonCode.NOT_APPLICABLE
        )

    def test_modified_lineage_is_not_ready(self) -> None:
        selection = self._build_lineage(DecisionKind.MODIFY)
        prepared = self._evaluate(selection)
        self.assertIs(prepared.readiness.outcome, ReadinessOutcome.NOT_READY)
        self.assertIs(
            prepared.readiness.reason_code,
            ReadinessReasonCode.SUPERSEDED_BY_MODIFICATION,
        )

    def test_deterministic_construction(self) -> None:
        selection = self._build_lineage(DecisionKind.ACCEPT)
        first = self._evaluate(selection, identities=self._plan("a"))
        second = self._evaluate(selection, identities=self._plan("b"))
        # Same canonical inputs produce equal readiness modulo the identity plan.
        self.assertEqual(first.readiness.outcome, second.readiness.outcome)
        self.assertEqual(first.readiness.reason_code, second.readiness.reason_code)
        self.assertEqual(
            first.readiness.structural_valid, second.readiness.structural_valid
        )

    def test_unknown_selection_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.service.evaluate_readiness(
                source_selection_id=TranscriptCurrentSelectionId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_inconsistent_applicability_lineage_raises(self) -> None:
        selection = self._build_lineage(DecisionKind.ACCEPT)
        # Corrupt the applicability revision lineage.
        corrupted = TranscriptApplicabilityEvaluation(
            identity=TranscriptApplicabilityEvaluationId("evaluation"),
            domain_result_id=DomainResultId("evaluation-result"),
            source_decision_id=TranscriptReviewDecisionId("decision"),
            decision_kind=DecisionKind.ACCEPT,
            outcome=ApplicabilityOutcome.APPLICABLE,
            review_item_id=ReviewItemId("item-0"),
            candidate_reference_id=CandidateReferenceId("candidate-0"),
            source_revision_id=TranscriptRevisionId("other-revision"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="derived",
        )
        self.applicabilities.save(corrupted)  # overwrites the consistent record
        with self.assertRaises(TranscriptReadinessEvaluationError):
            self._evaluate(selection)

    def test_requires_running_execution(self) -> None:
        selection = self._build_lineage(DecisionKind.ACCEPT)
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(TranscriptReadinessEvaluationError):
            self._evaluate(selection)

    def test_record_without_persistence_raises(self) -> None:
        selection = self._build_lineage(DecisionKind.ACCEPT)
        with self.assertRaises(RuntimeError):
            self.service.record_readiness(
                source_selection_id=selection.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
