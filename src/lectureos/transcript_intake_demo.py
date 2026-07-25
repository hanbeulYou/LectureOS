"""Deterministic no-decoding demonstration of Source Media transcription intake eligibility (040 §13).

Reuses the committed media-import fixtures (arbitrary media-like bytes — **not** playable video with usable
audio) to prove the confirmed first-slice behavior with no ffmpeg, decoding, network, or transcription:

    Fixture bytes → Media Import → Persisted SourceMedia → Transcript Intake Eligibility → Intake result
                 → Repository Validation

It proves: an imported Source Media can be admitted; repeated admission is idempotent; a missing Source Media is
rejected; a malformed Source Media identity is rejected; no transcript content or execution result is created;
the repository validates healthy; and the intake identities are content-derived (byte deterministic).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.transcript_source_intake import TranscriptSourceIntakeError
from lectureos.composition import (
    compose_sqlite_media_import_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteSourceMediaRepository,
    initialize_sqlite_database,
)
from lectureos.validation import validate_database

_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
# Transcript-side tables that must remain empty — admission produces no transcript content or execution result.
_TRANSCRIPT_CONTENT_TABLES = (
    "provider_transcript_results",
    "raw_transcripts",
    "transcript_segments",
    "corrected_transcript_revisions",
)


def run_transcript_intake_demo(fixtures_directory: str | None = None) -> dict:
    fixtures = Path(fixtures_directory) if fixtures_directory else _FIXTURES
    sample_a = fixtures / "sample-a.bin"
    sample_b = fixtures / "sample-b.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media_service = compose_sqlite_media_import_service(connection)
        media_a = media_service.import_media(str(sample_a)).record
        media_b = media_service.import_media(str(sample_b)).record
        media_a_before = SQLiteSourceMediaRepository(connection).get(media_a.identity)

        intake = compose_sqlite_transcript_source_intake_service(connection)
        first = intake.admit(media_a.identity.value)
        repeated = intake.admit(media_a.identity.value)
        other = intake.admit(media_b.identity.value)

        missing_rejected = False
        try:
            intake.admit("sha256:" + "0" * 64)
        except TranscriptSourceIntakeError:
            missing_rejected = True

        malformed_rejected = False
        try:
            intake.admit("not-a-canonical-media-id")
        except TranscriptSourceIntakeError:
            malformed_rejected = True

        distinct_intakes = connection.execute(
            "SELECT COUNT(*) FROM transcript_source_intakes"
        ).fetchone()[0]
        no_transcript_content = all(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
            for table in _TRANSCRIPT_CONTENT_TABLES
        )
        source_media_unmutated = (
            SQLiteSourceMediaRepository(connection).get(media_a.identity) == media_a_before
        )
        connection.close()

        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "sample_a_media_id": media_a.identity.value,
            "sample_a_intake_id": first.intake.identity.value,
            "sample_b_media_id": media_b.identity.value,
            "sample_b_intake_id": other.intake.identity.value,
            "distinct_intakes": distinct_intakes,
            # Behavioral checks.
            "first_admission_created": first.created,
            "repeated_admission_reused": not repeated.created
            and repeated.intake.identity == first.intake.identity,
            "distinct_media_distinct_intake": other.created
            and other.intake.identity != first.intake.identity,
            "missing_source_media_rejected": missing_rejected,
            "malformed_identity_rejected": malformed_rejected,
            "no_transcript_content_created": no_transcript_content,
            "source_media_unmutated": source_media_unmutated,
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "sample_a_media_id",
        "sample_a_intake_id",
        "sample_b_media_id",
        "sample_b_intake_id",
        "distinct_intakes",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_transcript_intake_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
