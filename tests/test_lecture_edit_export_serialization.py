"""Serialization and local materialization tests (044 §25, GOAL-032).

Drives the distinct format identity, the field mapping and what it deliberately omits, byte-level
determinism, the inherited C-6/C-7/C-8 materialization rules, the three failure layers, and the
separation of logical payload from physical file.
"""

import ast
import os
import pathlib
import tempfile
import unittest

from lectureos.application.lecture_edit_export_materialization import (
    LectureEditExportCollisionError,
    LectureEditExportContainmentError,
    LectureEditExportMaterializationService,
    LectureEditExportWriteError,
)
from lectureos.application.lecture_edit_export_serialization import (
    LECTURE_EDIT_EXPORT_JSON_ENCODING,
    LECTURE_EDIT_EXPORT_JSON_FORMAT,
    LECTURE_EDIT_EXPORT_JSON_MEDIA_TYPE,
    LECTURE_EDIT_EXPORT_JSON_VERSION,
    LectureEditExportSerializationError,
    SerializedLectureEditExport,
    serialize_lecture_edit_export_json,
)
from lectureos.composition import (
    compose_lecture_edit_export_materialization_service,
    compose_sqlite_lecture_edit_export_artifact_service,
)
from lectureos.infrastructure.local_lecture_edit_export_file_writer import (
    LocalLectureEditExportFileWriter,
)

from test_lecture_edit_export_assembly_service import _ACTOR, _ExportChain

import json


class _SerializationChain(_ExportChain):
    def setUp(self):
        super().setUp()
        self.artifacts = compose_sqlite_lecture_edit_export_artifact_service(
            self.connection
        )
        self.materializer = compose_lecture_edit_export_materialization_service()
        self.workspace = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.workspace.name)

    def tearDown(self):
        self.workspace.cleanup()
        super().tearDown()

    def _artifact(self, **judge):
        self._judge(**judge) if judge else self._modify()
        assembly = self.exports.admit_assembly(self.timeline.value).assembly
        return self.artifacts.derive_artifact(assembly.identity.value)

    def _serialized(self, **judge):
        return serialize_lecture_edit_export_json(self._artifact(**judge))


class FormatIdentityTests(_SerializationChain):
    def test_the_identity_is_distinct_from_the_legacy_one(self) -> None:
        """S-3: one identifier and version must never denote two payload shapes."""

        from lectureos.application.edit_export_serialization import (
            EDIT_EXPORT_JSON_FORMAT,
            EDIT_EXPORT_JSON_MEDIA_TYPE,
        )

        self.assertNotEqual(LECTURE_EDIT_EXPORT_JSON_FORMAT, EDIT_EXPORT_JSON_FORMAT)
        self.assertNotEqual(
            LECTURE_EDIT_EXPORT_JSON_MEDIA_TYPE, EDIT_EXPORT_JSON_MEDIA_TYPE
        )
        self.assertEqual(
            LECTURE_EDIT_EXPORT_JSON_FORMAT, "lectureos-lecture-edit-export-json"
        )
        self.assertEqual(
            LECTURE_EDIT_EXPORT_JSON_MEDIA_TYPE,
            "application/vnd.lectureos.lecture-edit-export+json",
        )

    def test_the_version_is_v1_not_a_bump_of_the_legacy_format(self) -> None:
        """S-3: a bump would falsely describe the legacy format as superseded."""

        self.assertEqual(LECTURE_EDIT_EXPORT_JSON_VERSION, "v1")

    def test_the_serialized_record_pins_its_own_identity(self) -> None:
        serialized = self._serialized()
        for field, value in (
            ("format", "lectureos-edit-export-json"),
            ("version", "v2"),
            ("media_type", "application/json"),
            ("encoding", "utf-16"),
        ):
            with self.assertRaises(LectureEditExportSerializationError):
                SerializedLectureEditExport(
                    **{
                        **{
                            "format": serialized.format,
                            "version": serialized.version,
                            "media_type": serialized.media_type,
                            "encoding": serialized.encoding,
                            "payload": serialized.payload,
                            "byte_length": serialized.byte_length,
                        },
                        field: value,
                    }
                )

    def test_an_inconsistent_byte_length_is_refused(self) -> None:
        serialized = self._serialized()
        with self.assertRaises(LectureEditExportSerializationError):
            SerializedLectureEditExport(
                format=serialized.format,
                version=serialized.version,
                media_type=serialized.media_type,
                encoding=serialized.encoding,
                payload=serialized.payload,
                byte_length=serialized.byte_length + 1,
            )


