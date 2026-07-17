import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lectureos import demo_cli
from lectureos.execution.identities import ArtifactId
from lectureos.export.identities import (
    MaterializationRequestId,
    MaterializationResultId,
)


class DemoCliTest(unittest.TestCase):
    def test_real_module_invocation_uses_default_filename(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            completed = self._run_cli("--output-directory", directory)
            path = Path(directory) / "lectureos-demo.srt"

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue(path.is_file())
            file_bytes = path.read_bytes()
            self.assertFalse(file_bytes.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r\n", file_bytes)
            self.assertIn("안녕하세요", file_bytes.decode("utf-8"))
            self.assertIn("status: success\n", completed.stdout)
            self.assertIn(f"file: {path}\n", completed.stdout)
            self.assertIn("export_artifact_id: demo-export-artifact\n", completed.stdout)
            self.assertIn(
                "materialization_request_id: demo-materialization-request\n",
                completed.stdout,
            )
            self.assertIn(
                "materialization_result_id: demo-materialization-result\n",
                completed.stdout,
            )
            self.assertIn(f"byte_size: {path.stat().st_size}\n", completed.stdout)
            self.assertNotIn("00:00:00,000", completed.stdout)

    def test_explicit_filename_is_passed_through(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            completed = self._run_cli(
                "--output-directory",
                directory,
                "--filename",
                "explicit.SRT",
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue((Path(directory) / "explicit.SRT").is_file())

    def test_missing_output_directory_is_argparse_usage_failure(self):
        completed = self._run_cli()
        self.assertEqual(2, completed.returncode)
        self.assertIn("usage:", completed.stderr)
        self.assertIn("--output-directory", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_relative_output_directory_is_known_execution_failure(self):
        completed = self._run_cli("--output-directory", "relative-directory")
        self.assertEqual(1, completed.returncode)
        self.assertIn("error: target directory must be absolute", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual("", completed.stdout)

    def test_cli_delegates_once_to_demo_runner_and_formats_result(self):
        fake = SimpleNamespace(
            export_artifact=SimpleNamespace(identity=ArtifactId("artifact")),
            materialization=SimpleNamespace(
                identity=MaterializationResultId("result"),
                request_id=MaterializationRequestId("request"),
                final_path="/absolute/output/demo.srt",
                byte_size=42,
            ),
        )
        output = io.StringIO()
        with patch.object(demo_cli, "run_end_to_end_demo", return_value=fake) as runner:
            with contextlib.redirect_stdout(output):
                status = demo_cli.main(
                    [
                        "--output-directory",
                        "/absolute/output",
                        "--filename",
                        "unchanged.SRT",
                    ]
                )
        self.assertEqual(0, status)
        runner.assert_called_once_with(
            "/absolute/output", filename="unchanged.SRT"
        )
        self.assertEqual(
            "status: success\n"
            "file: /absolute/output/demo.srt\n"
            "export_artifact_id: artifact\n"
            "materialization_request_id: request\n"
            "materialization_result_id: result\n"
            "byte_size: 42\n",
            output.getvalue(),
        )

    def test_known_failure_is_concise_but_unexpected_failure_is_not_hidden(self):
        stderr = io.StringIO()
        with patch.object(
            demo_cli,
            "run_end_to_end_demo",
            side_effect=ValueError("invalid filename"),
        ):
            with contextlib.redirect_stderr(stderr):
                status = demo_cli.main(["--output-directory", "/absolute/output"])
        self.assertEqual(1, status)
        self.assertEqual("error: invalid filename\n", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

        with patch.object(
            demo_cli,
            "run_end_to_end_demo",
            side_effect=RuntimeError("programming defect"),
        ):
            with self.assertRaisesRegex(RuntimeError, "programming defect"):
                demo_cli.main(["--output-directory", "/absolute/output"])

    def test_adapter_does_not_import_or_call_domain_services(self):
        source = Path("src/lectureos/demo_cli.py").read_text()
        self.assertIn("from lectureos.demo import", source)
        self.assertNotIn("lectureos.subtitle", source)
        self.assertNotIn("lectureos.transcript", source)
        self.assertNotIn("lectureos.export", source)
        self.assertNotIn("Service(", source)

    @staticmethod
    def _run_cli(*arguments):
        root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(root / "src")
        return subprocess.run(
            [sys.executable, "-m", "lectureos.demo_cli", *arguments],
            cwd=root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
