import unittest

from lectureos.application import (
    PreparedSubtitleSrtMaterialization,
    SubtitleMaterializationState,
    SubtitleMaterializationStorageKind,
    SubtitleSrtMaterialization,
    SubtitleSrtMaterializationIdentityPlan,
    SubtitleSrtMaterializationOutcome,
)
from lectureos.application.identities import SubtitleSrtMaterializationId
from lectureos.execution.identities import (
    ArtifactId,
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)


def _materialization(**overrides) -> SubtitleSrtMaterialization:
    base = dict(
        identity=SubtitleSrtMaterializationId("materialization"),
        domain_result_id=DomainResultId("materialization-result"),
        source_artifact_id=ArtifactId("artifact"),
        storage_kind=SubtitleMaterializationStorageKind.LOCAL_FILE,
        relative_location="subtitles/artifact.srt",
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="materialized the srt artifact",
    )
    base.update(overrides)
    return SubtitleSrtMaterialization(**base)


def _outcome(**overrides) -> SubtitleSrtMaterializationOutcome:
    base = dict(
        materialization_id=SubtitleSrtMaterializationId("materialization"),
        state=SubtitleMaterializationState.MATERIALIZED,
        byte_length=42,
    )
    base.update(overrides)
    return SubtitleSrtMaterializationOutcome(**base)


class SubtitleSrtMaterializationTests(unittest.TestCase):
    def test_valid(self) -> None:
        self.assertEqual(_materialization().relative_location, "subtitles/artifact.srt")

    def test_artifact_identity_distinct_from_materialization_identity(self) -> None:
        m = _materialization()
        self.assertNotEqual(m.identity.value, m.source_artifact_id.value)

    def test_relative_location_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _materialization(relative_location="  ")

    def test_relative_location_must_not_be_absolute(self) -> None:
        with self.assertRaises(ValueError):
            _materialization(relative_location="/etc/passwd")

    def test_relative_location_must_not_traverse(self) -> None:
        with self.assertRaises(ValueError):
            _materialization(relative_location="../outside.srt")
        with self.assertRaises(ValueError):
            _materialization(relative_location="a/../../b.srt")

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _materialization(reason="  ")

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _materialization(sequence=-1)

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _materialization(
                sequence=0,
                previous_materialization_id=SubtitleSrtMaterializationId("earlier"),
            )

    def test_later_may_reference_previous(self) -> None:
        m = _materialization(
            sequence=1,
            previous_materialization_id=SubtitleSrtMaterializationId("earlier"),
        )
        self.assertEqual(
            m.previous_materialization_id, SubtitleSrtMaterializationId("earlier")
        )


class SubtitleSrtMaterializationOutcomeTests(unittest.TestCase):
    def test_valid_materialized(self) -> None:
        self.assertEqual(_outcome().byte_length, 42)

    def test_valid_failed(self) -> None:
        outcome = _outcome(
            state=SubtitleMaterializationState.FAILED,
            byte_length=None,
            failure_reason="different bytes present at location",
        )
        self.assertEqual(outcome.failure_reason, "different bytes present at location")

    def test_materialized_requires_byte_length(self) -> None:
        with self.assertRaises(ValueError):
            _outcome(byte_length=None)
        with self.assertRaises(ValueError):
            _outcome(byte_length=-1)

    def test_materialized_must_not_carry_failure_reason(self) -> None:
        with self.assertRaises(ValueError):
            _outcome(failure_reason="x")

    def test_failed_requires_failure_reason(self) -> None:
        with self.assertRaises(ValueError):
            _outcome(state=SubtitleMaterializationState.FAILED, byte_length=None)
        with self.assertRaises(ValueError):
            _outcome(
                state=SubtitleMaterializationState.FAILED,
                byte_length=None,
                failure_reason="  ",
            )

    def test_failed_must_not_carry_byte_length(self) -> None:
        with self.assertRaises(ValueError):
            _outcome(
                state=SubtitleMaterializationState.FAILED,
                byte_length=42,
                failure_reason="oops",
            )

    def test_state_must_be_terminal(self) -> None:
        with self.assertRaises(ValueError):
            _outcome(state=SubtitleMaterializationState.PENDING, byte_length=None)


class IdentityPlanAndPreparedTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = SubtitleSrtMaterializationIdentityPlan(
            materialization_id=SubtitleSrtMaterializationId("materialization"),
            materialization_result_id=DomainResultId("materialization-result"),
        )
        self.assertEqual(
            plan.materialization_id, SubtitleSrtMaterializationId("materialization")
        )

    def test_prepared_holds_materialization(self) -> None:
        prepared = PreparedSubtitleSrtMaterialization(
            materialization=_materialization(), materialization_result=None
        )
        self.assertEqual(
            prepared.materialization.relative_location, "subtitles/artifact.srt"
        )


if __name__ == "__main__":
    unittest.main()
