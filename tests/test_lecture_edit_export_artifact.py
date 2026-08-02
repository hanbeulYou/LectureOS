"""Record and derivation tests for the Edit Export Artifact (044 §24, GOAL-031).

Drives the one-Assembly anchor, the presented values and their owner, the converging deterministic
identity, the read-only/never-persisted character, the explicit Representation Failures, and — the
decision §21 could not have made — that nothing is re-evaluated at this stage.
"""

import unittest

from lectureos.application.identities import (
    LectureApprovedEditDecisionId,
    LectureEditExportArtifactId,
    LectureEditExportAssemblyId,
)
from lectureos.application.lecture_edit_export_artifact import (
    EDIT_EXPORT_ARTIFACT_CONTRACT_VERSION,
    ArtifactRepresentationFailureError,
    LectureEditExportArtifact,
    LectureEditExportArtifactError,
    LectureEditExportArtifactService,
    derive_edit_export_artifact_identity,
    require_canonical_artifact_id,
)
from lectureos.composition import compose_sqlite_lecture_edit_export_artifact_service
from lectureos.execution.identities import SourceTimelineId
from lectureos.persistence.lecture_edit_export_assembly import (
    SQLiteEditExportAssemblyRepository,
    SQLiteEditExportScopeRepository,
)

from test_lecture_edit_export_assembly_service import _ACTOR, _ExportChain

_ASSEMBLY = LectureEditExportAssemblyId("lecture-edit-export-assembly:" + "a" * 64)


class IdentityTests(unittest.TestCase):
    def test_identity_binds_the_source_assembly_and_nothing_else(self) -> None:
        other = LectureEditExportAssemblyId("lecture-edit-export-assembly:" + "b" * 64)
        self.assertEqual(
            derive_edit_export_artifact_identity(_ASSEMBLY),
            derive_edit_export_artifact_identity(_ASSEMBLY),
        )
        self.assertNotEqual(
            derive_edit_export_artifact_identity(_ASSEMBLY),
            derive_edit_export_artifact_identity(other),
        )

    def test_no_discriminator_parameter_exists(self) -> None:
        """AR-7: plurality is permitted but no route is provided to manufacture it."""

        import inspect

        signature = inspect.signature(derive_edit_export_artifact_identity)
        self.assertEqual(list(signature.parameters), ["source_assembly_id"])

    def test_malformed_identity_strings_are_refused(self) -> None:
        for value in (
            "",
            "lecture-edit-export-artifact",
            "lecture-edit-export-artifact:short",
            "edit-export-artifact:" + "a" * 64,
        ):
            with self.assertRaises(LectureEditExportArtifactError):
                require_canonical_artifact_id(value)


class RecordTests(unittest.TestCase):
    def _artifact(self, entries):
        return LectureEditExportArtifact(
            identity=derive_edit_export_artifact_identity(_ASSEMBLY),
            source_assembly_id=_ASSEMBLY,
            source_timeline_id=SourceTimelineId("timeline:x"),
            entries=entries,
        )

    def test_the_artifact_owns_no_execution_result_or_lifecycle_field(self) -> None:
        """AR-5 / AR-9: no run, execution, DomainResult, status, or wall clock."""

        fields = set(LectureEditExportArtifact.__dataclass_fields__)
        self.assertEqual(
            fields,
            {
                "identity",
                "source_assembly_id",
                "source_timeline_id",
                "entries",
                "artifact_contract_version",
            },
        )
        for forbidden in (
            "domain_result_id",
            "processing_run_id",
            "unit_execution_id",
            "status",
            "lifecycle",
            "is_current",
            "created_at",
            "export_profile",
            "export_configuration",
            "path",
            "payload",
        ):
            self.assertNotIn(forbidden, fields)

    def test_a_tampered_identity_is_refused(self) -> None:
        with self.assertRaises(LectureEditExportArtifactError):
            LectureEditExportArtifact(
                identity=LectureEditExportArtifactId(
                    "lecture-edit-export-artifact:" + "0" * 64
                ),
                source_assembly_id=_ASSEMBLY,
                source_timeline_id=SourceTimelineId("timeline:x"),
                entries=(),
            )

    def test_an_unsupported_contract_version_is_refused(self) -> None:
        with self.assertRaises(LectureEditExportArtifactError):
            LectureEditExportArtifact(
                identity=derive_edit_export_artifact_identity(_ASSEMBLY),
                source_assembly_id=_ASSEMBLY,
                source_timeline_id=SourceTimelineId("timeline:x"),
                entries=(),
                artifact_contract_version=EDIT_EXPORT_ARTIFACT_CONTRACT_VERSION + 1,
            )


