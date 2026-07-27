"""Deterministic demonstration of Human Decisions over Effective Review Subjects (GOAL-015).

Drives the whole slice with fake provider results, manual candidates, and explicit human actors —
no LLM, ASR, network, or model:

    A. Raw candidate → review subject → explicit accept → current + applicable
    B. Identical request again → reused idempotently (no duplicate authority row)
    C. Same intent by another actor while authority already matches → reused
       (GOAL-009's released repeated-intent rule: authority is a state, not a ledger)
    D. Corrected candidate → subject → explicit reject → reject is current AND applicable;
       candidate/cue rows unchanged
    E. Explicit modify → recorded as authority only (no cue edit, no replacement candidate,
       no revision, no final selection)
    F. Changed judgment appends: reject → accept supersedes; both immutable in history;
       current derives as the highest sequence (never latest-row)
    G. Transcript authority changes → decisions remain valid history; applicability derives
       stale; no automatic new decision
    H. Byte-identical cue content under distinct subjects → distinct decision identities
    I. A damaged candidate graph (isolated copy) refuses new decisions with nothing persisted

It also proves downstream isolation: no legacy decision/review/final-selection/export rows exist
afterwards. The committed golden reproduces byte-for-byte.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.effective_subtitle_review_decision import (
    DecisionApplicability,
    DecisionSubjectIntegrityError,
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


def run_effective_decision_demo(media_fixtures_directory: str | None = None) -> dict:
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

        # A/B/C: accept, idempotent replay, repeated intent by another actor.
        s1 = generation.generate(intake_id=intake_id).candidate
        r1 = preparation.prepare_review(candidate_id=s1.identity.value).subject
        d1 = decisions.decide(
            review_subject_id=r1.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        d1_replay = decisions.decide(
            review_subject_id=r1.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        d1_other_actor = decisions.decide(
            review_subject_id=r1.identity.value, kind="accept", reviewer="reviewer:lee"
        )
        d1_applicability = decisions.applicability(d1.decision)

        # D/E/F: corrected subject — reject, modify, supersession chain.
        raw_segments = SQLiteRawTranscriptRepository(connection).get(
            TranscriptId(raw_1)
        ).segment_ids
        correction = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake_id,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw_1, "segment_id": raw_segments[0].value,
                 "candidate_ref": "c1", "source_type": "manual",
                 "source_reference": "human:editor-1",
                 "proposed_text": "안녕하세요 여러분", "source_text_snapshot": _SOURCE_TEXTS[0],
                 "rationale": "맞춤법 교정"}
            ),
        ).candidate.identity.value
        human = compose_sqlite_correction_candidate_decision_service(connection)
        human.decide(candidate_id=correction, kind="accept", reviewer="reviewer:kim")
        revision = compose_sqlite_corrected_revision_generation_service(connection).generate(
            candidate_id=correction
        ).revision.identity.value
        selection = compose_sqlite_corrected_revision_selection_service(connection)
        selection.select_revision(revision_id=revision, reviewer="selector:kim")
        s2 = generation.generate(intake_id=intake_id).candidate
        r2 = preparation.prepare_review(candidate_id=s2.identity.value).subject
        cue_texts_before = [c.text for c in generation.cues(s2.identity.value)]

        d2_reject = decisions.decide(
            review_subject_id=r2.identity.value, kind="reject", reviewer="reviewer:kim"
        )
        reject_applicable = decisions.applicability(d2_reject.decision)
        d2_modify = decisions.decide(
            review_subject_id=r2.identity.value, kind="modify", reviewer="reviewer:kim"
        )
        modify_applicable = decisions.applicability(d2_modify.decision)
        d2_accept = decisions.decide(
            review_subject_id=r2.identity.value, kind="accept", reviewer="reviewer:park"
        )
        r2_history = decisions.history(r2.identity.value)
        r2_current = decisions.current(r2.identity.value)
        reject_after = decisions.applicability(d2_reject.decision)
        cue_texts_after = [c.text for c in generation.cues(s2.identity.value)]
        candidate_count = connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_candidates"
        ).fetchone()[0]

        # G: authority changes derive staleness; decisions stay immutable; no auto decision.
        human.decide(candidate_id=correction, kind="reject", reviewer="reviewer:kim")
        d2_accept_after_reject = decisions.applicability(d2_accept.decision)
        history_after = decisions.history(r2.identity.value)

        # H: byte-identical content, different subject → distinct decisions.
        raw_2 = _admit_raw("B")
        raw_selection.select(intake_id, raw_2)
        selection.select_raw_fallback(intake_id=intake_id, reviewer="selector:kim")
        s3 = generation.generate(intake_id=intake_id).candidate
        r3 = preparation.prepare_review(candidate_id=s3.identity.value).subject
        d3 = decisions.decide(
            review_subject_id=r3.identity.value, kind="accept", reviewer="reviewer:kim"
        )

        decision_rows = connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_review_decisions"
        ).fetchone()[0]
        downstream_rows = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("subtitle_review_decisions", "subtitle_final_subtitles",
                          "review_items", "subtitle_candidates")
        }
        connection.close()

        # I: a damaged candidate graph refuses new decisions (isolated copy).
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
        damaged_connection = open_sqlite_database(damaged)
        invalid_graph_blocked = False
        try:
            broken = compose_sqlite_effective_subtitle_review_decision_service(
                damaged_connection
            )
            before = damaged_connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_review_decisions"
            ).fetchone()[0]
            try:
                broken.decide(
                    review_subject_id=r1.identity.value, kind="reject",
                    reviewer="reviewer:kim",
                )
            except DecisionSubjectIntegrityError:
                after = damaged_connection.execute(
                    "SELECT COUNT(*) FROM subtitle_effective_review_decisions"
                ).fetchone()[0]
                invalid_graph_blocked = after == before
        finally:
            damaged_connection.close()

        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "intake_id": intake_id,
            "review_subject_r1_id": r1.identity.value,
            "review_subject_r2_id": r2.identity.value,
            "decision_d1_id": d1.decision.identity.value,
            "decision_reject_id": d2_reject.decision.identity.value,
            "decision_accept_id": d2_accept.decision.identity.value,
            "decision_d3_id": d3.decision.identity.value,
            "decision_count": decision_rows,
            # Behavioral checks.
            "explicit_accept_current_and_applicable": d1.outcome.value == "recorded"
            and d1.decision.kind.value == "accept"
            and d1_applicability is DecisionApplicability.APPLICABLE,
            "identical_request_reused": d1_replay.outcome.value == "reused"
            and d1_replay.decision.identity == d1.decision.identity,
            "matching_intent_by_other_actor_reused": d1_other_actor.outcome.value == "reused"
            and d1_other_actor.decision.reviewer.value == "reviewer:kim",
            "reject_current_and_applicable": d2_reject.outcome.value == "recorded"
            and reject_applicable is DecisionApplicability.APPLICABLE,
            "modify_is_authority_only": d2_modify.outcome.value == "changed"
            and modify_applicable is DecisionApplicability.APPLICABLE
            and cue_texts_before == cue_texts_after
            and candidate_count == 2,
            "supersession_appends_and_derives_current": [d.kind.value for d in r2_history]
            == ["reject", "modify", "accept"]
            and r2_current is not None
            and r2_current.identity == d2_accept.decision.identity
            and reject_after is DecisionApplicability.SUPERSEDED,
            "stale_subject_keeps_history_and_derives": d2_accept_after_reject
            is DecisionApplicability.STALE_DUE_TO_CANDIDATE_SOURCE
            and [d.identity for d in history_after] == [d.identity for d in r2_history],
            "same_content_distinct_subjects_distinct_decisions": r3.identity != r1.identity
            and d3.decision.identity != d1.decision.identity,
            "invalid_graph_blocks_decision": invalid_graph_blocked,
            "no_downstream_records_created": all(v == 0 for v in downstream_rows.values()),
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "intake_id",
        "review_subject_r1_id",
        "review_subject_r2_id",
        "decision_d1_id",
        "decision_reject_id",
        "decision_accept_id",
        "decision_d3_id",
        "decision_count",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_effective_decision_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
