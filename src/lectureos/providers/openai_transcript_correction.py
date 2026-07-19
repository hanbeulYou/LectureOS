"""OpenAI Responses adapter for provider-neutral Transcript correction proposals."""

from __future__ import annotations

import json
import os
import socket
from math import isfinite
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lectureos.application.transcript_correction_generation import (
    CorrectionGenerationFailure,
    CorrectionGenerationRequest,
    CorrectionProposal,
)
from lectureos.transcript.identities import TranscriptSegmentId

OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_CORRECTION_MODEL = "gpt-5.6-terra"

ResponseTransport = Callable[[dict, str, float], dict]


class OpenAITranscriptCorrectionAdapter:
    """Translate one neutral correction request through OpenAI Structured Outputs."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_OPENAI_CORRECTION_MODEL,
        timeout_seconds: float = 30.0,
        transport: ResponseTransport | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("OpenAI correction model must not be blank")
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("OpenAI correction timeout must be positive and finite")
        self._api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._transport = transport or _post_openai_response

    def generate_corrections(
        self, request: CorrectionGenerationRequest
    ) -> tuple[CorrectionProposal, ...]:
        if self._api_key is None or not self._api_key.strip():
            raise CorrectionGenerationFailure("OPENAI_API_KEY is required")
        body = self._request_body(request)
        try:
            response = self._transport(body, self._api_key, self.timeout_seconds)
        except CorrectionGenerationFailure:
            raise
        except (TimeoutError, socket.timeout) as error:
            raise CorrectionGenerationFailure("OpenAI correction request timed out") from error
        except Exception as error:
            raise CorrectionGenerationFailure("OpenAI correction request failed") from error
        return self._parse_response(response)

    def _request_body(self, request: CorrectionGenerationRequest) -> dict:
        context = {
            "transcript_id": request.transcript_id.value,
            "parent_revision_id": (
                request.parent_revision_id.value if request.parent_revision_id else None
            ),
            "source_media_id": request.source_media_id.value,
            "source_timeline_id": request.source_timeline_id.value,
            "segments": [
                {
                    "identity": segment.identity.value,
                    "text": segment.text,
                    "source_order": segment.source_order,
                    "start": segment.start,
                    "end": segment.end,
                    "speaker_label": segment.speaker_label,
                }
                for segment in request.segments
            ],
        }
        return {
            "model": self.model,
            "store": False,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Correct Korean lecture transcript recognition errors only. "
                        "Return no proposal when the source is already defensible. "
                        "Never change segment identity, order, timing, or meaning."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        context, ensure_ascii=False, separators=(",", ":"), sort_keys=True
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "lectureos_transcript_corrections",
                    "strict": True,
                    "schema": _CORRECTION_SCHEMA,
                }
            },
        }

    def _parse_response(self, response: dict) -> tuple[CorrectionProposal, ...]:
        if not isinstance(response, dict):
            raise CorrectionGenerationFailure("OpenAI correction response must be an object")
        if response.get("status") != "completed":
            raise CorrectionGenerationFailure("OpenAI correction response was not completed")
        output_text = _extract_output_text(response)
        try:
            payload = json.loads(output_text)
        except (TypeError, json.JSONDecodeError) as error:
            raise CorrectionGenerationFailure(
                "OpenAI correction output was not valid JSON"
            ) from error
        if not isinstance(payload, dict) or set(payload) != {"proposals"}:
            raise CorrectionGenerationFailure("OpenAI correction output shape is invalid")
        proposals = payload["proposals"]
        if not isinstance(proposals, list):
            raise CorrectionGenerationFailure("OpenAI correction proposals must be an array")
        return tuple(self._parse_proposal(item) for item in proposals)

    def _parse_proposal(self, item: object) -> CorrectionProposal:
        required = {
            "target_segment_id",
            "proposed_text",
            "rationale",
            "evidence",
            "confidence",
            "uncertainty",
        }
        if not isinstance(item, dict) or set(item) != required:
            raise CorrectionGenerationFailure("OpenAI correction proposal shape is invalid")
        if not all(
            isinstance(item[name], str)
            for name in ("target_segment_id", "proposed_text", "rationale")
        ):
            raise CorrectionGenerationFailure("OpenAI correction proposal text is invalid")
        evidence = item["evidence"]
        if not isinstance(evidence, list) or not all(
            isinstance(value, str) for value in evidence
        ):
            raise CorrectionGenerationFailure("OpenAI correction evidence is invalid")
        confidence = _optional_number(item["confidence"], "confidence")
        uncertainty = _optional_number(item["uncertainty"], "uncertainty")
        try:
            target = TranscriptSegmentId(item["target_segment_id"])
            return CorrectionProposal(
                target_segment_id=target,
                proposed_text=item["proposed_text"],
                rationale=item["rationale"],
                evidence=tuple(evidence),
                confidence=confidence,
                uncertainty=uncertainty,
                provider_reference=f"openai:{self.model}",
            )
        except ValueError as error:
            raise CorrectionGenerationFailure(
                "OpenAI correction proposal contains an invalid value"
            ) from error


def _extract_output_text(response: dict) -> str:
    output = response.get("output")
    if not isinstance(output, list):
        raise CorrectionGenerationFailure("OpenAI correction response output is missing")
    texts = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise CorrectionGenerationFailure("OpenAI correction request was refused")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
    if len(texts) != 1:
        raise CorrectionGenerationFailure("OpenAI correction response requires one output text")
    return texts[0]


def _optional_number(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CorrectionGenerationFailure(f"OpenAI correction {name} is invalid")
    number = float(value)
    if not isfinite(number):
        raise CorrectionGenerationFailure(f"OpenAI correction {name} is invalid")
    return number


def _post_openai_response(body: dict, api_key: str, timeout_seconds: float) -> dict:
    request = Request(
        OPENAI_RESPONSES_ENDPOINT,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
    except HTTPError as error:
        raise CorrectionGenerationFailure(
            f"OpenAI correction request failed with HTTP {error.code}"
        ) from error
    except (URLError, TimeoutError, socket.timeout) as error:
        raise CorrectionGenerationFailure("OpenAI correction request failed") from error
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CorrectionGenerationFailure("OpenAI correction response was not valid JSON") from error
    if not isinstance(payload, dict):
        raise CorrectionGenerationFailure("OpenAI correction response must be an object")
    return payload


_CORRECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "target_segment_id": {"type": "string"},
                    "proposed_text": {"type": "string"},
                    "rationale": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": ["number", "null"]},
                    "uncertainty": {"type": ["number", "null"]},
                },
                "required": [
                    "target_segment_id",
                    "proposed_text",
                    "rationale",
                    "evidence",
                    "confidence",
                    "uncertainty",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["proposals"],
    "additionalProperties": False,
}


__all__ = ["OpenAITranscriptCorrectionAdapter"]
