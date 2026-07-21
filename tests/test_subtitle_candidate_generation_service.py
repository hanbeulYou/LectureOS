import unittest

from lectureos.application import (
    ReadinessOutcome,
    SubtitleCandidateGenerationError,
    SubtitleCandidateGenerationService,
    SubtitleCandidateIdentityPlan,
    SubtitleIntakeOutcome,
    SubtitleTranscriptIntake,
)
from lectureos.application.identities import (
    SubtitleCandidateCueId,
    SubtitleCandidateId,
    SubtitleTranscriptIntakeId,
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
from lectureos.execution.repositories import InMemoryRepository
from lectureos.execution.service import ExecutionService
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import (
    CorrectedTranscriptRevision,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)
from lectureos.transcript.service import TranscriptService


class SubtitleCandidateGenerationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.media_id = SourceMediaId("media")
        self.timeline_id = SourceTimelineId("timeline")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="candidate",
                capabilities=(CapabilityReference("subtitle.candidate"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("candidate"),
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
        self.segment_ids = (
            TranscriptSegmentId("segment-0"),
            TranscriptSegmentId("segment-1"),
        )
        self.raw = RawTranscript(
            identity=TranscriptId("raw"),
            domain_result_id=DomainResultId("raw-result"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            provider_result_id=provider.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=self.segment_ids,
        )
        self.segments = (
            TranscriptSegment(
                identity=self.segment_ids[0],
                transcript_id=self.raw.identity,
                source_timeline_id=self.timeline_id,
                text="one",
                source_order=0,
                start=0.0,
                end=1.0,
            ),
            TranscriptSegment(
                identity=self.segment_ids[1],
                transcript_id=self.raw.identity,
                source_timeline_id=self.timeline_id,
                text="two",
                source_order=1,
                start=1.0,
                end=2.0,
            ),
        )
        self.transcripts.register_provider_result(provider)
        self.transcripts.create_raw_transcript(self.raw, self.segments)
        self.revision = CorrectedTranscriptRevision(
            identity=TranscriptRevisionId("revision"),
            transcript_id=self.raw.identity,
            domain_result_id=DomainResultId("revision-result"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=self.segment_ids,
            parent_raw_transcript_id=self.raw.identity,
        )
        self.transcripts.create_corrected_revision(self.revision, self.segments)
        self.intakes = InMemoryRepository()
        self.service = SubtitleCandidateGenerationService(
            self.intakes, self.transcripts, self.execution
        )

    def _intake(
        self, name="intake", eligible=True, transcript_id=None, revision_id=None
    ) -> SubtitleTranscriptIntake:
        if eligible:
            readiness_outcome = ReadinessOutcome.READY
            outcome = SubtitleIntakeOutcome.ELIGIBLE
            reason = "ready transcript is eligible for subtitle work"
        else:
            readiness_outcome = ReadinessOutcome.NOT_READY
            outcome = SubtitleIntakeOutcome.NOT_ELIGIBLE
            reason = "transcript is not ready"
        record = SubtitleTranscriptIntake(
            identity=SubtitleTranscriptIntakeId(name),
            domain_result_id=DomainResultId(f"{name}-result"),
            source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
            readiness_outcome=readiness_outcome,
            outcome=outcome,
            source_selection_id=TranscriptCurrentSelectionId("selection"),
            source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
            source_decision_id=TranscriptReviewDecisionId("decision"),
            review_item_id=ReviewItemId("item-0"),
            candidate_reference_id=CandidateReferenceId("candidate-0"),
            source_transcript_id=transcript_id or self.raw.identity,
            source_revision_id=revision_id or self.revision.identity,
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            validation_id=TranscriptValidationId("validation"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason=reason,
        )
        self.intakes.save(record)
        return record

    def _plan(self, name="candidate", cues=2) -> SubtitleCandidateIdentityPlan:
        return SubtitleCandidateIdentityPlan(
            candidate_id=SubtitleCandidateId(name),
            candidate_result_id=DomainResultId(f"{name}-result"),
            cue_ids=tuple(SubtitleCandidateCueId(f"cue-{i}") for i in range(cues)),
        )

    def _generate(self, intake, **overrides):
        base = dict(
            source_intake_id=intake.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )
        base.update(overrides)
        return self.service.generate_candidate(**base)

    def test_eligible_generates_one_cue_per_segment_with_lineage(self) -> None:
        intake = self._intake()
        prepared = self._generate(intake)
        candidate = prepared.candidate
        self.assertEqual(len(prepared.cues), 2)
        self.assertEqual(candidate.cue_ids, tuple(c.identity for c in prepared.cues))
        self.assertEqual(candidate.source_intake_id, intake.identity)
        self.assertEqual(candidate.source_revision_id, self.revision.identity)
        self.assertEqual(candidate.source_transcript_id, self.raw.identity)
        self.assertEqual(candidate.source_media_id, self.media_id)
        self.assertEqual(candidate.source_timeline_id, self.timeline_id)
        self.assertEqual(candidate.validation_id, TranscriptValidationId("validation"))
        self.assertEqual(candidate.review_item_id, ReviewItemId("item-0"))
        self.assertEqual(
            candidate.candidate_reference_id, CandidateReferenceId("candidate-0")
        )
        # cues ordered, each traceable to its own source segment and timeline range
        self.assertEqual(
            [cue.source_segment_ids for cue in prepared.cues],
            [(self.segment_ids[0],), (self.segment_ids[1],)],
        )
        self.assertEqual([cue.display_order for cue in prepared.cues], [0, 1])
        self.assertEqual([cue.text for cue in prepared.cues], ["one", "two"])
        self.assertEqual((prepared.cues[0].start, prepared.cues[0].end), (0.0, 1.0))
        self.assertEqual(
            prepared.candidate_result.kind, "subtitle_candidate"
        )
        self.assertEqual(
            prepared.candidate_result.upstream_results, (intake.domain_result_id,)
        )

    def test_untimed_segments_produce_untimed_cues(self) -> None:
        untimed_ids = (
            TranscriptSegmentId("untimed-0"),
            TranscriptSegmentId("untimed-1"),
        )
        raw = RawTranscript(
            identity=TranscriptId("raw-untimed"),
            domain_result_id=DomainResultId("raw-untimed-result"),
            source_media_id=self.media_id,
            source_timeline_id=self.timeline_id,
            provider_result_id=ProviderTranscriptResultId("provider"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=untimed_ids,
        )
        untimed = (
            TranscriptSegment(
                identity=untimed_ids[0],
                transcript_id=raw.identity,
                source_timeline_id=None,
                text="one",
                source_order=0,
            ),
            TranscriptSegment(
                identity=untimed_ids[1],
                transcript_id=raw.identity,
                source_timeline_id=None,
                text="two",
                source_order=1,
            ),
        )
        # A revision whose segments are untimed still yields cues (time traceable "when possible").
        revision = CorrectedTranscriptRevision(
            identity=TranscriptRevisionId("revision-untimed"),
            transcript_id=raw.identity,
            domain_result_id=DomainResultId("revision-untimed-result"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=untimed_ids,
            parent_raw_transcript_id=raw.identity,
        )
        self.transcripts.create_raw_transcript(raw, untimed)
        self.transcripts.create_corrected_revision(revision, untimed)
        intake = self._intake(
            name="intake-untimed",
            transcript_id=raw.identity,
            revision_id=revision.identity,
        )
        prepared = self._generate(intake)
        self.assertIsNone(prepared.cues[0].start)
        self.assertIsNone(prepared.cues[0].source_timeline_id)

    def test_not_eligible_intake_is_refused(self) -> None:
        intake = self._intake(name="not-eligible", eligible=False)
        with self.assertRaises(SubtitleCandidateGenerationError):
            self._generate(intake)

    def test_identity_plan_cue_count_must_match(self) -> None:
        intake = self._intake()
        with self.assertRaises(SubtitleCandidateGenerationError):
            self._generate(intake, identities=self._plan(cues=1))

    def test_unknown_intake_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.service.generate_candidate(
                source_intake_id=SubtitleTranscriptIntakeId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_requires_running_execution(self) -> None:
        intake = self._intake()
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(SubtitleCandidateGenerationError):
            self._generate(intake)

    def test_deterministic_construction(self) -> None:
        intake = self._intake()
        self.assertEqual(self._generate(intake), self._generate(intake))

    def test_record_without_persistence_raises(self) -> None:
        intake = self._intake()
        with self.assertRaises(RuntimeError):
            self.service.record_candidate(
                source_intake_id=intake.identity,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
