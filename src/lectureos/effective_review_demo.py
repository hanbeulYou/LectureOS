"""Deterministic demonstration of Effective-Source Subtitle Review Preparation (GOAL-014).

Drives the whole slice with fake provider results, manual candidates, and explicit human decisions —
no LLM, ASR, network, or model:

    A. Raw candidate S1 (GOAL-013 path) → prepare → Review Subject R1 (exact binding, current)
    B. Prepare S1 again → R1 reused (no duplicate rows)
    C. Real Accept → Corrected Revision → select → candidate S2 → prepare → distinct R2 with
       corrected source binding and reachable Raw parent lineage
    D. Raw fallback → regenerate (reuses S1) → prepare → original R1 reused
    E. Raw R2 with byte-identical content → candidate S3 → prepare → distinct R3
       (same content ≠ same candidate ≠ same review subject)
    F. Transcript authority changes (re-select corrected, then Reject) → R1/R2 remain immutable
       historical evidence with derived stale currentness; no automatic re-preparation
    G. A structurally damaged candidate graph (isolated copy) refuses preparation explicitly
       with nothing persisted

It also proves authority isolation: no Human Decision, reviewer, legacy review record, final
selection, or export exists afterwards. The committed golden reproduces byte-for-byte.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.effective_subtitle_review_preparation import (
    CandidateGraphIntegrityError,
    ReviewSubjectCurrentness,
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
    compose_sqlite_effective_subtitle_review_preparation_service,
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


def run_effective_review_demo(media_fixtures_directory: str | None = None) -> dict:
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
        preparation = compose_sqlite_effective_subtitle_review_preparation_service(connection)

        # A/B: prepare + replay.
        s1 = generation.generate(intake_id=intake_id).candidate
        r1 = preparation.prepare_review(candidate_id=s1.identity.value)
        r1_replay = preparation.prepare_review(candidate_id=s1.identity.value)

        # C: real Human Authority path → corrected candidate → distinct subject.
        raw_segments = SQLiteRawTranscriptRepository(connection).get(
            TranscriptId(raw_1)
        ).segment_ids
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
        s2 = generation.generate(intake_id=intake_id).candidate
        r2 = preparation.prepare_review(candidate_id=s2.identity.value)

        # D: Raw round trip — S1 reused, R1 reused.
        selection.select_raw_fallback(intake_id=intake_id, reviewer="selector:kim")
        s1_again = generation.generate(intake_id=intake_id).candidate
        r1_roundtrip = preparation.prepare_review(candidate_id=s1_again.identity.value)

        # E: byte-identical content, different candidate → distinct subject.
        raw_2 = _admit_raw("B")
        raw_selection.select(intake_id, raw_2)
        s3 = generation.generate(intake_id=intake_id).candidate
        r3 = preparation.prepare_review(candidate_id=s3.identity.value)

        # F: authority changes derive staleness; subjects stay immutable; no auto re-preparation.
        raw_selection.select(intake_id, raw_1)
        selection.select_revision(revision_id=revision, reviewer="selector:kim")
        decisions.decide(candidate_id=candidate, kind="reject", reviewer="reviewer:kim")
        r1_after = preparation.get(r1.subject.identity.value)
        r2_after = preparation.get(r2.subject.identity.value)
        r2_status = preparation.status(r2_after)
        subject_rows = connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_review_subjects"
        ).fetchone()[0]
        authority_rows = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("subtitle_review_preparations", "subtitle_review_decisions",
                          "subtitle_final_subtitles", "review_items")
        }
        connection.close()

        # G: a structurally damaged candidate graph refuses preparation (isolated copy).
        damaged = Path(directory) / "damaged.sqlite3"
        import shutil

        shutil.copyfile(database, damaged)
        damage = sqlite3.connect(damaged)
        try:
            damage.execute("PRAGMA foreign_keys = OFF")
            damage.execute(
                "DELETE FROM subtitle_effective_candidate_cue_segments WHERE cue_id = "
                "(SELECT identity FROM subtitle_effective_candidate_cues "
                " WHERE candidate_id = ? AND ordinal = 0)",
                (s1.identity.value,),
            )
            damage.execute(
                "DELETE FROM subtitle_effective_candidate_cues "
                "WHERE candidate_id = ? AND ordinal = 0",
                (s1.identity.value,),
            )
            damage.commit()
        finally:
            damage.close()
        from lectureos.persistence import open_sqlite_database

        damaged_connection = open_sqlite_database(damaged)
        invalid_graph_blocked = False
        try:
            broken_preparation = compose_sqlite_effective_subtitle_review_preparation_service(
                damaged_connection
            )
            before = damaged_connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_review_subjects"
            ).fetchone()[0]
            damage_target = s1.identity.value
            try:
                broken_preparation.prepare_review(candidate_id=damage_target)
            except CandidateGraphIntegrityError:
                after = damaged_connection.execute(
                    "SELECT COUNT(*) FROM subtitle_effective_review_subjects"
                ).fetchone()[0]
                invalid_graph_blocked = after == before
        finally:
            damaged_connection.close()

        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "intake_id": intake_id,
            "candidate_s1_id": s1.identity.value,
            "candidate_s2_id": s2.identity.value,
            "candidate_s3_id": s3.identity.value,
            "review_subject_r1_id": r1.subject.identity.value,
            "review_subject_r2_id": r2.subject.identity.value,
            "review_subject_r3_id": r3.subject.identity.value,
            "review_subject_count": subject_rows,
            # Behavioral checks.
            "prepare_binds_exact_candidate": r1.outcome.value == "created"
            and r1.subject.candidate_id == s1.identity
            and r1.status.review_subject_currentness is ReviewSubjectCurrentness.CURRENT,
            "identical_replay_reuses": r1_replay.outcome.value == "reused"
            and r1_replay.subject.identity == r1.subject.identity,
            "corrected_subject_distinct_with_lineage": r2.outcome.value == "created"
            and r2.subject.identity != r1.subject.identity
            and r2.subject.candidate_id == s2.identity
            and s2.source_kind.value == "corrected_transcript_revision"
            and s2.parent_raw_transcript_id.value == raw_1,
            "raw_round_trip_reuses_subject": s1_again.identity == s1.identity
            and r1_roundtrip.outcome.value == "reused"
            and r1_roundtrip.subject.identity == r1.subject.identity,
            "same_content_different_candidate_distinct": s3.identity != s1.identity
            and r3.subject.identity != r1.subject.identity
            and r3.subject.candidate_graph_fingerprint
            != r1.subject.candidate_graph_fingerprint,
            "authority_changes_keep_subjects_immutable": r1_after == r1.subject
            and r2_after == r2.subject and subject_rows == 3,
            "staleness_is_derived_not_stored": r2_status.review_subject_currentness
            is ReviewSubjectCurrentness.STALE_DUE_TO_CANDIDATE_SOURCE
            and r2_status.candidate_source_currentness.value
            == "stale_due_to_selected_revision_inapplicability",
            "invalid_graph_blocks_preparation": invalid_graph_blocked,
            "no_authority_records_created": all(v == 0 for v in authority_rows.values()),
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "intake_id",
        "candidate_s1_id",
        "candidate_s2_id",
        "candidate_s3_id",
        "review_subject_r1_id",
        "review_subject_r2_id",
        "review_subject_r3_id",
        "review_subject_count",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_effective_review_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
