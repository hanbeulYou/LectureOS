import unittest

from lectureos.application import (
    PreparedSubtitleSrtArtifact,
    SubtitleArtifactFormat,
    SubtitleSrtArtifact,
    SubtitleSrtArtifactIdentityPlan,
)
from lectureos.application.identities import SubtitleApprovedDocumentId
from lectureos.execution.identities import (
    ArtifactId,
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)

_PAYLOAD = "1\n00:00:00,000 --> 00:00:01,000\n첫 자막\n"


def _artifact(**overrides) -> SubtitleSrtArtifact:
    base = dict(
        identity=ArtifactId("artifact"),
        domain_result_id=DomainResultId("artifact-result"),
        source_approved_document_id=SubtitleApprovedDocumentId("document"),
        format=SubtitleArtifactFormat.SRT,
        payload=_PAYLOAD,
        byte_length=len(_PAYLOAD.encode("utf-8")),
        cue_count=1,
        encoding="utf-8",
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="generated the srt artifact",
    )
    base.update(overrides)
    return SubtitleSrtArtifact(**base)


class SubtitleSrtArtifactTests(unittest.TestCase):
    def test_valid_artifact(self) -> None:
        self.assertIs(_artifact().format, SubtitleArtifactFormat.SRT)

    def test_valid_empty_artifact(self) -> None:
        artifact = _artifact(payload="", byte_length=0, cue_count=0)
        self.assertEqual(artifact.payload, "")

    def test_byte_length_must_match_payload(self) -> None:
        with self.assertRaises(ValueError):
            _artifact(byte_length=1)

    def test_byte_length_counts_utf8_bytes(self) -> None:
        # a multibyte payload's byte length differs from its character length
        self.assertNotEqual(_artifact().byte_length, len(_PAYLOAD))

    def test_encoding_must_be_utf8(self) -> None:
        with self.assertRaises(ValueError):
            _artifact(encoding="latin-1")

    def test_cue_count_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _artifact(cue_count=-1)

    def test_empty_payload_requires_zero_cues(self) -> None:
        with self.assertRaises(ValueError):
            _artifact(payload="", byte_length=0, cue_count=1)
        with self.assertRaises(ValueError):
            _artifact(cue_count=0)

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _artifact(reason="  ")

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _artifact(sequence=-1)

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _artifact(sequence=0, previous_artifact_id=ArtifactId("earlier"))

    def test_later_may_reference_previous(self) -> None:
        artifact = _artifact(sequence=1, previous_artifact_id=ArtifactId("earlier"))
        self.assertEqual(artifact.previous_artifact_id, ArtifactId("earlier"))


class IdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = SubtitleSrtArtifactIdentityPlan(
            artifact_id=ArtifactId("artifact"),
            artifact_result_id=DomainResultId("artifact-result"),
        )
        self.assertEqual(plan.artifact_id, ArtifactId("artifact"))


class PreparedTests(unittest.TestCase):
    def test_prepared_holds_artifact(self) -> None:
        prepared = PreparedSubtitleSrtArtifact(artifact=_artifact(), artifact_result=None)
        self.assertEqual(prepared.artifact.cue_count, 1)


if __name__ == "__main__":
    unittest.main()
