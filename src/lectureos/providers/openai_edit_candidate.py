"""OpenAI Responses adapter for provider-neutral Edit Candidate generation (042 §9.2).

Translates one provider-neutral generation request into an OpenAI Structured Outputs call and parses the
strict response into provider-neutral proposals. It owns request construction, invocation, strict-schema
configuration, provider-native parsing, and provider-native failure translation only; it never queries
repositories, constructs canonical identities, writes Candidate records, defines Candidate Type meanings,
or returns raw provider JSON through the Port. Registry membership and range-context validation are the
generation service's responsibility, so an unknown Candidate Type or out-of-context range becomes a
generation-layer normalization diagnostic rather than an adapter failure.
"""

from __future__ import annotations

import json
import os
import socket
from math import isfinite
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lectureos.application.edit_candidate_generation import (
    EditCandidateGenerationRequest,
    EditCandidateMalformedOutputError,
    EditCandidateProviderFailure,
    GeneratedProposal,
)

OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_EDIT_CANDIDATE_MODEL = "gpt-5.6-terra"
EDIT_CANDIDATE_PROMPT_VERSION = "edit-candidate-generation.v1"

ResponseTransport = Callable[[dict, str, float], dict]

_SYSTEM_PROMPT = (
    "You prepare advisory Edit Candidate proposals for human review of a Korean lecture recording. "
    "Use only these candidate_type keys and nothing else: "
    "non_lecture_region (a region may contain non-instructional material such as chatter, equipment or "
    "setup issues, waiting, pre/post-class material, or breaks); "
    "redundant_restatement (a region may contain a misspeak, restart, repeated phrase, repeated "
    "explanation, or redundant restatement); "
    "delivery_concern (a region may contain a possible delivery, continuity, or clarity concern). "
    "Each proposal is advisory only: it is never a deletion or edit command, never a value judgment, and "
    "never a review decision. Ground every proposal in the supplied transcript excerpt and finding "
    "evidence; never invent facts. Give each proposal exactly one located time range that lies within the "
    "supplied context window. Write a concise, human-reviewable rationale that names the concern and why "
    "the chosen candidate_type applies; do not include hidden reasoning, chain of thought, review "
    "decisions, or executable edit instructions. Return zero proposals when none is warranted. Respond "
    "only with the required structured output."
)


