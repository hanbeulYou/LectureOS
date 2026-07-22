import unittest

from lectureos.application import (
    SubtitleArtifactFormat,
    SubtitleMaterializationState,
    SubtitleSrtArtifact,
    SubtitleSrtMaterializationError,
    SubtitleSrtMaterializationIdentityPlan,
    SubtitleSrtMaterializationService,
)
from lectureos.application.identities import (
    SubtitleApprovedDocumentId,
    SubtitleSrtMaterializationId,
)
from lectureos.application.subtitle_srt_materialization import (
    MaterializationCollisionError,
    MaterializationWriteError,
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
ARTIFACT = ArtifactId("artifact")
PAYLOAD = "1\n00:00:00,000 --> 00:00:01,000\n첫 자막\n"


class _FakeArtifactQuery:
    def __init__(self, artifact) -> None:
        self._artifact = artifact

    def get(self, identity):
        if self._artifact is None:
            return None
        return self._artifact if identity == self._artifact.identity else None


class _FakeStore:
    def __init__(self) -> None:
        self.materializations = {}
        self.outcomes = {}
        self.results = {}

    def get(self, identity):
        return self.materializations.get(identity)

    def get_outcome(self, identity):
        return self.outcomes.get(identity)

    def persist_materialization_intent(self, *, materialization, materialization_result):
        if materialization.identity in self.materializations:
            raise ValueError("materialization identity already exists")
        self.materializations[materialization.identity] = materialization
        self.results[materialization_result.identity] = materialization_result

    def persist_materialization_outcome(self, *, outcome):
        if outcome.materialization_id not in self.materializations:
            raise ValueError("outcome must reference an existing materialization")
        if outcome.materialization_id in self.outcomes:
            raise ValueError("outcome already exists")
        self.outcomes[outcome.materialization_id] = outcome


class _FakeWriter:
    def __init__(self) -> None:
        self.files = {}
        self.fail_write = False

    def write(self, *, relative_location, content):
        if self.fail_write:
            raise MaterializationWriteError("simulated disk failure")
        existing = self.files.get(relative_location)
        if existing is not None:
            if existing == content:
                return len(content)
            raise MaterializationCollisionError("different bytes present")
        self.files[relative_location] = content
        return len(content)

    def read(self, *, relative_location):
        return self.files.get(relative_location)


def _artifact(payload=PAYLOAD):
    return SubtitleSrtArtifact(
        identity=ARTIFACT,
        domain_result_id=DomainResultId("artifact-result"),
        source_approved_document_id=SubtitleApprovedDocumentId("document"),
        format=SubtitleArtifactFormat.SRT,
        payload=payload,
        byte_length=len(payload.encode("utf-8")),
        cue_count=1 if payload else 0,
        encoding="utf-8",
        source_media_id=MEDIA,
        source_timeline_id=TIMELINE,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="generated",
    )


class SubtitleSrtMaterializationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="materialization",
                capabilities=(CapabilityReference("subtitle.export"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("materialization"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.store = _FakeStore()
        self.writer = _FakeWriter()

    def _service(self, artifact=None):
        return SubtitleSrtMaterializationService(
            _FakeArtifactQuery(_artifact() if artifact is None else artifact),
            self.store,
            self.execution,
            self.writer,
            self.store,
        )

    def _plan(self, name="mat"):
        return SubtitleSrtMaterializationIdentityPlan(
            materialization_id=SubtitleSrtMaterializationId(name),
            materialization_result_id=DomainResultId(f"{name}-result"),
        )

    def _record(self, service, name="mat"):
        return service.record_materialization(
            source_artifact_id=ARTIFACT,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=self._plan(name),
        )

    def test_record_first_success_materializes(self) -> None:
        record = self._record(self._service())
        self.assertIs(record.outcome.state, SubtitleMaterializationState.MATERIALIZED)
        self.assertEqual(record.outcome.byte_length, len(PAYLOAD.encode("utf-8")))
        # file written with exact bytes
        self.assertEqual(self.writer.files["mat.srt"], PAYLOAD.encode("utf-8"))
        # intent persisted before outcome; DomainResult chained to the artifact
        intent = self.store.get(SubtitleSrtMaterializationId("mat"))
        self.assertEqual(intent.source_artifact_id, ARTIFACT)
        result = self.store.results[DomainResultId("mat-result")]
        self.assertEqual(result.kind, "subtitle_srt_materialization")
        self.assertEqual(result.upstream_results, (DomainResultId("artifact-result"),))

    def test_intent_is_durable_before_write(self) -> None:
        # a write failure still leaves a durable PENDING intent + a FAILED outcome
        self.writer.fail_write = True
        record = self._record(self._service())
        self.assertIs(record.outcome.state, SubtitleMaterializationState.FAILED)
        self.assertIsNotNone(self.store.get(SubtitleSrtMaterializationId("mat")))
        self.assertNotIn("mat.srt", self.writer.files)

    def test_empty_artifact_payload_materializes_zero_bytes(self) -> None:
        record = self._record(self._service(artifact=_artifact(payload="")))
        self.assertIs(record.outcome.state, SubtitleMaterializationState.MATERIALIZED)
        self.assertEqual(record.outcome.byte_length, 0)
        self.assertEqual(self.writer.files["mat.srt"], b"")

    def test_unknown_artifact_raises(self) -> None:
        service = SubtitleSrtMaterializationService(
            _FakeArtifactQuery(None), self.store, self.execution, self.writer, self.store
        )
        with self.assertRaises(KeyError):
            self._record(service)

    def test_requires_running_execution(self) -> None:
        service = self._service()
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(SubtitleSrtMaterializationError):
            self._record(service)

    def test_different_bytes_collision_is_failed(self) -> None:
        self.writer.files["mat.srt"] = b"pre-existing different bytes"
        record = self._record(self._service())
        self.assertIs(record.outcome.state, SubtitleMaterializationState.FAILED)
        self.assertIn("Collision", record.outcome.failure_reason)
        # original file untouched
        self.assertEqual(self.writer.files["mat.srt"], b"pre-existing different bytes")

    def test_identical_bytes_is_idempotent_materialized(self) -> None:
        self.writer.files["mat.srt"] = PAYLOAD.encode("utf-8")
        record = self._record(self._service())
        self.assertIs(record.outcome.state, SubtitleMaterializationState.MATERIALIZED)

    def test_duplicate_identity_returns_existing_record(self) -> None:
        service = self._service()
        first = self._record(service)
        second = self._record(service)
        self.assertEqual(first.materialization, second.materialization)
        self.assertEqual(first.outcome, second.outcome)
        self.assertEqual(len(self.store.materializations), 1)

    def test_dangling_pending_is_completed_on_retry(self) -> None:
        # simulate a crash after intent commit but before outcome: persist only the intent
        service = self._service()
        prepared_plan = self._plan()
        artifact = _artifact()
        from lectureos.application.subtitle_srt_materialization import (
            SubtitleSrtMaterialization,
            SubtitleMaterializationStorageKind,
        )
        from lectureos.execution.models import DomainResultReference

        intent = SubtitleSrtMaterialization(
            identity=prepared_plan.materialization_id,
            domain_result_id=prepared_plan.materialization_result_id,
            source_artifact_id=ARTIFACT,
            storage_kind=SubtitleMaterializationStorageKind.LOCAL_FILE,
            relative_location="mat.srt",
            source_media_id=MEDIA,
            source_timeline_id=TIMELINE,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="pending",
        )
        self.store.persist_materialization_intent(
            materialization=intent,
            materialization_result=DomainResultReference(
                identity=prepared_plan.materialization_result_id,
                kind="subtitle_srt_materialization",
                source_media=MEDIA,
                source_timeline=TIMELINE,
                upstream_results=(artifact.domain_result_id,),
            ),
        )
        self.assertIsNone(self.store.get_outcome(prepared_plan.materialization_id))
        record = self._record(service)
        self.assertIs(record.outcome.state, SubtitleMaterializationState.MATERIALIZED)

    def test_reconcile_matching_file_completes_materialized(self) -> None:
        self._persist_only_intent("mat.srt")
        self.writer.files["mat.srt"] = PAYLOAD.encode("utf-8")
        record = self._service().reconcile_materialization(
            materialization_id=SubtitleSrtMaterializationId("mat")
        )
        self.assertIs(record.outcome.state, SubtitleMaterializationState.MATERIALIZED)

    def test_reconcile_different_file_fails(self) -> None:
        self._persist_only_intent("mat.srt")
        self.writer.files["mat.srt"] = b"different"
        record = self._service().reconcile_materialization(
            materialization_id=SubtitleSrtMaterializationId("mat")
        )
        self.assertIs(record.outcome.state, SubtitleMaterializationState.FAILED)

    def test_reconcile_absent_file_writes_and_materializes(self) -> None:
        self._persist_only_intent("mat.srt")
        record = self._service().reconcile_materialization(
            materialization_id=SubtitleSrtMaterializationId("mat")
        )
        self.assertIs(record.outcome.state, SubtitleMaterializationState.MATERIALIZED)
        self.assertEqual(self.writer.files["mat.srt"], PAYLOAD.encode("utf-8"))

    def test_reconcile_already_terminal_returns(self) -> None:
        service = self._service()
        self._record(service)
        record = service.reconcile_materialization(
            materialization_id=SubtitleSrtMaterializationId("mat")
        )
        self.assertIs(record.outcome.state, SubtitleMaterializationState.MATERIALIZED)

    def test_reconcile_unknown_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._service().reconcile_materialization(
                materialization_id=SubtitleSrtMaterializationId("missing")
            )

    def _persist_only_intent(self, relative_location) -> None:
        from lectureos.application.subtitle_srt_materialization import (
            SubtitleSrtMaterialization,
            SubtitleMaterializationStorageKind,
        )
        from lectureos.execution.models import DomainResultReference

        intent = SubtitleSrtMaterialization(
            identity=SubtitleSrtMaterializationId("mat"),
            domain_result_id=DomainResultId("mat-result"),
            source_artifact_id=ARTIFACT,
            storage_kind=SubtitleMaterializationStorageKind.LOCAL_FILE,
            relative_location=relative_location,
            source_media_id=MEDIA,
            source_timeline_id=TIMELINE,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            sequence=0,
            reason="pending",
        )
        self.store.persist_materialization_intent(
            materialization=intent,
            materialization_result=DomainResultReference(
                identity=DomainResultId("mat-result"),
                kind="subtitle_srt_materialization",
                source_media=MEDIA,
                source_timeline=TIMELINE,
                upstream_results=(DomainResultId("artifact-result"),),
            ),
        )


if __name__ == "__main__":
    unittest.main()
