import copy
import unittest
from pathlib import Path

from lectureos.application import (
    EditExportArtifact,
    EditExportArtifactEntry,
    EditExportMaterializationError,
    EditExportMaterializationResult,
    EditExportMaterializationService,
)
from lectureos.application.edit_export_materialization import (
    EditExportCollisionError,
    EditExportWriteError,
)
from lectureos.application.edit_review import EditReviewDecisionKind
from lectureos.application.identities import (
    ApprovedEditExportRepresentationId,
    EditExportArtifactId,
    EditExportAssemblyId,
)
from lectureos.execution.identities import SourceMediaId, SourceTimelineId
from lectureos.review.identities import HumanActorReference

_ACTOR = HumanActorReference("reviewer:alice")
_DEST = Path("/tmp/lectureos-edit-export-test/edits.json")


def _entry(name):
    return EditExportArtifactEntry(
        source_representation_id=ApprovedEditExportRepresentationId(name),
        decision_kind=EditReviewDecisionKind.ACCEPT,
        approved_range_start=0.5,
        approved_range_end=1.5,
        approved_candidate_type="non_lecture_region",
        approved_rationale="approved rationale",
        actor=_ACTOR,
    )


def _artifact():
    return EditExportArtifact(
        identity=EditExportArtifactId("edit-export:a"),
        source_assembly_id=EditExportAssemblyId("a"),
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        entries=(_entry("m1"),),
    )


class _FakeWriter:
    def __init__(self, *, error=None):
        self.error = error
        self.writes = []

    def write(self, *, destination, content, overwrite):
        if self.error is not None:
            raise self.error
        self.writes.append((Path(destination), bytes(content), overwrite))
        return len(content)


class EditExportMaterializationServiceTests(unittest.TestCase):
    def test_success_returns_structured_result(self) -> None:
        writer = _FakeWriter()
        service = EditExportMaterializationService(writer)
        result = service.materialize_artifact(artifact=_artifact(), destination=_DEST)
        self.assertIsInstance(result, EditExportMaterializationResult)
        self.assertEqual(result.format, "lectureos-edit-export-json")
        self.assertEqual(result.version, "v1")
        self.assertEqual(result.encoding, "utf-8")
        self.assertEqual(result.final_path, str(_DEST))
        self.assertEqual(len(writer.writes), 1)
        written_path, written_bytes, overwrite = writer.writes[0]
        self.assertEqual(written_path, _DEST)
        self.assertFalse(overwrite)
        self.assertEqual(result.byte_length, len(written_bytes))

    def test_write_collision_becomes_explicit_error(self) -> None:
        service = EditExportMaterializationService(
            _FakeWriter(error=EditExportCollisionError("different bytes"))
        )
        with self.assertRaises(EditExportMaterializationError):
            service.materialize_artifact(artifact=_artifact(), destination=_DEST)

    def test_write_failure_becomes_explicit_error(self) -> None:
        service = EditExportMaterializationService(
            _FakeWriter(error=EditExportWriteError("io failure"))
        )
        with self.assertRaises(EditExportMaterializationError):
            service.materialize_artifact(artifact=_artifact(), destination=_DEST)

    def test_serialization_failure_happens_before_any_write(self) -> None:
        # Inject a non-finite value that JSON cannot represent; the writer must never be called.
        artifact = _artifact()
        broken_entry = copy.copy(artifact.entries[0])
        object.__setattr__(broken_entry, "approved_range_start", float("nan"))
        broken = copy.copy(artifact)
        object.__setattr__(broken, "entries", (broken_entry,))
        writer = _FakeWriter()
        service = EditExportMaterializationService(writer)
        with self.assertRaises(ValueError):
            service.materialize_artifact(artifact=broken, destination=_DEST)
        self.assertEqual(writer.writes, [])

    def test_overwrite_flag_is_forwarded(self) -> None:
        writer = _FakeWriter()
        service = EditExportMaterializationService(writer)
        service.materialize_artifact(artifact=_artifact(), destination=_DEST, overwrite=True)
        self.assertTrue(writer.writes[0][2])


if __name__ == "__main__":
    unittest.main()
