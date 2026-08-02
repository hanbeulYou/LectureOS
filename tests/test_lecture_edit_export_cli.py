"""CLI tests for the Edit Export Assembly (044 §23, GOAL-030)."""

import contextlib
import io
import unittest

from lectureos import lecture_edit_export_cli
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository

from test_lecture_review_authority_service import _ACTOR, _OTHER_ACTOR, _Chain


def _run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = lecture_edit_export_cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class _ExportCliChain(_Chain):
    def setUp(self):
        super().setUp()
        self.timeline = (
            SQLiteRawTranscriptRepository(self.connection)
            .get(self.raw.raw_transcript_id)
            .source_timeline_id
        ).value
        # The CLI opens its own connection; release the write lock held by the fixture.
        self.connection.commit()

    def _scope(self):
        return _run("scope", "--source-timeline", self.timeline, "--database", str(self.database))

    def _assemble(self):
        return _run(
            "assemble", "--source-timeline", self.timeline, "--database", str(self.database)
        )


class LectureEditExportCliTests(_ExportCliChain):
    def test_scope_reports_why_a_candidate_is_not_eligible(self) -> None:
        code, out, _ = self._scope()
        self.assertEqual(code, 0)
        self.assertIn("no_recorded_authority", out)
        self.assertIn("does NOT mean no judgment exists", out)
        self.assertIn("export-eligible members: 0", out)
        self.assertIn("this observation is derived and stored nothing", out)

    def test_scope_states_what_is_not_part_of_this_contract(self) -> None:
        _, out, _ = self._scope()
        self.assertIn("other concrete formats: not part of this contract", out)
        self.assertIn("selection and final selection: not part of this pipeline at all", out)
        self.assertIn("overlap adjudication: not part of this contract", out)

    def test_assemble_records_the_complete_eligible_scope(self) -> None:
        self._judge()
        self.connection.commit()
        code, out, _ = self._assemble()
        self.assertEqual(code, 0)
        self.assertIn("admitted edit export assembly", out)
        self.assertIn("members: 1", out)
        self.assertIn("no human authority was exercised", out)
        self.assertIn("never a selection", out)

    def test_assemble_replays_idempotently(self) -> None:
        self._judge()
        self.connection.commit()
        self._assemble()
        code, out, _ = self._assemble()
        self.assertEqual(code, 0)
        self.assertIn("reused edit export assembly", out)

    def test_assemble_stops_on_an_undecided_policy_and_says_why(self) -> None:
        code, out, err = self._assemble()
        self.assertEqual(code, 1)
        self.assertIn("no export-eligible approved edit", err)
        self.assertIn("contract gap, not a product refusal", err)

    def test_a_cross_actor_conflict_stops_assemble_but_not_scope(self) -> None:
        self._judge()
        self._judge(actor=_OTHER_ACTOR, decision_kind="reject")
        self.connection.commit()
        code, out, _ = self._scope()
        self.assertEqual(code, 0)
        self.assertIn("cross_actor_conflict", out)
        self.assertIn("never arbitrated", out)
        self.assertIn("cross-actor review conflicts: 1", out)
        code, _, err = self._assemble()
        self.assertEqual(code, 1)
        self.assertIn("cross-actor Review Conflict", err)
        self.assertIn(_ACTOR, err)

    def test_show_prints_the_membership_and_its_order_caveat(self) -> None:
        self._judge()
        self.connection.commit()
        _, out, _ = self._assemble()
        identity = [
            line.split(": ", 1)[1]
            for line in out.splitlines()
            if line.startswith("edit export assembly: ")
        ][0]
        code, shown, _ = _run(
            "show", "--assembly", identity, "--database", str(self.database)
        )
        self.assertEqual(code, 0)
        self.assertIn(identity, shown)
        self.assertIn("deterministic presentation only", shown)

    def test_show_reports_an_unknown_assembly_without_crashing(self) -> None:
        code, out, _ = _run(
            "show",
            "--assembly",
            "lecture-edit-export-assembly:" + "f" * 64,
            "--database",
            str(self.database),
        )
        self.assertEqual(code, 1)
        self.assertIn("no such edit export assembly", out)

    def test_history_explains_why_several_assemblies_may_coexist(self) -> None:
        self._judge()
        self.connection.commit()
        self._assemble()
        code, out, _ = _run(
            "history", "--source-timeline", self.timeline, "--database", str(self.database)
        )
        self.assertEqual(code, 0)
        self.assertIn("recorded assemblies: 1", out)
        self.assertIn("no recorded assembly is ever", out)

    def test_a_malformed_identity_is_reported_as_an_error(self) -> None:
        code, _, err = _run(
            "show", "--assembly", "nonsense", "--database", str(self.database)
        )
        self.assertEqual(code, 1)
        self.assertIn("malformed", err)


