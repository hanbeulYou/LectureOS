"""Concrete local ASR engine runner backed by faster-whisper (040 §15).

The single concrete local ASR engine for the first slice. It runs the `faster-whisper` Python library
(a CTranslate2 Whisper implementation) entirely locally on CPU by default, decoding the media internally (no
separate ffmpeg step). The library is imported **lazily**, so the core package imports and tests run without it
installed; its absence surfaces as an explicit `LocalAsrDependencyError`. A missing/unusable model surfaces as
`LocalAsrModelError`, and a transcription failure as `LocalAsrEngineError`. Timestamped segments are extracted
and their text preserved verbatim; the detected/used language is captured truthfully. It makes no shell call and
constructs no command string (there is no subprocess), so there is no shell-injection surface.

The `model_factory` seam lets tests drive the exact invocation shape (model/device/compute-type propagation,
segment/text extraction, error translation) with a fake model, without the real dependency or a downloaded
model.
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

# A factory that builds an engine model exposing ``transcribe(media_path, language=...) -> (segments, info)``.
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
            segments_iter, info = engine_model.transcribe(media_path, language=language)
            segments = tuple(
                LocalAsrSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=segment.text,
                )
                for segment in segments_iter
            )
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
