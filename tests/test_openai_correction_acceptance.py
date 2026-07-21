import unittest
from unittest.mock import patch

from lectureos.openai_correction_acceptance import run_credentialed_acceptance
from lectureos.providers import openai_transcript_correction


class OpenAICorrectionAcceptanceTests(unittest.TestCase):
    def test_fake_transport_exercises_canonical_restart_path(self):
        response = {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                '{"proposals":[{"target_segment_id":"synthetic-segment",'
                                '"proposed_text":"윤동주의 서시를 읽겠습니다.",'
                                '"rationale":"조사 인식 오류 수정","evidence":[],'
                                '"confidence":0.98,"uncertainty":0.02}]}'
                            ),
                        }
                    ],
                }
            ],
        }
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}), patch.object(
            openai_transcript_correction,
            "_post_openai_response",
            return_value=response,
        ):
            summary = run_credentialed_acceptance()
        self.assertEqual(summary["proposal_count"], 1)
        self.assertTrue(summary["canonical_restart_verified"])
        self.assertTrue(summary["structural_valid"])


if __name__ == "__main__":
    unittest.main()
