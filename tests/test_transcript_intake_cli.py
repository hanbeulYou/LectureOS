import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.composition import compose_sqlite_media_import_service
from lectureos.persistence import initialize_sqlite_database
from lectureos.transcript_intake_cli import main, run_transcript_intake
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class TranscriptIntakeCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "sample.bin"
        source.write_bytes(b"transcript-intake-cli-sample \x00\x01")
        self.media_id = (
            compose_sqlite_media_import_service(connection)
            .import_media(str(source))
            .record.identity.value
        )
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_success_creates_intake_and_states_no_transcription(self) -> None:
        code, out, _err = _run(["--media", self.media_id, "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("created transcript intake transcript-source-intake:", out)
        self.assertIn("no transcription was executed", out)

    def test_repeated_admission_reports_reused(self) -> None:
        _run(["--media", self.media_id, "--database", str(self.database)])
        code, out, _err = _run(["--media", self.media_id, "--database", str(self.database)])
        self.assertEqual(code, 0)
        self.assertIn("reused transcript intake", out)

    def test_malformed_identity_exits_one_and_leaves_db_unchanged(self) -> None:
        before = self.database.read_bytes()
        code, _out, err = _run(["--media", "not-a-media-id", "--database", str(self.database)])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_unknown_source_media_exits_one(self) -> None:
        code, _out, err = _run(
            ["--media", "sha256:" + "0" * 64, "--database", str(self.database)]
        )
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_missing_database_exits_one(self) -> None:
        code, _out, err = _run(
            ["--media", self.media_id, "--database", str(self.base / "nope.db")]
        )
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_run_transcript_intake_returns_result(self) -> None:
        result = run_transcript_intake(database=str(self.database), source_media_id=self.media_id)
        self.assertTrue(result.created)
        self.assertEqual(result.intake.source_media_id.value, self.media_id)

    def test_admitted_repository_validates_healthy(self) -> None:
        run_transcript_intake(database=str(self.database), source_media_id=self.media_id)
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
