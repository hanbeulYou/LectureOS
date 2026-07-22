import unittest

from lectureos.application import (
    RULE_OVERLAP_ADJACENT,
    SubtitleValidation,
    SubtitleValidationCategory,
    SubtitleValidationFinding,
    SubtitleValidationIdentityPlan,
    finding_identity,
)
from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleTranscriptIntakeId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)


def _finding(**overrides) -> SubtitleValidationFinding:
    base = dict(
        identity=SubtitleValidationFindingId("finding-0"),
        validation_id=SubtitleValidationId("validation"),
        rule=RULE_OVERLAP_ADJACENT,
        category=SubtitleValidationCategory.OVERLAP,
        blocking=True,
        description="timed unit overlaps the following unit",
        target_timed_unit_id=SubtitleTimedUnitId("timed-1"),
    )
    base.update(overrides)
    return SubtitleValidationFinding(**base)


def _validation(**overrides) -> SubtitleValidation:
    base = dict(
        identity=SubtitleValidationId("validation"),
        domain_result_id=DomainResultId("validation-result"),
        source_time_revision_id=SubtitleTimeRevisionId("time"),
        source_reading_revision_id=SubtitleReadingRevisionId("reading"),
        source_candidate_id=SubtitleCandidateId("candidate"),
        source_intake_id=SubtitleTranscriptIntakeId("intake"),
        source_readiness_id=TranscriptReadinessEvaluationId("readiness"),
        source_selection_id=TranscriptCurrentSelectionId("selection"),
        source_applicability_id=TranscriptApplicabilityEvaluationId("evaluation"),
        source_decision_id=TranscriptReviewDecisionId("decision"),
        review_item_id=ReviewItemId("item"),
        candidate_reference_id=CandidateReferenceId("reference"),
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("revision"),
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        source_transcript_validation_id=TranscriptValidationId("transcript-validation"),
        structural_valid=True,
        provenance_complete=True,
        timeline_traceable=True,
        ordering_consistent=True,
        time_consistent=True,
        finding_ids=(),
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="structural validation of the time revision",
    )
    base.update(overrides)
    return SubtitleValidation(**base)


class SubtitleValidationFindingTests(unittest.TestCase):
    def test_valid_finding(self) -> None:
        self.assertEqual(_finding().rule, RULE_OVERLAP_ADJACENT)

    def test_rule_is_independent_of_description(self) -> None:
        # Same stable rule, different explanatory wording.
        a = _finding(description="units overlap")
        b = _finding(description="the display intervals overlap on the source timeline")
        self.assertEqual(a.rule, b.rule)
        self.assertNotEqual(a.description, b.description)

    def test_revision_level_finding_allows_null_target(self) -> None:
        self.assertIsNone(_finding(target_timed_unit_id=None).target_timed_unit_id)

    def test_rule_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _finding(rule="  ")

    def test_description_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _finding(description="  ")


class SubtitleValidationTests(unittest.TestCase):
    def test_valid_empty_findings_is_structurally_valid(self) -> None:
        validation = _validation()
        self.assertTrue(validation.structural_valid)
        self.assertEqual(validation.finding_ids, ())

    def test_validation_with_findings(self) -> None:
        validation = _validation(
            structural_valid=False,
            time_consistent=False,
            finding_ids=(
                SubtitleValidationFindingId("f-0"),
                SubtitleValidationFindingId("f-1"),
            ),
        )
        self.assertEqual(len(validation.finding_ids), 2)

    def test_finding_ids_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            _validation(
                finding_ids=(
                    SubtitleValidationFindingId("f-0"),
                    SubtitleValidationFindingId("f-0"),
                )
            )

    def test_sequence_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _validation(sequence=-1)

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _validation(reason="  ")

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _validation(
                sequence=0,
                previous_validation_id=SubtitleValidationId("earlier"),
            )

    def test_later_may_reference_previous(self) -> None:
        validation = _validation(
            sequence=1, previous_validation_id=SubtitleValidationId("earlier")
        )
        self.assertEqual(
            validation.previous_validation_id, SubtitleValidationId("earlier")
        )


class FindingIdentityTests(unittest.TestCase):
    def test_deterministic_derivation(self) -> None:
        vid = SubtitleValidationId("validation")
        self.assertEqual(finding_identity(vid, 0), finding_identity(vid, 0))
        self.assertNotEqual(finding_identity(vid, 0), finding_identity(vid, 1))

    def test_negative_ordinal_rejected(self) -> None:
        with self.assertRaises(ValueError):
            finding_identity(SubtitleValidationId("validation"), -1)


class SubtitleValidationIdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = SubtitleValidationIdentityPlan(
            validation_id=SubtitleValidationId("validation"),
            validation_result_id=DomainResultId("validation-result"),
        )
        self.assertEqual(plan.validation_id, SubtitleValidationId("validation"))


if __name__ == "__main__":
    unittest.main()
