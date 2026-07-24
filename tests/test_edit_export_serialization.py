import copy
import json
import unittest

from lectureos.application import (
    EDIT_EXPORT_JSON_FORMAT,
    EDIT_EXPORT_JSON_VERSION,
    EditExportArtifact,
    EditExportArtifactEntry,
    EditExportSerializationError,
    SerializedEditExport,
    serialize_edit_export_json,
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


def _entry(name, **overrides):
    base = dict(
        source_representation_id=ApprovedEditExportRepresentationId(name),
        decision_kind=EditReviewDecisionKind.ACCEPT,
        approved_range_start=0.5,
        approved_range_end=1.5,
        approved_candidate_type="non_lecture_region",
        approved_rationale="approved rationale",
        actor=_ACTOR,
    )
    base.update(overrides)
    return EditExportArtifactEntry(**base)


def _artifact(entries):
    return EditExportArtifact(
        identity=EditExportArtifactId("edit-export:assembly-1"),
        source_assembly_id=EditExportAssemblyId("assembly-1"),
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        entries=entries,
    )


class EditExportSerializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact = _artifact(
            (
                _entry("m1"),
                _entry(
                    "m2",
                    decision_kind=EditReviewDecisionKind.MODIFY,
                    approved_candidate_type="condense_repetition",
                    approved_rationale="approved: 반복 설명 압축",
                    approved_range_start=0.75,
                    approved_range_end=1.25,
                ),
            )
        )

    def test_format_and_version_identity(self) -> None:
        serialized = serialize_edit_export_json(self.artifact)
        self.assertIsInstance(serialized, SerializedEditExport)
        self.assertEqual(serialized.format, EDIT_EXPORT_JSON_FORMAT)
        self.assertEqual(serialized.version, EDIT_EXPORT_JSON_VERSION)
        self.assertEqual(serialized.encoding, "utf-8")
        document = json.loads(serialized.payload)
        self.assertEqual(document["format"], EDIT_EXPORT_JSON_FORMAT)
        self.assertEqual(document["version"], EDIT_EXPORT_JSON_VERSION)

    def test_every_field_is_present_and_faithful(self) -> None:
        document = json.loads(serialize_edit_export_json(self.artifact).payload)
        self.assertEqual(document["artifact_id"], "edit-export:assembly-1")
        self.assertEqual(document["source_assembly_id"], "assembly-1")
        self.assertEqual(document["source_media_id"], "media")
        self.assertEqual(document["source_timeline_id"], "timeline")
        first, second = document["edits"]
        self.assertEqual(first["source_representation_id"], "m1")
        self.assertEqual(first["decision_kind"], "accept")
        self.assertEqual(first["approved_range_start"], 0.5)
        self.assertEqual(first["approved_range_end"], 1.5)
        self.assertEqual(first["approved_candidate_type"], "non_lecture_region")
        self.assertEqual(first["approved_rationale"], "approved rationale")
        self.assertEqual(first["actor"], "reviewer:alice")
        self.assertEqual(second["decision_kind"], "modify")
        self.assertEqual(second["approved_candidate_type"], "condense_repetition")

    def test_entries_serialized_in_canonical_order(self) -> None:
        document = json.loads(serialize_edit_export_json(self.artifact).payload)
        self.assertEqual(
            [e["source_representation_id"] for e in document["edits"]], ["m1", "m2"]
        )

    def test_deterministic_bytes(self) -> None:
        self.assertEqual(
            serialize_edit_export_json(self.artifact).payload,
            serialize_edit_export_json(self.artifact).payload,
        )

    def test_utf8_lf_and_trailing_newline(self) -> None:
        payload = serialize_edit_export_json(self.artifact).payload
        self.assertTrue(payload.endswith("\n"))
        self.assertNotIn("\r", payload)
        # Non-ASCII (Korean) is preserved unescaped, not \uXXXX-escaped.
        self.assertIn("반복 설명 압축", payload)
        self.assertNotIn("\\uc0", payload)

    def test_byte_length_matches_payload(self) -> None:
        serialized = serialize_edit_export_json(self.artifact)
        self.assertEqual(
            serialized.byte_length, len(serialized.payload.encode("utf-8"))
        )

    def test_non_finite_value_is_explicit_representation_failure(self) -> None:
        # An Artifact validates finite ranges, so bypass __post_init__ to inject a non-finite value and
        # prove the serializer rejects it explicitly (never emitting invalid/lossy JSON).
        artifact = _artifact((_entry("m1"),))
        broken_entry = copy.copy(artifact.entries[0])
        object.__setattr__(broken_entry, "approved_range_end", float("inf"))
        broken = copy.copy(artifact)
        object.__setattr__(broken, "entries", (broken_entry,))
        with self.assertRaises(EditExportSerializationError):
            serialize_edit_export_json(broken)

    def test_serialization_does_not_mutate_artifact(self) -> None:
        before = (
            self.artifact.identity,
            self.artifact.entries,
        )
        serialize_edit_export_json(self.artifact)
        self.assertEqual((self.artifact.identity, self.artifact.entries), before)


if __name__ == "__main__":
    unittest.main()
