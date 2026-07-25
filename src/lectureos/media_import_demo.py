"""Deterministic mock demonstration of local Media Import (045 §1).

Imports small committed binary fixtures (arbitrary media-like bytes — **not** playable video) into a throwaway
SQLite repository and proves the confirmed first-slice behavior with no ffmpeg, network, or platform codecs:

- first import of a fixture creates a canonical, content-addressed Source Media record;
- re-importing identical bytes is idempotent (reused);
- identical bytes under a different filename resolve the same record (reused);
- changed bytes at a reused path create a new record;
- the resulting repository passes read-only repository validation;
- the source bytes are never modified.

Media identity and fingerprint are content-derived, so the demo's identity/fingerprint facts are byte
deterministic; only observed source paths are environment specific.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.composition import compose_sqlite_media_import_service
from lectureos.persistence import initialize_sqlite_database
from lectureos.validation import validate_database

_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"


def run_media_import_demo(fixtures_directory: str | None = None) -> dict:
    fixtures = Path(fixtures_directory) if fixtures_directory else _FIXTURES
    sample_a = fixtures / "sample-a.bin"
    sample_a_copy = fixtures / "sample-a-copy.bin"
    sample_b = fixtures / "sample-b.bin"
    a_bytes_before = sample_a.read_bytes()

    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        database = base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)
        service = compose_sqlite_media_import_service(connection)

        first = service.import_media(str(sample_a))
        repeated = service.import_media(str(sample_a))
        same_content_other_name = service.import_media(str(sample_a_copy))
        different_content = service.import_media(str(sample_b))

        # Changed content at a reused path: import fresh content, overwrite the same path, re-import.
        reused_path = base / "reused-path.bin"
        reused_path.write_bytes(b"changed-content-demo:first-revision\n")
        reused_first = service.import_media(str(reused_path))
        reused_path.write_bytes(b"changed-content-demo:second-revision\n")
        reused_changed = service.import_media(str(reused_path))

        distinct_media = connection.execute(
            "SELECT COUNT(*) FROM source_media"
        ).fetchone()[0]
        connection.close()

        validation = validate_database(str(database))

        summary = {
            # Deterministic, content-addressed facts (golden).
            "sample_a_identity": first.record.identity.value,
            "sample_a_fingerprint": (
                f"{first.record.fingerprint_algorithm}:{first.record.fingerprint_digest}"
            ),
            "sample_a_byte_length": first.record.byte_length,
            "sample_b_identity": different_content.record.identity.value,
            "sample_b_fingerprint": (
                f"{different_content.record.fingerprint_algorithm}:"
                f"{different_content.record.fingerprint_digest}"
            ),
            "sample_b_byte_length": different_content.record.byte_length,
            "distinct_media_records": distinct_media,
            # Behavioral checks.
            "first_import_created": first.created,
            "repeated_import_reused": not repeated.created
            and repeated.record.identity == first.record.identity,
            "same_content_other_name_reused": not same_content_other_name.created
            and same_content_other_name.record.identity == first.record.identity,
            "different_content_created": different_content.created
            and different_content.record.identity != first.record.identity,
            "changed_content_same_path_new_record": reused_first.created
            and reused_changed.created
            and reused_changed.record.identity != reused_first.record.identity,
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
            "source_bytes_unchanged": sample_a.read_bytes() == a_bytes_before,
        }
        return summary


def _golden(summary: dict) -> dict:
    # The deterministic, environment-independent subset committed as a golden fixture.
    keys = (
        "sample_a_identity",
        "sample_a_fingerprint",
        "sample_a_byte_length",
        "sample_b_identity",
        "sample_b_fingerprint",
        "sample_b_byte_length",
        "distinct_media_records",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_media_import_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
