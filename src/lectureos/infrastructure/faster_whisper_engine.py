"""Concrete local ASR engine runner backed by faster-whisper (040 §15).

The single concrete local ASR engine for the first slice. It runs the `faster-whisper` Python library
(a CTranslate2 Whisper implementation) entirely locally on CPU by default, decoding the media internally (no
separate ffmpeg step). The library is imported **lazily**, so the core package imports and tests run without it
installed; its absence surfaces as an explicit `LocalAsrDependencyError`. A missing/unusable model surfaces as
`LocalAsrModelError`, and a transcription failure as `LocalAsrEngineError`. Timestamped segments are extracted
and their text preserved verbatim; the detected/used language is captured truthfully. It makes no shell call and
constructs no command string (there is no subprocess), so there is no shell-injection surface.

The decoding parameters LectureOS has an opinion about are **declared by Application and passed explicitly**
(040 §15 L-15 / PATCH-0040 P-1), so an upstream change to the library's defaults cannot alter LectureOS
behaviour. `vad_filter` and every VAD setting are deliberately absent: L-16 declines them because the measured
behaviour deletes real speech and produces unusable segment durations.

The `model_factory` seam lets tests drive the exact invocation shape (model/device/compute-type propagation,
configuration propagation, segment/text extraction, error translation) with a fake model, without the real
dependency or a downloaded model.
"""

from __future__ import annotations

from typing import Callable

from lectureos.application.local_asr_transcription import (
    FASTER_WHISPER_PROVIDER,
    LocalAsrDependencyError,
    LocalAsrEngineError,
    LocalAsrError,
    LocalAsrModelError,
    LocalAsrResult,
    LocalAsrSegment,
)

# A factory that builds an engine model exposing ``transcribe(media_path, **options)``, where
# options carry the declared configuration and, when resuming, ``clip_timestamps``.
ModelFactory = Callable[[str, str, str], object]


class FasterWhisperEngineRunner:
    """Runs faster-whisper locally; ``model_factory`` is injectable for testing without the real library."""

    def __init__(self, model_factory: ModelFactory | None = None) -> None:
        self._model_factory = model_factory

    def _factory(self) -> ModelFactory:
        if self._model_factory is not None:
            return self._model_factory
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise LocalAsrDependencyError(
                "faster-whisper is not installed; install the 'faster-whisper' package "
                "to use the local ASR adapter"
            ) from error

        def _build(model: str, device: str, compute_type: str) -> object:
            return WhisperModel(model, device=device, compute_type=compute_type)

        return _build

    def transcribe(
        self,
        *,
        media_path: str,
        model: str,
        language: str | None,
        device: str,
        compute_type: str,
        condition_on_previous_text: bool,
        start_offset: float | None = None,
        on_segment=None,
    ) -> LocalAsrResult:
        factory = self._factory()
        try:
            engine_model = factory(model, device, compute_type)
        except LocalAsrError:
            raise
        except Exception as error:  # model missing / unusable / download refused
            raise LocalAsrModelError(
                f"could not load local ASR model {model!r}: {error}"
            ) from error

        try:
            # 040 §15 L-15 / PATCH-0040 P-1: the Application-declared configuration is passed explicitly, so an
            # upstream change to the library's default cannot alter LectureOS behaviour. No VAD parameter is
            # passed here — L-16 declines `vad_filter` and every VAD setting, and adding one would be a
            # contract change, not a tuning decision.
            options = {
                "language": language,
                "condition_on_previous_text": condition_on_previous_text,
            }
            if start_offset is not None:
                # 040 §15 CP-12: resume decodes from an explicit instant on the same media.
                # `clip_timestamps` seeks to that frame and the library restores emitted timestamps
                # onto the ORIGINAL media timeline, so the adapter never re-bases anything — which
                # is what keeps L-6's verbatim-timing requirement intact.
                options["clip_timestamps"] = str(start_offset)
            segments_iter, info = engine_model.transcribe(media_path, **options)
            # The library yields lazily, so each segment is surfaced to the caller as it is decoded.
            # `on_segment` is how the adapter records a durable checkpoint during a long run rather
            # than only after it (040 §15 CP-11); it never alters what is returned.
            produced: list[LocalAsrSegment] = []
            for segment in segments_iter:
                converted = LocalAsrSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=segment.text,
                )
                if on_segment is not None:
                    on_segment(converted)
                produced.append(converted)
            segments = tuple(produced)
        except LocalAsrError:
            raise
        except Exception as error:
            raise LocalAsrEngineError(
                f"local ASR engine failed while transcribing: {error}"
            ) from error

        used_language = getattr(info, "language", None) or language
        return LocalAsrResult(
            provider=FASTER_WHISPER_PROVIDER,
            model=model,
            language=used_language,
            segments=segments,
        )


__all__ = ["FasterWhisperEngineRunner", "ModelFactory"]
