"""Shared released-chain fixture for the Human Timing Correction tests (040 §17/§18/§19, PATCH-0047).

Builds a real repository through the released services only — media import, intake, provider
admission, current Raw Transcript selection — so every timing-correction test runs against genuine
lineage rather than a hand-built database.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
)

MEDIA_FIXTURES = (
    Path(__file__).resolve().parents[1] / "examples" / "media-import" / "fixtures"
)

# Three timed segments with real gaps, so neighbour overlap has something to be judged against.
SEGMENTS = (
    {"start": 0.0, "end": 2.5, "text": "첫 문장"},
    {"start": 10.0, "end": 20.0, "text": "둘째 문장"},
    {"start": 25.0, "end": 30.0, "text": "셋째 문장"},
)


class TimingCorrectionFixture:
    """A released-chain repository with one intake, one current Raw Transcript, and three segments."""

    def __init__(self, directory: str, segments=SEGMENTS, provider_result_ref: str = "A") -> None:
        self.root = Path(directory)
        self.database_path = self.root / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)

        media = (
            compose_sqlite_media_import_service(self.connection)
            .import_media(str(MEDIA_FIXTURES / "sample-a.bin"))
            .record
        )
        self.intake_id = (
            compose_sqlite_transcript_source_intake_service(self.connection)
            .admit(media.identity.value)
            .intake.identity.value
        )
        admission = compose_sqlite_provider_transcript_admission_service(
            self.connection
        ).admit(
            intake_id=self.intake_id,
            document=build_provider_transcript_document(
                {
                    "provider": "fake-asr",
                    "model": "tiny",
                    "language": "ko",
                    "provider_result_ref": provider_result_ref,
                    "segments": [dict(segment) for segment in segments],
                }
            ),
        ).admission
        self.raw_transcript_id = admission.raw_transcript_id.value
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.intake_id, self.raw_transcript_id
        )
        self.raw_transcript = SQLiteRawTranscriptRepository(self.connection).get(
            admission.raw_transcript_id
        )
        self.segments = tuple(
            SQLiteTranscriptSegmentRepository(self.connection).get(segment_id)
            for segment_id in self.raw_transcript.segment_ids
        )
        # The middle segment: it has a neighbour on both sides.
        self.target = self.segments[1]

    def segment(self, identity):
        return SQLiteTranscriptSegmentRepository(self.connection).get(identity)

    def proposal(self, **overrides) -> dict:
        """A valid human-authored proposal against the target segment, before any override."""

        payload = {
            "raw_transcript_id": self.raw_transcript_id,
            "segment_id": self.target.identity.value,
            "candidate_ref": "t1",
            "author": "human:editor-1",
            "source_start_snapshot": self.target.start,
            "source_end_snapshot": self.target.end,
            "proposed_start": 18.0,
            "proposed_end": 24.0,
            "rationale": "발화가 18초에 시작한다",
        }
        payload.update(overrides)
        return payload

    def close(self) -> None:
        self.connection.close()


def temporary_fixture(**kwargs):
    """A ``(TemporaryDirectory, TimingCorrectionFixture)`` pair the caller owns and closes."""

    directory = tempfile.TemporaryDirectory()
    return directory, TimingCorrectionFixture(directory.name, **kwargs)
