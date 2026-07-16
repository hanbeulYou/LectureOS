import unittest
from dataclasses import replace

from lectureos.execution.identities import (
    ProcessingRunId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.subtitle.applicability import SubtitleApplicabilityService
from lectureos.subtitle.identities import (
    SubtitleCueId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from lectureos.subtitle.models import SubtitleValidationFinding
from lectureos.subtitle.validation import SubtitleValidationService
from tests import test_subtitle_decision_application as subtitle_application_fixture


class SubtitleRevisionValidationIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.fixture = subtitle_application_fixture.ApprovedSubtitleDecisionApplicationTest(
            "test_accept_creates_new_subtitle_revision"
        )
        self.fixture.setUp()
        self.validation = SubtitleValidationService(
            self.fixture.subtitle,
            self.fixture.transcript,
            self.fixture.execution,
        )
        self.applicability = SubtitleApplicabilityService(
            self.fixture.subtitle, self.fixture.execution
        )

    def test_valid_revision_creates_revision_targeted_result(self):
        revision = self._accepted_revision()
        before_revision = self.fixture.subtitle.get_revision(revision.identity)
        before_cues = tuple(
            self.fixture.subtitle.get_cue(cue_id) for cue_id in revision.cue_ids
        )
        result = self._validate(revision)
        self.assertTrue(result.structural_valid)
        self.assertEqual(revision.identity, result.target_revision_id)
        self.assertIsNone(result.target_candidate_id)
        self.assertEqual(revision.cue_ids, result.target_cue_ids)
        self.assertEqual(self.fixture.working_context, result.working_context)
        self.assertIsNotNone(result.recorded_at)
        self.assertEqual(before_revision, self.fixture.subtitle.get_revision(revision.identity))
        self.assertEqual(
            before_cues,
            tuple(self.fixture.subtitle.get_cue(cue_id) for cue_id in revision.cue_ids),
        )

    def test_candidate_and_revision_validation_have_distinct_identities(self):
        candidate_result = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("candidate-validation"),
            candidate_id=self.fixture.candidate.identity,
            run_id=self.fixture.run_id,
            unit_execution_id=self.fixture.execution_id,
        )
        revision = self._accepted_revision()
        revision_result = self._validate(revision)
        self.assertNotEqual(candidate_result.identity, revision_result.identity)
        self.assertEqual(self.fixture.candidate.identity, candidate_result.target_candidate_id)
        self.assertEqual(revision.identity, revision_result.target_revision_id)

    def test_revision_cue_sequence_drives_validation(self):
        revision = self._accepted_revision()
        result = self._validate(revision)
        self.assertEqual(revision.cue_ids, result.target_cue_ids)
        self.assertEqual((), self.validation.get_validation_findings(result.identity))

    def test_structural_failure_persists_result_and_findings(self):
        revision = self._accepted_revision()
        second = self.fixture.subtitle.get_cue(revision.cue_ids[1])
        self.fixture.subtitle.cues.save(replace(second, display_order=0))
        before = self.fixture.subtitle.get_revision(revision.identity)
        result = self._validate(revision)
        findings = self.validation.get_validation_findings(result.identity)
        self.assertFalse(result.structural_valid)
        self.assertIn("duplicate_display_order", {item.rule for item in findings})
        self.assertEqual(before, self.fixture.subtitle.get_revision(revision.identity))
        self.assertTrue(all(item.revision_id == revision.identity for item in findings))

    def test_duplicate_revision_cue_reference_is_structural_failure(self):
        revision = self._accepted_revision()
        duplicate = replace(
            revision,
            cue_ids=(revision.cue_ids[0], revision.cue_ids[0]),
        )
        self.fixture.subtitle.revisions.save(duplicate)
        result = self._validate(duplicate)
        self.assertFalse(result.structural_valid)
        self.assertIn(
            "duplicate_cue_reference",
            {
                finding.rule
                for finding in self.validation.get_validation_findings(
                    result.identity
                )
            },
        )

    def test_modified_revision_validates_replacement_cue_not_original(self):
        revision, application_result = self._modified_revision()
        result = self._validate(revision)
        self.assertTrue(result.structural_valid)
        self.assertIn(application_result.replacement_cue_id, result.target_cue_ids)
        self.assertNotIn(application_result.original_cue_id, result.target_cue_ids)
        replacement = self.fixture.subtitle.get_cue(
            application_result.replacement_cue_id
        )
        self.assertEqual(application_result.original_cue_id, replacement.replaces_cue_id)

    def test_missing_cue_is_invalid_request_and_persists_nothing(self):
        revision = self._accepted_revision()
        corrupt = replace(
            revision,
            cue_ids=(SubtitleCueId("missing-revision-cue"),),
        )
        self.fixture.subtitle.revisions.save(corrupt)
        with self.assertRaisesRegex(KeyError, "unknown Cue"):
            self._validate(corrupt)
        self._assert_no_validation("revision-validation")

    def test_lineage_and_timeline_mismatch_are_invalid_requests(self):
        revision = self._accepted_revision()
        cue = self.fixture.subtitle.get_cue(revision.cue_ids[0])
        mismatches = (
            replace(cue, subtitle_id=replace(revision.subtitle_id, value="other")),
            replace(cue, source_timeline_id=SourceTimelineId("other-timeline")),
        )
        for index, corrupt in enumerate(mismatches):
            with self.subTest(index=index):
                self.fixture.subtitle.cues.save(corrupt)
                with self.assertRaisesRegex(ValueError, "lineage"):
                    self._validate(
                        revision,
                        validation_id=f"invalid-lineage-{index}",
                    )
                self._assert_no_validation(f"invalid-lineage-{index}")
                self.fixture.subtitle.cues.save(cue)

    def test_invalid_replacement_lineage_is_rejected_before_persistence(self):
        revision, application_result = self._modified_revision()
        replacement = self.fixture.subtitle.get_cue(
            application_result.replacement_cue_id
        )
        self.fixture.subtitle.cues.save(
            replace(replacement, replaces_cue_id=SubtitleCueId("missing-original"))
        )
        with self.assertRaisesRegex(KeyError, "original"):
            self._validate(revision)
        self._assert_no_validation("revision-validation")

    def test_validation_execution_and_working_context_must_match(self):
        revision = self._accepted_revision()
        with self.assertRaisesRegex(KeyError, "execution provenance"):
            self._validate(
                revision,
                run_id=ProcessingRunId("wrong-run"),
            )
        self._assert_no_validation("revision-validation")
        with self.assertRaisesRegex(ValueError, "execution provenance"):
            self._validate(
                revision,
                validation_id="wrong-context-validation",
                working_context=WorkingContextReference("wrong-context"),
            )
        self._assert_no_validation("wrong-context-validation")

    def test_duplicate_validation_identity_is_rejected(self):
        revision = self._accepted_revision()
        first = self._validate(revision)
        with self.assertRaisesRegex(ValueError, "identity already exists"):
            self._validate(revision)
        self.assertEqual(first, self.fixture.subtitle.get_validation(first.identity))

    def test_finding_collision_does_not_leave_result(self):
        revision = self._accepted_revision()
        second = self.fixture.subtitle.get_cue(revision.cue_ids[1])
        self.fixture.subtitle.cues.save(replace(second, display_order=0))
        finding_id = SubtitleValidationFindingId("collision-validation:0")
        self.fixture.subtitle.findings.save(
            SubtitleValidationFinding(
                identity=finding_id,
                validation_id=SubtitleValidationId("other-validation"),
                rule="existing",
                description="identity collision fixture",
                blocking=True,
            )
        )
        with self.assertRaisesRegex(ValueError, "finding identity already exists"):
            self._validate(revision, validation_id="collision-validation")
        self._assert_no_validation("collision-validation")

    def test_revalidation_is_append_only_and_explicitly_ordered(self):
        revision = self._accepted_revision()
        first = self._validate(revision, validation_id="revision-validation-1")
        second = self._validate(revision, validation_id="revision-validation-2")
        history = self.validation.get_revision_validation_history(revision.identity)
        self.assertEqual((first, second), history)
        self.assertEqual(0, first.sequence)
        self.assertEqual(1, second.sequence)
        self.assertEqual(first.identity, second.previous_validation_id)
        self.assertEqual(
            second,
            self.validation.get_latest_revision_validation(revision.identity),
        )
        self.assertEqual(first, self.fixture.subtitle.get_validation(first.identity))

    def test_validation_does_not_change_applicability_review_or_application(self):
        revision, application_result = self._modified_revision()
        before_review = self.fixture.review.get_decision(
            application_result.source_decision_id
        )
        before_result = self.fixture.application.get_subtitle_application_result(
            application_result.identity
        )
        before_selection = self.applicability.selection_records.all()
        before_conditions = self.applicability.condition_records.all()
        self._validate(revision)
        self.assertEqual(before_selection, self.applicability.selection_records.all())
        self.assertEqual(before_conditions, self.applicability.condition_records.all())
        self.assertEqual(
            before_review,
            self.fixture.review.get_decision(application_result.source_decision_id),
        )
        self.assertEqual(
            before_result,
            self.fixture.application.get_subtitle_application_result(
                application_result.identity
            ),
        )

    def test_validation_creates_no_final_export_or_human_decision(self):
        revision = self._accepted_revision()
        result = self._validate(revision)
        self.assertFalse(hasattr(result, "final_subtitle_id"))
        self.assertFalse(hasattr(result, "artifact_id"))
        self.assertFalse(hasattr(self.validation, "accept"))
        self.assertFalse(hasattr(self.validation, "select_current_revision"))

    def _accepted_revision(self):
        _, approved = self.fixture._accept()
        application_result = self.fixture._apply(approved.identity)
        return self.fixture.subtitle.get_revision(
            application_result.created_revision_id
        )

    def _modified_revision(self):
        _, modification, approved = self.fixture._modify()
        from lectureos.application.identities import SubtitleTextReplacementId
        from lectureos.application.models import SubtitleTextReplacement

        application_result = self.fixture._apply(
            approved.identity,
            text_replacement=SubtitleTextReplacement(
                identity=SubtitleTextReplacementId("revision-validation-replacement"),
                modification_id=modification.identity,
                target_cue_id=self.fixture.cues[0].identity,
                replacement_text="검증할 수정 자막",
            ),
            replacement_cue_id=SubtitleCueId("revision-validation-replacement-cue"),
        )
        revision = self.fixture.subtitle.get_revision(
            application_result.created_revision_id
        )
        return revision, application_result

    def _validate(
        self,
        revision,
        *,
        validation_id="revision-validation",
        working_context=None,
        run_id=None,
        unit_execution_id=None,
    ):
        return self.validation.validate_revision_in_context(
            validation_id=SubtitleValidationId(validation_id),
            revision_id=revision.identity,
            working_context=working_context or self.fixture.working_context,
            run_id=run_id or self.fixture.run_id,
            unit_execution_id=unit_execution_id or self.fixture.execution_id,
        )

    def _assert_no_validation(self, validation_id):
        identity = SubtitleValidationId(validation_id)
        self.assertIsNone(self.fixture.subtitle.get_validation(identity))
        self.assertEqual((), self.validation.get_validation_findings(identity))


if __name__ == "__main__":
    unittest.main()
