import unittest
from dataclasses import replace
from pathlib import Path

from lectureos.execution.identities import (
    ArtifactId,
    PluginReference,
    WorkingContextReference,
)
from lectureos.export.identities import ExportRequestId, SystemRequesterReference
from lectureos.export.models import (
    ExportFormat,
    ExportRequesterKind,
    ExportRequesterReference,
    ExportTargetMode,
)
from lectureos.export.service import MinimalSrtExportService, SRT_SERIALIZER_VERSION
from lectureos.review.identities import HumanActorReference
from lectureos.subtitle.applicability import SubtitleConditionReason
from lectureos.subtitle.identities import (
    SubtitleCueId,
    SubtitleRevisionApplicabilityId,
)
from tests import test_final_subtitle_selection as final_fixture


class MinimalSrtExportTest(unittest.TestCase):
    def setUp(self):
        self.fixture = final_fixture.FinalSubtitleSelectionTest(
            "test_current_valid_revision_can_be_selected_as_final"
        )
        self.fixture.setUp()
        self.revision = self.fixture.first
        self.validation = self.fixture._prepare(self.revision)
        self.final = self.fixture._select_final(
            self.revision, self.validation.identity
        )
        self.service = MinimalSrtExportService(
            self.fixture.service,
            self.fixture.fixture.subtitle,
            self.fixture.validation,
            self.fixture.applicability,
        )
        self.human_requester = ExportRequesterReference(
            kind=ExportRequesterKind.HUMAN,
            human_actor=HumanActorReference("srt-exporter"),
        )
        self.system_requester = ExportRequesterReference(
            kind=ExportRequesterKind.SYSTEM,
            system_reference=SystemRequesterReference("scheduled-export"),
        )

    def test_active_final_exports_canonical_srt(self):
        before = self._upstream_state()
        artifact = self._export()
        expected = (
            "1\n"
            "00:00:00,000 --> 00:00:01,000\n"
            "첫 자막\n\n"
            "2\n"
            "00:00:01,000 --> 00:00:02,000\n"
            "둘째 자막\n"
        )
        self.assertEqual(expected, artifact.content)
        self.assertIsInstance(artifact.content, str)
        self.assertEqual(SRT_SERIALIZER_VERSION, artifact.serializer_version)
        self.assertEqual(self.final.identity, artifact.final_selection_id)
        self.assertEqual(self.revision.identity, artifact.revision_id)
        self.assertEqual(self.validation.identity, artifact.final_validation_id)
        self.assertEqual(self.validation.identity, artifact.latest_validation_id)
        self.assertEqual(self.revision.cue_ids, artifact.cue_ids)
        self.assertEqual(before, self._upstream_state())
        self.assertFalse(hasattr(artifact, "path"))
        self.assertFalse(hasattr(artifact, "digest"))

    def test_revision_cue_order_drives_indices_not_repository_order(self):
        first_cue = self.fixture.fixture.subtitle.get_cue(self.revision.cue_ids[0])
        second_cue = self.fixture.fixture.subtitle.get_cue(self.revision.cue_ids[1])
        self.fixture.fixture.subtitle.cues._records = {
            second_cue.identity: second_cue,
            first_cue.identity: first_cue,
        }
        content = self._export().content
        self.assertLess(content.index("첫 자막"), content.index("둘째 자막"))

    def test_timestamp_rounding_and_rollovers(self):
        milliseconds = self.service._milliseconds
        timestamp = self.service._format_timestamp
        self.assertEqual("00:00:01,234", timestamp(milliseconds(1.2344)))
        self.assertEqual("00:00:01,235", timestamp(milliseconds(1.2345)))
        self.assertEqual("00:00:02,000", timestamp(milliseconds(1.999999999)))
        self.assertEqual("00:01:05,042", timestamp(milliseconds(65.042)))
        self.assertEqual("12:34:56,789", timestamp(milliseconds(45296.789)))
        self.assertEqual("25:03:04,005", timestamp(milliseconds(90184.005)))
        with self.assertRaisesRegex(ValueError, "non-negative"):
            milliseconds(-0.001)

    def test_rounding_collapse_blocks_without_partial_write(self):
        first = self.fixture.fixture.subtitle.get_cue(self.revision.cue_ids[0])
        self.fixture.fixture.subtitle.cues.save(
            replace(first, start=1.0001, end=1.0004)
        )
        self.validation = self.fixture._validate(
            self.revision, "rounding-collapse-validation"
        )
        with self.assertRaisesRegex(ValueError, "collapses"):
            self._export()
        self._assert_no_exports()

    def test_unicode_multiline_and_newline_canonicalization(self):
        first = self.fixture.fixture.subtitle.get_cue(self.revision.cue_ids[0])
        self.fixture.fixture.subtitle.cues.save(
            replace(first, text="  한글 English 123!  \r\n둘째 줄\r셋째 줄")
        )
        self.validation = self.fixture._validate(
            self.revision, "multiline-validation"
        )
        content = self._export().content
        self.assertIn("  한글 English 123!  \n둘째 줄\n셋째 줄", content)
        self.assertNotIn("\r", content)
        self.assertTrue(content.endswith("\n"))
        self.assertFalse(content.endswith("\n\n"))

    def test_blank_or_boundary_newlines_are_rejected_without_text_rewrite(self):
        original = self.fixture.fixture.subtitle.get_cue(self.revision.cue_ids[0])
        for index, text in enumerate(
            ("첫 줄\n\n둘째 줄", "첫 줄\n", "\n첫 줄", "첫 줄\n   \n둘째 줄")
        ):
            with self.subTest(text=text):
                self.fixture.fixture.subtitle.cues.save(replace(original, text=text))
                self.validation = self.fixture._validate(
                    self.revision, f"blank-line-validation-{index}"
                )
                with self.assertRaisesRegex(ValueError, "blank lines"):
                    self._export(
                        request_id=f"blank-line-request-{index}",
                        artifact_id=f"blank-line-artifact-{index}",
                    )
                self._assert_no_exports()

    def test_past_final_requires_historical_mode(self):
        past_final, current_final = self._replace_final()
        with self.assertRaisesRegex(ValueError, "latest Final Selection"):
            self._export(final_selection_id=past_final.identity)
        artifact = self._export(
            request_id="historical-request",
            artifact_id="historical-artifact",
            final_selection_id=past_final.identity,
            target_mode=ExportTargetMode.HISTORICAL_REPRODUCTION,
        )
        self.assertEqual(
            ExportTargetMode.HISTORICAL_REPRODUCTION, artifact.target_mode
        )
        self.assertEqual(past_final.identity, artifact.final_selection_id)
        self.assertEqual(current_final, self.fixture.service.get_latest_final_selection(
            self.fixture.fixture.working_context, self.revision.subtitle_id
        ))

    def test_active_final_cannot_use_historical_mode(self):
        with self.assertRaisesRegex(ValueError, "historical Final Selection"):
            self._export(target_mode=ExportTargetMode.HISTORICAL_REPRODUCTION)
        self._assert_no_exports()

    def test_latest_invalid_validation_blocks_active_export(self):
        latest = self.fixture._validate(self.revision, "invalid-after-final")
        self.fixture.fixture.subtitle.validations.save(
            replace(latest, structural_valid=False)
        )
        with self.assertRaisesRegex(ValueError, "latest valid Validation"):
            self._export()
        self._assert_no_exports()

    def test_historical_invalid_latest_requires_risk_acknowledgment(self):
        past_final, _ = self._replace_final()
        latest = self.fixture._validate(
            self.revision, "historical-invalid-latest"
        )
        self.fixture.fixture.subtitle.validations.save(
            replace(latest, structural_valid=False)
        )
        kwargs = dict(
            final_selection_id=past_final.identity,
            target_mode=ExportTargetMode.HISTORICAL_REPRODUCTION,
        )
        with self.assertRaisesRegex(ValueError, "risk acknowledgment"):
            self._export(**kwargs)
        artifact = self._export(
            request_id="risk-request",
            artifact_id="risk-artifact",
            historical_risk_acknowledged=True,
            **kwargs,
        )
        self.assertTrue(artifact.historical_risk_acknowledged)
        self.assertEqual(latest.identity, artifact.latest_validation_id)

    def test_invalid_final_time_validation_evidence_blocks_reproduction(self):
        past_final, _ = self._replace_final()
        final_validation = self.fixture.fixture.subtitle.get_validation(
            past_final.validation_id
        )
        self.fixture.fixture.subtitle.validations.save(
            replace(final_validation, structural_valid=False)
        )
        with self.assertRaisesRegex(ValueError, "evidence is invalid"):
            self._export(
                final_selection_id=past_final.identity,
                target_mode=ExportTargetMode.HISTORICAL_REPRODUCTION,
            )
        self._assert_no_exports()

    def test_stale_requires_export_level_acknowledgment_and_remains_stale(self):
        stale = self.fixture.applicability.mark_revision_stale(
            identity=SubtitleRevisionApplicabilityId("stale-after-final"),
            working_context=self.fixture.fixture.working_context,
            revision_id=self.revision.identity,
            actor=self.fixture.actor,
            reason=SubtitleConditionReason.MANUAL_STALE,
        )
        with self.assertRaisesRegex(ValueError, "requires acknowledgment"):
            self._export()
        artifact = self._export(stale_condition_acknowledged=True)
        self.assertTrue(artifact.stale_condition_acknowledged)
        self.assertEqual(
            stale,
            self.fixture.applicability.get_latest_condition(
                self.fixture.fixture.working_context, self.revision.identity
            ),
        )

    def test_human_and_system_requesters_are_preserved(self):
        human_artifact = self._export()
        system_artifact = self._export(
            request_id="system-request",
            artifact_id="system-artifact",
            requester=self.system_requester,
        )
        self.assertEqual(self.human_requester, human_artifact.requester)
        self.assertEqual(self.system_requester, system_artifact.requester)
        self.assertNotEqual(self.final.actor, human_artifact.requester.human_actor)
        with self.assertRaisesRegex(TypeError, "typed requester"):
            self._export(
                request_id="bad-requester-request",
                artifact_id="bad-requester-artifact",
                requester=PluginReference("execution-is-not-requester"),
            )

    def test_successful_request_is_idempotent_by_request_identity(self):
        first = self._export()
        repeated = self._export(artifact_id="unused-artifact")
        self.assertEqual(first, repeated)
        self.assertEqual(1, len(self.service.requests.all()))
        self.assertEqual(1, len(self.service.artifacts.all()))
        self.assertEqual(
            first,
            self.service.get_artifact_for_request(ExportRequestId("srt-request")),
        )

    def test_same_request_identity_with_different_content_is_rejected(self):
        self._export()
        with self.assertRaisesRegex(ValueError, "identity collision"):
            self._export(
                requester=self.system_requester,
                artifact_id="unused-artifact",
            )
        self.assertEqual(1, len(self.service.requests.all()))
        self.assertEqual(1, len(self.service.artifacts.all()))

    def test_new_request_for_same_final_creates_new_artifact(self):
        first = self._export()
        second = self._export(
            request_id="re-export-request",
            artifact_id="re-export-artifact",
        )
        self.assertNotEqual(first.identity, second.identity)
        self.assertNotEqual(first.request_id, second.request_id)
        self.assertEqual(first.content, second.content)
        self.assertEqual(first, self.service.get_export_artifact(first.identity))
        self.assertEqual(
            (first, second),
            self.service.list_artifacts_for_final_selection(self.final.identity),
        )
        self.assertEqual(
            (first, second),
            self.service.list_artifacts_for_revision(self.revision.identity),
        )

    def test_working_context_missing_cue_and_artifact_collision_write_nothing(self):
        with self.assertRaisesRegex(ValueError, "Working Context"):
            self._export(working_context=WorkingContextReference("wrong-context"))
        self._assert_no_exports()

        missing_cue_id = self.revision.cue_ids[0]
        missing_cue = self.fixture.fixture.subtitle.cues._records.pop(missing_cue_id)
        with self.assertRaisesRegex(KeyError, "unknown Cue"):
            self._export()
        self._assert_no_exports()
        self.fixture.fixture.subtitle.cues._records[missing_cue_id] = missing_cue

        self._export(
            request_id="existing-artifact-request",
            artifact_id="shared-artifact",
        )
        with self.assertRaisesRegex(ValueError, "Artifact identity"):
            self._export(
                request_id="colliding-artifact-request",
                artifact_id="shared-artifact",
            )
        self.assertEqual(1, len(self.service.requests.all()))
        self.assertEqual(1, len(self.service.artifacts.all()))

    def test_empty_cue_sequence_and_validation_history_corruption_write_nothing(self):
        original_revision = self.fixture.fixture.subtitle.get_revision(
            self.revision.identity
        )
        original_validation = self.fixture.fixture.subtitle.get_validation(
            self.validation.identity
        )
        self.fixture.fixture.subtitle.revisions.save(
            replace(original_revision, cue_ids=())
        )
        self.fixture.fixture.subtitle.validations.save(
            replace(original_validation, target_cue_ids=())
        )
        with self.assertRaisesRegex(ValueError, "at least one Cue"):
            self._export()
        self._assert_no_exports()

        self.fixture.fixture.subtitle.revisions.save(original_revision)
        self.fixture.fixture.subtitle.validations.save(
            replace(original_validation, sequence=2)
        )
        with self.assertRaisesRegex(RuntimeError, "history is corrupt"):
            self._export()
        self._assert_no_exports()

    def test_invalid_replacement_cue_lineage_writes_nothing(self):
        replacement = self.fixture.fixture.subtitle.get_cue(self.revision.cue_ids[0])
        self.fixture.fixture.subtitle.cues.save(
            replace(
                replacement,
                replaces_cue_id=SubtitleCueId("missing-original-cue"),
            )
        )
        with self.assertRaisesRegex(KeyError, "original does not exist"):
            self._export()
        self._assert_no_exports()

    def test_unsupported_format_and_mode_write_nothing(self):
        with self.assertRaisesRegex(ValueError, "unsupported Export format"):
            self._export(format="vtt")
        with self.assertRaisesRegex(ValueError, "unsupported Export target mode"):
            self._export(target_mode="active_final")
        self._assert_no_exports()

    def test_export_uses_public_boundaries_and_has_no_rendering_or_file_output(self):
        source = Path("src/lectureos/export/service.py").read_text()
        self.assertNotIn("lectureos.subtitle.repositories", source)
        self.assertNotIn("lectureos.review.repositories", source)
        self.assertNotIn("lectureos.execution.repositories", source)
        self.assertFalse(hasattr(self.service, "render"))
        self.assertFalse(hasattr(self.service, "write_file"))
        self.assertFalse(hasattr(self.service, "export_vtt"))

    def _replace_final(self):
        past = self.final
        second = self.fixture._derived_revision("export-replacement")
        validation = self.fixture._validate(
            second, "export-replacement-validation"
        )
        self.fixture._select_current(
            second,
            identity="export-replacement-current",
            superseded_identity="export-original-superseded",
        )
        current = self.fixture._select_final(
            second,
            validation.identity,
            identity="export-replacement-final",
        )
        return past, current

    def _export(
        self,
        *,
        request_id="srt-request",
        artifact_id="srt-artifact",
        working_context=None,
        final_selection_id=None,
        target_mode=ExportTargetMode.ACTIVE_FINAL,
        requester=None,
        format=ExportFormat.SRT,
        stale_condition_acknowledged=False,
        historical_risk_acknowledged=False,
    ):
        return self.service.export_final_subtitle_to_srt(
            request_id=ExportRequestId(request_id),
            artifact_id=ArtifactId(artifact_id),
            working_context=working_context
            or self.fixture.fixture.working_context,
            final_selection_id=final_selection_id or self.final.identity,
            target_mode=target_mode,
            requester=requester or self.human_requester,
            format=format,
            stale_condition_acknowledged=stale_condition_acknowledged,
            historical_risk_acknowledged=historical_risk_acknowledged,
        )

    def _upstream_state(self):
        return (
            self.fixture.fixture.subtitle.get_revision(self.revision.identity),
            tuple(
                self.fixture.fixture.subtitle.get_cue(cue_id)
                for cue_id in self.revision.cue_ids
            ),
            self.fixture.fixture.subtitle.get_validation(self.validation.identity),
            self.fixture.applicability.selection_records.all(),
            self.fixture.applicability.condition_records.all(),
            self.fixture.service.selections.all(),
        )

    def _assert_no_exports(self):
        self.assertEqual((), self.service.requests.all())
        self.assertEqual((), self.service.artifacts.all())


if __name__ == "__main__":
    unittest.main()
