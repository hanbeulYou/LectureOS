import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.media_import_cli import main, run_media_import
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class MediaImportCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.source = self.base / "sample.bin"
        self.source.write_bytes(b"media-import-cli-sample \x00\x01\x02")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_success_creates_record_and_exits_zero(self) -> None:
        code, out, _err = _run(
            [str(self.source), "--database", str(self.database)]
        )
        self.assertEqual(code, 0)
        self.assertIn("created source media sha256:", out)
        self.assertTrue(self.database.is_file())

    def test_repeated_import_reports_reused(self) -> None:
        _run([str(self.source), "--database", str(self.database)])
        code, out, _err = _run([str(self.source), "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("reused source media sha256:", out)

    def test_missing_source_exits_one_and_leaves_db_unchanged(self) -> None:
        # Create the DB first via a successful import, snapshot it, then a failed import must not change it.
        _run([str(self.source), "--database", str(self.database)])
        before = self.database.read_bytes()
        code, _out, err = _run(
            [str(self.base / "nope.bin"), "--database", str(self.database)]
        )
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_directory_source_exits_one(self) -> None:
        directory = self.base / "adir"
        directory.mkdir()
        code, _out, err = _run([str(directory), "--database", str(self.database)])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_empty_source_exits_one(self) -> None:
        empty = self.base / "empty.bin"
        empty.write_bytes(b"")
        code, _out, err = _run([str(empty), "--database", str(self.database)])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_run_media_import_returns_result(self) -> None:
        result = run_media_import(database=str(self.database), source_path=str(self.source))
        self.assertTrue(result.created)
        self.assertTrue(result.record.identity.value.startswith("sha256:"))

    def test_imported_repository_validates_healthy(self) -> None:
        run_media_import(database=str(self.database), source_path=str(self.source))
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")

    def test_source_bytes_unchanged_after_import(self) -> None:
        before = self.source.read_bytes()
        run_media_import(database=str(self.database), source_path=str(self.source))
        self.assertEqual(self.source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
