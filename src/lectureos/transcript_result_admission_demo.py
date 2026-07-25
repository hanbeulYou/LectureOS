"""Deterministic no-ASR demonstration of the External ASR Boundary admission (040 §14).

Drives the whole first-slice flow with no ffmpeg, Whisper, decoding, network, or real media:

    Fixture bytes → Media Import → Transcript Source Intake → Fake Provider Result (committed JSON fixture)
                 → Provider Result Admission → Raw Transcript → Repository Validation

The "fake provider" is a committed, deterministic provider-result fixture (with Korean text) — it is **not**
the output of any real ASR engine. It proves: a valid result is admitted and a canonical Raw Transcript is
created; replay is idempotent; a conflicting replay (same reference, different payload) is rejected; malformed
timing and a missing intake are rejected; no media file is read and no ASR engine runs during admission; the
provider evidence is preserved un-normalized and kept distinct from the Raw Transcript; and the repository
validates healthy. The reported identities are content-derived, so the committed golden reproduces byte-for-byte.
"""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from lectureos.application.provider_transcript_admission import (
    ProviderTranscriptAdmissionConflictError,
    ProviderTranscriptAdmissionError,
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteProviderTranscriptResultRepository,
    SQLiteRawTranscriptRepository,
    SQLiteSourceMediaRepository,
    initialize_sqlite_database,
)
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
_PROVIDER_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "transcript-result-admission"
    / "fixtures"
    / "provider-result.json"
)


def _load_provider_payload(path: Path | None = None) -> dict:
    source = path if path is not None else _PROVIDER_FIXTURE
    return json.loads(source.read_text(encoding="utf-8"))


def run_transcript_result_admission_demo(
    media_fixtures_directory: str | None = None,
    provider_fixture_path: str | None = None,
) -> dict:
    media_fixtures = (
        Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    )
    sample = media_fixtures / "sample-a.bin"
    payload = _load_provider_payload(
        Path(provider_fixture_path) if provider_fixture_path else None
    )
    document = build_provider_transcript_document(payload)

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        media_before = SQLiteSourceMediaRepository(connection).get(media.identity)
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake

        service = compose_sqlite_provider_transcript_admission_service(connection)
        first = service.admit(intake_id=intake.identity.value, document=document)
        repeated = service.admit(intake_id=intake.identity.value, document=document)

        # A conflicting replay: same provider result reference, different segment payload.
        conflicting_payload = copy.deepcopy(payload)
        conflicting_payload["segments"][0]["text"] = "다른 내용으로 바뀐 전사"
        conflicting_document = build_provider_transcript_document(conflicting_payload)
        conflict_rejected = False
        try:
            service.admit(intake_id=intake.identity.value, document=conflicting_document)
        except ProviderTranscriptAdmissionConflictError:
            conflict_rejected = True

        # Malformed timing (end <= start) is rejected while building the document (no admission attempted).
        malformed_timing_rejected = False
        try:
            build_provider_transcript_document(
                {
                    "provider": "fake-deterministic-asr",
                    "provider_result_ref": "bad-timing",
                    "segments": [{"start": 3.0, "end": 3.0, "text": "zero length"}],
                }
            )
        except ProviderTranscriptAdmissionError:
            malformed_timing_rejected = True

        # A missing intake is rejected.
        missing_intake_rejected = False
        try:
            service.admit(
                intake_id="transcript-source-intake:sha256:" + "0" * 64,
                document=document,
            )
        except ProviderTranscriptAdmissionError:
            missing_intake_rejected = True

        raw = SQLiteRawTranscriptRepository(connection).get(first.admission.raw_transcript_id)
        provider_result = SQLiteProviderTranscriptResultRepository(connection).get(
            first.admission.provider_transcript_result_id
        )
        admission_count = connection.execute(
            "SELECT COUNT(*) FROM provider_transcript_admissions"
        ).fetchone()[0]
        media_unmutated = (
            SQLiteSourceMediaRepository(connection).get(media.identity) == media_before
        )
        provider_evidence_distinct = (
            provider_result is not None
            and raw is not None
            and provider_result.identity != raw.identity
            and raw.provider_result_id == provider_result.identity
            and provider_result.normalized is False
        )
        provider_evidence_preserved = (
            provider_result is not None
            and "안녕하세요" in provider_result.original_content
        )
        connection.close()

        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "media_id": media.identity.value,
            "intake_id": intake.identity.value,
            "provider_result_ref": document.provider_result_ref,
            "admission_id": first.admission.identity.value,
            "provider_transcript_result_id": first.admission.provider_transcript_result_id.value,
            "raw_transcript_id": first.admission.raw_transcript_id.value,
            "segment_count": first.admission.segment_count,
            "content_fingerprint": first.admission.content_fingerprint,
            # Behavioral checks.
            "first_admission_created": first.created,
            "replay_is_idempotent": not repeated.created
            and repeated.admission.identity == first.admission.identity,
            "conflicting_replay_rejected": conflict_rejected,
            "malformed_timing_rejected": malformed_timing_rejected,
            "missing_intake_rejected": missing_intake_rejected,
            "raw_transcript_created": raw is not None and len(raw.segment_ids) == document.segments.__len__(),
            "provider_evidence_preserved": provider_evidence_preserved,
            "provider_evidence_distinct_from_transcript": provider_evidence_distinct,
            "single_admission": admission_count == 1,
            "source_media_unmutated": media_unmutated,
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "media_id",
        "intake_id",
        "provider_result_ref",
        "admission_id",
        "provider_transcript_result_id",
        "raw_transcript_id",
        "segment_count",
        "content_fingerprint",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_transcript_result_admission_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
