import inspect
import unittest

from lectureos.application import (
    CorrectionCandidateIdentityPlan,
    CorrectionGenerationFailure,
    CorrectionGenerationIdentityPlan,
    CorrectionGenerationRequest,
    CorrectionProposal,
    CorrectionSegmentContext,
)
from lectureos.application import transcript_correction_generation as contract
from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    PluginReference,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)


class RecordingCorrectionCapability:
    def __init__(self, proposals=(), error=None) -> None:
        self.proposals = proposals
        self.error = error
        self.requests = []

    def generate_corrections(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.proposals


class TranscriptCorrectionGenerationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.segment = CorrectionSegmentContext(
            identity=TranscriptSegmentId("segment"),
            text="source text",
            source_order=0,
            source_timeline_id=SourceTimelineId("timeline"),
            start=1.0,
            end=2.0,
            speaker_label="teacher",
            confidence=0.8,
            uncertainty=0.2,
        )
        self.request = CorrectionGenerationRequest(
            transcript_id=TranscriptId("transcript"),
            parent_revision_id=None,
            source_media_id=SourceMediaId("media"),
            source_timeline_id=SourceTimelineId("timeline"),
            run_id=ProcessingRunId("run"),
            unit_execution_id=UnitExecutionId("execution"),
            capability=CapabilityReference("transcript.correction"),
            segments=(self.segment,),
        )
        self.proposal = CorrectionProposal(
            target_segment_id=self.segment.identity,
            proposed_text="corrected text",
            rationale="recognition correction",
            evidence=("glossary", "source audio"),
            confidence=0.9,
            uncertainty=0.1,
            capability=self.request.capability,
            plugin_reference=PluginReference("opaque-plugin"),
            provider_reference="opaque-provider:model",
        )

    def test_request_and_proposal_preserve_provider_neutral_values(self) -> None:
        capability = RecordingCorrectionCapability((self.proposal,))
        self.assertEqual(capability.generate_corrections(self.request), (self.proposal,))
        self.assertEqual(capability.requests, [self.request])
        self.assertEqual(self.request.segments, (self.segment,))
        self.assertEqual(self.proposal.evidence, ("glossary", "source audio"))

    def test_contract_supports_explicit_failure_without_fallback(self) -> None:
        failure = CorrectionGenerationFailure("unavailable")
        capability = RecordingCorrectionCapability(error=failure)
        with self.assertRaises(CorrectionGenerationFailure):
            capability.generate_corrections(self.request)
        self.assertEqual(capability.requests, [self.request])

    def test_identity_plan_is_caller_owned_and_separate_from_proposal(self) -> None:
        plan = CorrectionGenerationIdentityPlan(
            candidates=(
                CorrectionCandidateIdentityPlan(
                    candidate_id=CorrectionCandidateId("candidate"),
                    candidate_result_id=DomainResultId("candidate-result"),
                    replacement_segment_id=TranscriptSegmentId("replacement"),
                ),
            ),
            revision_id=TranscriptRevisionId("revision"),
            revision_result_id=DomainResultId("revision-result"),
            validation_id=TranscriptValidationId("validation"),
        )
        self.assertEqual(len(plan.candidates), 1)
        self.assertFalse(hasattr(self.proposal, "candidate_id"))
        self.assertFalse(hasattr(self.proposal, "revision_id"))

    def test_application_contract_has_no_concrete_provider_or_storage_import(self) -> None:
        source = inspect.getsource(contract)
        for forbidden in ("sqlite3", "openai", "anthropic", "google.generativeai", "httpx"):
            self.assertNotIn(forbidden, source.lower())


if __name__ == "__main__":
    unittest.main()
