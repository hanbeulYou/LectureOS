"""Record-level tests for the Edit Export Assembly (044 §23, GOAL-030).

Pins what the identity binds, what it deliberately leaves out, and the structural invariants of the
membership — without a database.
"""

import unittest

from lectureos.application.identities import (
    LectureApprovedEditDecisionId,
    LectureEditExportAssemblyId,
)
from lectureos.application.lecture_edit_export_assembly import (
    EDIT_EXPORT_ASSEMBLY_CONTRACT_VERSION,
    LectureEditExportAssembly,
    LectureEditExportAssemblyError,
    LectureEditExportAssemblyMember,
    canonical_member_order,
    derive_edit_export_assembly_identity,
    require_canonical_assembly_id,
    require_source_timeline,
)
from lectureos.execution.identities import SourceTimelineId

_TIMELINE = SourceTimelineId("timeline:lecture-1")
_A = LectureApprovedEditDecisionId("lecture-approved-edit-decision:" + "a" * 64)
_B = LectureApprovedEditDecisionId("lecture-approved-edit-decision:" + "b" * 64)


def _assembly(*members: LectureApprovedEditDecisionId, timeline=_TIMELINE):
    identity = derive_edit_export_assembly_identity(timeline, members)
    return LectureEditExportAssembly(
        identity=identity,
        source_timeline_id=timeline,
        members=tuple(
            LectureEditExportAssemblyMember(
                assembly_id=identity, ordinal=ordinal, approved_edit_decision_id=member
            )
            for ordinal, member in enumerate(members)
        ),
    )


class IdentityTests(unittest.TestCase):
    def test_identity_binds_the_timeline_and_the_exact_membership(self) -> None:
        self.assertEqual(
            derive_edit_export_assembly_identity(_TIMELINE, (_A, _B)),
            derive_edit_export_assembly_identity(_TIMELINE, (_A, _B)),
        )
        self.assertNotEqual(
            derive_edit_export_assembly_identity(_TIMELINE, (_A, _B)),
            derive_edit_export_assembly_identity(_TIMELINE, (_A,)),
        )
        self.assertNotEqual(
            derive_edit_export_assembly_identity(_TIMELINE, (_A,)),
            derive_edit_export_assembly_identity(
                SourceTimelineId("timeline:other"), (_A,)
            ),
        )

    def test_membership_must_participate_or_a_changed_scope_is_unrecordable(self) -> None:
        """Why EA-10 binds membership as well as the anchor.

        Membership is derived and total, so an upstream authority change legitimately makes a *new*
        assembly gather a different set. If only the timeline participated, that second assembly
        would collide with the first and could never be recorded.
        """

        first = _assembly(_A, _B)
        second = _assembly(_A)
        self.assertNotEqual(first.identity, second.identity)

    def test_a_tampered_identity_is_refused(self) -> None:
        good = _assembly(_A)
        with self.assertRaises(LectureEditExportAssemblyError):
            LectureEditExportAssembly(
                identity=LectureEditExportAssemblyId(
                    "lecture-edit-export-assembly:" + "0" * 64
                ),
                source_timeline_id=good.source_timeline_id,
                members=good.members,
            )

    def test_malformed_identity_strings_are_refused(self) -> None:
        for value in (
            "",
            "lecture-edit-export-assembly",
            "lecture-edit-export-assembly:short",
            "edit-export-assembly:" + "a" * 64,
        ):
            with self.assertRaises(LectureEditExportAssemblyError):
                require_canonical_assembly_id(value)

    def test_a_blank_source_timeline_is_refused(self) -> None:
        for value in ("", "   "):
            with self.assertRaises(LectureEditExportAssemblyError):
                require_source_timeline(value)