class DerivationTests(_ExportChain):
    def setUp(self):
        super().setUp()
        self.artifacts = compose_sqlite_lecture_edit_export_artifact_service(
            self.connection
        )

    def _assembly(self):
        return self.exports.admit_assembly(self.timeline.value).assembly

    def test_one_assembly_yields_one_artifact_presenting_every_member(self) -> None:
        second = self._second_candidate()
        self._judge()
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value, decision_kind="accept", actor=_ACTOR
        )
        assembly = self._assembly()
        artifact = self.artifacts.derive_artifact(assembly.identity.value)
        self.assertEqual(artifact.source_assembly_id, assembly.identity)
        self.assertEqual(artifact.source_timeline_id, assembly.source_timeline_id)
        self.assertEqual(len(artifact.entries), len(assembly.members))
        self.assertEqual(artifact.member_ids, assembly.member_ids)

    def test_the_presented_values_come_from_the_owning_records(self) -> None:
        """AR-3: the ApprovedEditDecision owns them; the Artifact presents them verbatim."""

        recorded = self._modify()
        artifact = self.artifacts.derive_artifact(self._assembly().identity.value)
        entry = artifact.entries[0]
        approved = recorded.approved
        self.assertEqual(entry.decision_kind, approved.approved_decision_kind)
        self.assertEqual(entry.approved_range_start, approved.approved_range_start)
        self.assertEqual(entry.approved_range_end, approved.approved_range_end)
        self.assertEqual(entry.approved_label, approved.approved_label)
        self.assertEqual(entry.approved_rationale, approved.approved_rationale)
        self.assertEqual(entry.actor.value, _ACTOR)
        self.assertEqual(entry.source_review_decision_id, recorded.decision.identity)

    def test_derivation_converges_and_reads_no_wall_clock(self) -> None:
        self._judge()
        assembly = self._assembly()
        first = self.artifacts.derive_artifact(assembly.identity.value)
        second = self.artifacts.derive_artifact(assembly.identity.value)
        self.assertEqual(first, second)
        self.assertEqual(
            first.identity, derive_edit_export_artifact_identity(assembly.identity)
        )

    def test_different_assemblies_derive_different_artifacts(self) -> None:
        second = self._second_candidate()
        self._judge()
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value, decision_kind="accept", actor=_ACTOR
        )
        first = self._assembly()
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value, decision_kind="reject", actor=_ACTOR
        )
        later = self._assembly()
        self.assertNotEqual(first.identity, later.identity)
        self.assertNotEqual(
            self.artifacts.derive_artifact(first.identity.value).identity,
            self.artifacts.derive_artifact(later.identity.value).identity,
        )

    def test_entry_order_follows_the_assemblys_canonical_member_order(self) -> None:
        second = self._second_candidate()
        self._judge()
        self.reviews.admit_review_decision(
            candidate_id=second.identity.value, decision_kind="accept", actor=_ACTOR
        )
        assembly = self._assembly()
        artifact = self.artifacts.derive_artifact(assembly.identity.value)
        self.assertEqual(
            [entry.ordinal for entry in artifact.entries], [0, 1]
        )
        self.assertEqual(artifact.member_ids, assembly.member_ids)


class NothingIsReDecidedTests(_ExportChain):
    """AR-8 — the decision `§21` could not have made, and its three consequences."""

    def setUp(self):
        super().setUp()
        self.artifacts = compose_sqlite_lecture_edit_export_artifact_service(
            self.connection
        )

    def test_a_superseded_member_still_yields_a_correct_artifact(self) -> None:
        self._judge()
        assembly = self.exports.admit_assembly(self.timeline.value).assembly
        before = self.artifacts.derive_artifact(assembly.identity.value)
        self._judge(decision_kind="reject")  # the member's judgment is superseded
        after = self.artifacts.derive_artifact(assembly.identity.value)
        self.assertEqual(before, after)
        self.assertEqual(len(after.entries), 1)

    def test_a_chain_that_lost_standing_still_yields_a_correct_artifact(self) -> None:
        self._judge()
        assembly = self.exports.admit_assembly(self.timeline.value).assembly
        before = self.artifacts.derive_artifact(assembly.identity.value)
        self._revise("c2", "교정 2")  # the chain loses current standing
        self.assertEqual(
            self._scope().standings[0].eligibility.value,
            "superseded_by_authority_change",
        )
        self.assertEqual(
            self.artifacts.derive_artifact(assembly.identity.value), before
        )

    def test_a_later_cross_actor_conflict_does_not_stop_derivation(self) -> None:
        """The undecided conflict policy stays with §23 admission and is not reopened here."""

        self._judge()
        assembly = self.exports.admit_assembly(self.timeline.value).assembly
        self._judge(actor="reviewer:park", decision_kind="reject")
        self.assertTrue(self._scope().has_conflict)
        artifact = self.artifacts.derive_artifact(assembly.identity.value)
        self.assertEqual(len(artifact.entries), 1)

    def test_derivation_writes_nothing_anywhere(self) -> None:
        self._judge()
        assembly = self.exports.admit_assembly(self.timeline.value).assembly
        counts = {
            table: self.connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in (
                "lecture_review_decisions",
                "lecture_approved_edit_decisions",
                "lecture_review_authority_positions",
                "lecture_edit_export_assemblies",
                "lecture_edit_export_assembly_members",
                "processing_runs",
                "domain_result_references",
            )
        }
        for _ in range(3):
            self.artifacts.derive_artifact(assembly.identity.value)
        for table, expected in counts.items():
            self.assertEqual(
                self.connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0],
                expected,
                table,
            )

    def test_no_artifact_relation_exists_at_all(self) -> None:
        """AR-11: derived and regenerable, so nothing durable was added."""

        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        self.assertNotIn("lecture_edit_export_artifacts", tables)
        self.assertNotIn("lecture_edit_export_artifact_entries", tables)

    def test_the_legacy_artifact_path_is_never_touched(self) -> None:
        self._judge()
        assembly = self.exports.admit_assembly(self.timeline.value).assembly
        self.artifacts.derive_artifact(assembly.identity.value)
        for table in (
            "approved_edit_export_representations",
            "edit_export_assemblies",
            "edit_export_assembly_members",
        ):
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
            )