class FieldMappingTests(_SerializationChain):
    def _document(self, **judge):
        return json.loads(self._serialized(**judge).payload)

    def test_the_document_carries_exactly_the_contracted_fields(self) -> None:
        document = self._document()
        self.assertEqual(
            list(document),
            [
                "format",
                "version",
                "artifact_id",
                "source_assembly_id",
                "source_timeline_id",
                "edits",
            ],
        )
        self.assertEqual(
            list(document["edits"][0]),
            [
                "source_approved_edit_decision_id",
                "decision_kind",
                "approved_range_start",
                "approved_range_end",
                "approved_label",
                "approved_rationale",
                "actor",
            ],
        )

    def test_no_source_media_field_exists(self) -> None:
        """S-4: the Artifact does not carry it and §22 does not require it in the document."""

        self.assertNotIn("source_media_id", self._document())

    def test_the_legacy_member_reference_name_is_not_used(self) -> None:
        """S-4: §19's atom does not exist here, so its field name must not appear."""

        self.assertNotIn("source_representation_id", self._document()["edits"][0])

    def test_the_approved_values_are_copied_verbatim(self) -> None:
        recorded = self._modify()
        assembly = self.exports.admit_assembly(self.timeline.value).assembly
        artifact = self.artifacts.derive_artifact(assembly.identity.value)
        edit = json.loads(serialize_lecture_edit_export_json(artifact).payload)["edits"][0]
        approved = recorded.approved
        self.assertEqual(edit["decision_kind"], approved.approved_decision_kind.value)
        self.assertEqual(edit["approved_range_start"], approved.approved_range_start)
        self.assertEqual(edit["approved_range_end"], approved.approved_range_end)
        self.assertEqual(edit["approved_label"], approved.approved_label)
        self.assertEqual(edit["approved_rationale"], approved.approved_rationale)
        self.assertEqual(edit["actor"], _ACTOR)
        self.assertEqual(
            edit["source_approved_edit_decision_id"], approved.identity.value
        )

    def test_edit_order_follows_the_artifacts_canonical_order(self) -> None:
        second = self._second_candidate()
        self._judge()
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value, decision_kind="accept", actor=_ACTOR
        )
        assembly = self.exports.admit_assembly(self.timeline.value).assembly
        artifact = self.artifacts.derive_artifact(assembly.identity.value)
        document = json.loads(serialize_lecture_edit_export_json(artifact).payload)
        self.assertEqual(
            [edit["source_approved_edit_decision_id"] for edit in document["edits"]],
            [entry.source_approved_edit_decision_id.value for entry in artifact.entries],
        )


class DeterminismTests(_SerializationChain):
    def test_the_same_artifact_always_yields_the_same_bytes(self) -> None:
        artifact = self._artifact()
        first = serialize_lecture_edit_export_json(artifact)
        second = serialize_lecture_edit_export_json(artifact)
        self.assertEqual(first.payload, second.payload)
        self.assertEqual(first.content, second.content)

    def test_re_deriving_the_artifact_yields_the_same_bytes(self) -> None:
        self._judge()
        assembly = self.exports.admit_assembly(self.timeline.value).assembly
        one = serialize_lecture_edit_export_json(
            self.artifacts.derive_artifact(assembly.identity.value)
        )
        two = serialize_lecture_edit_export_json(
            self.artifacts.derive_artifact(assembly.identity.value)
        )
        self.assertEqual(one.content, two.content)

    def test_encoding_line_endings_and_trailing_newline(self) -> None:
        serialized = self._serialized()
        self.assertEqual(serialized.encoding, LECTURE_EDIT_EXPORT_JSON_ENCODING)
        self.assertNotIn("\r", serialized.payload)
        self.assertTrue(serialized.payload.endswith("\n"))
        self.assertFalse(serialized.payload.endswith("\n\n"))
        self.assertEqual(
            serialized.byte_length, len(serialized.payload.encode("utf-8"))
        )

    def test_non_ascii_is_preserved_unescaped(self) -> None:
        serialized = self._serialized()
        self.assertIn("앞부분만 잘라내는 것으로 승인한다", serialized.payload)
        self.assertNotIn("\\u", serialized.payload)

    def test_the_payload_reads_no_wall_clock_or_process_state(self) -> None:
        """S-5: nothing time-, path-, or process-dependent may appear in the bytes."""

        artifact = self._artifact()
        first = serialize_lecture_edit_export_json(artifact).content
        cwd = os.getcwd()
        try:
            os.chdir(self.base)
            second = serialize_lecture_edit_export_json(artifact).content
        finally:
            os.chdir(cwd)
        self.assertEqual(first, second)