class LectureEditExportArtifactCliTests(_ExportCliChain):
    """`artifact` — the canonical external representation, never stored (044 §24)."""

    def _artifact_of(self):
        self._judge()
        self.connection.commit()
        _, out, _ = self._assemble()
        identity = [
            line.split(": ", 1)[1]
            for line in out.splitlines()
            if line.startswith("edit export assembly: ")
        ][0]
        return identity, _run(
            "artifact", "--assembly", identity, "--database", str(self.database)
        )

    def test_artifact_presents_the_approved_meaning(self) -> None:
        assembly, (code, out, _) = self._artifact_of()
        self.assertEqual(code, 0)
        self.assertIn("edit export artifact: lecture-edit-export-artifact:", out)
        self.assertIn(f"source assembly: {assembly}", out)
        self.assertIn("presented edits: 1", out)
        self.assertIn("accept by reviewer:lee", out)
        self.assertIn("source timeline range:", out)

    def test_artifact_states_what_it_is_not(self) -> None:
        _, (_, out, _) = self._artifact_of()
        self.assertIn("never output-timeline coordinates", out)
        self.assertIn("carries no executable edit meaning", out)
        self.assertIn("derived, regenerable, and not stored", out)
        self.assertIn(
            "no eligibility, standing, authority, or conflict was re-evaluated", out
        )
        self.assertIn("other concrete formats: not part of this contract", out)

    def test_artifact_derivation_converges(self) -> None:
        assembly, (_, first, _) = self._artifact_of()
        _, second, _ = _run(
            "artifact", "--assembly", assembly, "--database", str(self.database)
        )
        self.assertEqual(first, second)

    def test_an_unknown_assembly_is_an_error(self) -> None:
        code, _, err = _run(
            "artifact",
            "--assembly",
            "lecture-edit-export-assembly:" + "f" * 64,
            "--database",
            str(self.database),
        )
        self.assertEqual(code, 1)
        self.assertIn("unknown edit export assembly", err)


class LectureEditExportSerializationCliTests(_ExportCliChain):
    """`serialize` and `materialize` (044 §25)."""

    def setUp(self):
        super().setUp()
        import tempfile, pathlib
        self.workspace = tempfile.TemporaryDirectory()
        self.out = pathlib.Path(self.workspace.name)

    def tearDown(self):
        self.workspace.cleanup()
        super().tearDown()

    def _assembly_id(self):
        self._judge()
        self.connection.commit()
        _, out, _ = self._assemble()
        return [
            line.split(": ", 1)[1]
            for line in out.splitlines()
            if line.startswith("edit export assembly: ")
        ][0]

    def test_serialize_prints_the_format_identity_and_payload(self) -> None:
        assembly = self._assembly_id()
        code, out, _ = _run(
            "serialize", "--assembly", assembly, "--database", str(self.database)
        )
        self.assertEqual(code, 0)
        self.assertIn("format: lectureos-lecture-edit-export-json", out)
        self.assertIn("format version: v1", out)
        self.assertIn(
            "media type: application/vnd.lectureos.lecture-edit-export+json", out
        )
        self.assertIn('"source_approved_edit_decision_id"', out)
        self.assertNotIn('"source_media_id"', out)
        self.assertIn("distinct from the legacy lectureos-edit-export-json", out)
        self.assertIn("nothing was written and nothing was stored", out)

    def test_serialize_is_byte_stable(self) -> None:
        assembly = self._assembly_id()
        _, first, _ = _run(
            "serialize", "--assembly", assembly, "--database", str(self.database)
        )
        _, second, _ = _run(
            "serialize", "--assembly", assembly, "--database", str(self.database)
        )
        self.assertEqual(first, second)

    def test_materialize_places_a_file_and_reports_it(self) -> None:
        assembly = self._assembly_id()
        destination = self.out / "nested" / "edits.json"
        code, out, _ = _run(
            "materialize",
            "--assembly",
            assembly,
            "--destination",
            str(destination),
            "--database",
            str(self.database),
        )
        self.assertEqual(code, 0)
        self.assertIn(f"materialized: {destination}", out)
        self.assertIn("supplied by the caller", out)
        self.assertIn("the write was atomic", out)
        self.assertTrue(destination.is_file())
        self.assertTrue(destination.read_text().endswith("\n"))

    def test_materialize_refuses_a_colliding_destination(self) -> None:
        assembly = self._assembly_id()
        destination = self.out / "edits.json"
        destination.write_bytes(b"other\n")
        code, _, err = _run(
            "materialize",
            "--assembly",
            assembly,
            "--destination",
            str(destination),
            "--database",
            str(self.database),
        )
        self.assertEqual(code, 1)
        self.assertIn("refusing to overwrite", err)
        self.assertEqual(destination.read_bytes(), b"other\n")

    def test_materialize_overwrites_only_when_asked(self) -> None:
        assembly = self._assembly_id()
        destination = self.out / "edits.json"
        destination.write_bytes(b"other\n")
        code, _, _ = _run(
            "materialize",
            "--assembly",
            assembly,
            "--destination",
            str(destination),
            "--overwrite",
            "--database",
            str(self.database),
        )
        self.assertEqual(code, 0)
        self.assertIn("lectureos-lecture-edit-export-json", destination.read_text())

    def test_materialize_refuses_a_relative_destination(self) -> None:
        assembly = self._assembly_id()
        code, _, err = _run(
            "materialize",
            "--assembly",
            assembly,
            "--destination",
            "relative/edits.json",
            "--database",
            str(self.database),
        )
        self.assertEqual(code, 1)
        self.assertIn("absolute path", err)


if __name__ == "__main__":
    unittest.main()
