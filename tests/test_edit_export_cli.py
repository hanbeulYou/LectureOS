import json
import tempfile
import unittest
from pathlib import Path

from lectureos.application.edit_export_assembly import EditExportAssemblyIdentityPlan
from lectureos.application.identities import EditExportAssemblyId
from lectureos.composition import compose_sqlite_edit_export_assembly_service
from lectureos.edit_export_assembly_acceptance import _seed_representations
from lectureos.edit_export_cli import main, run_edit_export
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import initialize_sqlite_database
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_ASSEMBLY = "cli-assembly"


class EditExportCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.db = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.db)
        execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(
            connection
        )
        accepted, modified, again = _seed_representations(
            connection, execution, run_id, execution_id
        )
        self.members = (
            accepted.representation.identity,
            modified.representation.identity,
            again.representation.identity,
        )
        compose_sqlite_edit_export_assembly_service(
            connection, execution
        ).record_assembly(
            source_timeline_id=SourceTimelineId(TIMELINE_ID),
            member_representation_ids=self.members,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=EditExportAssemblyIdentityPlan(
                assembly_id=EditExportAssemblyId(_ASSEMBLY),
                assembly_result_id=DomainResultId(f"{_ASSEMBLY}-result"),
            ),
        )
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_run_edit_export_produces_readable_file(self) -> None:
        output = self.base / "out" / "edits.json"
        result = run_edit_export(
            database=str(self.db), assembly_id=_ASSEMBLY, output=str(output)
        )
        self.assertTrue(output.is_file())
        self.assertEqual(result.format, "lectureos-edit-export-json")
        self.assertEqual(result.version, "v1")
        document = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(document["source_assembly_id"], _ASSEMBLY)
        self.assertEqual(len(document["edits"]), len(self.members))

    def test_main_success_returns_zero(self) -> None:
        output = self.base / "out" / "edits.json"
        code = main(
            [_ASSEMBLY, "--database", str(self.db), "--output", str(output)]
        )
        self.assertEqual(code, 0)
        self.assertTrue(output.is_file())

    def test_main_unknown_assembly_returns_one_and_leaves_no_file(self) -> None:
        output = self.base / "out" / "edits.json"
        code = main(
            ["no-such-assembly", "--database", str(self.db), "--output", str(output)]
        )
        self.assertEqual(code, 1)
        self.assertFalse(output.exists())

    def test_main_collision_returns_one_and_preserves_file(self) -> None:
        output = self.base / "edits.json"
        output.write_text("preexisting", encoding="utf-8")
        code = main(
            [_ASSEMBLY, "--database", str(self.db), "--output", str(output)]
        )
        self.assertEqual(code, 1)
        self.assertEqual(output.read_text(encoding="utf-8"), "preexisting")

    def test_main_overwrite_flag_replaces_file(self) -> None:
        output = self.base / "edits.json"
        output.write_text("preexisting", encoding="utf-8")
        code = main(
            [
                _ASSEMBLY,
                "--database",
                str(self.db),
                "--output",
                str(output),
                "--overwrite",
            ]
        )
        self.assertEqual(code, 0)
        document = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(document["source_assembly_id"], _ASSEMBLY)

    def test_missing_database_returns_one(self) -> None:
        output = self.base / "out" / "edits.json"
        code = main(
            [
                _ASSEMBLY,
                "--database",
                str(self.base / "nonexistent.sqlite3"),
                "--output",
                str(output),
            ]
        )
        self.assertEqual(code, 1)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
