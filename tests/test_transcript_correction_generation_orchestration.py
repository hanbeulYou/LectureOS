import unittest
from dataclasses import replace

from lectureos.application import (
    CorrectionCandidateIdentityPlan,
    CorrectionGenerationIdentityPlan,
    CorrectionGenerationRequest,
    CorrectionProposal,
    TranscriptCorrectionGenerationError,
    TranscriptCorrectionGenerationService,
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
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptApplicability,
    TranscriptSegment,
)
from lectureos.transcript.service import TranscriptService


class FakeCorrectionCapability:
    def __init__(self, proposals=(), error=None) -> None:
        self.proposals = proposals
        self.error = error
        self.requests = []

    def generate_corrections(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.proposals


class TranscriptCorrectionGenerationOrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.unit_id = ProcessingUnitId("unit")
        self.media_id = SourceMediaId("media")
        self.timeline_id = SourceTimelineId("timeline")
        self.capability = CapabilityReference("transcript.correction")
        self.execution = ExecutionService()
        self.execution.register_unit(
            ProcessingUnit(
                identity=self.unit_id,
                purpose="correct transcript",
                capabilities=(self.capability,),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("correct transcript"),
            working_context=WorkingContextReference("context"),
            unit_ids=(self.unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id,
            run_id=self.run_id,
            unit_id=self.unit_id,
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
            segment_ids=(TranscriptSegmentId("segment-b"), TranscriptSegmentId("segment-a")),
        )
        self.segments = (
            TranscriptSegment(
                identity=self.raw.segment_ids[0],
                transcript_id=self.raw.identity,
                source_timeline_id=self.timeline_id,
                text="wrong one",
                source_order=0,
                start=0.0,
                end=1.0,
                speaker_label="teacher",
                confidence=0.5,
                uncertainty=0.5,
            ),
            TranscriptSegment(
                identity=self.raw.segment_ids[1],
                transcript_id=self.raw.identity,
                source_timeline_id=self.timeline_id,
                text="wrong two",
                source_order=1,
                start=1.0,
                end=2.0,
            ),
        )
        self.transcripts.register_provider_result(provider)
        self.transcripts.create_raw_transcript(self.raw, self.segments)

    def _plan(self, count=2):
        return CorrectionGenerationIdentityPlan(
            candidates=tuple(
                CorrectionCandidateIdentityPlan(
                    candidate_id=CorrectionCandidateId(f"candidate-{index}"),
                    candidate_result_id=DomainResultId(f"candidate-result-{index}"),
                    replacement_segment_id=TranscriptSegmentId(f"replacement-{index}"),
                )
                for index in range(count)
            ),
            revision_id=TranscriptRevisionId("revision"),
            revision_result_id=DomainResultId("revision-result"),
            validation_id=TranscriptValidationId("validation"),
        )

    def _proposals(self):
        return (
            CorrectionProposal(
                target_segment_id=self.segments[1].identity,
                proposed_text="correct two",
                rationale="terminology",
                evidence=("glossary",),
                uncertainty=0.2,
            ),
            CorrectionProposal(
                target_segment_id=self.segments[0].identity,
                proposed_text="correct one",
                rationale="recognition",
                confidence=0.9,
            ),
        )

    def test_prepares_exact_canonical_records_without_persisting(self) -> None:
        provider = FakeCorrectionCapability(self._proposals())
        service = TranscriptCorrectionGenerationService(
            self.transcripts, self.execution, provider
        )
        prepared = service.prepare_correction(
            transcript_id=self.raw.identity,
            parent_revision_id=None,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=self.capability,
            identities=self._plan(),
        )

        self.assertEqual(len(provider.requests), 1)
        self.assertIsInstance(provider.requests[0], CorrectionGenerationRequest)
        self.assertEqual(
            tuple(segment.identity for segment in provider.requests[0].segments),
            self.raw.segment_ids,
        )
        self.assertEqual(
            tuple(candidate.segment_id for candidate in prepared.candidates),
            (self.segments[1].identity, self.segments[0].identity),
        )
        self.assertEqual(
            prepared.revision.segment_ids,
            (TranscriptSegmentId("replacement-1"), TranscriptSegmentId("replacement-0")),
        )
        self.assertEqual(
            prepared.revision.correction_candidate_ids,
            (CorrectionCandidateId("candidate-0"), CorrectionCandidateId("candidate-1")),
        )
        self.assertIsNone(prepared.revision.decision_reference)
        self.assertIsNone(prepared.revision.validation_id)
        self.assertIs(prepared.revision.applicability, TranscriptApplicability.UNDETERMINED)
        self.assertEqual(
            tuple(result.upstream_results for result in prepared.candidate_results),
            ((self.raw.domain_result_id,), (self.raw.domain_result_id,)),
        )
        self.assertEqual(
            prepared.revision_result.upstream_results, (self.raw.domain_result_id,)
        )
        self.assertIsNone(
            self.transcripts.get_candidate(CorrectionCandidateId("candidate-0"))
        )
        self.assertIsNone(
            self.transcripts.get_corrected_revision(TranscriptRevisionId("revision"))
        )

    def test_zero_proposals_is_explicit_no_op(self) -> None:
        provider = FakeCorrectionCapability(())
        prepared = TranscriptCorrectionGenerationService(
            self.transcripts, self.execution, provider
        ).prepare_correction(
            transcript_id=self.raw.identity,
            parent_revision_id=None,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=self.capability,
            identities=self._plan(0),
        )
        self.assertEqual(prepared.candidates, ())
        self.assertIsNone(prepared.revision)
        self.assertIsNone(prepared.validation_id)

    def test_rejects_duplicate_unknown_blank_and_mismatched_capability(self) -> None:
        invalid_sets = (
            (self._proposals()[0], replace(self._proposals()[0], proposed_text="other")),
            (replace(self._proposals()[0], target_segment_id=TranscriptSegmentId("missing")),),
            (replace(self._proposals()[0], proposed_text=" "),),
            (replace(self._proposals()[0], capability=CapabilityReference("other")),),
        )
        for proposals in invalid_sets:
            with self.subTest(proposals=proposals):
                provider = FakeCorrectionCapability(proposals)
                service = TranscriptCorrectionGenerationService(
                    self.transcripts, self.execution, provider
                )
                with self.assertRaises(TranscriptCorrectionGenerationError):
                    service.prepare_correction(
                        transcript_id=self.raw.identity,
                        parent_revision_id=None,
                        run_id=self.run_id,
                        unit_execution_id=self.execution_id,
                        capability=self.capability,
                        identities=self._plan(len(proposals)),
                    )
                self.assertEqual(len(provider.requests), 1)

    def test_provider_failure_propagates_and_preconditions_precede_invocation(self) -> None:
        error = RuntimeError("provider unavailable")
        provider = FakeCorrectionCapability(error=error)
        service = TranscriptCorrectionGenerationService(
            self.transcripts, self.execution, provider
        )
        with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
            service.prepare_correction(
                transcript_id=self.raw.identity,
                parent_revision_id=None,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                capability=self.capability,
                identities=self._plan(),
            )
        self.assertEqual(len(provider.requests), 1)

        never_called = FakeCorrectionCapability(self._proposals())
        with self.assertRaises(KeyError):
            TranscriptCorrectionGenerationService(
                self.transcripts, self.execution, never_called
            ).prepare_correction(
                transcript_id=TranscriptId("missing"),
                parent_revision_id=None,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                capability=self.capability,
                identities=self._plan(),
            )
        self.assertEqual(never_called.requests, [])

    def test_duplicate_canonical_identity_plan_is_rejected(self) -> None:
        plan = self._plan()
        duplicate = replace(
            plan,
            candidates=(plan.candidates[0], plan.candidates[0]),
        )
        with self.assertRaisesRegex(
            TranscriptCorrectionGenerationError, "identity plan must be unique"
        ):
            TranscriptCorrectionGenerationService(
                self.transcripts,
                self.execution,
                FakeCorrectionCapability(self._proposals()),
            ).prepare_correction(
                transcript_id=self.raw.identity,
                parent_revision_id=None,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                capability=self.capability,
                identities=duplicate,
            )

    def test_parent_revision_context_and_lineage_are_preserved(self) -> None:
        parent = CorrectedTranscriptRevision(
            identity=TranscriptRevisionId("parent"),
            transcript_id=self.raw.identity,
            domain_result_id=DomainResultId("parent-result"),
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            segment_ids=self.raw.segment_ids,
            parent_raw_transcript_id=self.raw.identity,
        )
        self.transcripts.create_corrected_revision(parent, self.segments)
        proposal = self._proposals()[:1]
        prepared = TranscriptCorrectionGenerationService(
            self.transcripts,
            self.execution,
            FakeCorrectionCapability(proposal),
        ).prepare_correction(
            transcript_id=self.raw.identity,
            parent_revision_id=parent.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            capability=self.capability,
            identities=self._plan(1),
        )
        self.assertEqual(prepared.request.parent_revision_id, parent.identity)
        self.assertEqual(prepared.candidates[0].target_revision_id, parent.identity)
        self.assertEqual(prepared.revision.parent_revision_id, parent.identity)
        self.assertEqual(
            prepared.revision_result.upstream_results, (parent.domain_result_id,)
        )


if __name__ == "__main__":
    unittest.main()
