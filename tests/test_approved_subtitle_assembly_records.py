import unittest

from lectureos.application import (
    PreparedSubtitleApprovedDocument,
    SubtitleApprovedAssemblyIdentityPlan,
    SubtitleApprovedDocument,
    SubtitleApprovedUnit,
    SubtitleApprovedUnitOrigin,
    SubtitleExportEligibility,
)
from lectureos.application.identities import (
    SubtitleApprovedDocumentId,
    SubtitleApprovedUnitId,
    SubtitleCandidateId,
    SubtitleFinalSubtitleId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId


def _unit(**overrides) -> SubtitleApprovedUnit:
    base = dict(
        identity=SubtitleApprovedUnitId("approved-unit"),
        document_id=SubtitleApprovedDocumentId("document"),
        source_timed_unit_id=SubtitleTimedUnitId("timed"),
        source_reading_unit_id=SubtitleReadingUnitId("reading"),
        origin=SubtitleApprovedUnitOrigin.ACCEPTED,
        display_order=0,
        start=0.0,
        end=1.5,
        lines=("첫 자막",),
        source_final_subtitle_id=SubtitleFinalSubtitleId("final"),
    )
    base.update(overrides)
    return SubtitleApprovedUnit(**base)


def _document(**overrides) -> SubtitleApprovedDocument:
    base = dict(
        identity=SubtitleApprovedDocumentId("document"),
        domain_result_id=DomainResultId("document-result"),
        source_time_revision_id=SubtitleTimeRevisionId("time"),
        source_reading_revision_id=SubtitleReadingRevisionId("reading"),
        eligibility=SubtitleExportEligibility.ELIGIBLE,
        source_candidate_id=SubtitleCandidateId("candidate"),
        source_transcript_id=TranscriptId("raw"),
        source_revision_id=TranscriptRevisionId("transcript-revision"),
        source_media_id=SourceMediaId("media"),
        source_timeline_id=SourceTimelineId("timeline"),
        approved_unit_ids=(SubtitleApprovedUnitId("approved-unit"),),
        omitted_unit_count=0,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
        reason="assembled the approved subtitle document",
    )
    base.update(overrides)
    return SubtitleApprovedDocument(**base)


class SubtitleApprovedUnitTests(unittest.TestCase):
    def test_valid_accepted_unit(self) -> None:
        self.assertIs(_unit().origin, SubtitleApprovedUnitOrigin.ACCEPTED)

    def test_valid_modified_unit(self) -> None:
        unit = _unit(origin=SubtitleApprovedUnitOrigin.MODIFIED, lines=("고친 자막",))
        self.assertIs(unit.origin, SubtitleApprovedUnitOrigin.MODIFIED)

    def test_valid_untouched_unit_has_no_final(self) -> None:
        unit = _unit(
            origin=SubtitleApprovedUnitOrigin.UNTOUCHED, source_final_subtitle_id=None
        )
        self.assertIsNone(unit.source_final_subtitle_id)

    def test_untouched_must_not_reference_final(self) -> None:
        with self.assertRaises(ValueError):
            _unit(origin=SubtitleApprovedUnitOrigin.UNTOUCHED)

    def test_accepted_and_modified_require_final(self) -> None:
        with self.assertRaises(ValueError):
            _unit(source_final_subtitle_id=None)
        with self.assertRaises(ValueError):
            _unit(origin=SubtitleApprovedUnitOrigin.MODIFIED, source_final_subtitle_id=None)

    def test_timing_must_be_resolved(self) -> None:
        with self.assertRaises(ValueError):
            _unit(start=-0.1)
        with self.assertRaises(ValueError):
            _unit(start=2.0, end=1.0)

    def test_lines_must_be_present_and_non_blank(self) -> None:
        with self.assertRaises(ValueError):
            _unit(lines=())
        with self.assertRaises(ValueError):
            _unit(lines=("  ",))

    def test_display_order_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _unit(display_order=-1)


class SubtitleApprovedDocumentTests(unittest.TestCase):
    def test_valid_eligible_document(self) -> None:
        self.assertIs(_document().eligibility, SubtitleExportEligibility.ELIGIBLE)

    def test_eligible_must_not_carry_reason(self) -> None:
        with self.assertRaises(ValueError):
            _document(ineligibility_reason="x")

    def test_valid_ineligible_document(self) -> None:
        document = _document(
            eligibility=SubtitleExportEligibility.INELIGIBLE,
            ineligibility_reason="included unit lacks resolved timing",
            approved_unit_ids=(),
        )
        self.assertIs(document.eligibility, SubtitleExportEligibility.INELIGIBLE)

    def test_ineligible_requires_reason(self) -> None:
        with self.assertRaises(ValueError):
            _document(
                eligibility=SubtitleExportEligibility.INELIGIBLE, approved_unit_ids=()
            )
        with self.assertRaises(ValueError):
            _document(
                eligibility=SubtitleExportEligibility.INELIGIBLE,
                ineligibility_reason="  ",
                approved_unit_ids=(),
            )

    def test_ineligible_must_not_carry_units(self) -> None:
        with self.assertRaises(ValueError):
            _document(
                eligibility=SubtitleExportEligibility.INELIGIBLE,
                ineligibility_reason="incomplete",
            )

    def test_unit_ids_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            _document(
                approved_unit_ids=(
                    SubtitleApprovedUnitId("dup"),
                    SubtitleApprovedUnitId("dup"),
                )
            )

    def test_reason_must_not_be_blank(self) -> None:
        with self.assertRaises(ValueError):
            _document(reason="  ")

    def test_sequence_and_counts_must_not_be_negative(self) -> None:
        with self.assertRaises(ValueError):
            _document(sequence=-1)
        with self.assertRaises(ValueError):
            _document(omitted_unit_count=-1)

    def test_first_must_not_reference_previous(self) -> None:
        with self.assertRaises(ValueError):
            _document(
                sequence=0, previous_document_id=SubtitleApprovedDocumentId("earlier")
            )

    def test_later_may_reference_previous(self) -> None:
        document = _document(
            sequence=1, previous_document_id=SubtitleApprovedDocumentId("earlier")
        )
        self.assertEqual(
            document.previous_document_id, SubtitleApprovedDocumentId("earlier")
        )

    def test_zero_finding_eligible_document_has_untouched_units(self) -> None:
        document = _document(omitted_unit_count=0)
        self.assertIs(document.eligibility, SubtitleExportEligibility.ELIGIBLE)


class IdentityPlanTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = SubtitleApprovedAssemblyIdentityPlan(
            document_id=SubtitleApprovedDocumentId("document"),
            document_result_id=DomainResultId("document-result"),
            unit_ids=(SubtitleApprovedUnitId("u0"), SubtitleApprovedUnitId("u1")),
        )
        self.assertEqual(len(plan.unit_ids), 2)

    def test_plan_requires_unit_ids(self) -> None:
        with self.assertRaises(ValueError):
            SubtitleApprovedAssemblyIdentityPlan(
                document_id=SubtitleApprovedDocumentId("document"),
                document_result_id=DomainResultId("document-result"),
                unit_ids=(),
            )

    def test_plan_unit_ids_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            SubtitleApprovedAssemblyIdentityPlan(
                document_id=SubtitleApprovedDocumentId("document"),
                document_result_id=DomainResultId("document-result"),
                unit_ids=(SubtitleApprovedUnitId("u"), SubtitleApprovedUnitId("u")),
            )


class PreparedTests(unittest.TestCase):
    def test_prepared_holds_document_and_units(self) -> None:
        prepared = PreparedSubtitleApprovedDocument(
            document=_document(), units=(_unit(),), document_result=None
        )
        self.assertEqual(len(prepared.units), 1)


if __name__ == "__main__":
    unittest.main()