class MembershipTests(unittest.TestCase):
    def test_ordinals_are_contiguous_from_zero(self) -> None:
        identity = derive_edit_export_assembly_identity(_TIMELINE, (_A, _B))
        with self.assertRaises(LectureEditExportAssemblyError):
            LectureEditExportAssembly(
                identity=identity,
                source_timeline_id=_TIMELINE,
                members=(
                    LectureEditExportAssemblyMember(
                        assembly_id=identity, ordinal=0, approved_edit_decision_id=_A
                    ),
                    LectureEditExportAssemblyMember(
                        assembly_id=identity, ordinal=2, approved_edit_decision_id=_B
                    ),
                ),
            )

    def test_a_negative_ordinal_is_refused(self) -> None:
        with self.assertRaises(LectureEditExportAssemblyError):
            LectureEditExportAssemblyMember(
                assembly_id=LectureEditExportAssemblyId(
                    "lecture-edit-export-assembly:" + "a" * 64
                ),
                ordinal=-1,
                approved_edit_decision_id=_A,
            )

    def test_one_approved_edit_appears_at_most_once_per_assembly(self) -> None:
        identity = derive_edit_export_assembly_identity(_TIMELINE, (_A, _A))
        with self.assertRaises(LectureEditExportAssemblyError):
            LectureEditExportAssembly(
                identity=identity,
                source_timeline_id=_TIMELINE,
                members=(
                    LectureEditExportAssemblyMember(
                        assembly_id=identity, ordinal=0, approved_edit_decision_id=_A
                    ),
                    LectureEditExportAssemblyMember(
                        assembly_id=identity, ordinal=1, approved_edit_decision_id=_A
                    ),
                ),
            )

    def test_members_must_belong_to_their_assembly(self) -> None:
        identity = derive_edit_export_assembly_identity(_TIMELINE, (_A,))
        with self.assertRaises(LectureEditExportAssemblyError):
            LectureEditExportAssembly(
                identity=identity,
                source_timeline_id=_TIMELINE,
                members=(
                    LectureEditExportAssemblyMember(
                        assembly_id=LectureEditExportAssemblyId(
                            "lecture-edit-export-assembly:" + "c" * 64
                        ),
                        ordinal=0,
                        approved_edit_decision_id=_A,
                    ),
                ),
            )

    def test_the_record_itself_carries_at_least_one_member(self) -> None:
        """Not an empty-scope policy — that is undecided and refused earlier, by the service."""

        identity = derive_edit_export_assembly_identity(_TIMELINE, ())
        with self.assertRaises(LectureEditExportAssemblyError):
            LectureEditExportAssembly(
                identity=identity, source_timeline_id=_TIMELINE, members=()
            )

    def test_an_unsupported_contract_version_is_refused(self) -> None:
        good = _assembly(_A)
        with self.assertRaises(LectureEditExportAssemblyError):
            LectureEditExportAssembly(
                identity=good.identity,
                source_timeline_id=good.source_timeline_id,
                members=good.members,
                assembly_contract_version=EDIT_EXPORT_ASSEMBLY_CONTRACT_VERSION + 1,
            )


class OwnedFieldTests(unittest.TestCase):
    def test_the_assembly_copies_no_approved_payload_and_no_execution_provenance(self) -> None:
        """EA-2/EA-8: it references its members and owns no snapshot, result, or execution."""

        fields = set(LectureEditExportAssembly.__dataclass_fields__)
        self.assertEqual(
            fields,
            {
                "identity",
                "source_timeline_id",
                "members",
                "assembly_contract_version",
            },
        )
        member_fields = set(LectureEditExportAssemblyMember.__dataclass_fields__)
        self.assertEqual(
            member_fields,
            {"assembly_id", "ordinal", "approved_edit_decision_id"},
        )

    def test_no_status_currentness_or_selection_field_exists(self) -> None:
        """EA-7 and §20 A-12: no lifecycle, no stored currentness, no selection."""

        for forbidden in (
            "status",
            "lifecycle",
            "is_current",
            "current",
            "stale",
            "selected",
            "selection",
            "domain_result_id",
            "processing_run_id",
            "unit_execution_id",
            "created_at",
        ):
            self.assertNotIn(forbidden, LectureEditExportAssembly.__dataclass_fields__)
            self.assertNotIn(
                forbidden, LectureEditExportAssemblyMember.__dataclass_fields__
            )


class OrderTests(unittest.TestCase):
    def test_canonical_order_is_a_pure_function_of_the_member_set(self) -> None:
        class _Fake:
            def __init__(self, identity):
                self.identity = identity

        one, two = _Fake(_A), _Fake(_B)
        self.assertEqual(
            [d.identity for d in canonical_member_order((two, one))],
            [d.identity for d in canonical_member_order((one, two))],
        )
        self.assertEqual(
            [d.identity for d in canonical_member_order((two, one))], [_A, _B]
        )


if __name__ == "__main__":
    unittest.main()
