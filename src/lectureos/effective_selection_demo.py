"""Deterministic demonstration of Effective Subtitle Final Selection (GOAL-016).

Drives the whole slice with fake provider results, manual candidates, and explicit human actors —
no LLM, ASR, network, or model:

    A. Raw candidate → subject → Accept → eligibility(yes) → explicit select → current + applicable
    B. Exact replay → reused (no duplicate authority row)
    C/D. Reject and Modify current decisions → ineligible, selection refused, nothing persisted
    E. Superseded Accept (accept → reject) → ineligible (old Accept never grants eligibility)
    F. Eligible candidate B selected → append; B current, A superseded; both immutable
    G. Transcript authority changes → selections remain immutable history; applicability derives
       (supporting decision stale) — no automatic reselection
    H. Accept → Reject → new Accept (new decision sequence) → explicit re-select of the same
       subject appends a NEW selection bound to the NEW supporting Accept (changed authority
       lineage never silently reuses the old selection)
    I. Byte-identical cue content under distinct candidates → distinct selection identities
    J. Damaged candidate graph (isolated copy) → selection refused, nothing persisted
    K. Downstream isolation: no export rows, no files, no legacy final-selection rows

The committed golden reproduces byte-for-byte.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.effective_subtitle_final_selection import (
    EffectiveSubtitleFinalSelectionError,
    ReviewSubjectNotEligibleError,
    SelectionApplicability,
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
    compose_sqlite_effective_subtitle_final_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteRawTranscriptRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.transcript.identities import TranscriptId
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
_SOURCE_TEXTS = ("안녕하세요 여러부", "오늘의 강의입니다")


def run_effective_selection_demo(media_fixtures_directory: str | None = None) -> dict:
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
        decisions = compose_sqlite_effective_subtitle_review_decision_service(connection)
        selection = compose_sqlite_effective_subtitle_final_selection_service(connection)

        # A/B: accept → eligible → select → replay.
        s1 = generation.generate(intake_id=intake_id).candidate
        r1 = preparation.prepare_review(candidate_id=s1.identity.value).subject
        accept_1 = decisions.decide(
            review_subject_id=r1.identity.value, kind="accept", reviewer="reviewer:kim"
        ).decision
        eligibility_before = selection.eligibility(r1.identity.value)
        f1 = selection.select_final(
            review_subject_id=r1.identity.value, selector="selector:park"
        )
        f1_replay = selection.select_final(
            review_subject_id=r1.identity.value, selector="selector:park"
        )
        f1_applicability = selection.applicability(f1.selection)

        # C/D/E: reject, modify, and superseded accept all block NEW selection.
        decisions.decide(
            review_subject_id=r1.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        reject_blocked = modify_blocked = superseded_accept_blocked = False
        try:
            selection.select_final(review_subject_id=r1.identity.value, selector="selector:park")
        except ReviewSubjectNotEligibleError:
            reject_blocked = True
        superseded_accept_blocked = reject_blocked  # the old Accept never re-grants eligibility
        decisions.decide(
            review_subject_id=r1.identity.value, kind="modify", reviewer="reviewer:kim"
        )
        try:
            selection.select_final(review_subject_id=r1.identity.value, selector="selector:park")
        except ReviewSubjectNotEligibleError:
            modify_blocked = True
        rows_after_blocks = connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_final_selections"
        ).fetchone()[0]

        # H: a NEW Accept (new decision sequence) → explicit re-select appends with NEW lineage.
        accept_2 = decisions.decide(
            review_subject_id=r1.identity.value, kind="accept", reviewer="reviewer:kim"
        ).decision
        f2 = selection.select_final(
            review_subject_id=r1.identity.value, selector="selector:park"
        )

        # F/I: a distinct candidate with byte-identical content → eligible → select → append.
        raw_2 = _admit_raw("B")
        raw_selection.select(intake_id, raw_2)
        compose_sqlite_corrected_revision_selection_service(connection).select_raw_fallback(
            intake_id=intake_id, reviewer="selector:kim"
        )
        s2 = generation.generate(intake_id=intake_id).candidate
        r2 = preparation.prepare_review(candidate_id=s2.identity.value).subject
        decisions.decide(
            review_subject_id=r2.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        f3 = selection.select_final(
            review_subject_id=r2.identity.value, selector="selector:park"
        )
        history = selection.history(intake_id)
        current = selection.current(intake_id)
        f2_after = selection.applicability(f2.selection)
        f1_final = selection.get(f1.selection.identity.value)

        # G: authority change → applicability derives; history immutable; no auto reselection.
        raw_selection.select(intake_id, raw_1)
        f3_after_switch = selection.applicability(f3.selection)
        history_after = selection.history(intake_id)

        selection_rows = connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_final_selections"
        ).fetchone()[0]
        downstream_rows = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("subtitle_final_subtitles", "subtitle_srt_artifacts",
                          "subtitle_srt_materializations", "subtitle_review_decisions")
        }
        connection.close()

        # J: damaged candidate graph refuses selection (isolated copy).
        import shutil

        damaged = Path(directory) / "damaged.sqlite3"
        shutil.copyfile(database, damaged)
        damage = sqlite3.connect(damaged)
        try:
            damage.execute("PRAGMA foreign_keys = OFF")
            damage.execute(
                "DELETE FROM subtitle_effective_candidate_cue_segments WHERE cue_id = "
                "(SELECT identity FROM subtitle_effective_candidate_cues "
                " WHERE candidate_id = ? AND ordinal = 0)",
                (s2.identity.value,),
            )
            damage.execute(
                "DELETE FROM subtitle_effective_candidate_cues "
                "WHERE candidate_id = ? AND ordinal = 0",
                (s2.identity.value,),
            )
            damage.commit()
        finally:
            damage.close()
        damaged_connection = open_sqlite_database(damaged)
        invalid_graph_blocked = False
        try:
            broken = compose_sqlite_effective_subtitle_final_selection_service(
                damaged_connection
            )
            before = damaged_connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_final_selections"
            ).fetchone()[0]
            try:
                broken.select_final(
                    review_subject_id=r2.identity.value, selector="selector:park"
                )
            except EffectiveSubtitleFinalSelectionError:
                after = damaged_connection.execute(
                    "SELECT COUNT(*) FROM subtitle_effective_final_selections"
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
            "selection_f1_id": f1.selection.identity.value,
            "selection_f2_id": f2.selection.identity.value,
            "selection_f3_id": f3.selection.identity.value,
            "selection_count": selection_rows,
            # Behavioral checks.
            "eligible_accept_selects_current_applicable": eligibility_before.eligible
            and f1.outcome.value == "recorded"
            and f1.selection.candidate_id == s1.identity
            and f1.selection.review_subject_id == r1.identity
            and f1.selection.supporting_decision_id == accept_1.identity
            and f1.selection.selector.value == "selector:park"
            and f1_applicability is SelectionApplicability.APPLICABLE,
            "exact_replay_reused": f1_replay.outcome.value == "reused"
            and f1_replay.selection.identity == f1.selection.identity,
            "reject_and_modify_and_superseded_accept_block": reject_blocked
            and modify_blocked and superseded_accept_blocked
            and rows_after_blocks == 1,
            "new_accept_appends_new_lineage": f2.outcome.value == "changed"
            and f2.selection.identity != f1.selection.identity
            and f2.selection.supporting_decision_id == accept_2.identity
            and accept_2.identity != accept_1.identity,
            "changed_candidate_appends_and_supersedes": f3.outcome.value == "changed"
            and current is not None
            and current.identity == f3.selection.identity
            and f2_after is SelectionApplicability.SUPERSEDED
            and [s.sequence for s in history] == [0, 1, 2]
            and f1_final == f1.selection,
            "same_content_distinct_candidates_distinct_selections": s2.identity != s1.identity
            and f3.selection.identity != f1.selection.identity,
            "authority_change_derives_not_mutates": f3_after_switch
            is not SelectionApplicability.APPLICABLE
            and [s.identity for s in history_after] == [s.identity for s in history],
            "invalid_graph_blocks_selection": invalid_graph_blocked,
            "no_export_or_legacy_records": all(v == 0 for v in downstream_rows.values()),
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "intake_id",
        "candidate_s1_id",
        "candidate_s2_id",
        "selection_f1_id",
        "selection_f2_id",
        "selection_f3_id",
        "selection_count",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_effective_selection_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
