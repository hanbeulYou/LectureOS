import unittest
from datetime import datetime, timezone

from lectureos.application import (
    RULE_ORDERING_NON_MONOTONIC,
    RULE_OVERLAP_ADJACENT,
    SubtitleReviewDecisionError,
    SubtitleReviewDecisionIdentityPlan,
    SubtitleReviewDecisionService,
    SubtitleReviewItemLink,
    SubtitleReviewPreparation,
)
from lectureos.application.identities import (
    SubtitleCandidateId,
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
    ReviewContextId,
    ReviewItemId,
)
from lectureos.review.models import CandidateReference, DecisionKind, ReviewItem
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)

WHEN = datetime(2026, 7, 22, 21, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 7, 22, 21, 5, tzinfo=timezone.utc)
MEDIA = SourceMediaId("media")
TIMELINE = SourceTimelineId("timeline")


class _FakeQuery:
    def __init__(self, records) -> None:
        self._records = {record.identity: record for record in records}

    def get(self, identity):
        return self._records.get(identity)


class SubtitleReviewDecisionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="review-decision",
                capabilities=(CapabilityReference("subtitle.review"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("review-decision"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.rules = {"item-0": RULE_ORDERING_NON_MONOTONIC, "item-1": RULE_OVERLAP_ADJACENT}
        self.preparation = self._preparation(["item-0", "item-1"])
        self.items = [self._item("item-0"), self._item("item-1")]
        self.references = [self._reference("ref-item-0"), self._reference("ref-item-1")]
        self.service = SubtitleReviewDecisionService(
            _FakeQuery([self.preparation]),
            _FakeQuery(self.items),
            _FakeQuery(self.references),
            self.execution,
        )

    def _item(self, name) -> ReviewItem:
        return ReviewItem(
            identity=ReviewItemId(name),
            candidate_id=CandidateReferenceId(f"ref-{name}"),
            context_id=ReviewContextId("prep-context"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
        )

    def _reference(self, name, kind="subtitle_validation_finding", revision="time") -> CandidateReference:
        return CandidateReference(
            identity=CandidateReferenceId(name),
            kind=kind,
            source_domain="subtitle",
            domain_result_id=DomainResultId("validation-result"),
            source_media_id=MEDIA,
            source_timeline_id=TIMELINE,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            revision_reference=f"subtitle_time_revision:{revision}",
        )

    def _preparation(self, item_names) -> SubtitleReviewPreparation:
        links = tuple(
            SubtitleReviewItemLink(
                review_item_id=ReviewItemId(name),
                candidate_reference_id=CandidateReferenceId(f"ref-{name}"),
                source_finding_id=SubtitleValidationFindingId(f"finding-{name}"),
                rule=self.rules[name],
                target_timed_unit_id=SubtitleTimedUnitId(f"timed-{name}"),
            )
            for name in item_names
        )
        return SubtitleReviewPreparation(
            identity=SubtitleReviewPreparationId("preparation"),
            domain_result_id=DomainResultId("preparation-result"),
            source_validation_id=SubtitleValidationId("validation"),
            source_time_revision_id=SubtitleTimeRevisionId("time"),
            source_reading_revision_id=SubtitleReadingRevisionId("reading"),
            source_candidate_id=SubtitleCandidateId("candidate"),
            source_intake_id=SubtitleTranscriptIntakeId("intake"),
            source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
            source_selection_id=TranscriptCurrentSelectionId("selection"),
            source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
            source_decision_id=TranscriptReviewDecisionId("decision"),
            source_review_item_id=ReviewItemId("source-item"),
            source_candidate_reference_id=CandidateReferenceId("source-reference"),
            source_transcript_id=TranscriptId("raw"),
            source_revision_id=TranscriptRevisionId("revision"),
            source_media_id=MEDIA,
            source_timeline_id=TIMELINE,
            source_transcript_validation_id=TranscriptValidationId("transcript-validation"),
            context_id=ReviewContextId("prep-context"),
            item_links=links,
            item_count=len(links),
            source_structural_valid=False,
            provenance_complete=True,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="preparation",
        )

    def _plan(self, name="decision", when=WHEN) -> SubtitleReviewDecisionIdentityPlan:
        return SubtitleReviewDecisionIdentityPlan(
            decision_id=SubtitleReviewDecisionId(name),
            decision_result_id=DomainResultId(f"{name}-result"),
            decided_at=when,
        )

    def _record(self, item="item-0", kind=DecisionKind.ACCEPT, **overrides):
        base = dict(
            preparation_id=SubtitleReviewPreparationId("preparation"),
            review_item_id=ReviewItemId(item),
            reviewer=HumanActorReference("reviewer"),
            kind=kind,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        base.update(overrides)
        return self.service.prepare_decision(**base)

    def test_accept_records_with_subtitle_provenance(self) -> None:
        prepared = self._record("item-0", DecisionKind.ACCEPT)
        decision = prepared.decision
        self.assertIs(decision.kind, DecisionKind.ACCEPT)
        self.assertEqual(decision.review_item_id, ReviewItemId("item-0"))
        self.assertEqual(decision.candidate_reference_id, CandidateReferenceId("ref-item-0"))
        self.assertEqual(
            decision.source_preparation_id, SubtitleReviewPreparationId("preparation")
        )
        self.assertEqual(decision.source_validation_id, SubtitleValidationId("validation"))
        self.assertEqual(decision.source_time_revision_id, SubtitleTimeRevisionId("time"))
        self.assertEqual(
            decision.source_finding_id, SubtitleValidationFindingId("finding-item-0")
        )
        self.assertEqual(decision.rule, RULE_ORDERING_NON_MONOTONIC)
        self.assertEqual(decision.decided_at, WHEN)
        self.assertEqual(
            prepared.decision_result.kind, "subtitle_review_decision"
        )
        self.assertEqual(
            prepared.decision_result.upstream_results,
            (DomainResultId("preparation-result"),),
        )

    def test_reject_records(self) -> None:
        self.assertIs(self._record("item-1", DecisionKind.REJECT).decision.kind, DecisionKind.REJECT)

    def test_modify_with_text_records(self) -> None:
        decision = self._record(
            "item-0", DecisionKind.MODIFY, modified_text="corrected"
        ).decision
        self.assertEqual(decision.modified_text, "corrected")

    def test_modify_requires_text(self) -> None:
        with self.assertRaises(SubtitleReviewDecisionError):
            self._record("item-0", DecisionKind.MODIFY)

    def test_accept_must_not_carry_text(self) -> None:
        with self.assertRaises(SubtitleReviewDecisionError):
            self._record("item-0", DecisionKind.ACCEPT, modified_text="x")

    def test_non_human_reviewer_rejected(self) -> None:
        with self.assertRaises(SubtitleReviewDecisionError):
            self._record("item-0", reviewer="not-a-human")

    def test_review_item_not_in_preparation(self) -> None:
        other = self._item("item-stray")
        service = SubtitleReviewDecisionService(
            _FakeQuery([self.preparation]),
            _FakeQuery([*self.items, other]),
            _FakeQuery([*self.references, self._reference("ref-item-stray")]),
            self.execution,
        )
        with self.assertRaises(SubtitleReviewDecisionError):
            service.prepare_decision(
                preparation_id=SubtitleReviewPreparationId("preparation"),
                review_item_id=ReviewItemId("item-stray"),
                reviewer=HumanActorReference("reviewer"),
                kind=DecisionKind.ACCEPT,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_wrong_candidate_reference_kind_rejected(self) -> None:
        service = SubtitleReviewDecisionService(
            _FakeQuery([self.preparation]),
            _FakeQuery(self.items),
            _FakeQuery([self._reference("ref-item-0", kind="transcript_correction_candidate"),
                        self._reference("ref-item-1")]),
            self.execution,
        )
        with self.assertRaises(SubtitleReviewDecisionError):
            service.prepare_decision(
                preparation_id=SubtitleReviewPreparationId("preparation"),
                review_item_id=ReviewItemId("item-0"),
                reviewer=HumanActorReference("reviewer"),
                kind=DecisionKind.ACCEPT,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_provenance_mismatch_rejected(self) -> None:
        service = SubtitleReviewDecisionService(
            _FakeQuery([self.preparation]),
            _FakeQuery(self.items),
            _FakeQuery([self._reference("ref-item-0", revision="other"),
                        self._reference("ref-item-1")]),
            self.execution,
        )
        with self.assertRaises(SubtitleReviewDecisionError):
            service.prepare_decision(
                preparation_id=SubtitleReviewPreparationId("preparation"),
                review_item_id=ReviewItemId("item-0"),
                reviewer=HumanActorReference("reviewer"),
                kind=DecisionKind.ACCEPT,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_unknown_preparation_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._record(preparation_id=SubtitleReviewPreparationId("missing"))

    def test_unknown_item_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._record(review_item_id=ReviewItemId("missing"))

    def test_requires_running_execution(self) -> None:
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(SubtitleReviewDecisionError):
            self._record("item-0")

    def test_append_only_supersession(self) -> None:
        first = self._record("item-0", DecisionKind.ACCEPT).decision
        second = self._record(
            "item-0",
            DecisionKind.MODIFY,
            modified_text="corrected",
            identities=self._plan("decision-2", LATER),
            sequence=1,
            previous_decision_id=first.identity,
        ).decision
        self.assertEqual(second.previous_decision_id, first.identity)
        self.assertEqual(second.sequence, 1)

    def test_deterministic_construction(self) -> None:
        self.assertEqual(self._record("item-0"), self._record("item-0"))

    def test_record_without_persistence_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            self.service.record_decision(
                preparation_id=SubtitleReviewPreparationId("preparation"),
                review_item_id=ReviewItemId("item-0"),
                reviewer=HumanActorReference("reviewer"),
                kind=DecisionKind.ACCEPT,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