class RepresentationFailureTests(_ExportChain):
    """AR-10 / §21 B-11 — explicit failure, never a silently shortened Artifact."""

    def setUp(self):
        super().setUp()
        self.artifacts = compose_sqlite_lecture_edit_export_artifact_service(
            self.connection
        )

    def test_an_unknown_assembly_is_refused(self) -> None:
        with self.assertRaises(LectureEditExportArtifactError):
            self.artifacts.derive_artifact(
                "lecture-edit-export-assembly:" + "f" * 64
            )

    def test_a_malformed_assembly_identity_is_refused_before_anything_else(self) -> None:
        with self.assertRaises(Exception):
            self.artifacts.derive_artifact("nonsense")

    def test_an_unresolvable_member_fails_explicitly(self) -> None:
        self._judge()
        assembly = self.exports.admit_assembly(self.timeline.value).assembly

        class _Missing:
            def get_approved(self, identity):
                return None

            def get_decision(self, identity):  # pragma: no cover - never reached
                return None

        service = LectureEditExportArtifactService(
            assembly_query=SQLiteEditExportAssemblyRepository(self.connection),
            decision_query=_Missing(),
            scope_query=SQLiteEditExportScopeRepository(self.connection),
        )
        with self.assertRaises(ArtifactRepresentationFailureError) as raised:
            service.derive_artifact(assembly.identity.value)
        self.assertIn("cannot be resolved", str(raised.exception))
        self.assertIn("nothing was omitted", str(raised.exception))

    def test_a_member_from_another_timeline_fails_explicitly(self) -> None:
        """§21 B-11's second case: lineage inconsistent with the Assembly."""

        self._judge()
        assembly = self.exports.admit_assembly(self.timeline.value).assembly

        class _ForeignScope:
            def candidate_ids_for_source_timeline(self, source_timeline_id):
                return ()

        service = LectureEditExportArtifactService(
            assembly_query=SQLiteEditExportAssemblyRepository(self.connection),
            decision_query=self.artifacts._decisions,
            scope_query=_ForeignScope(),
        )
        with self.assertRaises(ArtifactRepresentationFailureError) as raised:
            service.derive_artifact(assembly.identity.value)
        self.assertIn("does not belong to the assembly's Source Timeline", str(raised.exception))

    def test_a_missing_review_decision_fails_explicitly(self) -> None:
        self._judge()
        assembly = self.exports.admit_assembly(self.timeline.value).assembly
        real = self.artifacts._decisions

        class _NoDecision:
            def get_approved(self, identity):
                return real.get_approved(identity)

            def get_decision(self, identity):
                return None

        service = LectureEditExportArtifactService(
            assembly_query=SQLiteEditExportAssemblyRepository(self.connection),
            decision_query=_NoDecision(),
            scope_query=SQLiteEditExportScopeRepository(self.connection),
        )
        with self.assertRaises(ArtifactRepresentationFailureError) as raised:
            service.derive_artifact(assembly.identity.value)
        self.assertIn("human actor", str(raised.exception))

    def test_failure_leaves_the_approved_sources_untouched(self) -> None:
        self._judge()
        assembly = self.exports.admit_assembly(self.timeline.value).assembly
        before = self.connection.execute(
            "SELECT identity, approved_label, approved_rationale FROM "
            "lecture_approved_edit_decisions ORDER BY identity"
        ).fetchall()

        class _Missing:
            def get_approved(self, identity):
                return None

            def get_decision(self, identity):  # pragma: no cover
                return None

        service = LectureEditExportArtifactService(
            assembly_query=SQLiteEditExportAssemblyRepository(self.connection),
            decision_query=_Missing(),
            scope_query=SQLiteEditExportScopeRepository(self.connection),
        )
        with self.assertRaises(ArtifactRepresentationFailureError):
            service.derive_artifact(assembly.identity.value)
        self.assertEqual(
            self.connection.execute(
                "SELECT identity, approved_label, approved_rationale FROM "
                "lecture_approved_edit_decisions ORDER BY identity"
            ).fetchall(),
            before,
        )


if __name__ == "__main__":
    unittest.main()
