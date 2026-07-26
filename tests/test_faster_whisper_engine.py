"""Concrete adapter contract tests for the faster-whisper engine runner (040 §15).

These drive the real invocation shape with an injected fake model factory (and a simulated missing dependency),
so they need no faster-whisper install, model download, GPU, or network.
"""

import sys
import unittest

from lectureos.application.local_asr_transcription import (
    LocalAsrDependencyError,
    LocalAsrEngineError,
    LocalAsrModelError,
)
from lectureos.infrastructure.faster_whisper_engine import FasterWhisperEngineRunner


class _FakeSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class _FakeInfo:
    def __init__(self, language):
        self.language = language


class _FakeModel:
    def __init__(self, record, segments, info, transcribe_error=None):
        self._record = record
        self._segments = segments
        self._info = info
        self._transcribe_error = transcribe_error

    def transcribe(self, media_path, language=None):
        self._record["transcribe"] = {"media_path": media_path, "language": language}
        if self._transcribe_error is not None:
            raise self._transcribe_error
        return (iter(self._segments), self._info)


def _factory(record, *, segments=None, info=None, build_error=None, transcribe_error=None):
    segments = segments if segments is not None else [
        _FakeSegment(0.0, 1.5, "안녕"),
        _FakeSegment(1.5, 3.0, "하세요"),
    ]
    info = info if info is not None else _FakeInfo("ko")

    def build(model, device, compute_type):
        record["build"] = {"model": model, "device": device, "compute_type": compute_type}
        if build_error is not None:
            raise build_error
        return _FakeModel(record, segments, info, transcribe_error)

    return build


class FasterWhisperEngineRunnerTests(unittest.TestCase):
    def test_invocation_shape_and_conversion(self):
        record = {}
        runner = FasterWhisperEngineRunner(model_factory=_factory(record))
        result = runner.transcribe(
            media_path="/tmp/a.wav",
            model="tiny",
            language="ko",
            device="cpu",
            compute_type="int8",
        )
        self.assertEqual(record["build"], {"model": "tiny", "device": "cpu", "compute_type": "int8"})
        self.assertEqual(record["transcribe"], {"media_path": "/tmp/a.wav", "language": "ko"})
        self.assertEqual(result.provider, "faster-whisper")
        self.assertEqual(result.model, "tiny")
        self.assertEqual(result.language, "ko")
        self.assertEqual(len(result.segments), 2)
        self.assertEqual(result.segments[0].start, 0.0)
        self.assertEqual(result.segments[0].end, 1.5)
        self.assertEqual(result.segments[0].text, "안녕")
        self.assertEqual(result.segments[1].text, "하세요")

    def test_used_language_falls_back_to_requested_when_info_absent(self):
        record = {}
        runner = FasterWhisperEngineRunner(
            model_factory=_factory(record, info=_FakeInfo(None))
        )
        result = runner.transcribe(
            media_path="/tmp/a.wav", model="tiny", language="en", device="cpu", compute_type="int8"
        )
        self.assertEqual(result.language, "en")

    def test_model_build_failure_becomes_model_error(self):
        record = {}
        runner = FasterWhisperEngineRunner(
            model_factory=_factory(record, build_error=RuntimeError("cannot load"))
        )
        with self.assertRaises(LocalAsrModelError):
            runner.transcribe(
                media_path="/tmp/a.wav", model="ghost", language=None, device="cpu", compute_type="int8"
            )

    def test_transcribe_failure_becomes_engine_error(self):
        record = {}
        runner = FasterWhisperEngineRunner(
            model_factory=_factory(record, transcribe_error=RuntimeError("decode failed"))
        )
        with self.assertRaises(LocalAsrEngineError):
            runner.transcribe(
                media_path="/tmp/a.wav", model="tiny", language=None, device="cpu", compute_type="int8"
            )

    def test_generator_failure_during_iteration_becomes_engine_error(self):
        record = {}

        def failing_gen():
            yield _FakeSegment(0.0, 1.0, "ok")
            raise RuntimeError("mid-stream failure")

        runner = FasterWhisperEngineRunner(
            model_factory=_factory(record, segments=failing_gen())
        )
        with self.assertRaises(LocalAsrEngineError):
            runner.transcribe(
                media_path="/tmp/a.wav", model="tiny", language=None, device="cpu", compute_type="int8"
            )

    def test_missing_dependency_becomes_dependency_error(self):
        runner = FasterWhisperEngineRunner()  # default path imports faster_whisper lazily
        saved = sys.modules.get("faster_whisper")
        sys.modules["faster_whisper"] = None  # force ImportError on `from faster_whisper import ...`
        try:
            with self.assertRaises(LocalAsrDependencyError):
                runner.transcribe(
                    media_path="/tmp/a.wav", model="tiny", language=None, device="cpu", compute_type="int8"
                )
        finally:
            if saved is not None:
                sys.modules["faster_whisper"] = saved
            else:
                del sys.modules["faster_whisper"]

    def test_no_subprocess_or_shell_usage(self):
        # The runner is a pure library call; it must not spawn a shell/subprocess (no injection surface).
        import inspect

        import lectureos.infrastructure.faster_whisper_engine as module

        source = inspect.getsource(module)
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("subprocess.", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", source)


if __name__ == "__main__":
    unittest.main()
