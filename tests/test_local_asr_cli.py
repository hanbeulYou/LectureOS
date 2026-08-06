import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lectureos.application.local_asr_transcription import LocalAsrResult, LocalAsrSegment
from lectureos.composition import (
    compose_sqlite_local_asr_transcription_service as _real_compose,
    compose_sqlite_media_import_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database
from lectureos.validation import validate_database
import lectureos.local_asr_cli as cli


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class _FakeEngine:
    def __init__(self, segments=None):
        self._segments = segments if segments is not None else (
            LocalAsrSegment(0.0, 2.0, "안녕하세요"),
            LocalAsrSegment(2.0, 4.0, "강의를 시작합니다"),
        )

    def transcribe(
        self, *, media_path, model, language, device, compute_type, condition_on_previous_text
    ):
        self.condition_on_previous_text = condition_on_previous_text
        return LocalAsrResult(
            provider="faster-whisper", model=model, language=language or "ko", segments=self._segments
        )


def _patched_compose(engine):
    def factory(connection):
        return _real_compose(connection, engine_runner=engine)
    return factory


class LocalAsrCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.source = self.base / "lecture.bin"
        self.source.write_bytes(b"local-asr-cli-sample \x00\x01\x02")
        connection = initialize_sqlite_database(self.database)
        media_id = (
            compose_sqlite_media_import_service(connection)
            .import_media(str(self.source))
            .record.identity.value
        )
        self.intake_id = (
            compose_sqlite_transcript_source_intake_service(connection)
            .admit(media_id)
            .intake.identity.value
        )
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _argv(self, *, intake=None, database=None, model="tiny", extra=None):
        argv = [
            "--intake", intake or self.intake_id,
            "--database", str(database or self.database),
            "--model", model,
        ]
        if extra:
            argv += extra
        return argv

    def test_success_runs_real_execution_and_prints(self):
        with mock.patch.object(cli, "compose_sqlite_local_asr_transcription_service", _patched_compose(_FakeEngine())):
            code, out, _err = _run(self._argv(extra=["--language", "ko"]))
        self.assertEqual(code, 0)
        self.assertIn("created provider transcript admission provider-transcript-admission:", out)
        self.assertIn("canonical raw transcript: raw-transcript:", out)
        self.assertIn("provider/model: faster-whisper/tiny", out)
        self.assertIn("segments: 2", out)
        self.assertIn("real ASR execution occurred: yes", out)

    def test_output_discloses_the_provider_configuration(self):
        """040 §15 L-15 (PATCH-0040 P-6): the configuration is visible in the ordinary result."""

        with mock.patch.object(
            cli, "compose_sqlite_local_asr_transcription_service", _patched_compose(_FakeEngine())
        ):
            code, out, _err = _run(self._argv(extra=["--language", "ko"]))
        self.assertEqual(code, 0)
        self.assertIn("provider configuration: condition_on_previous_text=False", out)
        self.assertIn("vad_filter not enabled", out)
        self.assertIn("provider result reference: local-asr:v2:", out)
        self.assertIn("cond_prev_text=false", out)

    def test_cli_exposes_no_override_for_the_configuration(self):
        """P-2: an override flag would be the bypass the contract exists to prevent."""

        help_text = cli._parser().format_help()
        for forbidden in (
            "--condition-on-previous-text",
            "--vad",
            "--vad-filter",
            "--no-condition",
        ):
            self.assertNotIn(forbidden, help_text)

    def test_replay_reports_reused_without_execution(self):
        engine = _FakeEngine()
        with mock.patch.object(cli, "compose_sqlite_local_asr_transcription_service", _patched_compose(engine)):
            _run(self._argv(extra=["--language", "ko"]))
            code, out, _err = _run(self._argv(extra=["--language", "ko"]))
        self.assertEqual(code, 0)
        self.assertIn("reused provider transcript admission", out)
        self.assertIn("real ASR execution occurred: no (reused prior admission)", out)

    def test_unknown_intake_exits_one(self):
        with mock.patch.object(cli, "compose_sqlite_local_asr_transcription_service", _patched_compose(_FakeEngine())):
            code, _out, err = _run(self._argv(intake="transcript-source-intake:sha256:" + "0" * 64))
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_malformed_intake_exits_one_and_leaves_db_unchanged(self):
        before = self.database.read_bytes()
        with mock.patch.object(cli, "compose_sqlite_local_asr_transcription_service", _patched_compose(_FakeEngine())):
            code, _out, err = _run(self._argv(intake="not-an-intake"))
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_changed_source_exits_one(self):
        self.source.write_bytes(b"changed bytes after import")
        with mock.patch.object(cli, "compose_sqlite_local_asr_transcription_service", _patched_compose(_FakeEngine())):
            code, _out, err = _run(self._argv())
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_missing_database_exits_one(self):
        with mock.patch.object(cli, "compose_sqlite_local_asr_transcription_service", _patched_compose(_FakeEngine())):
            code, _out, err = _run(self._argv(database=self.base / "nope.db"))
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_malformed_engine_output_exits_one(self):
        bad = _FakeEngine(segments=(LocalAsrSegment(3.0, 3.0, "zero length"),))
        with mock.patch.object(cli, "compose_sqlite_local_asr_transcription_service", _patched_compose(bad)):
            code, _out, err = _run(self._argv())
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_admitted_repository_validates_healthy(self):
        with mock.patch.object(cli, "compose_sqlite_local_asr_transcription_service", _patched_compose(_FakeEngine())):
            _run(self._argv(extra=["--language", "ko"]))
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
