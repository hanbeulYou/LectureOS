import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lectureos import real_media_demo
from lectureos.real_media_demo import (
    OpenAIWhisperAdapter,
    ProviderSegment,
    ProviderTranscription,
    RealMediaDemoError,
    _parse_whisper_transcription,
    run_real_media_demo,
)


class _FakeProvider:
    def __init__(self, transcription):
        self.transcription = transcription
        self.received = None

    def transcribe_video(self, input_video):
        self.received = input_video
        return self.transcription


class RealMediaDemoTest(unittest.TestCase):
    def test_provider_payload_maps_without_becoming_a_domain_model(self):
        payload = {
            "text": "안녕하세요 실제 강의입니다.",
            "duration": 2.75,
            "language": "ko",
            "segments": [
                {"id": 0, "start": 0.0, "end": 1.25, "text": " 안녕하세요 "},
                {"id": 1, "start": 1.25, "end": 2.75, "text": "실제 강의입니다."},
            ],
        }

        result = _parse_whisper_transcription(payload, model="whisper-1")

        self.assertEqual("openai:whisper-1", result.provider_reference)
        self.assertEqual(2.75, result.duration)
        self.assertEqual(
            (
                ProviderSegment("안녕하세요", 0.0, 1.25),
                ProviderSegment("실제 강의입니다.", 1.25, 2.75),
            ),
            result.segments,
        )
        self.assertEqual(payload, json.loads(result.original_content))
        self.assertNotIn("lectureos.transcript", type(result).__module__)

    def test_invalid_provider_payload_is_rejected_at_adapter_boundary(self):
        cases = (
            {},
            {"segments": []},
            {"segments": [{"text": "", "start": 0, "end": 1}]},
            {"segments": [{"text": "text", "start": 2, "end": 1}]},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(RealMediaDemoError):
                    _parse_whisper_transcription(payload, model="whisper-1")

    def test_openai_adapter_extracts_audio_and_invokes_transcription_endpoint(self):
        payload = {
            "duration": 1.0,
            "segments": [{"text": "real media", "start": 0.0, "end": 1.0}],
        }
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode(
            "utf-8"
        )

        def create_audio(_video, audio):
            audio.write_bytes(b"encoded audio")

        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            video = Path(directory) / "sample.mp4"
            video.write_bytes(b"video")
            adapter = OpenAIWhisperAdapter(api_key="test-key")
            with patch.object(adapter, "_extract_audio", side_effect=create_audio) as extract:
                with patch("urllib.request.urlopen", return_value=response) as urlopen:
                    result = adapter.transcribe_video(video)

        extract.assert_called_once()
        request = urlopen.call_args.args[0]
        self.assertEqual("https://api.openai.com/v1/audio/transcriptions", request.full_url)
        self.assertIn(b'name="model"\r\n\r\nwhisper-1', request.data)
        self.assertIn(b'name="timestamp_granularities[]"', request.data)
        self.assertIn(b"encoded audio", request.data)
        self.assertEqual("openai:whisper-1", result.provider_reference)

    def test_real_media_runner_executes_existing_pipeline_and_materializes_srt(self):
        transcription = ProviderTranscription(
            provider_reference="openai:whisper-1",
            original_content='{"provider":"fixture"}',
            duration=3.5,
            segments=(
                ProviderSegment("첫 번째 실제 문장", 0.0, 1.5),
                ProviderSegment("Second real sentence.", 1.5, 3.5),
            ),
        )
        provider = _FakeProvider(transcription)

        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            video = Path(directory) / "sample.mp4"
            video.write_bytes(b"fake video passed only to provider boundary")
            result = run_real_media_demo(video, directory, provider=provider)
            path = Path(result.demo.materialization.final_path)
            file_bytes = path.read_bytes()

            self.assertEqual(video, provider.received)
            self.assertTrue(path.is_file())
            self.assertEqual("lectureos-real-media.srt", path.name)
            self.assertEqual(result.demo.export_artifact.content, file_bytes.decode("utf-8"))
            self.assertFalse(file_bytes.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r\n", file_bytes)
            self.assertIn("첫 번째 실제 문장", result.demo.export_artifact.content)
            self.assertIn("Second real sentence.", result.demo.export_artifact.content)
            self.assertEqual(2, len(result.demo.raw_transcript.segment_ids))
            self.assertEqual(2, len(result.demo.subtitle_revision.cue_ids))

    def test_cli_delegates_and_expected_failure_has_no_traceback(self):
        fake = SimpleNamespace(
            provider="openai:whisper-1",
            media_duration=2.0,
            demo=SimpleNamespace(
                raw_transcript=SimpleNamespace(segment_ids=(1, 2)),
                subtitle_revision=SimpleNamespace(cue_ids=(1, 2)),
                materialization=SimpleNamespace(final_path="/tmp/output.srt"),
            ),
        )
        stdout = io.StringIO()
        with patch.object(real_media_demo, "run_real_media_demo", return_value=fake) as runner:
            with contextlib.redirect_stdout(stdout):
                status = real_media_demo.main(
                    ["--input-video", "sample.mp4", "--output-directory", "/tmp"]
                )
        self.assertEqual(0, status)
        runner.assert_called_once_with("sample.mp4", "/tmp")
        self.assertIn("status: success\n", stdout.getvalue())
        self.assertIn("provider: openai:whisper-1\n", stdout.getvalue())
        self.assertIn("subtitle_count: 2\n", stdout.getvalue())

        stderr = io.StringIO()
        with patch.object(
            real_media_demo,
            "run_real_media_demo",
            side_effect=RealMediaDemoError("provider unavailable"),
        ):
            with contextlib.redirect_stderr(stderr):
                status = real_media_demo.main(
                    ["--input-video", "sample.mp4", "--output-directory", "/tmp"]
                )
        self.assertEqual(1, status)
        self.assertEqual("error: provider unavailable\n", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
