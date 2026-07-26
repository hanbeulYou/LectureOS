"""Deterministic demonstration of First Corrected Transcript Revision generation (040 §19, GOAL-010).

Drives the whole slice with fake provider results, a manual candidate, and explicit human decisions — no LLM,
ASR, network, or model:

    Fixture Source Media → Transcript Intake → Provider Result → Raw Transcript
                        → Current Raw Transcript Selection → Correction Candidate
                        → generate while Undecided (blocked) → Accept → explicit Generate → Corrected Revision
                        → replay Generate (reused) → Reject → generate (blocked) → revision survives
                        → Repository Validation

It proves (§70–§73): generation requires current Accepted authority and is explicit (acceptance alone creates
nothing); the resulting revision contains exactly the intended correction while every unaffected segment, all
timing, the Raw Transcript, the candidate, and the decision history remain unchanged; the revision is NOT
selected as current; identical replay reuses the same revision; a later Reject blocks new generation but never
deletes or invalidates the historical revision; and the committed golden reproduces byte-for-byte.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.corrected_revision_generation import (
    CandidateNotAcceptedError,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteCorrectedTranscriptRevisionRepository,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
)
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
_SOURCE_TEXT = "안녕하세요 여러부"
_CORRECTED_TEXT = "안녕하세요 여러분"
_UNAFFECTED_TEXT = "오늘 강의를 시작합니다"


def run_corrected_revision_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake.identity.value,
            document=build_provider_transcript_document(
                {"provider": "fake-asr", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.5, "text": _SOURCE_TEXT},
                              {"start": 2.5, "end": 5.0, "text": _UNAFFECTED_TEXT}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            intake.identity.value, raw.raw_transcript_id.value
        )
        raw_transcript = SQLiteRawTranscriptRepository(connection).get(raw.raw_transcript_id)
        segments = SQLiteTranscriptSegmentRepository(connection)
        target_segment = raw_transcript.segment_ids[0]
        unaffected_segment_before = segments.get(raw_transcript.segment_ids[1])

        candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake.identity.value,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw.raw_transcript_id.value, "segment_id": target_segment.value,
                 "candidate_ref": "c1", "source_type": "manual", "source_reference": "human:editor-1",
                 "proposed_text": _CORRECTED_TEXT, "source_text_snapshot": _SOURCE_TEXT,
                 "rationale": "맞춤법 교정"}
            ),
        ).candidate
        candidate_id = candidate.identity.value

        decisions = compose_sqlite_correction_candidate_decision_service(connection)
        generator = compose_sqlite_corrected_revision_generation_service(connection)

        # Undecided → generation blocked (acceptance is required and explicit).
        undecided_blocked = False
        try:
            generator.generate(candidate_id=candidate_id)
        except CandidateNotAcceptedError:
            undecided_blocked = True

        accept = decisions.decide(candidate_id=candidate_id, kind="accept", reviewer="reviewer:kim")
        # Acceptance alone creates nothing: no revision exists until the explicit generate command.
        revisions_after_accept = connection.execute(
            "SELECT COUNT(*) FROM corrected_transcript_revisions"
        ).fetchone()[0]

        first = generator.generate(candidate_id=candidate_id)
        replay = generator.generate(candidate_id=candidate_id)

        revision = SQLiteCorrectedTranscriptRevisionRepository(connection).get(first.revision.identity)
        revision_segments = [segments.get(s) for s in revision.segment_ids]
        source_segment_after = segments.get(target_segment)
        unaffected_after = segments.get(raw_transcript.segment_ids[1])

        # Later Reject: blocks new generation, never deletes/invalidates the historical revision.
        decisions.decide(candidate_id=candidate_id, kind="reject", reviewer="reviewer:kim")
        rejected_blocked = False
        try:
            generator.generate(candidate_id=candidate_id)
        except CandidateNotAcceptedError:
            rejected_blocked = True
        revision_survives = (
            SQLiteCorrectedTranscriptRevisionRepository(connection).get(first.revision.identity)
            is not None
        )
        decision_history = decisions.history(candidate_id)
        current_selection = compose_sqlite_current_raw_transcript_selection_service(connection).current(
            intake.identity.value
        )
        connection.close()
        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "candidate_id": candidate_id,
            "authorizing_decision_id": first.generation.authorizing_decision_id.value,
            "revision_id": first.revision.identity.value,
            "generation_id": first.generation.identity.value,
            "content_fingerprint": first.generation.content_fingerprint,
            "corrected_text": revision_segments[0].text,
            # Behavioral checks.
            "undecided_blocked": undecided_blocked,
            "acceptance_alone_created_nothing": revisions_after_accept == 0,
            "generation_created": first.outcome == "created",
            "correction_applied": revision_segments[0].text == _CORRECTED_TEXT
            and revision_segments[0].replaces_segment_id == target_segment,
            "timing_preserved": revision_segments[0].start == 0.0 and revision_segments[0].end == 2.5,
            "unaffected_segment_identical": revision_segments[1] == unaffected_segment_before == unaffected_after,
            "raw_transcript_unchanged": source_segment_after.text == _SOURCE_TEXT,
            "revision_not_current": revision.applicability.value == "undetermined"
            and current_selection.raw_transcript_id == raw.raw_transcript_id,
            "authorizing_decision_referenced": first.generation.authorizing_decision_id
            == accept.decision.identity,
            "replay_reused": replay.outcome == "reused"
            and replay.revision.identity == first.revision.identity,
            "later_reject_blocks_new_generation": rejected_blocked,
            "revision_survives_reject": revision_survives,
            "decision_history_intact": [d.kind.value for d in decision_history] == ["accept", "reject"],
            "repository_validates_healthy": validation.health.value == "healthy" and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "candidate_id",
        "authorizing_decision_id",
        "revision_id",
        "generation_id",
        "content_fingerprint",
        "corrected_text",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_corrected_revision_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
