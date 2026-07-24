import dataclasses
import unittest

from lectureos.application import (
    EDIT_EXPORT_ASSEMBLY_RESULT_KIND,
    EditExportAssembly,
    EditExportAssemblyError,
    EditExportAssemblyIdentityPlan,
    EditExportAssemblyService,
)
from lectureos.application.edit_export import ApprovedEditExportRepresentation
from lectureos.application.edit_review import EditReviewDecisionKind
from lectureos.application.identities import (
    AnalysisFindingId,
    ApprovedEditDecisionId,
    ApprovedEditExportRepresentationId,
    EditCandidateId,
    EditExportAssemblyId,
    EditReviewDecisionId,
)
from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    ProcessingUnitId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import ExecutionIntent, ProcessingUnit
from lectureos.execution.service import ExecutionService
from lectureos.review.identities import HumanActorReference

_MEDIA = SourceMediaId("media")
_TIMELINE = SourceTimelineId("timeline")
_ACTOR = HumanActorReference("reviewer:alice")


def _rep(name, *, timeline=_TIMELINE, media=_MEDIA):
    return ApprovedEditExportRepresentation(
        identity=ApprovedEditExportRepresentationId(name),
        domain_result_id=DomainResultId(f"{name}-result"),
        source_approved_decision_id=ApprovedEditDecisionId(f"{name}-approved"),
        source_review_decision_id=EditReviewDecisionId(f"{name}-review"),
        source_candidate_id=EditCandidateId(f"{name}-candidate"),
        decision_kind=EditReviewDecisionKind.ACCEPT,
        approved_range_start=0.5,
        approved_range_end=1.5,
        approved_candidate_type="non_lecture_region",
        approved_rationale="approved rationale",
        actor=_ACTOR,
        source_media_id=media,
        source_timeline_id=timeline,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
    )


class _Repo:
    def __init__(self, records):
        self._records = {r.identity: r for r in records}

    def get(self, identity):
        return self._records.get(identity)


def _plan(name="a"):
    return EditExportAssemblyIdentityPlan(
        assembly_id=EditExportAssemblyId(f"assembly-{name}"),
        assembly_result_id=DomainResultId(f"assembly-{name}-result"),
    )


