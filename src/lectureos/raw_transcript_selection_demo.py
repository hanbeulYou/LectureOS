"""Deterministic demonstration of Current Raw Transcript Selection and readiness (040 §16).

Drives the whole slice with fake (supplied) provider results — no real ASR — proving that one intake can hold
multiple distinct Raw Transcript candidates and that the current authoritative Raw Transcript is an explicit,
switchable, append-only decision:

    Fixture Source Media → Transcript Intake → Provider Result A → Raw Transcript A
                        → Provider Result B → Raw Transcript B → candidate listing
                        → select A → ready → switch to B → ready → repository validation

It proves: multiple distinct candidates; candidates are ordered by identity, **not** ranked by provider/model;
exactly one current Raw Transcript is authoritative; repeated identical selection is idempotent; switching changes
authority without deleting prior records; an unrelated Raw Transcript is rejected; readiness reflects the current
selection; validation stays healthy; and the committed golden reproduces byte-for-byte.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.current_raw_transcript_selection import (
    RawTranscriptSelectionError,
    TranscriptIntakeReadiness,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"


def _document(provider, model, ref, text):
    return build_provider_transcript_document(
        {
            "provider": provider,
            "model": model,
            "language": "ko",
            "provider_result_ref": ref,
            "segments": [
                {"start": 0.0, "end": 2.5, "text": text},
                {"start": 2.5, "end": 5.0, "text": "두 번째 구간"},
            ],
        }
    )


def run_raw_transcript_selection_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample_a = fixtures / "sample-a.bin"
    sample_b = fixtures / "sample-b.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample_a)).record
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake

        admit = compose_sqlite_provider_transcript_admission_service(connection)
        # Two distinct provider results (different provider/model, deliberately "larger" model on B) -> two Raw
        # Transcripts. Ordering must NOT follow provider name or model size.
        raw_a = admit.admit(
            intake_id=intake.identity.value,
            document=_document("fake-asr-alpha", "large", "ref-A", "알파 엔진 결과"),
        ).admission.raw_transcript_id
        raw_b = admit.admit(
            intake_id=intake.identity.value,
            document=_document("fake-asr-beta", "tiny", "ref-B", "베타 엔진 결과"),
        ).admission.raw_transcript_id

        selection = compose_sqlite_current_raw_transcript_selection_service(connection)
        candidates = selection.candidates(intake.identity.value)
        candidate_ids = [c.raw_transcript_id.value for c in candidates]

        readiness_before = selection.readiness(intake.identity.value).readiness
        select_a = selection.select(intake.identity.value, raw_a.value)
        select_a_again = selection.select(intake.identity.value, raw_a.value)
        readiness_a = selection.readiness(intake.identity.value)
        switch_b = selection.select(intake.identity.value, raw_b.value, reason="switch to B")
        readiness_b = selection.readiness(intake.identity.value)

        # A second intake's Raw Transcript may never be selected for the first intake.
        other_media = compose_sqlite_media_import_service(connection).import_media(str(sample_b)).record
        other_intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            other_media.identity.value
        ).intake
        other_raw = admit.admit(
            intake_id=other_intake.identity.value,
            document=_document("fake-asr-alpha", "large", "ref-A", "다른 인테이크"),
        ).admission.raw_transcript_id
        unrelated_rejected = False
        try:
            selection.select(intake.identity.value, other_raw.value)
        except RawTranscriptSelectionError:
            unrelated_rejected = True

        history_rows = connection.execute(
            "SELECT COUNT(*) FROM current_raw_transcript_selections "
            "WHERE transcript_source_intake_id = ?",
            (intake.identity.value,),
        ).fetchone()[0]
        connection.close()
        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "intake_id": intake.identity.value,
            "raw_a_id": raw_a.value,
            "raw_b_id": raw_b.value,
            "candidate_count": len(candidates),
            "selection_a_id": select_a.selection.identity.value,
            "selection_b_id": switch_b.selection.identity.value,
            # Behavioral checks.
            "two_distinct_candidates": len(candidate_ids) == 2 and raw_a != raw_b,
            "candidates_ordered_by_identity": candidate_ids == sorted(candidate_ids),
            "not_ready_before_selection": readiness_before == TranscriptIntakeReadiness.NOT_READY,
            "initial_selection_created": select_a.outcome.value == "created"
            and select_a.selection.sequence == 0,
            "repeated_selection_idempotent": select_a_again.outcome.value == "reused",
            "ready_after_selection": readiness_a.readiness == TranscriptIntakeReadiness.READY
            and readiness_a.current_raw_transcript_id == raw_a,
            "switch_changes_current": switch_b.outcome.value == "switched"
            and switch_b.selection.sequence == 1
            and readiness_b.current_raw_transcript_id == raw_b,
            "switch_preserves_history": history_rows == 2,
            "unrelated_raw_transcript_rejected": unrelated_rejected,
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "intake_id",
        "raw_a_id",
        "raw_b_id",
        "candidate_count",
        "selection_a_id",
        "selection_b_id",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_raw_transcript_selection_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
