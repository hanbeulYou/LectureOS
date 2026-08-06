"""Deterministic adapter-orchestration demonstration for the local ASR adapter (040 §15).

This exercises the adapter's orchestration with a **fake** deterministic engine runner — it is NOT a real ASR
quality demonstration and no real ASR engine runs here. It proves the wiring around the real engine boundary:

    Fixture bytes → Media Import → Transcript Intake → Local ASR Adapter orchestration → Fake engine output
                 → Provider Transcript Admission → Raw Transcript → Repository Validation

It proves: the adapter resolves Source Media lineage and hands the engine the verified source path; operational
source verification (existence + fingerprint) occurs; the existing provider-neutral admission service is the only
write boundary; replay reuses the admitted result without re-running the engine; a failure before admission
(changed source bytes) writes nothing; repository validation stays healthy; and the committed golden reproduces
byte-for-byte. Identities are content-derived, so the golden is deterministic.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.local_asr_transcription import (
    LocalAsrResult,
    LocalAsrSegment,
    LocalAsrSourceChangedError,
)
from lectureos.composition import (
    compose_sqlite_local_asr_transcription_service,
    compose_sqlite_media_import_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteProviderTranscriptResultRepository,
    SQLiteRawTranscriptRepository,
    initialize_sqlite_database,
)
from lectureos.validation import validate_database

_MEDIA_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "media-import"
    / "fixtures"
    / "sample-a.bin"
)

# A fixed, deterministic "engine output" with Korean text — NOT produced by a real ASR engine.
_FAKE_SEGMENTS = (
    LocalAsrSegment(0.0, 2.75, "안녕하세요, 로컬 ASR 어댑터 데모입니다."),
    LocalAsrSegment(2.75, 6.0, "이 세그먼트는 실제 엔진이 아니라 결정적 fake runner가 만든 것입니다."),
    LocalAsrSegment(6.0, 9.5, "출력은 기존 provider-neutral admission 경계를 통과합니다."),
)


class _FakeEngineRunner:
    """A deterministic fake local ASR engine; records the media path and language it was invoked with."""

    def __init__(self) -> None:
        self.invocations: list[dict] = []

    def transcribe(
        self, *, media_path, model, language, device, compute_type, condition_on_previous_text
    ):
        self.invocations.append(
            {
                "media_path": media_path,
                "model": model,
                "language": language,
                "device": device,
                "compute_type": compute_type,
                "condition_on_previous_text": condition_on_previous_text,
            }
        )
        return LocalAsrResult(
            provider="faster-whisper",
            model=model,
            language=language or "ko",
            segments=_FAKE_SEGMENTS,
        )


def run_local_asr_demo(media_fixture_path: str | None = None) -> dict:
    fixture = Path(media_fixture_path) if media_fixture_path else _MEDIA_FIXTURE
    fixture_bytes = fixture.read_bytes()

    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        database = base / "lectureos.sqlite3"
        # A private copy of the fixture bytes so the failure check can safely mutate the source file.
        source = base / "lecture-source.bin"
        source.write_bytes(fixture_bytes)

        connection = initialize_sqlite_database(database)
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake

        engine = _FakeEngineRunner()
        service = compose_sqlite_local_asr_transcription_service(connection, engine_runner=engine)

        first = service.transcribe(intake_id=intake.identity.value, model="tiny", language="ko")
        repeated = service.transcribe(intake_id=intake.identity.value, model="tiny", language="ko")

        raw = SQLiteRawTranscriptRepository(connection).get(first.admission.raw_transcript_id)
        provider_result = SQLiteProviderTranscriptResultRepository(connection).get(
            first.admission.provider_transcript_result_id
        )
        admission_count_before_failure = connection.execute(
            "SELECT COUNT(*) FROM provider_transcript_admissions"
        ).fetchone()[0]

        # Failure before admission writes nothing: change the source bytes, then a new-anchor run must fail
        # the fingerprint check and add no admission row and never invoke the engine.
        source.write_bytes(b"tampered-bytes-after-import")
        engine_calls_before_failure = len(engine.invocations)
        source_changed_rejected = False
        try:
            service.transcribe(intake_id=intake.identity.value, model="base", language="ko")
        except LocalAsrSourceChangedError:
            source_changed_rejected = True
        admission_count_after_failure = connection.execute(
            "SELECT COUNT(*) FROM provider_transcript_admissions"
        ).fetchone()[0]

        connection.close()
        validation = validate_database(str(database))

        engine_used_source_path = (
            len(engine.invocations) >= 1
            and engine.invocations[0]["media_path"] == str(source.resolve())
        )

        return {
            # Deterministic, content-derived facts (golden).
            "media_id": media.identity.value,
            "intake_id": intake.identity.value,
            "admission_id": first.admission.identity.value,
            "provider_transcript_result_id": first.admission.provider_transcript_result_id.value,
            "raw_transcript_id": first.admission.raw_transcript_id.value,
            "segment_count": first.admission.segment_count,
            "content_fingerprint": first.admission.content_fingerprint,
            # Behavioral checks.
            "first_execution_created_and_ran": first.created and first.executed,
            "replay_reused_without_rerun": (
                not repeated.created
                and not repeated.executed
                and repeated.admission.identity == first.admission.identity
                and len(engine.invocations) == 1
            ),
            "adapter_used_source_lineage": engine_used_source_path,
            "raw_transcript_created": raw is not None and len(raw.segment_ids) == len(_FAKE_SEGMENTS),
            "provider_evidence_distinct": (
                provider_result is not None
                and raw is not None
                and provider_result.identity != raw.identity
                and raw.provider_result_id == provider_result.identity
            ),
            "source_changed_rejected": source_changed_rejected,
            "failure_before_admission_wrote_nothing": (
                admission_count_after_failure == admission_count_before_failure
                and len(engine.invocations) == engine_calls_before_failure
            ),
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "media_id",
        "intake_id",
        "admission_id",
        "provider_transcript_result_id",
        "raw_transcript_id",
        "segment_count",
        "content_fingerprint",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_local_asr_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