class OpenAIEditCandidateGenerationAdapter:
    """Translate one neutral generation request through OpenAI Structured Outputs."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_OPENAI_EDIT_CANDIDATE_MODEL,
        timeout_seconds: float = 30.0,
        transport: ResponseTransport | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("OpenAI edit candidate model must not be blank")
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("OpenAI edit candidate timeout must be positive and finite")
        self._api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.prompt_version = EDIT_CANDIDATE_PROMPT_VERSION
        self.timeout_seconds = timeout_seconds
        self._transport = transport or _post_openai_response

    def generate_candidates(
        self, request: EditCandidateGenerationRequest
    ) -> tuple[GeneratedProposal, ...]:
        if self._api_key is None or not self._api_key.strip():
            raise EditCandidateProviderFailure("OPENAI_API_KEY is required")
        body = self._request_body(request)
        try:
            response = self._transport(body, self._api_key, self.timeout_seconds)
        except EditCandidateProviderFailure:
            raise
        except (TimeoutError, socket.timeout) as error:
            raise EditCandidateProviderFailure(
                "OpenAI edit candidate request timed out"
            ) from error
        except Exception as error:
            raise EditCandidateProviderFailure(
                "OpenAI edit candidate request failed"
            ) from error
        return self._parse_response(response)

    def _request_body(self, request: EditCandidateGenerationRequest) -> dict:
        # External egress is bounded to Finding Type/evidence, bounded transcript excerpts, allowed keys,
        # and the context window timing. No canonical identity, media, or file path is transmitted.
        context = {
            "finding_type": request.finding_type,
            "finding_evidence": request.finding_evidence,
            "finding_range": {
                "start": request.finding_range_start,
                "end": request.finding_range_end,
            },
            "context_window": {
                "start": request.context_window_start,
                "end": request.context_window_end,
            },
            "allowed_candidate_types": list(request.allowed_candidate_types),
            "transcript_context": [
                {
                    "text": segment.text,
                    "source_order": segment.source_order,
                    "start": segment.start,
                    "end": segment.end,
                }
                for segment in request.context_segments
            ],
        }
        return {
            "model": self.model,
            "store": False,
            "input": [
                {"role": "system", "content": _SYSTEM_PROMPT},
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
                    "name": "lectureos_edit_candidates",
                    "strict": True,
                    "schema": _EDIT_CANDIDATE_SCHEMA,
                }
            },
        }

    def _parse_response(self, response: dict) -> tuple[GeneratedProposal, ...]:
        if not isinstance(response, dict):
            raise EditCandidateMalformedOutputError(
                "OpenAI edit candidate response must be an object"
            )
        if response.get("status") != "completed":
            raise EditCandidateProviderFailure(
                "OpenAI edit candidate response was not completed"
            )
        output_text = _extract_output_text(response)
        try:
            payload = json.loads(output_text)
        except (TypeError, json.JSONDecodeError) as error:
            raise EditCandidateMalformedOutputError(
                "OpenAI edit candidate output was not valid JSON"
            ) from error
        if not isinstance(payload, dict) or set(payload) != {"proposals"}:
            raise EditCandidateMalformedOutputError(
                "OpenAI edit candidate output shape is invalid"
            )
        proposals = payload["proposals"]
        if not isinstance(proposals, list):
            raise EditCandidateMalformedOutputError(
                "OpenAI edit candidate proposals must be an array"
            )
        return tuple(
            self._parse_proposal(item, index) for index, item in enumerate(proposals)
        )

    def _parse_proposal(self, item: object, index: int) -> GeneratedProposal:
        required = {"candidate_type", "rationale", "range_start", "range_end"}
        if not isinstance(item, dict) or set(item) != required:
            raise EditCandidateMalformedOutputError(
                "OpenAI edit candidate proposal shape is invalid"
            )
        if not isinstance(item["candidate_type"], str) or not isinstance(
            item["rationale"], str
        ):
            raise EditCandidateMalformedOutputError(
                "OpenAI edit candidate proposal text is invalid"
            )
        start = _require_number(item["range_start"], "range_start")
        end = _require_number(item["range_end"], "range_end")
        return GeneratedProposal(
            candidate_type=item["candidate_type"],
            rationale=item["rationale"],
            range_start=start,
            range_end=end,
            source_index=index,
        )


def _extract_output_text(response: dict) -> str:
    output = response.get("output")
    if not isinstance(output, list):
        raise EditCandidateMalformedOutputError(
            "OpenAI edit candidate response output is missing"
        )
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
                raise EditCandidateProviderFailure(
                    "OpenAI edit candidate request was refused"
                )
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
    if len(texts) != 1:
        raise EditCandidateMalformedOutputError(
            "OpenAI edit candidate response requires one output text"
        )
    return texts[0]


def _require_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EditCandidateMalformedOutputError(
            f"OpenAI edit candidate {name} is invalid"
        )
    number = float(value)
    if not isfinite(number):
        raise EditCandidateMalformedOutputError(
            f"OpenAI edit candidate {name} is invalid"
        )
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
        raise EditCandidateProviderFailure(
            f"OpenAI edit candidate request failed with HTTP {error.code}"
        ) from error
    except (URLError, TimeoutError, socket.timeout) as error:
        raise EditCandidateProviderFailure(
            "OpenAI edit candidate request failed"
        ) from error
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EditCandidateMalformedOutputError(
            "OpenAI edit candidate response was not valid JSON"
        ) from error
    if not isinstance(payload, dict):
        raise EditCandidateMalformedOutputError(
            "OpenAI edit candidate response must be an object"
        )
    return payload


_EDIT_CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate_type": {"type": "string"},
                    "rationale": {"type": "string"},
                    "range_start": {"type": "number"},
                    "range_end": {"type": "number"},
                },
                "required": [
                    "candidate_type",
                    "rationale",
                    "range_start",
                    "range_end",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["proposals"],
    "additionalProperties": False,
}


__all__ = ["OpenAIEditCandidateGenerationAdapter"]
