"""Run one local video through OpenAI Whisper and the existing LectureOS demo."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lectureos.demo import (
    DemoRunResult,
    DemoTranscriptInput,
    DemoTranscriptSegment,
    run_demo_from_transcript,
)


class RealMediaDemoError(RuntimeError):
    """An expected media, provider, or provider-response failure."""


@dataclass(frozen=True, slots=True)
class ProviderSegment:
    text: str
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class ProviderTranscription:
    provider_reference: str
    original_content: str
    duration: float
    segments: tuple[ProviderSegment, ...]


@dataclass(frozen=True, slots=True)
class RealMediaDemoResult:
    provider: str
    media_duration: float
    demo: DemoRunResult


class OpenAIWhisperAdapter:
    """Translate one OpenAI Whisper response into provider-neutral adapter values."""

    _ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
    _MODEL = "whisper-1"

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        if self._api_key is None or not self._api_key.strip():
            raise RealMediaDemoError("OPENAI_API_KEY is required")

    def transcribe_video(self, input_video: str | Path) -> ProviderTranscription:
        video_path = Path(input_video).expanduser().resolve()
        if not video_path.is_file():
            raise RealMediaDemoError("input video must be an existing file")
        with tempfile.TemporaryDirectory(prefix="lectureos-real-media-") as directory:
            audio_path = Path(directory) / "audio.mp3"
            self._extract_audio(video_path, audio_path)
            payload = self._request_transcription(audio_path)
        return _parse_whisper_transcription(payload, model=self._MODEL)

    @staticmethod
    def _extract_audio(video_path: Path, audio_path: Path) -> None:
        try:
            completed = subprocess.run(
                (
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(video_path),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-b:a",
                    "64k",
                    str(audio_path),
                ),
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise RealMediaDemoError("ffmpeg is required to extract video audio") from error
        if completed.returncode != 0 or not audio_path.is_file():
            detail = completed.stderr.strip() or "unknown ffmpeg failure"
            raise RealMediaDemoError(f"could not extract video audio: {detail}")

    def _request_transcription(self, audio_path: Path) -> Mapping[str, Any]:
        boundary = f"lectureos-{uuid.uuid4().hex}"
        body = _multipart_body(
            boundary,
            audio_path,
            fields=(
                ("model", self._MODEL),
                ("response_format", "verbose_json"),
                ("timestamp_granularities[]", "segment"),
            ),
        )
        request = urllib.request.Request(
            self._ENDPOINT,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise RealMediaDemoError(
                f"OpenAI transcription request failed with HTTP {error.code}"
            ) from error
        except urllib.error.URLError as error:
            raise RealMediaDemoError(
                f"OpenAI transcription request failed: {error.reason}"
            ) from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RealMediaDemoError("OpenAI transcription response was not valid JSON") from error
        if not isinstance(decoded, Mapping):
            raise RealMediaDemoError("OpenAI transcription response must be an object")
        return decoded


def run_real_media_demo(
    input_video: str | Path,
    output_directory: str | Path,
    *,
    provider: OpenAIWhisperAdapter | None = None,
) -> RealMediaDemoResult:
    """Transcribe one video, then execute the existing approved demo pipeline."""

    adapter = provider if provider is not None else OpenAIWhisperAdapter()
    transcription = adapter.transcribe_video(input_video)
    if not transcription.segments:
        raise RealMediaDemoError("speech-to-text provider returned no segments")
    demo = run_demo_from_transcript(
        output_directory,
        filename="lectureos-real-media.srt",
        transcript_input=DemoTranscriptInput(
            provider_reference=transcription.provider_reference,
            original_content=transcription.original_content,
            segments=tuple(
                DemoTranscriptSegment(
                    text=segment.text,
                    start=segment.start,
                    end=segment.end,
                )
                for segment in transcription.segments
            ),
            correction_text=transcription.segments[0].text,
        ),
    )
    return RealMediaDemoResult(
        provider=transcription.provider_reference,
        media_duration=transcription.duration,
        demo=demo,
    )


def _parse_whisper_transcription(
    payload: Mapping[str, Any], *, model: str
) -> ProviderTranscription:
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise RealMediaDemoError("OpenAI transcription returned no timed segments")
    segments: list[ProviderSegment] = []
    for raw in raw_segments:
        if not isinstance(raw, Mapping):
            raise RealMediaDemoError("OpenAI transcription segment must be an object")
        text = raw.get("text")
        start = raw.get("start")
        end = raw.get("end")
        if not isinstance(text, str) or not text.strip():
            raise RealMediaDemoError("OpenAI transcription segment text must not be empty")
        if isinstance(start, bool) or not isinstance(start, (int, float)):
            raise RealMediaDemoError("OpenAI transcription segment start must be numeric")
        if isinstance(end, bool) or not isinstance(end, (int, float)):
            raise RealMediaDemoError("OpenAI transcription segment end must be numeric")
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
            raise RealMediaDemoError("OpenAI transcription segment time range is invalid")
        segments.append(ProviderSegment(text=text.strip(), start=float(start), end=float(end)))
    duration = payload.get("duration", segments[-1].end)
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration < 0
    ):
        raise RealMediaDemoError("OpenAI transcription duration must be non-negative")
    return ProviderTranscription(
        provider_reference=f"openai:{model}",
        original_content=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        duration=float(duration),
        segments=tuple(segments),
    )


def _multipart_body(
    boundary: str,
    audio_path: Path,
    *,
    fields: tuple[tuple[str, str], ...],
) -> bytes:
    marker = boundary.encode("ascii")
    parts: list[bytes] = []
    for name, value in fields:
        parts.extend(
            (
                b"--" + marker + b"\r\n",
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                value.encode("utf-8") + b"\r\n",
            )
        )
    parts.extend(
        (
            b"--" + marker + b"\r\n",
            (
                'Content-Disposition: form-data; name="file"; filename="audio.mp3"\r\n'
                "Content-Type: audio/mpeg\r\n\r\n"
            ).encode("ascii"),
            audio_path.read_bytes(),
            b"\r\n--" + marker + b"--\r\n",
        )
    )
    return b"".join(parts)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.real_media_demo",
        description="Transcribe one local video and materialize a LectureOS SRT.",
    )
    parser.add_argument("--input-video", required=True)
    parser.add_argument("--output-directory", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_real_media_demo(args.input_video, args.output_directory)
    except (RealMediaDemoError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    demo = result.demo
    print("status: success")
    print(f"provider: {result.provider}")
    print(f"media_duration_seconds: {result.media_duration:.3f}")
    print(f"transcript_segment_count: {len(demo.raw_transcript.segment_ids)}")
    print(f"subtitle_count: {len(demo.subtitle_revision.cue_ids)}")
    print(f"file: {demo.materialization.final_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
