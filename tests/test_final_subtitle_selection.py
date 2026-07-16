import unittest
from dataclasses import replace
from pathlib import Path

from lectureos.execution.identities import (
    DomainResultId,
    PluginReference,
    WorkingContextReference,
)
from lectureos.review.identities import HumanActorReference
from lectureos.subtitle.applicability import (
    SubtitleApplicabilityService,
    SubtitleConditionReason,
    SubtitleSelectionReason,
)
from lectureos.subtitle.final_selection import (
    FinalSubtitleSelection,
    FinalSubtitleSelectionIntegrityError,
    FinalSubtitleSelectionReason,
    FinalSubtitleSelectionService,
)
from lectureos.subtitle.identities import (
    FinalSubtitleSelectionId,
    SubtitleCueId,
    SubtitleRevisionApplicabilityId,
    SubtitleRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from lectureos.subtitle.models import SubtitleValidationFinding
from lectureos.subtitle.validation import SubtitleValidationService
from tests import test_subtitle_decision_application as subtitle_application_fixture


class FinalSubtitleSelectionTest(unittest.TestCase):
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
            self.fixture.subtitle,
            self.fixture.execution,
        )
        self.service = FinalSubtitleSelectionService(
            self.fixture.subtitle,
            self.validation,
            self.applicability,
            self.fixture.execution,
        )
        self.actor = HumanActorReference("final-subtitle-selector")
        self.first = self._accepted_revision()

    def test_current_valid_revision_can_be_selected_as_final(self):
        validation = self._validate(self.first)
        current = self._select_current(self.first)
        before_revision = self.fixture.subtitle.get_revision(self.first.identity)
        before_cues = tuple(
            self.fixture.subtitle.get_cue(cue_id) for cue_id in self.first.cue_ids
        )
        selected = self._select_final(self.first, validation.identity)
        self.assertNotEqual(self.first.identity.value, selected.identity.value)
        self.assertEqual(self.first.identity, selected.revision_id)
        self.assertEqual(self.actor, selected.actor)
        self.assertEqual(self.fixture.working_context, selected.working_context)
        self.assertEqual(self.first.subtitle_id, selected.subtitle_id)
        self.assertEqual(validation.identity, selected.validation_id)
        self.assertEqual(current.identity, selected.current_applicability_id)
        self.assertEqual(before_revision, self.fixture.subtitle.get_revision(self.first.identity))
        self.assertEqual(
            before_cues,
            tuple(self.fixture.subtitle.get_cue(cue_id) for cue_id in self.first.cue_ids),
        )
        self.assertFalse(hasattr(selected, "artifact_id"))

    def test_final_requires_human_actor(self):
        validation = self._prepare(self.first)
        with self.assertRaisesRegex(TypeError, "Human Actor"):
            self._select_final(
                self.first,
                validation.identity,
                actor=PluginReference("provider"),
            )
        self._assert_no_final()

    def test_non_current_superseded_and_historical_revisions_are_rejected(self):
        validation = self._validate(self.first)
        with self.assertRaisesRegex(ValueError, "current Revision"):
            self._select_final(self.first, validation.identity)
        self._assert_no_final()

        self._select_current(self.first)
        self.applicability.mark_revision_superseded(
            identity=SubtitleRevisionApplicabilityId("first-superseded"),
            working_context=self.fixture.working_context,
            revision_id=self.first.identity,
            actor=self.actor,
            reason=SubtitleSelectionReason.REPLACEMENT_SELECTION,
        )
        with self.assertRaisesRegex(ValueError, "current Revision"):
            self._select_final(self.first, validation.identity)
        self._assert_no_final()

        self.applicability.mark_revision_historical(
            identity=SubtitleRevisionApplicabilityId("first-historical"),
            working_context=self.fixture.working_context,
            revision_id=self.first.identity,
            actor=self.actor,
            reason=SubtitleSelectionReason.MANUAL_HISTORICAL,
        )
        with self.assertRaisesRegex(ValueError, "current Revision"):
            self._select_final(self.first, validation.identity)
        self._assert_no_final()

    def test_other_current_revision_blocks_target_without_changing_applicability(self):
        second = self._derived_revision("second")
        first_validation = self._validate(self.first)
        self._select_current(second)
        before = self.applicability.selection_records.all()
        with self.assertRaisesRegex(ValueError, "current Revision"):
            self._select_final(self.first, first_validation.identity)
        self.assertEqual(before, self.applicability.selection_records.all())
        self._assert_no_final()

    def test_stale_current_requires_typed_acknowledgment_and_remains_stale(self):
        validation = self._prepare(self.first)
        stale = self.applicability.mark_revision_stale(
            identity=SubtitleRevisionApplicabilityId("final-stale"),
            working_context=self.fixture.working_context,
            revision_id=self.first.identity,
            actor=self.actor,
            reason=SubtitleConditionReason.MANUAL_STALE,
        )
        with self.assertRaisesRegex(ValueError, "acknowledgment"):
            self._select_final(self.first, validation.identity)
        selected = self._select_final(
            self.first,
            validation.identity,
            stale_condition_acknowledged=True,
        )
        self.assertTrue(selected.stale_condition_acknowledged)
        self.assertEqual(stale.identity, selected.stale_condition_id)
        self.assertTrue(
            self.applicability.is_revision_stale(
                self.fixture.working_context, self.first.identity
            )
        )

    def test_acknowledgment_is_rejected_when_revision_is_not_stale(self):
        validation = self._prepare(self.first)
        with self.assertRaisesRegex(ValueError, "requires a stale Revision"):
            self._select_final(
                self.first,
                validation.identity,
                stale_condition_acknowledged=True,
            )
        self._assert_no_final()

    def test_latest_revision_validation_is_required(self):
        self._select_current(self.first)
        with self.assertRaisesRegex(ValueError, "requires Revision Validation"):
            self._select_final(self.first, SubtitleValidationId("missing"))
        first = self._validate(self.first, "first-validation")
        latest = self._validate(self.first, "latest-validation")
        with self.assertRaisesRegex(ValueError, "latest Revision Validation"):
            self._select_final(self.first, first.identity)
        selected = self._select_final(self.first, latest.identity)
        self.assertEqual(latest.identity, selected.validation_id)

    def test_candidate_validation_cannot_be_final_evidence(self):
        candidate_validation = self.validation.validate_candidate(
            validation_id=SubtitleValidationId("candidate-only-validation"),
            candidate_id=self.fixture.candidate.identity,
            run_id=self.fixture.run_id,
            unit_execution_id=self.fixture.execution_id,
        )
        self._select_current(self.first)
        with self.assertRaisesRegex(ValueError, "Revision Validation"):
            self._select_final(self.first, candidate_validation.identity)
        self._assert_no_final()

    def test_latest_invalid_validation_blocks_final_selection(self):
        first = self._prepare(self.first, validation_id="valid-before-failure")
        cue = self.fixture.subtitle.get_cue(self.first.cue_ids[1])
        self.fixture.subtitle.cues.save(replace(cue, display_order=0))
        failed = self._validate(self.first, "latest-failed-validation")
        self.assertFalse(failed.structural_valid)
        with self.assertRaisesRegex(ValueError, "structurally invalid"):
            self._select_final(self.first, failed.identity)
        with self.assertRaisesRegex(ValueError, "latest Revision Validation"):
            self._select_final(self.first, first.identity)
        self._assert_no_final()

    def test_non_blocking_findings_allow_final_selection(self):
        cue = self.fixture.subtitle.get_cue(self.first.cue_ids[1])
        self.fixture.subtitle.cues.save(replace(cue, start=1.5))
        validation = self._prepare(self.first)
        findings = self.validation.get_validation_findings(validation.identity)
        self.assertTrue(validation.structural_valid)
        self.assertTrue(findings)
        self.assertTrue(all(not finding.blocking for finding in findings))
        selected = self._select_final(self.first, validation.identity)
        self.assertEqual(validation.identity, selected.validation_id)

    def test_validation_context_and_cue_evidence_must_match(self):
        validation = self._prepare(self.first)
        self.fixture.subtitle.validations.save(
            replace(
                validation,
                working_context=WorkingContextReference("wrong-context"),
            )
        )
        with self.assertRaisesRegex(ValueError, "Validation evidence"):
            self._select_final(self.first, validation.identity)
        self._assert_no_final()

    def test_blocking_finding_blocks_even_if_result_claims_structural_validity(self):
        validation = self._prepare(self.first)
        finding = SubtitleValidationFinding(
            identity=SubtitleValidationFindingId("forced-blocking-finding"),
            validation_id=validation.identity,
            revision_id=self.first.identity,
            rule="forced_blocking",
            description="blocking integrity fixture",
            blocking=True,
        )
        self.fixture.subtitle.findings.save(finding)
        self.fixture.subtitle.validations.save(
            replace(validation, finding_ids=(finding.identity,))
        )
        with self.assertRaisesRegex(ValueError, "structurally invalid"):
            self._select_final(self.first, validation.identity)
        self._assert_no_final()

    def test_unknown_revision_missing_cue_and_wrong_context_leave_no_write(self):
        validation = self._prepare(self.first)
        with self.assertRaisesRegex(KeyError, "unknown Subtitle Revision"):
            self.service.select_final_subtitle(
                identity=FinalSubtitleSelectionId("unknown-revision-final"),
                working_context=self.fixture.working_context,
                revision_id=SubtitleRevisionId("missing-revision"),
                actor=self.actor,
                validation_id=validation.identity,
                reason=FinalSubtitleSelectionReason.MANUAL_SELECTION,
            )
        self._assert_no_final()

        self.fixture.subtitle.revisions.save(
            replace(self.first, cue_ids=(SubtitleCueId("missing-final-cue"),))
        )
        with self.assertRaisesRegex(KeyError, "unknown Cue"):
            self._select_final(self.first, validation.identity)
        self._assert_no_final()
        self.fixture.subtitle.revisions.save(self.first)

        with self.assertRaisesRegex(ValueError, "Working Context"):
            self.service.select_final_subtitle(
                identity=FinalSubtitleSelectionId("wrong-context-final"),
                working_context=WorkingContextReference("wrong-context"),
                revision_id=self.first.identity,
                actor=self.actor,
                validation_id=validation.identity,
                reason=FinalSubtitleSelectionReason.MANUAL_SELECTION,
            )
        self._assert_no_final()

    def test_replacement_appends_history_and_preserves_previous_final(self):
        first_validation = self._prepare(self.first)
        first_final = self._select_final(self.first, first_validation.identity)
        second = self._derived_revision("replacement")
        second_validation = self._validate(second, "replacement-validation")
        self._select_current(
            second,
            identity="replacement-current",
            superseded_identity="first-current-superseded",
        )
        second_final = self._select_final(
            second,
            second_validation.identity,
            identity="replacement-final",
            reason=FinalSubtitleSelectionReason.REPLACEMENT_SELECTION,
        )
        self.assertEqual(first_final.identity, second_final.previous_final_selection_id)
        self.assertEqual(1, second_final.sequence)
        self.assertEqual(
            (first_final, second_final),
            self.service.get_final_selection_history(
                self.fixture.working_context, self.first.subtitle_id
            ),
        )
        self.assertEqual(
            second_final,
            self.service.get_latest_final_selection(
                self.fixture.working_context, self.first.subtitle_id
            ),
        )
        self.assertEqual(first_final, self.service.get_final_selection(first_final.identity))
        self.assertEqual(
            (first_final,),
            self.service.get_final_selections_for_revision(self.first.identity),
        )
        self.assertFalse(
            self.service.is_active_final(
                self.fixture.working_context,
                self.first.subtitle_id,
                self.first.identity,
            )
        )
        self.assertTrue(
            self.service.is_active_final(
                self.fixture.working_context,
                self.first.subtitle_id,
                second.identity,
            )
        )

    def test_same_active_target_selection_is_idempotent(self):
        validation = self._prepare(self.first)
        first = self._select_final(self.first, validation.identity)
        repeated = self._select_final(
            self.first,
            validation.identity,
            identity="unused-final-identity",
            actor=HumanActorReference("different-human"),
            reason=FinalSubtitleSelectionReason.OTHER,
        )
        self.assertEqual(first, repeated)
        self.assertEqual(1, len(self.service.selections.all()))
        self._validate(self.first, "new-validation-does-not-select-final")
        self.assertEqual(1, len(self.service.selections.all()))

    def test_invalid_reason_and_identity_collision_leave_no_partial_write(self):
        validation = self._prepare(self.first)
        with self.assertRaisesRegex(ValueError, "typed reason"):
            self._select_final(
                self.first,
                validation.identity,
                reason="manual_selection",
            )
        self._assert_no_final()
        with self.assertRaisesRegex(ValueError, "requires a note"):
            self._select_final(
                self.first,
                validation.identity,
                reason=FinalSubtitleSelectionReason.OTHER,
            )
        self._assert_no_final()

        collision = FinalSubtitleSelection(
            identity=FinalSubtitleSelectionId("final-selection"),
            working_context=WorkingContextReference("other-context"),
            subtitle_id=self.first.subtitle_id,
            revision_id=self.first.identity,
            actor=self.actor,
            validation_id=validation.identity,
            current_applicability_id=SubtitleRevisionApplicabilityId("other-current"),
            selected_at=validation.recorded_at,
            sequence=0,
            reason=FinalSubtitleSelectionReason.MANUAL_SELECTION,
        )
        self.service.selections.save(collision)
        with self.assertRaisesRegex(ValueError, "identity already exists"):
            self._select_final(self.first, validation.identity)
        self.assertEqual((collision,), self.service.selections.all())

    def test_corrupt_history_is_not_silently_treated_as_latest(self):
        validation = self._prepare(self.first)
        selected = self._select_final(self.first, validation.identity)
        self.service.selections._records[selected.identity] = replace(
            selected, sequence=2
        )
        with self.assertRaisesRegex(
            FinalSubtitleSelectionIntegrityError, "history is corrupt"
        ):
            self.service.get_latest_final_selection(
                self.fixture.working_context, self.first.subtitle_id
            )

    def test_revision_and_replacement_lineage_are_checked_before_write(self):
        validation = self._prepare(self.first)
        cue = self.fixture.subtitle.get_cue(self.first.cue_ids[0])
        self.fixture.subtitle.cues.save(
            replace(cue, replaces_cue_id=replace(cue.identity, value="missing"))
        )
        with self.assertRaisesRegex(KeyError, "original is missing"):
            self._select_final(self.first, validation.identity)
        self._assert_no_final()

    def test_final_selection_changes_no_validation_applicability_or_review_records(self):
        validation = self._prepare(self.first)
        before = (
            self.fixture.subtitle.get_revision(self.first.identity),
            tuple(self.fixture.subtitle.get_cue(cue_id) for cue_id in self.first.cue_ids),
            self.fixture.subtitle.get_validation(validation.identity),
            self.applicability.selection_records.all(),
            self.applicability.condition_records.all(),
            self.fixture.review.decisions.all(),
            self.fixture.application._results.all(),
        )
        selected = self._select_final(self.first, validation.identity)
        after = (
            self.fixture.subtitle.get_revision(self.first.identity),
            tuple(self.fixture.subtitle.get_cue(cue_id) for cue_id in self.first.cue_ids),
            self.fixture.subtitle.get_validation(validation.identity),
            self.applicability.selection_records.all(),
            self.applicability.condition_records.all(),
            self.fixture.review.decisions.all(),
            self.fixture.application._results.all(),
        )
        self.assertEqual(before, after)
        self.assertFalse(hasattr(selected, "export_request_id"))
        self.assertFalse(hasattr(self.service, "withdraw_final"))

    def test_final_selection_uses_public_boundaries(self):
        source = Path("src/lectureos/subtitle/final_selection.py").read_text()
        self.assertNotIn("lectureos.review.repositories", source)
        self.assertNotIn("lectureos.execution.repositories", source)
        self.assertNotIn("lectureos.subtitle.repositories", source)

    def _accepted_revision(self):
        _, approved = self.fixture._accept()
        result = self.fixture._apply(approved.identity)
        return self.fixture.subtitle.get_revision(result.created_revision_id)

    def _derived_revision(self, suffix):
        revision = replace(
            self.first,
            identity=SubtitleRevisionId(f"final-{suffix}-revision"),
            domain_result_id=DomainResultId(f"final-{suffix}-result"),
            parent_candidate_id=None,
            parent_revision_id=self.first.identity,
            modification_provenance=f"final selection {suffix} fixture",
        )
        cues = tuple(
            self.fixture.subtitle.get_cue(cue_id) for cue_id in revision.cue_ids
        )
        self.fixture.subtitle.create_revision(revision, cues)
        return revision

    def _validate(self, revision, validation_id="final-revision-validation"):
        return self.validation.validate_revision_in_context(
            validation_id=SubtitleValidationId(validation_id),
            revision_id=revision.identity,
            working_context=self.fixture.working_context,
            run_id=self.fixture.run_id,
            unit_execution_id=self.fixture.execution_id,
        )

    def _select_current(
        self,
        revision,
        *,
        identity="final-current",
        superseded_identity=None,
    ):
        return self.applicability.select_current_revision(
            identity=SubtitleRevisionApplicabilityId(identity),
            superseded_identity=(
                SubtitleRevisionApplicabilityId(superseded_identity)
                if superseded_identity is not None
                else None
            ),
            working_context=self.fixture.working_context,
            revision_id=revision.identity,
            actor=self.actor,
            reason=SubtitleSelectionReason.MANUAL_SELECTION,
        )

    def _prepare(self, revision, validation_id="final-revision-validation"):
        validation = self._validate(revision, validation_id)
        self._select_current(revision)
        return validation

    def _select_final(
        self,
        revision,
        validation_id,
        *,
        identity="final-selection",
        actor=None,
        reason=FinalSubtitleSelectionReason.MANUAL_SELECTION,
        stale_condition_acknowledged=False,
    ):
        return self.service.select_final_subtitle(
            identity=FinalSubtitleSelectionId(identity),
            working_context=self.fixture.working_context,
            revision_id=revision.identity,
            actor=actor or self.actor,
            validation_id=validation_id,
            reason=reason,
            stale_condition_acknowledged=stale_condition_acknowledged,
        )

    def _assert_no_final(self):
        self.assertEqual((), self.service.selections.all())


if __name__ == "__main__":
    unittest.main()
