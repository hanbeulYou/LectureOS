import json
import unittest

from lectureos.application import (
    CorrectionGenerationFailure,
    CorrectionGenerationRequest,
    CorrectionSegmentContext,
)
from lectureos.execution.identities import (
    CapabilityReference,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.providers import OpenAITranscriptCorrectionAdapter
from lectureos.transcript.identities import TranscriptId, TranscriptSegmentId


def response_for(payload):
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(payload)}],
            }
        ],
    }


class OpenAITranscriptCorrectionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def transport(body, key, timeout):
            self.calls.append((body, key, timeout))
            return response_for(
                {
                    "proposals": [
                        {
                            "target_segment_id": "segment-1",
                            "proposed_text": "윤동주의 서시를 읽겠습니다.",
                            "rationale": "시인 이름의 음성 인식 오류를 바로잡음",
                            "evidence": ["문학 수업 문맥"],
                            "confidence": 0.95,
                            "uncertainty": 0.05,
                        }
                    ]
                }
            )

        self.transport = transport
        self.request = CorrectionGenerationRequest(
            transcript_id=TranscriptId("raw"),
            parent_revision_id=None,
            source_media_id=SourceMediaId("media"),
            source_timeline_id=SourceTimelineId("timeline"),
            run_id=ProcessingRunId("run"),
            unit_execution_id=UnitExecutionId("execution"),
            capability=CapabilityReference("transcript.correction"),
            segments=(
                CorrectionSegmentContext(
                    identity=TranscriptSegmentId("segment-1"),
                    text="윤동주에 서시를 읽겠습니다.",
                    source_order=0,
                    source_timeline_id=SourceTimelineId("timeline"),
                    start=0.0,
                    end=2.0,
                ),
            ),
        )

    def test_translates_request_and_strict_response(self):
        adapter = OpenAITranscriptCorrectionAdapter(
            api_key="secret", transport=self.transport, timeout_seconds=7
        )
        proposals = adapter.generate_corrections(self.request)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].target_segment_id, TranscriptSegmentId("segment-1"))
        self.assertEqual(proposals[0].provider_reference, "openai:gpt-5.6-terra")
        body, key, timeout = self.calls[0]
        self.assertEqual(key, "secret")
        self.assertEqual(timeout, 7)
        self.assertFalse(body["store"])
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertNotIn("secret", json.dumps(body))
        user_context = json.loads(body["input"][1]["content"])
        self.assertEqual(user_context["segments"][0]["text"], self.request.segments[0].text)
        self.assertNotIn("run_id", user_context)

    def test_zero_proposals_are_preserved(self):
        adapter = OpenAITranscriptCorrectionAdapter(
            api_key="secret", transport=lambda *_: response_for({"proposals": []})
        )
        self.assertEqual(adapter.generate_corrections(self.request), ())

    def test_missing_credential_is_safe(self):
        adapter = OpenAITranscriptCorrectionAdapter(api_key="", transport=self.transport)
        with self.assertRaisesRegex(CorrectionGenerationFailure, "OPENAI_API_KEY"):
            adapter.generate_corrections(self.request)
        self.assertEqual(self.calls, [])

    def test_malformed_refused_and_incomplete_responses_fail(self):
        cases = (
            {"status": "incomplete", "output": []},
            {
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "refusal"}]}],
            },
            response_for({"proposals": [{"target_segment_id": "segment-1"}]}),
            response_for({"proposals": "wrong"}),
        )
        for response in cases:
            with self.subTest(response=response):
                adapter = OpenAITranscriptCorrectionAdapter(
                    api_key="secret", transport=lambda *_, value=response: value
                )
                with self.assertRaises(CorrectionGenerationFailure):
                    adapter.generate_corrections(self.request)

    def test_transport_failure_does_not_leak_key(self):
        def failing(*_):
            raise RuntimeError("transport failed")

        adapter = OpenAITranscriptCorrectionAdapter(api_key="secret", transport=failing)
        with self.assertRaises(CorrectionGenerationFailure) as caught:
            adapter.generate_corrections(self.request)
        self.assertNotIn("secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
