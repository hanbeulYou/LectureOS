"""Deterministic demonstration of effective-generation Review records (043 §7.5, GOAL-028).

Drives the Review Foundation with caller-supplied human judgments — no UI, provider, LLM, ASR,
network, or execution record; the only writes of this contract are the append-only
`lecture_review_decisions` and `lecture_approved_edit_decisions` tables:

    A. Current admission → Analysis Finding → Edit Candidate prepared, with NO Lecture Segment
       anywhere and no legacy Review row
    B. accept → one ReviewDecision plus exactly one ApprovedEditDecision whose snapshot is the
       Candidate's proposal inherited verbatim
    C. reject → one ReviewDecision and NO ApprovedEditDecision, durable and auditable
    D. modify → a complete approved replacement owned solely by the ApprovedEditDecision, with the
       original Candidate byte-identical afterwards
    E. Exact replay of each of the three → reused, no new row
    F. A different human actor on the same candidate and kind → a distinct record (the actor
       participates in identity)
    G. Integral (0 vs 0.0) and negative-zero (-0.0 vs 0.0) approved-range spellings → same identity
    H. A second, differing modify by the same actor → explicit approval conflict, nothing written
       (R-11's reachable conflict branch)
    I. Invalid judgments (unknown kind, `Accept` casing, empty actor, partial modify, approved
       values supplied to accept/reject) → refused, nothing written
    J. Authority change → the anchor chain derives superseded_by_authority_change
    K. Admitting against the superseded chain → explicit refusal, no row; existing records untouched
    L. Authority returns → the chain is current again and the same judgment converges
    M. accept → reject → accept: the third submission converges on the first identity, so two
       contradicting judgments coexist as history and nothing adjudicates them (R-9's recorded
       consequence, inherited from the legacy constant-`sequence` path)
    N. Restart → identical reconstruction from the same stored graph
    O. Isolation: no legacy `edit_review_decisions` or `approved_edit_decisions` row, no
       ProcessingRun, no UnitExecution, no DomainResult of this contract, no ordinal or status
       column, nothing executed
    P. Repository validation stays healthy (a superseded chain and coexisting judgments are never
       corruption)

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
from lectureos.application.lecture_review_decision import (
    LectureReviewError,
    ReviewAnchorNotAdmissibleError,
    ReviewApprovalConflictError,
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
_APPROVED_RATIONALE = "앞부분만 잘라내는 것으로 승인한다"
_ACTOR = "reviewer:lee"
_OTHER_ACTOR = "reviewer:park"


def run_lecture_review_demo(media_fixtures_directory: str | None = None) -> dict:
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

        # A: a current chain down to one Edit Candidate, with no Lecture Segment anywhere.
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
        segments_before = _rows("lecture_analysis_segments")
        domain_results_before = _rows("domain_result_references")

        def _judge(**overrides):
            payload = {
                "candidate_id": candidate.identity.value,
                "decision_kind": "accept",
                "actor": _ACTOR,
            }
            payload.update(overrides)
            return reviews.admit_review_decision(**payload)

        def _modify(**overrides):
            payload = {
                "decision_kind": "modify",
                "approved_range_start": 0.0,
                "approved_range_end": 0.5,
                "approved_label": "trim_intro",
                "approved_rationale": _APPROVED_RATIONALE,
            }
            payload.update(overrides)
            return _judge(**payload)

        # B: accept → decision + one approved snapshot inherited from the candidate verbatim.
        accepted = _judge()

        # C: reject → decision only, approving nothing.
        rejected = _judge(decision_kind="reject")

        # D: modify → a complete approved replacement; the candidate itself is untouched.
        candidate_before_modify = compose_sqlite_lecture_analysis_edit_candidate_service(
            connection
        ).get(candidate.identity.value)
        modified = _modify()
        candidate_after_modify = compose_sqlite_lecture_analysis_edit_candidate_service(
            connection
        ).get(candidate.identity.value)

        # E: exact replay of each of the three → reused, no new row.
        decision_rows_after_first_pass = _rows("lecture_review_decisions")
        approved_rows_after_first_pass = _rows("lecture_approved_edit_decisions")
        replayed_accept = _judge()
        replayed_reject = _judge(decision_kind="reject")
        replayed_modify = _modify()
        decision_rows_after_replay = _rows("lecture_review_decisions")
        approved_rows_after_replay = _rows("lecture_approved_edit_decisions")

        # F: a different human actor is a distinct judgment (the actor is part of identity).
        other_actor = _judge(actor=_OTHER_ACTOR)

        # G: integral and negative-zero approved-range spellings converge.
        integral_modify = _modify(approved_range_start=0)
        negative_zero_modify = _modify(approved_range_start=-0.0)

        # H: a second, differing modify by the same actor → explicit approval conflict.
        rows_before_conflict = _rows("lecture_review_decisions")
        approved_before_conflict = _rows("lecture_approved_edit_decisions")
        approval_conflict_refused = False
        try:
            _modify(approved_range_end=0.9)
        except ReviewApprovalConflictError:
            approval_conflict_refused = True
        rows_after_conflict = _rows("lecture_review_decisions")
        approved_after_conflict = _rows("lecture_approved_edit_decisions")

        # I: invalid judgments refused before any write.
        refused_invalid = 0
        for bad in ({"decision_kind": "approve"}, {"decision_kind": "Accept"},
                    {"decision_kind": "ACCEPT"}, {"decision_kind": " accept"},
                    {"actor": "   "}, {"decision_kind": "modify"},
                    {"approved_label": "trim_intro"},
                    {"decision_kind": "reject", "approved_rationale": _APPROVED_RATIONALE},
                    {"decision_kind": "modify", "approved_range_start": 1.0,
                     "approved_range_end": 0.0, "approved_label": "trim_intro",
                     "approved_rationale": _APPROVED_RATIONALE},
                    {"decision_kind": "modify", "approved_range_start": -1.0,
                     "approved_range_end": 1.0, "approved_label": "trim_intro",
                     "approved_rationale": _APPROVED_RATIONALE},
                    {"decision_kind": "modify", "approved_range_start": 0.0,
                     "approved_range_end": float("inf"), "approved_label": "trim_intro",
                     "approved_rationale": _APPROVED_RATIONALE},
                    {"decision_kind": "modify", "approved_range_start": 0.0,
                     "approved_range_end": 1.0, "approved_label": "Bad Label",
                     "approved_rationale": _APPROVED_RATIONALE},
                    {"decision_kind": "modify", "approved_range_start": 0.0,
                     "approved_range_end": 1.0, "approved_label": "trim_intro",
                     "approved_rationale": "   "}):
            try:
                _judge(**bad)
            except LectureReviewError:
                refused_invalid += 1
        rows_after_invalid = _rows("lecture_review_decisions")
        approved_after_invalid = _rows("lecture_approved_edit_decisions")
        domain_results_after_reviews = _rows("domain_result_references")

        # J/K: authority change → chain superseded; new judgments refused, history untouched.
        revision_2 = _revise("c2", "안녕하세요 여러분, 반갑습니다")
        chain_after_change = reviews.anchor_status(accepted.decision)
        refused_superseded = False
        try:
            _judge(decision_kind="reject", actor="reviewer:choi")
        except ReviewAnchorNotAdmissibleError:
            refused_superseded = True
        rows_after_refusal = _rows("lecture_review_decisions")
        accepted_after_change = reviews.get(accepted.decision.identity.value)
        approved_after_change = reviews.get_approved(accepted.decision.identity.value)

        # L: authority returns → chain current again; the same judgment converges.
        selection.select_revision(revision_id=revision_1, reviewer="selector:kim")
        chain_after_return = reviews.anchor_status(accepted.decision)
        converged = _judge()

        # M: accept → reject → accept converges on the first identity; both judgments coexist.
        reversal = _judge()
        recorded = reviews.list_for_candidate(candidate.identity.value)
        coexisting_kinds = tuple(
            sorted(decision.decision_kind.value for decision in recorded
                   if decision.actor.value == _ACTOR)
        )

        legacy_review_rows = _rows("edit_review_decisions")
        legacy_approved_rows = _rows("approved_edit_decisions")
        processing_rows = _rows("processing_runs")
        unit_execution_rows = _rows("unit_executions")
        decision_columns = {
            row[1] for row in connection.execute(
                "PRAGMA table_info(lecture_review_decisions)"
            ).fetchall()
        }
        approved_columns = {
            row[1] for row in connection.execute(
                "PRAGMA table_info(lecture_approved_edit_decisions)"
            ).fetchall()
        }

        # N: restart — identical reconstruction from the same stored graph.
        connection.close()
        reopened = open_sqlite_database(database)
        try:
            restarted_service = compose_sqlite_lecture_review_service(reopened)
            restarted = restarted_service.get(accepted.decision.identity.value)
            restarted_approved = restarted_service.get_approved(
                accepted.decision.identity.value
            )
            restarted_list = restarted_service.list_for_candidate(candidate.identity.value)
            restarted_chain = restarted_service.anchor_status(restarted)
        finally:
            reopened.close()

        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "schema_version": SQLITE_SCHEMA_VERSION,
            "intake_id": intake_id,
            "admission_id": admission.identity.value,
            "finding_id": finding.identity.value,
            "candidate_id": candidate.identity.value,
            "revision_1_id": revision_1,
            "revision_2_id": revision_2,
            "accept_decision_id": accepted.decision.identity.value,
            "accept_approved_id": accepted.approved.identity.value,
            "reject_decision_id": rejected.decision.identity.value,
            "modify_decision_id": modified.decision.identity.value,
            "modify_approved_id": modified.approved.identity.value,
            "decision_count": len(recorded),
            "repository_validation": validation.health.value,
            # Behavioral checks.
            "accept_owns_inherited_approved_snapshot":
                accepted.outcome.value == "recorded"
                and accepted.decision.candidate_id == candidate.identity
                and accepted.decision.decision_kind.value == "accept"
                and accepted.decision.actor.value == _ACTOR
                and accepted.approved is not None
                and accepted.approved.review_decision_id == accepted.decision.identity
                and accepted.approved.approved_decision_kind.value == "accept"
                and accepted.approved.approved_range_start == candidate.range_start
                and accepted.approved.approved_range_end == candidate.range_end
                and accepted.approved.approved_label == candidate.candidate_type
                and accepted.approved.approved_rationale == candidate.rationale
                and segments_before == 0,
            "reject_records_a_durable_decision_with_no_approval":
                rejected.outcome.value == "recorded"
                and rejected.decision.decision_kind.value == "reject"
                and rejected.approved is None
                and rejected.decision.identity != accepted.decision.identity,
            "modify_owns_the_replacement_and_never_touches_the_candidate":
                modified.outcome.value == "recorded"
                and modified.approved is not None
                and modified.approved.approved_decision_kind.value == "modify"
                and modified.approved.approved_range_end == 0.5
                and modified.approved.approved_label == "trim_intro"
                and modified.approved.approved_rationale == _APPROVED_RATIONALE
                and candidate_after_modify == candidate_before_modify
                and candidate_after_modify.rationale == _CANDIDATE_RATIONALE,
            "exact_replay_reused_no_new_rows":
                replayed_accept.outcome.value == "reused"
                and replayed_reject.outcome.value == "reused"
                and replayed_modify.outcome.value == "reused"
                and replayed_accept.decision.identity == accepted.decision.identity
                and replayed_modify.approved.identity == modified.approved.identity
                and decision_rows_after_replay == decision_rows_after_first_pass == 3
                and approved_rows_after_replay == approved_rows_after_first_pass == 2,
            "a_different_human_actor_is_a_distinct_judgment":
                other_actor.outcome.value == "recorded"
                and other_actor.decision.identity != accepted.decision.identity
                and other_actor.approved.identity != accepted.approved.identity,
            "integral_and_negative_zero_approved_bounds_converge":
                integral_modify.outcome.value == "reused"
                and negative_zero_modify.outcome.value == "reused"
                and integral_modify.approved.identity == modified.approved.identity
                and negative_zero_modify.approved.identity == modified.approved.identity,
            "differing_second_modify_is_an_explicit_conflict_nothing_written":
                approval_conflict_refused
                and rows_after_conflict == rows_before_conflict
                and approved_after_conflict == approved_before_conflict,
            "invalid_judgments_refused_nothing_written":
                refused_invalid == 13
                and rows_after_invalid == rows_before_conflict
                and approved_after_invalid == approved_before_conflict,
            "superseded_chain_refused_history_untouched":
                refused_superseded
                and chain_after_change
                is AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE
                and rows_after_refusal == rows_before_conflict
                and accepted_after_change == accepted.decision
                and approved_after_change == accepted.approved,
            "returning_authority_restores_admissibility":
                chain_after_return is AdmissionAuthorityMatch.CURRENT
                and converged.outcome.value == "reused"
                and converged.decision.identity == accepted.decision.identity,
            "reversed_judgments_coexist_unadjudicated":
                reversal.outcome.value == "reused"
                and reversal.decision.identity == accepted.decision.identity
                and coexisting_kinds == ("accept", "modify", "reject")
                and not hasattr(accepted.decision, "sequence")
                and not hasattr(accepted.decision, "previous_decision_id"),
            "restart_reconstructs_identically":
                restarted == accepted.decision
                and restarted_approved == accepted.approved
                and len(restarted_list) == len(recorded)
                and restarted_chain is AdmissionAuthorityMatch.CURRENT,
            "execution_free_and_legacy_isolated":
                legacy_review_rows == 0
                and legacy_approved_rows == 0
                and processing_rows == 0
                and unit_execution_rows == 0
                and domain_results_after_reviews == domain_results_before
                and not (decision_columns | approved_columns) & {
                    "sequence", "domain_result_id", "processing_run_id", "unit_execution_id",
                    "status", "current", "stale", "selected", "previous_decision_id",
                    "source_media_id", "source_timeline_id",
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
        "accept_approved_id",
        "reject_decision_id",
        "modify_decision_id",
        "modify_approved_id",
        "decision_count",
        "repository_validation",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_lecture_review_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
