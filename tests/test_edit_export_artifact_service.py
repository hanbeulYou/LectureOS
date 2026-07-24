import dataclasses
import unittest

from lectureos.application import (
    EditExportArtifact,
    EditExportArtifactEntry,
    EditExportArtifactError,
    EditExportArtifactService,
)
from lectureos.application.edit_export import ApprovedEditExportRepresentation
from lectureos.application.edit_export_assembly import EditExportAssembly
from lectureos.application.edit_review import EditReviewDecisionKind
from lectureos.application.identities import (
    AnalysisFindingId,
    ApprovedEditDecisionId,
    ApprovedEditExportRepresentationId,
    EditCandidateId,
    EditExportArtifactId,
    EditExportAssemblyId,
    EditReviewDecisionId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.review.identities import HumanActorReference

_MEDIA = SourceMediaId("media")
_TIMELINE = SourceTimelineId("timeline")
_ACTOR = HumanActorReference("reviewer:alice")
_ASSEMBLY = EditExportAssemblyId("assembly")


def _rep(name, *, timeline=_TIMELINE, media=_MEDIA, kind=EditReviewDecisionKind.ACCEPT,
         candidate_type="non_lecture_region", rationale="approved rationale",
         start=0.5, end=1.5):
    return ApprovedEditExportRepresentation(
        identity=ApprovedEditExportRepresentationId(name),
        domain_result_id=DomainResultId(f"{name}-result"),
        source_approved_decision_id=ApprovedEditDecisionId(f"{name}-approved"),
        source_review_decision_id=EditReviewDecisionId(f"{name}-review"),
        source_candidate_id=EditCandidateId(f"{name}-candidate"),
        decision_kind=kind,
        approved_range_start=start,
        approved_range_end=end,
        approved_candidate_type=candidate_type,
        approved_rationale=rationale,
        actor=_ACTOR,
        source_media_id=media,
        source_timeline_id=timeline,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
        sequence=0,
    )


def _assembly(members, *, timeline=_TIMELINE, media=_MEDIA):
    ordered = tuple(sorted((m.identity for m in members), key=lambda i: i.value))
    return EditExportAssembly(
        identity=_ASSEMBLY,
        domain_result_id=DomainResultId("assembly-result"),
        source_media_id=media,
        source_timeline_id=timeline,
        member_representation_ids=ordered,
        run_id=ProcessingRunId("run"),
        unit_execution_id=UnitExecutionId("execution"),
    )


class _Repo:
    def __init__(self, records):
        self._records = {r.identity: r for r in records}

    def get(self, identity):
        return self._records.get(identity)


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


class EditExportArtifactDomainTests(unittest.TestCase):
    def test_valid_immutable_artifact(self) -> None:
        artifact = EditExportArtifact(
            identity=EditExportArtifactId("a"),
            source_assembly_id=_ASSEMBLY,
            source_media_id=_MEDIA,
            source_timeline_id=_TIMELINE,
            entries=(_entry("m1"),),
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            artifact.source_timeline_id = _TIMELINE  # type: ignore[misc]

    def _artifact(self, entries):
        return EditExportArtifact(
            identity=EditExportArtifactId("a"),
            source_assembly_id=_ASSEMBLY,
            source_media_id=_MEDIA,
            source_timeline_id=_TIMELINE,
            entries=entries,
        )

    def test_entries_must_be_non_empty(self) -> None:
        with self.assertRaises(ValueError):
            self._artifact(())

    def test_entries_must_be_unique(self) -> None:
        with self.assertRaises(ValueError):
            self._artifact((_entry("dup"), _entry("dup")))

    def test_entries_must_be_canonically_ordered(self) -> None:
        with self.assertRaises(ValueError):
            self._artifact((_entry("m2"), _entry("m1")))

    def test_entry_rejects_reject_kind(self) -> None:
        with self.assertRaises(ValueError):
            _entry("m1", decision_kind=EditReviewDecisionKind.REJECT)

    def test_entry_rejects_blank_rationale(self) -> None:
        with self.assertRaises(ValueError):
            _entry("m1", approved_rationale="   ")

    def test_entry_rejects_inverted_range(self) -> None:
        with self.assertRaises(ValueError):
            _entry("m1", approved_range_start=2.0, approved_range_end=1.0)

    def test_no_status_or_format_fields(self) -> None:
        fields = set(EditExportArtifact.__dataclass_fields__) | set(
            EditExportArtifactEntry.__dataclass_fields__
        )
        for forbidden in (
            "status", "state", "format", "mime_type", "filename", "path", "url",
            "checksum", "payload", "serialized", "profile", "configuration",
            "run_id", "unit_execution_id",
        ):
            self.assertNotIn(forbidden, fields)


class EditExportArtifactServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.m1 = _rep("m1", candidate_type="non_lecture_region", start=0.5, end=1.5)
        self.m2 = _rep(
            "m2", kind=EditReviewDecisionKind.MODIFY,
            candidate_type="condense_repetition", rationale="condensed", start=0.75, end=1.25,
        )
        self.assembly = _assembly((self.m1, self.m2))

    def _service(self, *, assembly=None, reps=None):
        assembly = assembly if assembly is not None else self.assembly
        reps = reps if reps is not None else (self.m1, self.m2)
        return EditExportArtifactService(_Repo((assembly,)), _Repo(reps))

    def _derive(self, service, **overrides):
        base = dict(source_assembly_id=_ASSEMBLY, identity=EditExportArtifactId("art"))
        base.update(overrides)
        return service.derive_artifact(**base)

    def test_presents_complete_meaning_in_canonical_order(self) -> None:
        artifact = self._derive(self._service())
        self.assertEqual(artifact.source_assembly_id, _ASSEMBLY)
        self.assertEqual(artifact.source_timeline_id, _TIMELINE)
        self.assertEqual(artifact.source_media_id, _MEDIA)
        self.assertEqual(
            tuple(e.source_representation_id for e in artifact.entries),
            self.assembly.member_representation_ids,
        )

    def test_faithful_presentation_of_each_member(self) -> None:
        artifact = self._derive(self._service())
        by_id = {self.m1.identity: self.m1, self.m2.identity: self.m2}
        for entry in artifact.entries:
            rep = by_id[entry.source_representation_id]
            self.assertEqual(entry.approved_range_start, rep.approved_range_start)
            self.assertEqual(entry.approved_range_end, rep.approved_range_end)
            self.assertEqual(entry.approved_candidate_type, rep.approved_candidate_type)
            self.assertEqual(entry.approved_rationale, rep.approved_rationale)
            self.assertEqual(entry.decision_kind, rep.decision_kind)
            self.assertEqual(entry.actor, rep.actor)

    def test_deterministic_regeneration(self) -> None:
        self.assertEqual(self._derive(self._service()), self._derive(self._service()))

    def test_new_identity_yields_another_artifact_same_meaning(self) -> None:
        first = self._derive(self._service(), identity=EditExportArtifactId("art-1"))
        second = self._derive(self._service(), identity=EditExportArtifactId("art-2"))
        self.assertNotEqual(first.identity, second.identity)
        self.assertEqual(first.entries, second.entries)

    def test_unknown_assembly_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._derive(
                self._service(), source_assembly_id=EditExportAssemblyId("missing")
            )

    def test_missing_member_is_explicit_representation_failure(self) -> None:
        # The Assembly references m1 and m2, but the representation repository lacks m2.
        with self.assertRaises(EditExportArtifactError):
            self._derive(self._service(reps=(self.m1,)))

    def test_member_lineage_inconsistent_with_assembly_rejected(self) -> None:
        stray = _rep("m2", timeline=SourceTimelineId("other-timeline"))
        with self.assertRaises(EditExportArtifactError):
            self._derive(self._service(reps=(self.m1, stray)))

    def test_derivation_does_not_mutate_upstream(self) -> None:
        reps = (self.m1, self.m2)
        service = self._service(reps=reps)
        before = (self.assembly, self.m1, self.m2)
        self._derive(service)
        self.assertEqual((self.assembly, self.m1, self.m2), before)


if __name__ == "__main__":
    unittest.main()
