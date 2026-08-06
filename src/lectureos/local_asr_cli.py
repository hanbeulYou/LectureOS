"""Runnable entry point for the first local ASR execution adapter (040 §15).

Runs one concrete local ASR engine (faster-whisper) over the source file of an already-admitted transcript
source intake, converts the output into the existing provider-neutral ``ProviderTranscriptDocument``, and admits
it through the existing Provider Transcript Result Admission service — producing (or reusing) exactly one
canonical Raw Transcript. It accepts an **intake identity, not a media path**; it resolves the reference-in-place
source file, verifies it still matches the stored Source Media fingerprint, and (unlike the pure admission CLI)
performs **real local ASR execution** on CPU by default. If an equivalent result was already admitted, it reuses
it without re-running the engine. On any failure before admission it prints an explicit error, returns non-zero,
and leaves the repository unchanged; an admission conflict preserves the prior evidence.

Invocation (src layout)::

    PYTHONPATH=src python3 -m lectureos.local_asr_cli \
        --intake <transcript-source-intake-id> --database <db-path> --model <model-identifier>
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from lectureos.application.local_asr_transcription import (
    APPROVED_LOCAL_ASR_CONFIGURATION,
    LocalAsrError,
    LocalAsrTranscriptionResult,
)
from lectureos.application.provider_transcript_admission import (
    ProviderTranscriptAdmissionError,
)
from lectureos.composition import compose_sqlite_local_asr_transcription_service
from lectureos.persistence import PersistenceError, open_sqlite_database


def run_local_asr_transcription(
    *,
    database: str,
    intake_id: str,
    model: str,
    language: str | None = None,
    device: str = "cpu",
    compute_type: str = "int8",
) -> LocalAsrTranscriptionResult:
    """Run the local ASR adapter for an intake (existing repository required)."""

    connection = open_sqlite_database(database)
    try:
        service = compose_sqlite_local_asr_transcription_service(connection)
        return service.transcribe(
            intake_id=intake_id,
            model=model,
            language=language,
            device=device,
            compute_type=compute_type,
        )
    finally:
        connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m lectureos.local_asr_cli",
        description=(
            "Transcribe an admitted transcript source intake with a local ASR engine (faster-whisper) and admit "
            "the result through the existing provider-neutral boundary, producing one canonical Raw Transcript. "
            "Accepts an intake id (not a media path). Runs real local ASR on CPU by default; requires the source "
            "file to still exist and match its stored fingerprint. Transcription accuracy is not guaranteed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  PYTHONPATH=src python3 -m lectureos.local_asr_cli "
            "--intake transcript-source-intake:sha256:<digest> --database /data/lectureos.sqlite3 --model tiny\n"
            "\n"
            "admit the Source Media as an intake first with: "
            "python3 -m lectureos.transcript_intake_cli --media <id> --database <db>\n"
            "exit status: 0 on success; 1 on unavailable/changed source, missing dependency or model, engine "
            "failure, malformed output, admission conflict, or any error (repository left unchanged before "
            "admission)."
        ),
    )
    parser.add_argument(
        "--intake",
        required=True,
        metavar="TRANSCRIPT_SOURCE_INTAKE_ID",
        help="canonical TranscriptSourceIntakeId (e.g. transcript-source-intake:sha256:<digest>)",
    )
    parser.add_argument(
        "--database",
        required=True,
        metavar="PATH",
        help="path to the existing LectureOS SQLite database that holds the intake",
    )
    parser.add_argument(
        "--model",
        required=True,
        metavar="MODEL",
        help="local ASR model identifier (e.g. tiny, base, small; faster-whisper model name or path)",
    )
    parser.add_argument(
        "--language",
        metavar="LANG",
        default=None,
        help="optional declared language code (e.g. ko, en); omit to let the engine auto-detect",
    )
    parser.add_argument(
        "--device",
        metavar="DEVICE",
        default="cpu",
        help="compute device for the engine (default: cpu)",
    )
    parser.add_argument(
        "--compute-type",
        metavar="TYPE",
        default="int8",
        help="engine compute type (default: int8, CPU-safe)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_local_asr_transcription(
            database=args.database,
            intake_id=args.intake,
            model=args.model,
            language=args.language,
            device=args.device,
            compute_type=args.compute_type,
        )
    except (
        LocalAsrError,
        ProviderTranscriptAdmissionError,
        KeyError,
        ValueError,
        OSError,
        PersistenceError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    admission = result.admission
    status = "created" if result.created else "reused"
    print(
        f"{status} provider transcript admission {admission.identity.value} "
        f"for intake {admission.transcript_source_intake_id.value}"
    )
    print(f"source media: {admission.source_media_id.value}")
    print(f"provider transcript result: {admission.provider_transcript_result_id.value}")
    print(f"canonical raw transcript: {admission.raw_transcript_id.value}")
    print(f"provider/model: {admission.provider_reference}/{admission.provider_model}")
    print(f"provider result reference: {admission.provider_result_ref}")
    print(
        "provider configuration: condition_on_previous_text="
        f"{APPROVED_LOCAL_ASR_CONFIGURATION.condition_on_previous_text} "
        "(approved; vad_filter not enabled)"
    )
    print(f"segments: {admission.segment_count}")
    print(f"real ASR execution occurred: {'yes' if result.executed else 'no (reused prior admission)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
