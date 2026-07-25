"""Runnable entry point for the External ASR Boundary — provider transcript result admission (040 §14).

Admits an externally produced ASR result for an already-admitted transcript source intake (by
``TranscriptSourceIntakeId``), reading a deterministic local provider-result JSON document. It preserves the
provider evidence and creates exactly one canonical Raw Transcript in an existing LectureOS repository, then
reports the provider-result identity, the canonical Raw Transcript identity, the segment count, and whether the
admission was created or reused. It **executes no ASR engine**, reads no media bytes, decodes nothing, and makes
no network request. It accepts an intake identity and a JSON document — **not** a media path. On failure it
prints an explicit error, returns non-zero, and leaves the repository unchanged.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.transcript_result_admit_cli \
        --intake <transcript-source-intake-id> --input <provider-result.json> --database <db-path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from lectureos.application.provider_transcript_admission import (
    ProviderTranscriptAdmissionResult,
    build_provider_transcript_document,
)
from lectureos.composition import compose_sqlite_provider_transcript_admission_service
from lectureos.persistence import PersistenceError, open_sqlite_database


def run_transcript_result_admission(
    *, database: str, intake_id: str, input_path: str
) -> ProviderTranscriptAdmissionResult:
    """Admit an external provider ASR result for an intake (existing repository required)."""

    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    document = build_provider_transcript_document(payload)
    connection = open_sqlite_database(database)
    try:
        return compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake_id, document=document
        )
    finally:
        connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.transcript_result_admit_cli",
        description=(
            "Admit an externally produced ASR result for an already-admitted transcript source intake, "
            "producing one canonical Raw Transcript. LectureOS does NOT execute an ASR engine, read media "
            "bytes, decode media, or make network requests — the provider result is supplied as a local JSON "
            "document (an intake id, not a media path)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "the --input JSON document has the shape:\n"
            "  {\n"
            '    "provider": "<provider-reference>",\n'
            '    "model": "<optional-model>",\n'
            '    "language": "<optional-declared-language>",\n'
            '    "provider_result_ref": "<external-result-reference>",\n'
            '    "segments": [ {"start": 0.0, "end": 2.5, "text": "..."}, ... ]\n'
            "  }\n"
            "\n"
            "admit the Source Media as an intake first with: "
            "python3 -m lectureos.transcript_intake_cli --media <id> --database <db>\n"
            "exit status: 0 on success; 1 on malformed/unknown/conflicting/invalid input "
            "(the repository is left unchanged)."
        ),
    )
    parser.add_argument(
        "--intake",
        required=True,
        metavar="TRANSCRIPT_SOURCE_INTAKE_ID",
        help="canonical TranscriptSourceIntakeId (e.g. transcript-source-intake:sha256:<digest>)",
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="PATH",
        help="path to a local provider-result JSON document (provider-neutral / LectureOS-native)",
    )
    parser.add_argument(
        "--database",
        required=True,
        metavar="PATH",
        help="path to the existing LectureOS SQLite database that holds the intake",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_transcript_result_admission(
            database=args.database, intake_id=args.intake, input_path=args.input
        )
    except (KeyError, ValueError, OSError, PersistenceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    admission = result.admission
    status = "created" if result.created else "reused"
    print(
        f"{status} provider transcript admission {admission.identity.value} "
        f"for intake {admission.transcript_source_intake_id.value}"
    )
    print(f"provider transcript result: {admission.provider_transcript_result_id.value}")
    print(f"canonical raw transcript: {admission.raw_transcript_id.value}")
    print(f"segments: {admission.segment_count}")
    print("LectureOS did not execute an ASR engine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
