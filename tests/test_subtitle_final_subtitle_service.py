import unittest

from lectureos.application import (
    RULE_OVERLAP_ADJACENT,
    SubtitleAppliedOutcome,
    SubtitleDecisionRevision,
    SubtitleFinalOutcome,
    SubtitleFinalSubtitleError,
    SubtitleFinalSubtitleIdentityPlan,
    SubtitleFinalSubtitleService,
    applied_outcome_for_kind,
)
from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleDecisionRevisionId,
    SubtitleFinalSubtitleId,
    SubtitleReadingRevisionId,
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
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
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

MEDIA = SourceMediaId("media")
TIMELINE = SourceTimelineId("timeline")


class _FakeDecisionRevisionQuery:
    def __init__(self, revision) -> None:
        self._revision = revision

    def get(self, identity):
        return self._revision if identity == self._revision.identity else None


class SubtitleFinalSubtitleServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="final-subtitle",
                capabilities=(CapabilityReference("subtitle.final"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("final-subtitle"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )

    def _revision(
        self, kind=DecisionKind.ACCEPT, applied_text=None
    ) -> SubtitleDecisionRevision:
        return SubtitleDecisionRevision(
            identity=SubtitleDecisionRevisionId("revision"),
            domain_result_id=DomainResultId("revision-result"),
            source_review_decision_id=SubtitleReviewDecisionId("decision"),
            decision_kind=kind,
            outcome=applied_outcome_for_kind(kind),
            review_item_id=ReviewItemId("item"),
            candidate_reference_id=CandidateReferenceId("reference"),
            source_preparation_id=SubtitleReviewPreparationId("preparation"),
            source_validation_id=SubtitleValidationId("validation"),
            source_time_revision_id=SubtitleTimeRevisionId("time"),
            source_reading_revision_id=SubtitleReadingRevisionId("reading"),
            source_candidate_id=SubtitleCandidateId("candidate"),
            source_finding_id=SubtitleValidationFindingId("finding"),
            rule=RULE_OVERLAP_ADJACENT,
            source_transcript_id=TranscriptId("raw"),
            source_revision_id=TranscriptRevisionId("transcript-revision"),
            source_media_id=MEDIA,
            source_timeline_id=TIMELINE,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="applied review decision into next subtitle revision",
            target_timed_unit_id=SubtitleTimedUnitId("timed-1"),
            applied_text=applied_text,
        )

    def _service(self, revision):
        return SubtitleFinalSubtitleService(
            _FakeDecisionRevisionQuery(revision), self.execution
        )

    def _plan(self, name="final"):
        return SubtitleFinalSubtitleIdentityPlan(
            final_id=SubtitleFinalSubtitleId(name),
            final_result_id=DomainResultId(f"{name}-result"),
        )

    def _select(self, service, plan=None):
        return service.select_final(
            source_decision_revision_id=SubtitleDecisionRevisionId("revision"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=plan or self._plan(),
        )

    def test_accept_is_final_with_carried_lineage(self) -> None:
        prepared = self._select(self._service(self._revision(DecisionKind.ACCEPT)))
        final = prepared.final
        self.assertIs(final.final_outcome, SubtitleFinalOutcome.FINAL)
        self.assertIs(final.applied_outcome, SubtitleAppliedOutcome.ACCEPTED)
        self.assertIs(final.decision_kind, DecisionKind.ACCEPT)
        self.assertIsNone(final.applied_text)
        self.assertEqual(
            final.source_decision_revision_id, SubtitleDecisionRevisionId("revision")
        )
        # full lineage carried from the decision revision (read-only)
        self.assertEqual(
            final.source_review_decision_id, SubtitleReviewDecisionId("decision")
        )
        self.assertEqual(final.review_item_id, ReviewItemId("item"))
        self.assertEqual(final.source_validation_id, SubtitleValidationId("validation"))
        self.assertEqual(
            final.source_reading_revision_id, SubtitleReadingRevisionId("reading")
        )
        self.assertEqual(final.source_candidate_id, SubtitleCandidateId("candidate"))
        self.assertEqual(final.source_transcript_id, TranscriptId("raw"))
        self.assertEqual(final.source_media_id, MEDIA)
        self.assertEqual(final.target_timed_unit_id, SubtitleTimedUnitId("timed-1"))
        self.assertEqual(final.rule, RULE_OVERLAP_ADJACENT)
        self.assertEqual(prepared.final_result.kind, "subtitle_final_subtitle")
        self.assertEqual(
            prepared.final_result.upstream_results, (DomainResultId("revision-result"),)
        )
        self.assertEqual(prepared.final_result.source_media, MEDIA)

    def test_reject_is_not_final(self) -> None:
        final = self._select(self._service(self._revision(DecisionKind.REJECT))).final
        self.assertIs(final.final_outcome, SubtitleFinalOutcome.NOT_FINAL)
        self.assertIs(final.applied_outcome, SubtitleAppliedOutcome.REJECTED)
        self.assertIsNone(final.applied_text)

    def test_modify_is_final_with_applied_text(self) -> None:
        revision = self._revision(DecisionKind.MODIFY, applied_text="corrected line")
        final = self._select(self._service(revision)).final
        self.assertIs(final.final_outcome, SubtitleFinalOutcome.FINAL)
        self.assertIs(final.applied_outcome, SubtitleAppliedOutcome.MODIFIED)
        self.assertEqual(final.applied_text, "corrected line")

    def test_unknown_revision_raises(self) -> None:
        service = self._service(self._revision())
        with self.assertRaises(KeyError):
            service.select_final(
                source_decision_revision_id=SubtitleDecisionRevisionId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_requires_running_execution(self) -> None:
        service = self._service(self._revision())
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(SubtitleFinalSubtitleError):
            self._select(service)

    def test_deterministic_construction(self) -> None:
        service = self._service(self._revision())
        self.assertEqual(self._select(service), self._select(service))

    def test_record_without_persistence_raises(self) -> None:
        service = self._service(self._revision())
        with self.assertRaises(RuntimeError):
            service.record_final(
                source_decision_revision_id=SubtitleDecisionRevisionId("revision"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
