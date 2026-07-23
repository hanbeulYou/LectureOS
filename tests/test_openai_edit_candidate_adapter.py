import json
import unittest

from lectureos.application import (
    EditCandidateGenerationRequest,
    EditCandidateMalformedOutputError,
    EditCandidateProviderFailure,
    GenerationTranscriptSegment,
)
from lectureos.providers import OpenAIEditCandidateGenerationAdapter
from lectureos.providers.openai_edit_candidate import EDIT_CANDIDATE_PROMPT_VERSION
from lectureos.execution.identities import SourceTimelineId


def _request():
    return EditCandidateGenerationRequest(
        finding_type="low_educational_value",
        finding_evidence="an off-topic aside appears",
        finding_range_start=1.0,
        finding_range_end=2.0,
        source_timeline_id=SourceTimelineId("timeline"),
        context_segments=(
            GenerationTranscriptSegment(text="line 0", source_order=0, start=0.0, end=1.0),
            GenerationTranscriptSegment(text="line 1", source_order=1, start=1.0, end=2.0),
        ),
        context_window_start=0.0,
        context_window_end=17.0,
        allowed_candidate_types=("delivery_concern", "non_lecture_region", "redundant_restatement"),
    )


def _completed(output_text: str) -> dict:
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": output_text}],
            }
        ],
    }


def _proposals_payload(*items) -> str:
    return json.dumps({"proposals": list(items)})


def _recording_transport(response):
    captured = {}

    def transport(body, api_key, timeout):
        captured["body"] = body
        captured["api_key"] = api_key
        captured["timeout"] = timeout
        return response

    transport.captured = captured
    return transport


