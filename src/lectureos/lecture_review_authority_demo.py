"""Deterministic demonstration of effective-generation Review authority history (043 §7.6, GOAL-029).

Drives the authority-history and current-selection contract with caller-supplied human judgments —
no UI, provider, LLM, ASR, network, or execution record; the only new write of this contract is the
append-only `lecture_review_authority_positions` table:

    A. Current chain down to one Edit Candidate, with one person's first judgment starting the
       history at sequence 0
    B. A reversal (accept → reject) appends sequence 1 superseding position 0
    C. Reversing back (→ accept) appends sequence 2 that references the FIRST decision again —
       two canonical decisions across three positions, which is the case §7.6 exists to close
    D. Re-submitting the judgment the head already records → reused, nothing written
    E. The current judgment is derived from the highest position, never stored, and it carries the
       approved snapshot of the decision it references
    F. Superseded positions remain valid immutable history and are never re-numbered
    G. A second actor keeps a completely separate history on the same Candidate
    H. With two actors, the Candidate-level observation derives NO current judgment and reports a
       cross-actor conflict — no priority, no recency, no role ranking
    I. Per-actor current judgments stay derivable while that conflict exists
    J. A scope with no history derives nothing, and that is not an error
    K. Authority change → the chain is superseded, new judgments are refused, and every recorded
       position stays byte-identical
    L. Authority returns → the same judgment converges on the head with no new position
    M. Restart → identical reconstruction from the same stored graph
    N. Isolation: no legacy row, no ProcessingRun, no UnitExecution, no DomainResult of this
       contract, and no ordinal, status, or currentness column on the two canonical records
    O. Repository validation stays healthy — several positions referencing one decision, superseded
       positions, and contradictory cross-actor histories are never corruption

The committed golden reproduces byte-for-byte; no machine paths, timestamps, or randomness appear.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.lecture_analysis_input_admission import (
    AdmissionAuthorityMatch,
)
from lectureos.application.lecture_review_authority import CandidateAuthorityStatus
from lectureos.application.lecture_review_decision import ReviewAnchorNotAdmissibleError
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_lecture_analysis_edit_candidate_service,
    compose_sqlite_lecture_analysis_finding_service,
    compose_sqlite_lecture_analysis_input_admission_service,
    compose_sqlite_lecture_review_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLITE_SCHEMA_VERSION,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"

_CANDIDATE_RATIONALE = "0.0~1.0s 구간은 수업 시작 전 잡담으로 보이므로 사람이 검토할 만하다"
_ACTOR = "reviewer:lee"
_OTHER_ACTOR = "reviewer:park"
_ABSENT_ACTOR = "reviewer:nobody"


def run_lecture_review_authority_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        intake_id = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake_id,
            document=build_provider_transcript_document(
                {"provider": "fake-asr", "model": "tiny", "language": "ko",
                 "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "안녕하세요 여러부"},
                              {"start": 1.0, "end": 2.0, "text": "오늘의 강의입니다"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            intake_id, raw.raw_transcript_id.value
        )
        selection = compose_sqlite_corrected_revision_selection_service(connection)

        def _revise(candidate_ref: str, proposed_text: str) -> str:
            segment_id = SQLiteRawTranscriptRepository(connection).get(
                raw.raw_transcript_id
            ).segment_ids[0]
            source_text = SQLiteTranscriptSegmentRepository(connection).get(segment_id).text
            candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
                intake_id=intake_id,
                candidate=build_correction_candidate_input(
                    {"raw_transcript_id": raw.raw_transcript_id.value,
                     "segment_id": segment_id.value,
                     "candidate_ref": candidate_ref, "source_type": "manual",
                     "source_reference": "human", "proposed_text": proposed_text,
                     "source_text_snapshot": source_text, "rationale": "발화 교정"}
                ),
            ).candidate.identity.value
            compose_sqlite_correction_candidate_decision_service(connection).decide(
                candidate_id=candidate, kind="accept", reviewer="reviewer:kim"
            )
            revision = compose_sqlite_corrected_revision_generation_service(
                connection
            ).generate(candidate_id=candidate).revision.identity.value
            selection.select_revision(revision_id=revision, reviewer="selector:kim")
            return revision

        def _rows(table: str) -> int:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        revision_1 = _revise("c1", "안녕하세요 여러분")
        admission = compose_sqlite_lecture_analysis_input_admission_service(
            connection
        ).admit(intake_id=intake_id).admission
        finding = compose_sqlite_lecture_analysis_finding_service(connection).admit(
            admission_id=admission.identity.value,
            finding_type="non_lecture_speech",
            evidence="시작 직후 수업과 무관한 발화가 관찰된다",
        ).finding
        candidate = compose_sqlite_lecture_analysis_edit_candidate_service(
            connection
        ).admit_edit_candidate(
            finding_id=finding.identity.value,
            candidate_type="non_lecture_region",
            range_start=0.0,
            range_end=1.0,
            rationale=_CANDIDATE_RATIONALE,
        ).candidate
        reviews = compose_sqlite_lecture_review_service(connection)
        candidate_id = candidate.identity.value
        domain_results_before = _rows("domain_result_references")

        def _judge(kind: str, actor: str = _ACTOR):
            return reviews.admit_review_decision(
                candidate_id=candidate_id, decision_kind=kind, actor=actor
            )

        # A: the first judgment starts the history at sequence 0.
        first = _judge("accept")

        # B: a reversal appends sequence 1 superseding position 0.
        reversed_once = _judge("reject")

        # C: reversing back appends sequence 2 referencing the FIRST decision again.
        reversed_back = _judge("accept")
        decisions_after_reversal = _rows("lecture_review_decisions")
        positions_after_reversal = _rows("lecture_review_authority_positions")

        # D: re-submitting what the head already records writes nothing.
        replayed = _judge("accept")
        positions_after_replay = _rows("lecture_review_authority_positions")

        # E/F: current derived from the highest position; earlier positions stay history.
        current = reviews.current_review(candidate_id, _ACTOR)
        current_approved = reviews.current_approved(candidate_id, _ACTOR)
        history = reviews.authority_history(candidate_id, _ACTOR)

        # G: a second actor keeps a separate history on the same Candidate.
        other_actor_first = _judge("reject", actor=_OTHER_ACTOR)
        other_history = reviews.authority_history(candidate_id, _OTHER_ACTOR)

        # H/I: no candidate-level current is derived, and per-actor currents stay derivable.
        observation = reviews.observe_candidate_authority(candidate_id)
        current_lee = reviews.current_review(candidate_id, _ACTOR)
        current_park = reviews.current_review(candidate_id, _OTHER_ACTOR)

        # J: a scope with no history derives nothing, which is not an error.
        absent_current = reviews.current_review(candidate_id, _ABSENT_ACTOR)
        absent_history = reviews.authority_history(candidate_id, _ABSENT_ACTOR)

        domain_results_after_reviews = _rows("domain_result_references")

        # K: authority change → refusal; every recorded position stays untouched.
        history_before_change = reviews.authority_history(candidate_id, _ACTOR)
        revision_2 = _revise("c2", "안녕하세요 여러분, 반갑습니다")
        chain_after_change = reviews.anchor_status(first.decision)
        refused_superseded = False
        try:
            _judge("reject", actor="reviewer:choi")
        except ReviewAnchorNotAdmissibleError:
            refused_superseded = True
        history_after_change = reviews.authority_history(candidate_id, _ACTOR)
        positions_after_refusal = _rows("lecture_review_authority_positions")

        # L: authority returns → the head already records this judgment, so nothing is appended.
        selection.select_revision(revision_id=revision_1, reviewer="selector:kim")
        chain_after_return = reviews.anchor_status(first.decision)
        converged = _judge("accept")
        positions_after_return = _rows("lecture_review_authority_positions")

        legacy_review_rows = _rows("edit_review_decisions")
        legacy_approved_rows = _rows("approved_edit_decisions")
        processing_rows = _rows("processing_runs")
        unit_execution_rows = _rows("unit_executions")
        canonical_columns = {
            row[1] for row in connection.execute(
                "PRAGMA table_info(lecture_review_decisions)"
            ).fetchall()
        } | {
            row[1] for row in connection.execute(
                "PRAGMA table_info(lecture_approved_edit_decisions)"
            ).fetchall()
        }
        position_columns = {
            row[1] for row in connection.execute(
                "PRAGMA table_info(lecture_review_authority_positions)"
            ).fetchall()
        }
        position_indexes = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' "
            "AND tbl_name = 'lecture_review_authority_positions' AND sql IS NOT NULL"
        ).fetchall()

        # M: restart — identical reconstruction from the same stored graph.
        connection.close()
        reopened = open_sqlite_database(database)
        try:
            restarted_service = compose_sqlite_lecture_review_service(reopened)
            restarted_history = restarted_service.authority_history(candidate_id, _ACTOR)
            restarted_current = restarted_service.current_review(candidate_id, _ACTOR)
            restarted_observation = restarted_service.observe_candidate_authority(
                candidate_id
            )
        finally:
            reopened.close()

        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "schema_version": SQLITE_SCHEMA_VERSION,
            "intake_id": intake_id,
            "admission_id": admission.identity.value,
            "finding_id": finding.identity.value,
            "candidate_id": candidate_id,
            "revision_1_id": revision_1,
            "revision_2_id": revision_2,
            "accept_decision_id": first.decision.identity.value,
            "reject_decision_id": reversed_once.decision.identity.value,
            "position_0_id": first.position.identity.value,
            "position_1_id": reversed_once.position.identity.value,
            "position_2_id": reversed_back.position.identity.value,
            "other_actor_position_0_id": other_actor_first.position.identity.value,
            "decision_count": decisions_after_reversal,
            "position_count": positions_after_reversal,
            "current_sequence": current.sequence,
            "candidate_authority_status": observation.status.value,
            "repository_validation": validation.health.value,
            # Behavioral checks.
            "first_judgment_starts_the_history_at_zero":
                first.outcome.value == "recorded"
                and first.position_outcome.value == "recorded"
                and first.position.sequence == 0
                and first.position.previous_position_id is None
                and first.position.review_decision_id == first.decision.identity,
            "a_reversal_appends_and_supersedes":
                reversed_once.position_outcome.value == "recorded"
                and reversed_once.position.sequence == 1
                and reversed_once.position.previous_position_id == first.position.identity
                and reversed_once.decision.identity != first.decision.identity,
            "reversing_back_reuses_the_decision_and_opens_a_new_position":
                reversed_back.outcome.value == "reused"
                and reversed_back.position_outcome.value == "recorded"
                and reversed_back.position.sequence == 2
                and reversed_back.decision.identity == first.decision.identity
                and reversed_back.position.previous_position_id
                == reversed_once.position.identity
                and decisions_after_reversal == 2
                and positions_after_reversal == 3,
            "one_decision_occupies_several_positions":
                history[0].review_decision_id == history[2].review_decision_id
                and history[0].identity != history[2].identity
                and not any(
                    "review_decision_id" in (row[0] or "") and "UNIQUE" in (row[0] or "")
                    for row in position_indexes
                ),
            "replaying_the_head_writes_nothing":
                replayed.position_outcome.value == "reused"
                and replayed.position.identity == reversed_back.position.identity
                and positions_after_replay == positions_after_reversal,
            "current_is_derived_from_the_highest_position":
                current is not None
                and current.sequence == 2
                and current.superseded_count == 2
                and current.decision.decision_kind.value == "accept"
                and current.decision.identity == first.decision.identity
                and current_approved is not None
                and current_approved.approved_label == candidate.candidate_type
                and "current" not in position_columns
                and "status" not in position_columns,
            "superseded_positions_remain_immutable_history":
                tuple(position.sequence for position in history) == (0, 1, 2)
                and history[0] == first.position
                and history[1] == reversed_once.position,
            "a_second_actor_keeps_a_separate_history":
                other_actor_first.position.sequence == 0
                and other_actor_first.position.previous_position_id is None
                and len(other_history) == 1
                and other_history[0].actor.value == _OTHER_ACTOR
                and len(history) == 3,
            "cross_actor_derives_no_current_and_reports_a_conflict":
                observation.status is CandidateAuthorityStatus.CROSS_ACTOR_CONFLICT
                and observation.current is None
                and observation.is_conflict
                and tuple(actor.value for actor in observation.actors)
                == (_ACTOR, _OTHER_ACTOR),
            "per_actor_currents_stay_derivable_during_the_conflict":
                current_lee.decision.decision_kind.value == "accept"
                and current_park.decision.decision_kind.value == "reject"
                and current_lee.sequence == 2
                and current_park.sequence == 0,
            "a_scope_without_history_derives_nothing":
                absent_current is None and absent_history == (),
            "superseded_chain_refused_history_untouched":
                refused_superseded
                and chain_after_change
                is AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE
                and history_after_change == history_before_change
                and positions_after_refusal == positions_after_replay + 1,
            "returning_authority_appends_nothing_for_the_same_judgment":
                chain_after_return is AdmissionAuthorityMatch.CURRENT
                and converged.position_outcome.value == "reused"
                and converged.position.identity == reversed_back.position.identity
                and positions_after_return == positions_after_refusal,
            "restart_reconstructs_identically":
                restarted_history == history
                and restarted_current == current
                and restarted_observation.status is observation.status
                and restarted_observation.current is None,
            "execution_free_and_canonical_records_untouched":
                legacy_review_rows == 0
                and legacy_approved_rows == 0
                and processing_rows == 0
                and unit_execution_rows == 0
                and domain_results_after_reviews == domain_results_before
                and not canonical_columns & {
                    "sequence", "ordinal", "previous_position_id", "status", "current",
                    "stale", "selected",
                }
                and not position_columns & {
                    "status", "current", "stale", "selected", "domain_result_id",
                    "processing_run_id", "unit_execution_id", "created_at",
                    "decision_kind", "approved_label", "approved_rationale",
                },
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "schema_version",
        "intake_id",
        "admission_id",
        "finding_id",
        "candidate_id",
        "revision_1_id",
        "revision_2_id",
        "accept_decision_id",
        "reject_decision_id",
        "position_0_id",
        "position_1_id",
        "position_2_id",
        "other_actor_position_0_id",
        "decision_count",
        "position_count",
        "current_sequence",
        "candidate_authority_status",
        "repository_validation",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_lecture_review_authority_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
