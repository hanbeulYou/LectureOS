"""Deterministic demonstration of Effective-Transcript Subtitle Candidate generation (041 §15, GOAL-013).

Drives the whole slice with fake provider results, manual candidates, and explicit human decisions —
no LLM, ASR, network, or model:

    A. Raw R1 selected → generate S1 (one passthrough cue per ordered Raw segment, exact lineage)
    B. Generate again → reuse S1 (no duplicate candidate/cue/lineage rows)
    C. Candidate → Accept (real Human Authority) → Corrected Revision C1 → select C1
       → generate S2 (distinct; corrected text; replacement + Raw parent lineage)
    D. Raw fallback → generate → reuse the original S1 (authority round trip)
    E. Raw R2 admitted with identical content/timing → select → fallback-consume → generate
       → distinct candidate (same content ≠ same source)
    F. Re-select C1 → Reject the correction candidate → generate fails explicitly
       (INAPPLICABLE, no silent fallback, no partial candidate); S1/S2 remain immutable and
       derived-stale/current facts stay truthful → Repository Validation stays healthy

It also proves legacy isolation: no rows are written to the legacy `subtitle_candidates` family and
no review/decision/final-selection/export record is created. The committed golden reproduces
byte-for-byte.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.effective_subtitle_generation import (
    EffectiveSubtitleGenerationError,
)
from lectureos.application.effective_transcript_consumption import (
    ConsumptionCurrentness,
    InapplicableSelectedRevisionError,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteRawTranscriptRepository,
    initialize_sqlite_database,
)
from lectureos.transcript.identities import TranscriptId
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
_SOURCE_TEXTS = ("안녕하세요 여러부", "오늘의 강의입니다")


def run_effective_subtitle_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        intake_id = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        provider = compose_sqlite_provider_transcript_admission_service(connection)
        raw_selection = compose_sqlite_current_raw_transcript_selection_service(connection)

        def _admit_raw(ref: str) -> str:
            return provider.admit(
                intake_id=intake_id,
                document=build_provider_transcript_document(
                    {"provider": "fake-asr", "model": "tiny", "language": "ko",
                     "provider_result_ref": ref,
                     "segments": [
                         {"start": float(i), "end": float(i) + 1.0, "text": text}
                         for i, text in enumerate(_SOURCE_TEXTS)
                     ]}
                ),
            ).admission.raw_transcript_id.value

        raw_1 = _admit_raw("A")
        raw_selection.select(intake_id, raw_1)
        generation = compose_sqlite_effective_subtitle_generation_service(connection)

        # A: Raw generation with exact passthrough lineage.
        s1 = generation.generate(intake_id=intake_id)
        raw_segments = SQLiteRawTranscriptRepository(connection).get(
            TranscriptId(raw_1)
        ).segment_ids

        # B: identical replay.
        s1_replay = generation.generate(intake_id=intake_id)

        # C: Accept → Corrected Revision → select → generate corrected candidate.
        candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake_id,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw_1, "segment_id": raw_segments[0].value,
                 "candidate_ref": "c1", "source_type": "manual",
                 "source_reference": "human:editor-1",
                 "proposed_text": "안녕하세요 여러분", "source_text_snapshot": _SOURCE_TEXTS[0],
                 "rationale": "맞춤법 교정"}
            ),
        ).candidate.identity.value
        decisions = compose_sqlite_correction_candidate_decision_service(connection)
        decisions.decide(candidate_id=candidate, kind="accept", reviewer="reviewer:kim")
        revision = compose_sqlite_corrected_revision_generation_service(connection).generate(
            candidate_id=candidate
        ).revision.identity.value
        selection = compose_sqlite_corrected_revision_selection_service(connection)
        selection.select_revision(revision_id=revision, reviewer="selector:kim")
        s2 = generation.generate(intake_id=intake_id)
        s2_cues = s2.cues
        corrected_segment = s2_cues[0].source_segment_ids[0]
        replacement_lineage_ok = False
        from lectureos.persistence import SQLiteTranscriptSegmentRepository

        seg_record = SQLiteTranscriptSegmentRepository(connection).get(corrected_segment)
        replacement_lineage_ok = (
            seg_record is not None
            and seg_record.replaces_segment_id == raw_segments[0]
            and seg_record.confidence is None  # human-corrected text carries no fabricated confidence
        )

        # D: Raw round trip reuses S1.
        selection.select_raw_fallback(intake_id=intake_id, reviewer="selector:kim")
        s1_roundtrip = generation.generate(intake_id=intake_id)

        # E: same content, different exact source entity.
        raw_2 = _admit_raw("B")  # identical segments/timings, distinct immutable entity
        raw_selection.select(intake_id, raw_2)
        s3 = generation.generate(intake_id=intake_id)

        # F: selected-but-inapplicable blocks generation explicitly.
        raw_selection.select(intake_id, raw_1)  # C1's parent current again
        selection.select_revision(revision_id=revision, reviewer="selector:kim")
        decisions.decide(candidate_id=candidate, kind="reject", reviewer="reviewer:kim")
        inapplicable_blocked = False
        try:
            generation.generate(intake_id=intake_id)
        except InapplicableSelectedRevisionError:
            inapplicable_blocked = True
        except EffectiveSubtitleGenerationError:
            inapplicable_blocked = False

        candidates_after = generation.list_for_intake(intake_id)
        s1_after = next(
            c for c in candidates_after if c.identity == s1.candidate.identity
        )
        s2_after = next(
            c for c in candidates_after if c.identity == s2.candidate.identity
        )
        s2_currentness = generation.currentness(s2_after)
        legacy_rows = connection.execute(
            "SELECT COUNT(*) FROM subtitle_candidates"
        ).fetchone()[0]
        review_rows = connection.execute(
            "SELECT COUNT(*) FROM subtitle_review_decisions"
        ).fetchone()[0]
        final_rows = connection.execute(
            "SELECT COUNT(*) FROM subtitle_final_subtitles"
        ).fetchone()[0]
        connection.close()
        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "intake_id": intake_id,
            "raw_1_id": raw_1,
            "raw_2_id": raw_2,
            "revision_id": revision,
            "candidate_s1_id": s1.candidate.identity.value,
            "candidate_s2_id": s2.candidate.identity.value,
            "candidate_s3_id": s3.candidate.identity.value,
            "candidate_count": len(candidates_after),
            # Behavioral checks.
            "raw_generation_passthrough": s1.outcome.value == "created"
            and s1.candidate.source_kind.value == "raw_transcript"
            and s1.candidate.source_transcript_identity == raw_1
            and [c.text for c in s1.cues] == list(_SOURCE_TEXTS)
            and [c.ordinal for c in s1.cues] == [0, 1]
            and [(c.start, c.end) for c in s1.cues] == [(0.0, 1.0), (1.0, 2.0)]
            and [c.source_segment_ids[0] for c in s1.cues] == list(raw_segments),
            "identical_replay_reuses": s1_replay.outcome.value == "reused"
            and s1_replay.candidate.identity == s1.candidate.identity,
            "corrected_generation_distinct": s2.outcome.value == "created"
            and s2.candidate.identity != s1.candidate.identity
            and s2.candidate.source_kind.value == "corrected_transcript_revision"
            and s2.candidate.source_transcript_identity == revision
            and s2.candidate.parent_raw_transcript_id.value == raw_1,
            "corrected_cue_uses_corrected_text": s2_cues[0].text == "안녕하세요 여러분"
            and s2_cues[1].text == _SOURCE_TEXTS[1]
            and (s2_cues[0].start, s2_cues[0].end) == (0.0, 1.0),
            "replacement_lineage_preserved": replacement_lineage_ok,
            "raw_round_trip_reuses_s1": s1_roundtrip.outcome.value == "reused"
            and s1_roundtrip.candidate.identity == s1.candidate.identity,
            "same_content_different_source_distinct": s3.outcome.value == "created"
            and s3.candidate.source_transcript_identity == raw_2
            and raw_2 != raw_1
            and s3.candidate.identity != s1.candidate.identity
            and s3.candidate.source_snapshot_fingerprint
            == s1.candidate.source_snapshot_fingerprint,
            "inapplicable_blocks_generation": inapplicable_blocked,
            "candidates_immutable_after_authority_changes": s1_after == s1.candidate
            and s2_after == s2.candidate and len(candidates_after) == 3,
            "currentness_is_derived": s2_currentness
            is ConsumptionCurrentness.STALE_DUE_TO_SELECTED_REVISION_INAPPLICABILITY,
            "legacy_pipeline_untouched": legacy_rows == 0 and review_rows == 0
            and final_rows == 0,
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "intake_id",
        "raw_1_id",
        "raw_2_id",
        "revision_id",
        "candidate_s1_id",
        "candidate_s2_id",
        "candidate_s3_id",
        "candidate_count",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_effective_subtitle_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
