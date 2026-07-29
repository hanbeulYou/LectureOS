import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.repository_validation_acceptance import _corrupt, _seed_healthy
from lectureos.validate_cli import main


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class ValidateCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "lecture.db"
        _seed_healthy(self.healthy)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_healthy_exits_zero(self) -> None:
        code, out, _err = _run(["--database", str(self.healthy)])
        self.assertEqual(code, 0)
        self.assertIn("health           : healthy", out)
        self.assertIn("errors           : 0", out)

    def test_errors_exit_one(self) -> None:
        broken = self.base / "broken.db"
        _corrupt(self.healthy, broken, lambda c: c.execute("DELETE FROM edit_export_assembly_members"))
        code, out, _err = _run(["--database", str(broken)])
        self.assertEqual(code, 1)
        self.assertIn("ASSEMBLY_EMPTY", out)

    def test_warnings_only_exit_two(self) -> None:
        broken = self.base / "warn.db"

        def _swap(c: sqlite3.Connection) -> None:
            c.execute("UPDATE edit_export_assembly_members SET ordinal = 100 WHERE ordinal = 0")
            c.execute("UPDATE edit_export_assembly_members SET ordinal = 0 WHERE ordinal = 2")
            c.execute("UPDATE edit_export_assembly_members SET ordinal = 2 WHERE ordinal = 100")

        _corrupt(self.healthy, broken, _swap)
        code, out, _err = _run(["--database", str(broken)])
        self.assertEqual(code, 2)
        self.assertIn("health           : warnings", out)

    def test_json_format_is_machine_readable(self) -> None:
        code, out, _err = _run(["--database", str(self.healthy), "--format", "json"])
        self.assertEqual(code, 0)
        document = json.loads(out)
        self.assertEqual(document["health"], "healthy")
        self.assertEqual(document["schema_version"], 49)
        self.assertIn("diagnostics", document)

    def test_missing_database_exits_one(self) -> None:
        code, out, _err = _run(["--database", str(self.base / "nope.db")])
        self.assertEqual(code, 1)
        self.assertIn("DATABASE_NOT_FOUND", out)


if __name__ == "__main__":
    unittest.main()