class SerializationFailureTests(_SerializationChain):
    def test_a_value_json_cannot_express_fails_explicitly(self) -> None:
        """S-8(b): an explicit serialization failure, never invalid output."""

        artifact = self._artifact()
        entry = artifact.entries[0]
        broken_entry = object.__new__(type(entry))
        for field in type(entry).__slots__:
            object.__setattr__(broken_entry, field, getattr(entry, field))
        object.__setattr__(broken_entry, "approved_range_end", float("inf"))
        broken = object.__new__(type(artifact))
        for field in type(artifact).__slots__:
            object.__setattr__(broken, field, getattr(artifact, field))
        object.__setattr__(broken, "entries", (broken_entry,))
        with self.assertRaises(LectureEditExportSerializationError) as raised:
            serialize_lecture_edit_export_json(broken)
        self.assertIn("cannot be represented", str(raised.exception))
        self.assertIn("approved sources are unchanged", str(raised.exception))

    def test_a_serialization_failure_writes_no_file(self) -> None:
        artifact = self._artifact()
        entry = artifact.entries[0]
        broken_entry = object.__new__(type(entry))
        for field in type(entry).__slots__:
            object.__setattr__(broken_entry, field, getattr(entry, field))
        object.__setattr__(broken_entry, "approved_range_start", float("nan"))
        broken = object.__new__(type(artifact))
        for field in type(artifact).__slots__:
            object.__setattr__(broken, field, getattr(artifact, field))
        object.__setattr__(broken, "entries", (broken_entry,))
        destination = self.base / "never.json"
        with self.assertRaises(LectureEditExportSerializationError):
            self.materializer.materialize_artifact(
                artifact=broken, destination=destination
            )
        self.assertFalse(destination.exists())


class MaterializationTests(_SerializationChain):
    def test_a_complete_file_is_placed_and_reported(self) -> None:
        artifact = self._artifact()
        serialized = serialize_lecture_edit_export_json(artifact)
        destination = self.base / "nested" / "edits.json"
        result = self.materializer.materialize_artifact(
            artifact=artifact, destination=destination
        )
        self.assertEqual(result.final_path, str(destination))
        self.assertEqual(result.format, LECTURE_EDIT_EXPORT_JSON_FORMAT)
        self.assertEqual(result.version, LECTURE_EDIT_EXPORT_JSON_VERSION)
        self.assertEqual(result.media_type, LECTURE_EDIT_EXPORT_JSON_MEDIA_TYPE)
        self.assertEqual(result.encoding, "utf-8")
        self.assertEqual(result.byte_length, serialized.byte_length)
        self.assertEqual(destination.read_bytes(), serialized.content)

    def test_identical_bytes_are_an_idempotent_success(self) -> None:
        artifact = self._artifact()
        destination = self.base / "edits.json"
        first = self.materializer.materialize_artifact(
            artifact=artifact, destination=destination
        )
        second = self.materializer.materialize_artifact(
            artifact=artifact, destination=destination
        )
        self.assertEqual(first, second)

    def test_different_bytes_collide_and_are_not_overwritten(self) -> None:
        artifact = self._artifact()
        destination = self.base / "edits.json"
        destination.write_bytes(b"pre-existing\n")
        with self.assertRaises(LectureEditExportCollisionError):
            self.materializer.materialize_artifact(
                artifact=artifact, destination=destination
            )
        self.assertEqual(destination.read_bytes(), b"pre-existing\n")

    def test_overwrite_happens_only_on_explicit_request(self) -> None:
        artifact = self._artifact()
        serialized = serialize_lecture_edit_export_json(artifact)
        destination = self.base / "edits.json"
        destination.write_bytes(b"pre-existing\n")
        result = self.materializer.materialize_artifact(
            artifact=artifact, destination=destination, overwrite=True
        )
        self.assertEqual(destination.read_bytes(), serialized.content)
        self.assertEqual(result.byte_length, serialized.byte_length)

    def test_a_symlink_destination_is_never_written(self) -> None:
        artifact = self._artifact()
        target = self.base / "real.json"
        target.write_bytes(b"target\n")
        link = self.base / "link.json"
        link.symlink_to(target)
        for overwrite in (False, True):
            with self.assertRaises(LectureEditExportContainmentError):
                self.materializer.materialize_artifact(
                    artifact=artifact, destination=link, overwrite=overwrite
                )
        self.assertEqual(target.read_bytes(), b"target\n")

    def test_a_directory_destination_is_never_overwritten(self) -> None:
        artifact = self._artifact()
        directory = self.base / "adir"
        directory.mkdir()
        with self.assertRaises(LectureEditExportCollisionError):
            self.materializer.materialize_artifact(
                artifact=artifact, destination=directory, overwrite=True
            )
        self.assertTrue(directory.is_dir())

    def test_a_relative_destination_is_refused(self) -> None:
        artifact = self._artifact()
        with self.assertRaises(LectureEditExportContainmentError):
            self.materializer.materialize_artifact(
                artifact=artifact, destination="relative/edits.json"
            )

    def test_no_partial_file_survives_a_write_failure(self) -> None:
        artifact = self._artifact()
        destination = self.base / "edits.json"

        class _Failing(LocalLectureEditExportFileWriter):
            def _atomic_write(self, final_path, content, *, overwrite):
                raise LectureEditExportWriteError("injected failure")

        service = LectureEditExportMaterializationService(_Failing())
        with self.assertRaises(LectureEditExportWriteError):
            service.materialize_artifact(artifact=artifact, destination=destination)
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.base.glob("*.tmp")), [])
        self.assertEqual(list(self.base.glob(".*")), [])

    def test_the_same_payload_may_be_placed_at_several_destinations(self) -> None:
        """S-6: the file is not the identity; more placements create no new artifact."""

        artifact = self._artifact()
        one = self.materializer.materialize_artifact(
            artifact=artifact, destination=self.base / "a.json"
        )
        two = self.materializer.materialize_artifact(
            artifact=artifact, destination=self.base / "b" / "c.json"
        )
        self.assertNotEqual(one.final_path, two.final_path)
        self.assertEqual(
            (self.base / "a.json").read_bytes(), (self.base / "b" / "c.json").read_bytes()
        )
        again = self.artifacts.derive_artifact(artifact.source_assembly_id.value)
        self.assertEqual(again.identity, artifact.identity)


