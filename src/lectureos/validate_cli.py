"""Runnable entry point for read-only repository validation (``lectureos validate``).

Validates that a LectureOS SQLite repository is internally consistent — identities, references, DomainResult
lineage, and the edit-export pipeline invariants — without modifying it. It prints a summary (objects checked,
warnings, errors, overall health) plus each diagnostic, and returns a machine-readable exit code.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.validate_cli --database lecture.db [--format text|json]

Exit codes:

    0  healthy      — no errors and no warnings
    1  errors       — one or more error diagnostics (repository is inconsistent)
    2  warnings     — warnings only, no errors
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from lectureos.validation import RepositoryHealth, ValidationReport, validate_database

_EXIT_BY_HEALTH = {
    RepositoryHealth.HEALTHY: 0,
    RepositoryHealth.ERRORS: 1,
    RepositoryHealth.WARNINGS: 2,
}


def _render_text(report: ValidationReport) -> str:
    version = "unknown" if report.schema_version is None else str(report.schema_version)
    lines = [
        "LectureOS repository validation",
        "",
        f"  schema version   : {version}",
        f"  objects checked  : {report.objects_checked}",
        f"  warnings         : {report.warning_count}",
        f"  errors           : {report.error_count}",
        f"  health           : {report.health.value}",
    ]
    if report.diagnostics:
        lines.append("")
        lines.append("diagnostics:")
        for diagnostic in report.diagnostics:
            lines.append(
                f"  [{diagnostic.severity.value.upper()}] {diagnostic.code} "
                f"@ {diagnostic.location}: {diagnostic.message}"
            )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.validate_cli",
        description=(
            "Validate that a LectureOS repository is internally consistent (read-only). Checks identities, "
            "references, DomainResult lineage, and edit-export pipeline invariants. Never modifies the "
            "repository."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  PYTHONPATH=src python3 -m lectureos.validate_cli --database lecture.db\n"
            "  PYTHONPATH=src python3 -m lectureos.validate_cli --database lecture.db --format json\n"
            "\n"
            "exit status: 0 healthy; 1 errors present; 2 warnings only."
        ),
    )
    parser.add_argument(
        "--database",
        required=True,
        metavar="PATH",
        help="path to the LectureOS SQLite database to validate",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = validate_database(args.database)
    if args.format == "json":
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print(_render_text(report))
    return _EXIT_BY_HEALTH[report.health]


if __name__ == "__main__":
    raise SystemExit(main())
