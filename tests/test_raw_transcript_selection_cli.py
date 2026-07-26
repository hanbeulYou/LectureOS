import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database
from lectureos.raw_transcript_selection_cli import main
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def _doc(ref, provider="fake", model="tiny"):
    return build_provider_transcript_document(
        {"provider": provider, "model": model, "language": "ko",
         "provider_result_ref": ref, "segments": [{"start": 0.0, "end": 1.0, "text": "가"}]}
    )


class RawTranscriptSelectionCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"selection-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        admit = compose_sqlite_provider_transcript_admission_service(connection)
        self.raw_a = admit.admit(intake_id=self.intake, document=_doc("ref-A")).admission.raw_transcript_id.value
        self.raw_b = admit.admit(intake_id=self.intake, document=_doc("ref-B")).admission.raw_transcript_id.value
        # A second intake with its own raw transcript, for the unrelated-selection case.
        source2 = self.base / "b.bin"
        source2.write_bytes(b"other \x00\x02")
        media2 = compose_sqlite_media_import_service(connection).import_media(str(source2)).record
        other_intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media2.identity.value
        ).intake.identity.value
        self.other_raw = admit.admit(intake_id=other_intake, document=_doc("ref-A")).admission.raw_transcript_id.value
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _db(self):
        return ["--database", str(self.database)]

    def test_candidates_lists_two_not_ranked(self):
        code, out, _err = _run(["candidates", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("2 (not ranked)", out)
        self.assertIn(self.raw_a, out)
        self.assertIn(self.raw_b, out)

    def test_readiness_not_ready_then_ready(self):
        code, out, _err = _run(["readiness", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("not_ready", out)
        _run(["select", "--intake", self.intake, "--transcript", self.raw_a, *self._db()])
        code, out, _err = _run(["readiness", "--intake", self.intake, *self._db()])
        self.assertIn("ready", out)
        self.assertIn(self.raw_a, out)

    def test_select_created_then_reused_then_switched(self):
        code, out, _err = _run(["select", "--intake", self.intake, "--transcript", self.raw_a, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("created current raw transcript", out)
        self.assertIn("readiness: ready", out)
        code, out, _err = _run(["select", "--intake", self.intake, "--transcript", self.raw_a, *self._db()])
        self.assertIn("reused current raw transcript", out)
        code, out, _err = _run(["select", "--intake", self.intake, "--transcript", self.raw_b, *self._db()])
        self.assertIn("switched current raw transcript", out)
        self.assertIn("superseded:", out)

    def test_candidates_marks_current(self):
        _run(["select", "--intake", self.intake, "--transcript", self.raw_a, *self._db()])
        code, out, _err = _run(["candidates", "--intake", self.intake, *self._db()])
        self.assertIn("*current", out)

    def test_unrelated_transcript_exits_one_and_leaves_db_unchanged(self):
        before = self.database.read_bytes()
        code, _out, err = _run(["select", "--intake", self.intake, "--transcript", self.other_raw, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_unknown_transcript_exits_one(self):
        code, _out, err = _run(["select", "--intake", self.intake, "--transcript", "raw-transcript:" + "0" * 64, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_malformed_intake_exits_one(self):
        code, _out, err = _run(["candidates", "--intake", "not-an-intake", *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_missing_database_exits_one(self):
        code, _out, err = _run(["readiness", "--intake", self.intake, "--database", str(self.base / "nope.db")])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_repository_validates_healthy_after_selection(self):
        _run(["select", "--intake", self.intake, "--transcript", self.raw_a, *self._db()])
        _run(["select", "--intake", self.intake, "--transcript", self.raw_b, *self._db()])
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