class OpenAIEditCandidateAdapterTests(unittest.TestCase):
    def _adapter(self, response):
        return OpenAIEditCandidateGenerationAdapter(
            api_key="test-key", transport=_recording_transport(response)
        )

    def test_request_includes_only_bounded_approved_context(self) -> None:
        transport = _recording_transport(_completed(_proposals_payload()))
        adapter = OpenAIEditCandidateGenerationAdapter(api_key="k", transport=transport)
        adapter.generate_candidates(_request())
        body = transport.captured["body"]
        user_content = json.loads(body["input"][1]["content"])
        self.assertEqual(
            set(user_content),
            {
                "finding_type",
                "finding_evidence",
                "finding_range",
                "context_window",
                "allowed_candidate_types",
                "transcript_context",
            },
        )
        # no canonical identity / media / file path leaks into the request
        serialized = json.dumps(body)
        for forbidden in ("source_media_id", "identity", "domain_result", "file", "path", "segment_id"):
            self.assertNotIn(forbidden, serialized)
        for seg in user_content["transcript_context"]:
            self.assertEqual(set(seg), {"text", "source_order", "start", "end"})

    def test_prompt_enumerates_exactly_three_registry_keys(self) -> None:
        transport = _recording_transport(_completed(_proposals_payload()))
        adapter = OpenAIEditCandidateGenerationAdapter(api_key="k", transport=transport)
        adapter.generate_candidates(_request())
        system = transport.captured["body"]["input"][0]["content"]
        for key in ("non_lecture_region", "redundant_restatement", "delivery_concern"):
            self.assertIn(key, system)
        self.assertIn("advisory", system)
        self.assertEqual(adapter.prompt_version, EDIT_CANDIDATE_PROMPT_VERSION)

    def test_strict_schema_requires_candidate_fields(self) -> None:
        transport = _recording_transport(_completed(_proposals_payload()))
        adapter = OpenAIEditCandidateGenerationAdapter(api_key="k", transport=transport)
        adapter.generate_candidates(_request())
        schema = transport.captured["body"]["text"]["format"]["schema"]
        item = schema["properties"]["proposals"]["items"]
        self.assertEqual(
            set(item["required"]),
            {"candidate_type", "rationale", "range_start", "range_end"},
        )
        self.assertFalse(item["additionalProperties"])
        self.assertTrue(transport.captured["body"]["text"]["format"]["strict"])

    def test_zero_proposals_parsed(self) -> None:
        adapter = self._adapter(_completed(_proposals_payload()))
        self.assertEqual(adapter.generate_candidates(_request()), ())

    def test_one_proposal_parsed(self) -> None:
        adapter = self._adapter(
            _completed(_proposals_payload(
                {"candidate_type": "non_lecture_region", "rationale": "r", "range_start": 1.0, "range_end": 1.5}
            ))
        )
        proposals = adapter.generate_candidates(_request())
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].candidate_type, "non_lecture_region")
        self.assertEqual(proposals[0].range_start, 1.0)
        self.assertEqual(proposals[0].source_index, 0)

    def test_multiple_proposals_preserve_order(self) -> None:
        adapter = self._adapter(
            _completed(_proposals_payload(
                {"candidate_type": "non_lecture_region", "rationale": "a", "range_start": 1.0, "range_end": 1.2},
                {"candidate_type": "delivery_concern", "rationale": "b", "range_start": 1.2, "range_end": 1.5},
            ))
        )
        proposals = adapter.generate_candidates(_request())
        self.assertEqual([p.candidate_type for p in proposals], ["non_lecture_region", "delivery_concern"])
        self.assertEqual([p.source_index for p in proposals], [0, 1])

    def test_provider_native_label_passes_through_unvalidated(self) -> None:
        # The adapter does not enforce the registry; the service does.
        adapter = self._adapter(
            _completed(_proposals_payload(
                {"candidate_type": "Remove This", "rationale": "r", "range_start": 1.0, "range_end": 1.5}
            ))
        )
        proposals = adapter.generate_candidates(_request())
        self.assertEqual(proposals[0].candidate_type, "Remove This")

    def test_unknown_proposal_field_rejected(self) -> None:
        adapter = self._adapter(
            _completed(_proposals_payload(
                {"candidate_type": "non_lecture_region", "rationale": "r", "range_start": 1.0, "range_end": 1.5, "extra": 1}
            ))
        )
        with self.assertRaises(EditCandidateMalformedOutputError):
            adapter.generate_candidates(_request())

    def test_malformed_top_level_output_fails(self) -> None:
        adapter = self._adapter(_completed("not json"))
        with self.assertRaises(EditCandidateMalformedOutputError):
            adapter.generate_candidates(_request())

    def test_wrong_output_shape_fails(self) -> None:
        adapter = self._adapter(_completed(json.dumps({"items": []})))
        with self.assertRaises(EditCandidateMalformedOutputError):
            adapter.generate_candidates(_request())

    def test_non_numeric_range_fails(self) -> None:
        adapter = self._adapter(
            _completed(_proposals_payload(
                {"candidate_type": "non_lecture_region", "rationale": "r", "range_start": "x", "range_end": 1.5}
            ))
        )
        with self.assertRaises(EditCandidateMalformedOutputError):
            adapter.generate_candidates(_request())

    def test_refusal_is_provider_failure(self) -> None:
        response = {
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}],
        }
        adapter = self._adapter(response)
        with self.assertRaises(EditCandidateProviderFailure):
            adapter.generate_candidates(_request())

    def test_incomplete_status_is_provider_failure(self) -> None:
        adapter = self._adapter({"status": "incomplete", "output": []})
        with self.assertRaises(EditCandidateProviderFailure):
            adapter.generate_candidates(_request())

    def test_transport_exception_translated_to_provider_failure(self) -> None:
        def boom(body, key, timeout):
            raise RuntimeError("socket exploded")

        adapter = OpenAIEditCandidateGenerationAdapter(api_key="k", transport=boom)
        with self.assertRaises(EditCandidateProviderFailure):
            adapter.generate_candidates(_request())

    def test_missing_api_key_is_provider_failure(self) -> None:
        adapter = OpenAIEditCandidateGenerationAdapter(
            api_key="", transport=_recording_transport(_completed(_proposals_payload()))
        )
        with self.assertRaises(EditCandidateProviderFailure):
            adapter.generate_candidates(_request())

    def test_no_hidden_retry_single_transport_call(self) -> None:
        calls = {"n": 0}

        def counting(body, key, timeout):
            calls["n"] += 1
            return _completed(_proposals_payload())

        adapter = OpenAIEditCandidateGenerationAdapter(api_key="k", transport=counting)
        adapter.generate_candidates(_request())
        self.assertEqual(calls["n"], 1)

    def test_no_raw_response_returned_through_port(self) -> None:
        adapter = self._adapter(
            _completed(_proposals_payload(
                {"candidate_type": "non_lecture_region", "rationale": "r", "range_start": 1.0, "range_end": 1.5}
            ))
        )
        proposals = adapter.generate_candidates(_request())
        for proposal in proposals:
            self.assertEqual(
                set(type(proposal).__dataclass_fields__),
                {"candidate_type", "rationale", "range_start", "range_end", "source_index"},
            )


if __name__ == "__main__":
    unittest.main()
