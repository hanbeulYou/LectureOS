import unittest

from lectureos.application import (
    EDIT_CANDIDATE_TYPE_REGISTRY,
    EditCandidateApplicationService,
    EditCandidateGenerationError,
    EditCandidateGenerationService,
    EditCandidateIdentityPlan,
    EditCandidateMalformedOutputError,
    EditCandidateProviderFailure,
    GeneratedProposal,
    GenerationOutcomeKind,
    is_registry_candidate_type,
    require_canonical_candidate_type,
)
from lectureos.application.analysis_finding import AnalysisFinding
from lectureos.application.identities import (
    AnalysisFindingId,
    EditCandidateId,
    EligibleAnalysisInputId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.application import LectureAnalysisEligibility
from lectureos.application.lecture_analysis_input import EligibleAnalysisInput
from lectureos.application.transcript_readiness_evaluation import ReadinessOutcome
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
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import CorrectedTranscriptRevision, TranscriptSegment

_MEDIA = SourceMediaId("media")
_TIMELINE = SourceTimelineId("timeline")
_INPUT_ID = EligibleAnalysisInputId("input")
_REVISION = TranscriptRevisionId("revision")


class _FakeFindingQuery:
    def __init__(self, finding):
        self._finding = finding

    def get(self, identity):
        if self._finding is not None and identity == self._finding.identity:
            return self._finding
        return None


class _FakeInputQuery:
    def __init__(self, eligible_input):
        self._input = eligible_input

    def get(self, identity):
        if self._input is not None and identity == self._input.identity:
            return self._input
        return None


class _FakeTranscriptQuery:
    def __init__(self, revision, segments):
        self._revision = revision
        self._segments = {s.identity: s for s in segments}

    def get_corrected_revision(self, identity):
        if self._revision is not None and identity == self._revision.identity:
            return self._revision
        return None

    def get_segment(self, identity):
        return self._segments.get(identity)


class _FakePort:
    def __init__(self, proposals=(), *, error=None):
        self._proposals = tuple(proposals)
        self._error = error
        self.calls = 0
        self.requests = []

    def generate_candidates(self, request):
        self.calls += 1
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return self._proposals


def _eligible_input():
    return EligibleAnalysisInput(
        identity=_INPUT_ID,
        domain_result_id=DomainResultId("input-result"),
        source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
        readiness_outcome=ReadinessOutcome.READY,
        eligibility=LectureAnalysisEligibility.ELIGIBLE,
        source_selection_id=TranscriptCurrentSelectionId("selection"),
        source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
        source_decision_id=TranscriptReviewDecisionId("decision"),
        review_item_id=ReviewItemId("item-0"),
        candidate_reference_id=CandidateReferenceId("candidate-0"),
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=_REVISION,
        source_media_id=_MEDIA,
        source_timeline_id=_TIMELINE,
        validation_id=TranscriptValidationId("validation"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="derived",
    )


def _finding(located=True):
    kwargs = dict(
        identity=AnalysisFindingId("finding"),
        domain_result_id=DomainResultId("finding-result"),
        source_input_id=_INPUT_ID,
        finding_type="low_educational_value",
        evidence="an off-topic aside appears mid-lecture",
        source_media_id=_MEDIA,
        source_timeline_id=_TIMELINE,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
    )
    if located:
        kwargs.update(range_start=1.0, range_end=2.0)
    return AnalysisFinding(**kwargs)


def _segments():
    return (
        TranscriptSegment(
            identity=TranscriptSegmentId("seg-0"),
            transcript_id=TranscriptId("raw"),
            source_timeline_id=_TIMELINE,
            text="line 0",
            source_order=0,
            start=0.0,
            end=1.0,
        ),
        TranscriptSegment(
            identity=TranscriptSegmentId("seg-1"),
            transcript_id=TranscriptId("raw"),
            source_timeline_id=_TIMELINE,
            text="line 1",
            source_order=1,
            start=1.0,
            end=2.0,
        ),
        TranscriptSegment(
            identity=TranscriptSegmentId("seg-far"),
            transcript_id=TranscriptId("raw"),
            source_timeline_id=_TIMELINE,
            text="far away",
            source_order=2,
            start=500.0,
            end=501.0,
        ),
    )


def _revision():
    return CorrectedTranscriptRevision(
        identity=_REVISION,
        transcript_id=TranscriptId("raw"),
        domain_result_id=DomainResultId("revision-result"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        segment_ids=(
            TranscriptSegmentId("seg-0"),
            TranscriptSegmentId("seg-1"),
            TranscriptSegmentId("seg-far"),
        ),
        parent_raw_transcript_id=TranscriptId("raw"),
    )


def _proposal(candidate_type="non_lecture_region", start=1.0, end=2.0, rationale="grounded reason"):
    return GeneratedProposal(
        candidate_type=candidate_type,
        rationale=rationale,
        range_start=start,
        range_end=end,
    )


class _RecordingAdmission:
    """Captures the normalized result and identity plan handed to the real admission service."""

    def __init__(self, inner):
        self._inner = inner
        self.calls = 0
        self.last_result = None

    def record_candidates(self, **kwargs):
        self.calls += 1
        self.last_result = kwargs["result"]
        return self._inner.record_candidates(**kwargs)


class EditCandidateGenerationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="edit-candidate-generation",
                capabilities=(CapabilityReference("lecture.edit_candidate"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("edit-candidate-generation"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.candidates = InMemoryRepository()
        self.finding = _finding()

    def _service(self, port, *, finding=None, admission=None):
        finding = finding if finding is not None else self.finding
        candidate_persist = _InMemoryCandidatePersistence(self.candidates)
        real_admission = EditCandidateApplicationService(
            _FakeFindingQuery(finding), self.execution, candidate_persist
        )
        admission = admission if admission is not None else real_admission
        return EditCandidateGenerationService(
            _FakeFindingQuery(finding),
            _FakeInputQuery(_eligible_input()),
            _FakeTranscriptQuery(_revision(), _segments()),
            self.execution,
            port,
            admission,
            context_window_seconds=15.0,
        )

    def _generate(self, service, **overrides):
        base = dict(
            source_finding_id=self.finding.identity,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identity_planner=_default_planner,
        )
        base.update(overrides)
        return service.generate(**base)

    # -- registry --------------------------------------------------------
    def test_registry_has_exactly_three_keys(self) -> None:
        self.assertEqual(
            EDIT_CANDIDATE_TYPE_REGISTRY,
            frozenset({"non_lecture_region", "redundant_restatement", "delivery_concern"}),
        )

    def test_registry_rejects_canonical_looking_non_registry_key(self) -> None:
        # A structurally valid canonical open key that is not in the provider registry.
        self.assertEqual(require_canonical_candidate_type("terminology_drift"), "terminology_drift")
        self.assertFalse(is_registry_candidate_type("terminology_drift"))

    def test_registry_rejects_provider_native_label(self) -> None:
        for junk in ("Remove", "REMOVE", "remove clip", "delete", "condense"):
            self.assertFalse(is_registry_candidate_type(junk))

    # -- outcomes --------------------------------------------------------
    def test_all_valid_success(self) -> None:
        port = _FakePort((_proposal("non_lecture_region"), _proposal("delivery_concern", 1.0, 1.5)))
        outcome = self._generate(self._service(port))
        self.assertIs(outcome.kind, GenerationOutcomeKind.ALL_VALID)
        self.assertEqual(len(outcome.admitted.candidates), 2)
        self.assertEqual(outcome.rejected, ())
        self.assertEqual([c.candidate.candidate_type for c in outcome.admitted.candidates],
                         ["non_lecture_region", "delivery_concern"])

    def test_zero_proposal_success_creates_no_candidates(self) -> None:
        port = _FakePort(())
        outcome = self._generate(self._service(port))
        self.assertIs(outcome.kind, GenerationOutcomeKind.NO_CANDIDATE)
        self.assertIsNone(outcome.admitted)
        self.assertEqual(len(self.candidates.all()), 0)

    def test_partial_success(self) -> None:
        port = _FakePort((_proposal("non_lecture_region"), _proposal("Bad Type", 1.0, 1.5)))
        outcome = self._generate(self._service(port))
        self.assertIs(outcome.kind, GenerationOutcomeKind.PARTIAL_SUCCESS)
        self.assertEqual(len(outcome.admitted.candidates), 1)
        self.assertEqual(len(outcome.rejected), 1)
        self.assertEqual(outcome.rejected[0].failure_category, "unknown_candidate_type")
        self.assertEqual(outcome.rejected[0].source_index, 1)

    def test_all_invalid_normalization_failure(self) -> None:
        port = _FakePort((_proposal("Bad", 1.0, 1.5), _proposal("non_lecture_region", rationale="  ")))
        outcome = self._generate(self._service(port))
        self.assertIs(outcome.kind, GenerationOutcomeKind.NORMALIZATION_FAILURE)
        self.assertIsNone(outcome.admitted)
        self.assertEqual(len(outcome.rejected), 2)
        self.assertEqual(len(self.candidates.all()), 0)

    def test_provider_failure_outcome(self) -> None:
        port = _FakePort(error=EditCandidateProviderFailure("timeout"))
        outcome = self._generate(self._service(port))
        self.assertIs(outcome.kind, GenerationOutcomeKind.PROVIDER_FAILURE)
        self.assertIsNone(outcome.admitted)
        self.assertEqual(len(self.candidates.all()), 0)

    def test_malformed_output_outcome(self) -> None:
        port = _FakePort(error=EditCandidateMalformedOutputError("bad json"))
        outcome = self._generate(self._service(port))
        self.assertIs(outcome.kind, GenerationOutcomeKind.MALFORMED_OUTPUT)
        self.assertIsNone(outcome.admitted)

    def test_provider_failure_is_not_no_candidate(self) -> None:
        self.assertIsNot(
            self._generate(self._service(_FakePort(error=EditCandidateProviderFailure("x")))).kind,
            GenerationOutcomeKind.NO_CANDIDATE,
        )

    # -- range / context -------------------------------------------------
    def test_range_out_of_context_is_rejected(self) -> None:
        # window = [max(0, 1-15), 2+15] = [0, 17]; a range beyond 17 is out of context.
        port = _FakePort((_proposal("non_lecture_region", 100.0, 101.0),))
        outcome = self._generate(self._service(port))
        self.assertIs(outcome.kind, GenerationOutcomeKind.NORMALIZATION_FAILURE)
        self.assertEqual(outcome.rejected[0].failure_category, "range_out_of_context")

    def test_invalid_range_is_rejected(self) -> None:
        port = _FakePort((_proposal("non_lecture_region", 2.0, 1.0),))
        outcome = self._generate(self._service(port))
        self.assertEqual(outcome.rejected[0].failure_category, "invalid_range")

    def test_zero_duration_range_is_accepted(self) -> None:
        port = _FakePort((_proposal("delivery_concern", 1.5, 1.5),))
        outcome = self._generate(self._service(port))
        self.assertIs(outcome.kind, GenerationOutcomeKind.ALL_VALID)

    def test_bounded_context_excludes_far_segments(self) -> None:
        port = _FakePort((_proposal("non_lecture_region"),))
        self._generate(self._service(port))
        request = port.requests[0]
        # only the two overlapping segments, not the far one
        self.assertEqual(len(request.context_segments), 2)
        self.assertTrue(all(seg.start < 100 for seg in request.context_segments))

    def test_no_usable_context_yields_no_candidate_without_provider_call(self) -> None:
        port = _FakePort((_proposal("non_lecture_region"),))
        outcome = self._generate(self._service(port, finding=_finding(located=False)))
        self.assertIs(outcome.kind, GenerationOutcomeKind.NO_CANDIDATE)
        self.assertEqual(port.calls, 0)

    def test_request_carries_no_canonical_identity(self) -> None:
        port = _FakePort((_proposal("non_lecture_region"),))
        self._generate(self._service(port))
        request = port.requests[0]
        self.assertFalse(hasattr(request, "finding_id"))
        self.assertFalse(hasattr(request, "source_media_id"))
        for seg in request.context_segments:
            self.assertFalse(hasattr(seg, "identity"))

    # -- service preconditions ------------------------------------------
    def test_unknown_finding_raises(self) -> None:
        port = _FakePort(())
        with self.assertRaises(KeyError):
            self._generate(self._service(port), source_finding_id=AnalysisFindingId("missing"))

    def test_non_running_execution_raises(self) -> None:
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(EditCandidateGenerationError):
            self._generate(self._service(_FakePort((_proposal(),))))

    def test_provider_called_exactly_once(self) -> None:
        port = _FakePort((_proposal("non_lecture_region"),))
        self._generate(self._service(port))
        self.assertEqual(port.calls, 1)

    def test_no_identity_consumed_on_zero_candidate(self) -> None:
        consumed = []

        def counting_planner(count):
            consumed.append(count)
            return _default_planner(count)

        port = _FakePort(())
        self._generate(self._service(port), identity_planner=counting_planner)
        self.assertEqual(consumed, [])

    def test_admission_failure_outcome(self) -> None:
        from lectureos.persistence.errors import PersistenceIdentityCollisionError

        class _FailingAdmission:
            def record_candidates(self, **kwargs):
                raise PersistenceIdentityCollisionError("identity already exists")

        port = _FakePort((_proposal("non_lecture_region"),))
        outcome = self._generate(self._service(port, admission=_FailingAdmission()))
        self.assertIs(outcome.kind, GenerationOutcomeKind.ADMISSION_FAILURE)
        self.assertIsNone(outcome.admitted)

    def test_normalized_result_carries_only_valid_registry_types(self) -> None:
        real = EditCandidateApplicationService(
            _FakeFindingQuery(self.finding),
            self.execution,
            _InMemoryCandidatePersistence(self.candidates),
        )
        recording = _RecordingAdmission(real)
        port = _FakePort((_proposal("non_lecture_region"), _proposal("Bad", 1.0, 1.5)))
        self._generate(self._service(port, admission=recording))
        self.assertEqual(recording.calls, 1)
        self.assertEqual(
            [c.candidate_type for c in recording.last_result.candidates],
            ["non_lecture_region"],
        )


# --- minimal in-memory candidate persistence for the admission service ---
class _InMemoryCandidatePersistence:
    def __init__(self, store):
        self._store = store

    def persist_edit_candidates(self, *, prepared):
        for record in prepared:
            self._store.save(record.candidate)


def _default_planner(count):
    return tuple(
        EditCandidateIdentityPlan(
            candidate_id=EditCandidateId(f"cand-{i}"),
            candidate_result_id=DomainResultId(f"cand-{i}-result"),
        )
        for i in range(count)
    )


if __name__ == "__main__":
    unittest.main()
