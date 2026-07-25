import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from lectureos.composition import (
    compose_sqlite_media_import_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database
from lectureos.transcript_result_admit_cli import main, run_transcript_result_admission
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


_DOC = {
    "provider": "fake-deterministic-asr",
    "model": "fake-model-v1",
    "language": "ko",
    "provider_result_ref": "ref-0001",
    "segments": [
        {"start": 0.0, "end": 2.5, "text": "안녕하세요"},
        {"start": 2.5, "end": 5.0, "text": "강의를 시작합니다"},
    ],
}


class TranscriptResultAdmitCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "sample.bin"
        source.write_bytes(b"asr-admit-cli-sample \x00\x01\x02")
        media_id = (
            compose_sqlite_media_import_service(connection)
            .import_media(str(source))
            .record.identity.value
        )
        self.intake_id = (
            compose_sqlite_transcript_source_intake_service(connection)
            .admit(media_id)
            .intake.identity.value
        )
        connection.close()
        self.input_path = self.base / "provider-result.json"
        self._write(self.input_path, _DOC)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write(self, path: Path, payload) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _argv(self, *, intake=None, input_path=None, database=None):
        return [
            "--intake", intake or self.intake_id,
            "--input", str(input_path or self.input_path),
            "--database", str(database or self.database),
        ]

    def test_success_admits_and_states_no_asr(self) -> None:
        code, out, _err = _run(self._argv())
        self.assertEqual(code, 0)
        self.assertIn("created provider transcript admission provider-transcript-admission:", out)
        self.assertIn("provider transcript result: provider-transcript-result:", out)
        self.assertIn("canonical raw transcript: raw-transcript:", out)
        self.assertIn("segments: 2", out)
        self.assertIn("LectureOS did not execute an ASR engine", out)

    def test_replay_reports_reused(self) -> None:
        _run(self._argv())
        code, out, _err = _run(self._argv())
        self.assertEqual(code, 0)
        self.assertIn("reused provider transcript admission", out)

    def test_malformed_json_exits_one_and_leaves_db_unchanged(self) -> None:
        bad = self.base / "bad.json"
        bad.write_text("{ this is not json", encoding="utf-8")
        before = self.database.read_bytes()
        code, _out, err = _run(self._argv(input_path=bad))
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_invalid_transcript_exits_one(self) -> None:
        invalid = self.base / "invalid.json"
        self._write(
            invalid,
            {
                "provider": "p",
                "provider_result_ref": "r",
                "segments": [{"start": 3.0, "end": 1.0, "text": "reversed"}],
            },
        )
        before = self.database.read_bytes()
        code, _out, err = _run(self._argv(input_path=invalid))
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_conflicting_replay_exits_one(self) -> None:
        _run(self._argv())
        conflicting = self.base / "conflict.json"
        payload = json.loads(json.dumps(_DOC))
        payload["segments"][0]["text"] = "다른 내용"
        self._write(conflicting, payload)
        code, _out, err = _run(self._argv(input_path=conflicting))
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_unknown_intake_exits_one(self) -> None:
        code, _out, err = _run(
            self._argv(intake="transcript-source-intake:sha256:" + "0" * 64)
        )
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_missing_database_exits_one(self) -> None:
        code, _out, err = _run(self._argv(database=self.base / "nope.db"))
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_run_returns_result_and_repository_validates_healthy(self) -> None:
        result = run_transcript_result_admission(
            database=str(self.database),
            intake_id=self.intake_id,
            input_path=str(self.input_path),
        )
        self.assertTrue(result.created)
        self.assertEqual(result.admission.segment_count, 2)
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
