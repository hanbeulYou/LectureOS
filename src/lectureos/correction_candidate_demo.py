"""Deterministic demonstration of Transcript Correction Candidate Admission (040 §17).

Drives the whole slice with fake (supplied) provider results and manual candidates — no LLM, ASR, network, or
model — proving that proposed corrections are recorded as immutable suggestions against the current Raw Transcript
segment without ever being applied:

    Fixture Source Media → Transcript Intake → Provider Result → Raw Transcript
                        → Current Raw Transcript Selection
                        → Candidate A for Segment 1 → replay A → Candidate B for Segment 1
                        → candidate listing → switch current Raw Transcript
                        → historical candidates preserved but not applicable → Repository Validation

It proves: readiness is required; a candidate targets one immutable segment; source text is unchanged; replay is
idempotent; multiple candidates coexist; no candidate is ranked or applied; switching the current Raw Transcript
preserves historical candidates (now not applicable); unrelated (not-current) and stale (snapshot mismatch)
admissions are rejected; validation stays healthy; and the committed golden reproduces byte-for-byte.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    CorrectionCandidateAdmissionError,
    RawTranscriptNotCurrentError,
    SourceTextMismatchError,
    build_correction_candidate_input,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_correction_candidate_admission_service,
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
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"

_SEGMENT_TEXT = "안녕하세요 여러부"  # deliberately misspelled source; candidates propose the fix


def _provider_document(ref, model, first_text):
    return build_provider_transcript_document(
        {
            "provider": "fake-asr",
            "model": model,
            "language": "ko",
            "provider_result_ref": ref,
            "segments": [
                {"start": 0.0, "end": 2.5, "text": first_text},
                {"start": 2.5, "end": 5.0, "text": "오늘 강의를 시작합니다"},
            ],
        }
    )


def run_correction_candidate_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake
        admit = compose_sqlite_provider_transcript_admission_service(connection)
        raw = admit.admit(
            intake_id=intake.identity.value,
            document=_provider_document("A", "tiny", _SEGMENT_TEXT),
        ).admission
        raw_transcript = SQLiteRawTranscriptRepository(connection).get(raw.raw_transcript_id)
        segment_id = raw_transcript.segment_ids[0]
        segment_text_before = SQLiteTranscriptSegmentRepository(connection).get(segment_id).text

        candidates = compose_sqlite_correction_candidate_admission_service(connection)

        def _candidate(ref, proposed, snapshot=segment_text_before):
            return build_correction_candidate_input(
                {
                    "raw_transcript_id": raw.raw_transcript_id.value,
                    "segment_id": segment_id.value,
                    "candidate_ref": ref,
                    "source_type": "manual",
                    "source_reference": "human:editor-1",
                    "proposed_text": proposed,
                    "source_text_snapshot": snapshot,
                    "rationale": "spelling fix",
                }
            )

        # Readiness required: admission before selection is rejected.
        not_ready_rejected = False
        try:
            candidates.admit(intake_id=intake.identity.value, candidate=_candidate("c1", "안녕하세요 여러분"))
        except CorrectionCandidateAdmissionError:
            not_ready_rejected = True

        selection = compose_sqlite_current_raw_transcript_selection_service(connection)
        selection.select(intake.identity.value, raw.raw_transcript_id.value)

        first = candidates.admit(intake_id=intake.identity.value, candidate=_candidate("c1", "안녕하세요 여러분"))
        replay = candidates.admit(intake_id=intake.identity.value, candidate=_candidate("c1", "안녕하세요 여러분"))
        second = candidates.admit(intake_id=intake.identity.value, candidate=_candidate("c2", "안녕하세요, 여러분!"))

        # Stale snapshot is rejected.
        stale_rejected = False
        try:
            candidates.admit(intake_id=intake.identity.value, candidate=_candidate("c3", "x", snapshot="WRONG"))
        except SourceTextMismatchError:
            stale_rejected = True

        listed = candidates.candidates(intake.identity.value)
        segment_text_after = SQLiteTranscriptSegmentRepository(connection).get(segment_id).text

        # Switch the current Raw Transcript: existing candidates remain but become not-applicable.
        raw_b = admit.admit(
            intake_id=intake.identity.value,
            document=_provider_document("B", "large", "완전히 다른 인식"),
        ).admission
        selection.select(intake.identity.value, raw_b.raw_transcript_id.value)
        after_switch = candidates.candidates(intake.identity.value)

        # Admitting against the now-superseded Raw Transcript is rejected (not current).
        not_current_rejected = False
        try:
            candidates.admit(intake_id=intake.identity.value, candidate=_candidate("c4", "다른 제안"))
        except RawTranscriptNotCurrentError:
            not_current_rejected = True

        admission_count = connection.execute(
            "SELECT COUNT(*) FROM correction_candidate_admissions"
        ).fetchone()[0]
        connection.close()
        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "intake_id": intake.identity.value,
            "raw_transcript_id": raw.raw_transcript_id.value,
            "segment_id": segment_id.value,
            "candidate_a_id": first.candidate.identity.value,
            "candidate_b_id": second.candidate.identity.value,
            "candidate_count": admission_count,
            # Behavioral checks.
            "not_ready_rejected": not_ready_rejected,
            "candidate_admitted": first.created,
            "raw_text_unchanged": segment_text_before == segment_text_after == _SEGMENT_TEXT,
            "replay_idempotent": not replay.created
            and replay.candidate.identity == first.candidate.identity,
            "two_distinct_candidates": second.created
            and second.candidate.identity != first.candidate.identity,
            "candidates_all_applicable_before_switch": len(listed) == 2
            and all(v.applicable_to_current_selection for v in listed),
            "candidates_preserved_after_switch": len(after_switch) == 2,
            "candidates_not_applicable_after_switch": all(
                not v.applicable_to_current_selection for v in after_switch
            ),
            "stale_rejected": stale_rejected,
            "not_current_rejected": not_current_rejected,
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "intake_id",
        "raw_transcript_id",
        "segment_id",
        "candidate_a_id",
        "candidate_b_id",
        "candidate_count",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_correction_candidate_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
