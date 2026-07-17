import tempfile
import unittest
from pathlib import Path

from lectureos.demo import run_end_to_end_demo


class EndToEndDemoTest(unittest.TestCase):
    def test_complete_pipeline_materializes_linked_utf8_srt(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            result = run_end_to_end_demo(directory)
            path = Path(result.materialization.final_path)
            file_bytes = path.read_bytes()

            self.assertTrue(path.is_file())
            self.assertEqual("lectureos-demo.srt", path.name)
            self.assertFalse(file_bytes.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r\n", file_bytes)
            self.assertEqual(result.export_artifact.content, file_bytes.decode("utf-8"))
            self.assertEqual(
                result.final_selection.identity,
                result.export_artifact.final_selection_id,
            )
            self.assertEqual(
                result.subtitle_revision.identity,
                result.final_selection.revision_id,
            )
            self.assertEqual(
                result.export_artifact.identity,
                result.materialization.artifact_id,
            )
            self.assertEqual(
                result.subtitle_candidate.identity,
                result.subtitle_revision.parent_candidate_id,
            )
            self.assertEqual(
                result.raw_transcript.identity,
                result.transcript_revision.transcript_id,
            )
            self.assertEqual("안녕하세요", result.export_artifact.content.splitlines()[2])

    def test_demo_records_are_immutable_across_downstream_orchestration(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            result = run_end_to_end_demo(directory, filename="preserved.srt")
            records = (
                result.raw_transcript,
                result.transcript_candidate,
                result.transcript_revision,
                result.subtitle_candidate,
                result.subtitle_revision,
                result.final_selection,
                result.export_artifact,
            )
            for record in records:
                with self.subTest(record=type(record).__name__):
                    with self.assertRaises((AttributeError, TypeError)):
                        record.identity = record.identity


if __name__ == "__main__":
    unittest.main()
