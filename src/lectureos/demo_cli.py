"""Thin command-line adapter for the in-process LectureOS demonstration.

Usage::

    PYTHONPATH=src python3 -m lectureos.demo_cli \
        --output-directory /absolute/existing/directory \
        --filename lectureos-demo.srt
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from lectureos.demo import DemoRunResult, run_end_to_end_demo


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.demo_cli",
        description="Run the in-process LectureOS demo and materialize one SRT file.",
    )
    parser.add_argument(
        "--output-directory",
        required=True,
        help="absolute existing non-symlink directory for the SRT file",
    )
    parser.add_argument(
        "--filename",
        default="lectureos-demo.srt",
        help="requested SRT filename (default: lectureos-demo.srt)",
    )
    return parser


def _render_success(result: DemoRunResult) -> str:
    return "\n".join(
        (
            "status: success",
            f"file: {result.materialization.final_path}",
            f"export_artifact_id: {result.export_artifact.identity.value}",
            (
                "materialization_request_id: "
                f"{result.materialization.request_id.value}"
            ),
            f"materialization_result_id: {result.materialization.identity.value}",
            f"byte_size: {result.materialization.byte_size}",
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_end_to_end_demo(
            args.output_directory,
            filename=args.filename,
        )
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(_render_success(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
