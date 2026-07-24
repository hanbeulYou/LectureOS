import tempfile
import unittest
from pathlib import Path

from lectureos.edit_export_demo import main, run_edit_export_demo

_GOLDEN = (
    Path(__file__).resolve().parent.parent
    / "examples"
    / "edit-export"
    / "expected"
    / "edit-export.json"
)


class EditExportDemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.out = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_demo_produces_a_real_file(self) -> None:
        result = run_edit_export_demo(str(self.out))
        produced = Path(result.output_path)
        self.assertTrue(produced.is_file())
        self.assertEqual(result.format, "lectureos-edit-export-json")
        self.assertEqual(result.version, "v1")

    def test_demo_stage_summary(self) -> None:
        result = run_edit_export_demo(str(self.out))
        self.assertEqual(result.transcript_segments, 2)
        self.assertEqual(result.analysis_findings, 1)
        self.assertEqual(result.edit_candidates, 2)
        self.assertEqual(result.review_decisions, 2)
        self.assertEqual(result.approved_decisions, 2)
        self.assertEqual(result.export_representations, 3)
        self.assertEqual(result.assembly_members, 3)
        self.assertEqual(result.artifact_entries, 3)

    def test_demo_output_matches_golden_fixture(self) -> None:
        result = run_edit_export_demo(str(self.out))
        produced = Path(result.output_path).read_bytes()
        self.assertEqual(
            produced,
            _GOLDEN.read_bytes(),
            "demo output drifted from examples/edit-export/expected/edit-export.json; "
            "regenerate the golden fixture only after an intentional, reviewed change",
        )

    def test_demo_is_deterministic(self) -> None:
        first = Path(run_edit_export_demo(str(self.out)).output_path).read_bytes()
        with tempfile.TemporaryDirectory() as second_dir:
            second = Path(run_edit_export_demo(second_dir).output_path).read_bytes()
        self.assertEqual(first, second)

    def test_main_returns_zero_and_writes_file(self) -> None:
        code = main(["--output-directory", str(self.out)])
        self.assertEqual(code, 0)
        self.assertTrue((self.out / "edit-export.json").is_file())

    def test_main_reports_error_on_bad_output_directory(self) -> None:
        # A relative destination is rejected by the local writer (absolute path required).
        code = main(["--output-directory", "relative-not-absolute"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
