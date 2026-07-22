import unittest

from lectureos.application import (
    SubtitleApprovedDocument,
    SubtitleApprovedUnit,
    SubtitleApprovedUnitOrigin,
    SubtitleArtifactFormat,
    SubtitleArtifactGenerationError,
    SubtitleExportEligibility,
    SubtitleSrtArtifactGenerationService,
    SubtitleSrtArtifactIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleApprovedDocumentId,
    SubtitleApprovedUnitId,
    SubtitleCandidateId,
    SubtitleFinalSubtitleId,
    SubtitleReadingUnitId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleReadingRevisionId,
)
from lectureos.execution.identities import (
    ArtifactId,
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

MEDIA = SourceMediaId("media")
TIMELINE = SourceTimelineId("timeline")
DOCUMENT = SubtitleApprovedDocumentId("document")


class _FakeDocumentQuery:
    def __init__(self, document, units) -> None:
        self._document = document
        self._units = {unit.identity: unit for unit in units}

    def get(self, identity):
        return self._document if identity == self._document.identity else None

    def get_unit(self, identity):
        return self._units.get(identity)


def _unit(name, order, start, end, lines, *, origin=SubtitleApprovedUnitOrigin.ACCEPTED, final="f"):
    return SubtitleApprovedUnit(
        identity=SubtitleApprovedUnitId(name),
        document_id=DOCUMENT,
        source_timed_unit_id=SubtitleTimedUnitId(f"{name}-timed"),
        source_reading_unit_id=SubtitleReadingUnitId(f"{name}-reading"),
        origin=origin,
        display_order=order,
        start=start,
        end=end,
        lines=lines,
        source_final_subtitle_id=(
            None if origin is SubtitleApprovedUnitOrigin.UNTOUCHED else SubtitleFinalSubtitleId(final)
        ),
    )


def _document(unit_ids, eligibility=SubtitleExportEligibility.ELIGIBLE, reason=None):
    return SubtitleApprovedDocument(
        identity=DOCUMENT,
        domain_result_id=DomainResultId("document-result"),
        source_time_revision_id=SubtitleTimeRevisionId("time"),
        source_reading_revision_id=SubtitleReadingRevisionId("reading"),
        eligibility=eligibility,
        source_candidate_id=SubtitleCandidateId("candidate"),
        source_transcript_id=__import__(
            "lectureos.transcript.identities", fromlist=["TranscriptId"]
        ).TranscriptId("raw"),
        source_revision_id=__import__(
            "lectureos.transcript.identities", fromlist=["TranscriptRevisionId"]
        ).TranscriptRevisionId("transcript-revision"),
        source_media_id=MEDIA,
        source_timeline_id=TIMELINE,
        approved_unit_ids=tuple(unit_ids),
        omitted_unit_count=0,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="assembled",
        ineligibility_reason=reason,
    )


class SubtitleSrtArtifactGenerationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="srt-artifact",
                capabilities=(CapabilityReference("subtitle.export"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("srt-artifact"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )

    def _service(self, units, eligibility=SubtitleExportEligibility.ELIGIBLE, reason=None):
        document = _document([u.identity for u in units], eligibility, reason)
        return SubtitleSrtArtifactGenerationService(
            _FakeDocumentQuery(document, units), self.execution
        )

    def _plan(self):
        return SubtitleSrtArtifactIdentityPlan(
            artifact_id=ArtifactId("artifact"),
            artifact_result_id=DomainResultId("artifact-result"),
        )

    def _generate(self, service):
        return service.generate_artifact(
            source_approved_document_id=DOCUMENT,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(),
        )

    def test_serializes_ordered_cues(self) -> None:
        units = [
            _unit("a", 0, 0.0, 1.5, ("첫 자막",)),
            _unit("b", 1, 1.5, 3.0, ("둘째 줄1", "둘째 줄2"), origin=SubtitleApprovedUnitOrigin.MODIFIED),
        ]
        prepared = self._generate(self._service(units))
        artifact = prepared.artifact
        self.assertIs(artifact.format, SubtitleArtifactFormat.SRT)
        self.assertEqual(artifact.cue_count, 2)
        self.assertEqual(
            artifact.payload,
            "1\n00:00:00,000 --> 00:00:01,500\n첫 자막\n\n"
            "2\n00:00:01,500 --> 00:00:03,000\n둘째 줄1\n둘째 줄2\n",
        )
        self.assertEqual(artifact.byte_length, len(artifact.payload.encode("utf-8")))
        self.assertEqual(artifact.encoding, "utf-8")
        self.assertEqual(prepared.artifact_result.kind, "subtitle_srt_artifact")
        self.assertEqual(
            prepared.artifact_result.upstream_results, (DomainResultId("document-result"),)
        )
        self.assertEqual(prepared.artifact_result.source_media, MEDIA)

    def test_contiguous_numbering_and_order(self) -> None:
        units = [
            _unit("a", 0, 0.0, 1.0, ("A",)),
            _unit("b", 1, 1.0, 2.0, ("B",)),
            _unit("c", 2, 2.0, 3.0, ("C",)),
        ]
        payload = self._generate(self._service(units)).artifact.payload
        self.assertTrue(payload.startswith("1\n"))
        self.assertIn("\n\n2\n", payload)
        self.assertIn("\n\n3\n", payload)

    def test_timestamp_rounding_half_up(self) -> None:
        units = [_unit("a", 0, 0.0005, 1.0015, ("x",))]
        payload = self._generate(self._service(units)).artifact.payload
        # 0.0005s -> 1ms (half up), 1.0015s -> 1002ms (half up)
        self.assertIn("00:00:00,001 --> 00:00:01,002", payload)

    def test_empty_eligible_document_yields_empty_payload(self) -> None:
        prepared = self._generate(self._service([]))
        self.assertEqual(prepared.artifact.payload, "")
        self.assertEqual(prepared.artifact.byte_length, 0)
        self.assertEqual(prepared.artifact.cue_count, 0)

    def test_ineligible_document_is_rejected(self) -> None:
        service = self._service(
            [], eligibility=SubtitleExportEligibility.INELIGIBLE, reason="incomplete"
        )
        with self.assertRaises(SubtitleArtifactGenerationError):
            self._generate(service)

    def test_collapsed_duration_is_rejected(self) -> None:
        units = [_unit("a", 0, 1.0, 1.0, ("x",))]  # end == start -> collapses at ms
        with self.assertRaises(SubtitleArtifactGenerationError):
            self._generate(self._service(units))

    def test_unknown_document_raises(self) -> None:
        service = self._service([_unit("a", 0, 0.0, 1.0, ("x",))])
        with self.assertRaises(KeyError):
            service.generate_artifact(
                source_approved_document_id=SubtitleApprovedDocumentId("missing"),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )

    def test_requires_running_execution(self) -> None:
        service = self._service([_unit("a", 0, 0.0, 1.0, ("x",))])
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(SubtitleArtifactGenerationError):
            self._generate(service)

    def test_deterministic_construction(self) -> None:
        units = [_unit("a", 0, 0.0, 1.0, ("x",))]
        service = self._service(units)
        self.assertEqual(self._generate(service), self._generate(service))

    def test_record_without_persistence_raises(self) -> None:
        service = self._service([_unit("a", 0, 0.0, 1.0, ("x",))])
        with self.assertRaises(RuntimeError):
            service.record_generation(
                source_approved_document_id=DOCUMENT,
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=self._plan(),
            )


if __name__ == "__main__":
    unittest.main()