class EditExportAssemblyDomainTests(unittest.TestCase):
    def _members(self, *names):
        return tuple(
            sorted(
                (ApprovedEditExportRepresentationId(n) for n in names),
                key=lambda i: i.value,
            )
        )

    def _assembly(self, members):
        return EditExportAssembly(
            identity=EditExportAssemblyId("a"),
            domain_result_id=DomainResultId("a-result"),
            source_media_id=_MEDIA,
            source_timeline_id=_TIMELINE,
            member_representation_ids=members,
            run_id=ProcessingRunId("run"),
            unit_execution_id=UnitExecutionId("execution"),
        )

    def test_valid_immutable_assembly(self) -> None:
        assembly = self._assembly(self._members("m1", "m2"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            assembly.source_timeline_id = _TIMELINE  # type: ignore[misc]

    def test_membership_must_be_non_empty(self) -> None:
        with self.assertRaises(ValueError):
            self._assembly(())

    def test_membership_must_be_unique(self) -> None:
        rep = ApprovedEditExportRepresentationId("dup")
        with self.assertRaises(ValueError):
            self._assembly((rep, rep))

    def test_membership_must_be_canonically_ordered(self) -> None:
        unordered = (
            ApprovedEditExportRepresentationId("m2"),
            ApprovedEditExportRepresentationId("m1"),
        )
        with self.assertRaises(ValueError):
            self._assembly(unordered)

    def test_no_status_or_format_or_artifact_fields(self) -> None:
        fields = set(EditExportAssembly.__dataclass_fields__)
        for forbidden in (
            "status", "state", "current", "superseded", "revision", "replacement",
            "profile", "configuration", "format", "mime_type", "filename", "path",
            "url", "checksum", "payload", "serialized", "artifact_id", "eligibility",
        ):
            self.assertNotIn(forbidden, fields)


class EditExportAssemblyServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = ProcessingRunId("run")
        self.execution_id = UnitExecutionId("execution")
        self.execution = ExecutionService()
        unit_id = ProcessingUnitId("unit")
        self.execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="edit-export-assembly",
                capabilities=(CapabilityReference("lecture.export"),),
            )
        )
        self.execution.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("edit-export-assembly"),
            working_context=WorkingContextReference("context"),
            unit_ids=(unit_id,),
        )
        self.execution.start_unit_execution(
            execution_id=self.execution_id, run_id=self.run_id, unit_id=unit_id
        )
        self.m1 = _rep("m1")
        self.m2 = _rep("m2")
        self.m3 = _rep("m3")

    def _service(self, records=None):
        records = records if records is not None else (self.m1, self.m2, self.m3)
        return EditExportAssemblyService(_Repo(records), self.execution)

    def _evaluate(self, service, members, **overrides):
        base = dict(
            source_timeline_id=_TIMELINE,
            member_representation_ids=members,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=_plan(),
        )
        base.update(overrides)
        return service.evaluate_assembly(**base)

    def test_successful_creation_from_explicit_members(self) -> None:
        prepared = self._evaluate(
            self._service(), (self.m1.identity, self.m2.identity)
        )
        self.assertEqual(prepared.assembly.source_timeline_id, _TIMELINE)
        self.assertEqual(prepared.assembly.source_media_id, _MEDIA)
        self.assertEqual(
            prepared.assembly.member_representation_ids,
            tuple(sorted((self.m1.identity, self.m2.identity), key=lambda i: i.value)),
        )
        self.assertEqual(
            prepared.assembly_result.kind, EDIT_EXPORT_ASSEMBLY_RESULT_KIND
        )

    def test_multi_upstream_lineage_covers_all_members(self) -> None:
        prepared = self._evaluate(
            self._service(), (self.m1.identity, self.m2.identity, self.m3.identity)
        )
        canonical = tuple(
            sorted(
                (self.m1.identity, self.m2.identity, self.m3.identity),
                key=lambda i: i.value,
            )
        )
        by_id = {self.m1.identity: self.m1, self.m2.identity: self.m2, self.m3.identity: self.m3}
        self.assertEqual(
            prepared.assembly_result.upstream_results,
            tuple(by_id[i].domain_result_id for i in canonical),
        )
        self.assertEqual(len(prepared.assembly_result.upstream_results), 3)

    def test_reordered_input_normalizes_to_same_canonical_assembly(self) -> None:
        forward = self._evaluate(
            self._service(), (self.m1.identity, self.m2.identity, self.m3.identity)
        )
        reversed_ = self._evaluate(
            self._service(), (self.m3.identity, self.m2.identity, self.m1.identity)
        )
        self.assertEqual(forward.assembly, reversed_.assembly)
        self.assertEqual(forward.assembly_result, reversed_.assembly_result)

    def test_empty_membership_rejected(self) -> None:
        with self.assertRaises(EditExportAssemblyError):
            self._evaluate(self._service(), ())

    def test_duplicate_membership_rejected(self) -> None:
        with self.assertRaises(EditExportAssemblyError):
            self._evaluate(self._service(), (self.m1.identity, self.m1.identity))

    def test_missing_member_rejected(self) -> None:
        with self.assertRaises(KeyError):
            self._evaluate(
                self._service(),
                (self.m1.identity, ApprovedEditExportRepresentationId("missing")),
            )

    def test_cross_timeline_member_rejected(self) -> None:
        other = _rep("other", timeline=SourceTimelineId("other-timeline"))
        with self.assertRaises(EditExportAssemblyError):
            self._evaluate(
                self._service((self.m1, other)),
                (self.m1.identity, other.identity),
            )

    def test_mismatched_anchor_rejected(self) -> None:
        with self.assertRaises(EditExportAssemblyError):
            self._evaluate(
                self._service(),
                (self.m1.identity,),
                source_timeline_id=SourceTimelineId("different-anchor"),
            )

    def test_cross_media_member_rejected(self) -> None:
        other = _rep("other-media", media=SourceMediaId("other-media"))
        with self.assertRaises(EditExportAssemblyError):
            self._evaluate(
                self._service((self.m1, other)),
                (self.m1.identity, other.identity),
            )

    def test_non_running_execution_rejected(self) -> None:
        self.execution.cancel_unit_execution(self.execution_id)
        with self.assertRaises(EditExportAssemblyError):
            self._evaluate(self._service(), (self.m1.identity,))

    def test_unknown_run_rejected(self) -> None:
        with self.assertRaises(KeyError):
            self._evaluate(
                self._service(),
                (self.m1.identity,),
                run_id=ProcessingRunId("missing-run"),
            )

    def test_deterministic_construction(self) -> None:
        members = (self.m1.identity, self.m2.identity)
        self.assertEqual(
            self._evaluate(self._service(), members),
            self._evaluate(self._service(), members),
        )

    def test_no_implicit_member_discovery(self) -> None:
        # Only the explicitly supplied member is admitted, never every representation in the repository.
        prepared = self._evaluate(self._service(), (self.m1.identity,))
        self.assertEqual(
            prepared.assembly.member_representation_ids, (self.m1.identity,)
        )

    def test_record_without_persistence_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            self._service().record_assembly(
                source_timeline_id=_TIMELINE,
                member_representation_ids=(self.m1.identity,),
                run_id=self.run_id,
                unit_execution_id=self.execution_id,
                identities=_plan(),
            )


if __name__ == "__main__":
    unittest.main()