class PersistenceAndSeparationTests(_SerializationChain):
    def test_nothing_is_written_to_the_database(self) -> None:
        artifact = self._artifact()
        counts = {
            table: self.connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in (
                "lecture_review_decisions",
                "lecture_approved_edit_decisions",
                "lecture_review_authority_positions",
                "lecture_edit_export_assemblies",
                "lecture_edit_export_assembly_members",
                "processing_runs",
                "domain_result_references",
            )
        }
        self.materializer.materialize_artifact(
            artifact=artifact, destination=self.base / "edits.json"
        )
        for table, expected in counts.items():
            self.assertEqual(
                self.connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0],
                expected,
                table,
            )

    def test_no_serialization_or_materialization_relation_exists(self) -> None:
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        for forbidden in (
            "lecture_edit_export_artifacts",
            "lecture_edit_export_serializations",
            "lecture_edit_export_materializations",
        ):
            self.assertNotIn(forbidden, tables)

    def test_the_legacy_export_relations_stay_empty(self) -> None:
        artifact = self._artifact()
        self.materializer.materialize_artifact(
            artifact=artifact, destination=self.base / "edits.json"
        )
        for table in (
            "approved_edit_export_representations",
            "edit_export_assemblies",
            "edit_export_assembly_members",
        ):
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
            )


class GenerationSeparationTests(unittest.TestCase):
    """This generation carries no source-level dependency on the legacy Export boundary."""

    def _imports(self, module_path: str) -> set[str]:
        import lectureos

        root = pathlib.Path(lectureos.__file__).resolve().parent.parent.parent
        tree = ast.parse((root / module_path).read_text())
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        return names

    def test_the_new_modules_import_no_legacy_edit_export_module(self) -> None:
        for path in (
            "src/lectureos/application/lecture_edit_export_serialization.py",
            "src/lectureos/application/lecture_edit_export_materialization.py",
            "src/lectureos/infrastructure/local_lecture_edit_export_file_writer.py",
        ):
            for name in self._imports(path):
                self.assertNotIn("edit_export_serialization", name.split(".")[-1:])
                self.assertFalse(
                    name.endswith("application.edit_export_materialization"), path
                )
                self.assertFalse(name.endswith("application.edit_export_artifact"), path)
                self.assertFalse(
                    name.endswith("local_edit_export_file_writer"), path
                )


if __name__ == "__main__":
    unittest.main()
