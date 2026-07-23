"""In-process acceptance for the Edit-Pipeline Review Application Foundation — First Slice (043 §7.4).

Reuses the durable Transcript Pipeline chain, records the ELIGIBLE Eligible Analysis Input, a canonical
Analysis Finding and a canonical Edit Candidate, then admits human Review decisions through the Edit-Pipeline
Review Application boundary and verifies the full first slice:

    EditCandidate -> durable EditReviewDecision -> durable ApprovedEditDecision (accept/modify)

It confirms: Accept snapshots the Candidate's values; Modify carries the human-approved replacement while the
Candidate stays unchanged; Reject records only the decision; provenance chains
`ApprovedEditDecision -> EditReviewDecision -> EditCandidate`; the Candidate is not mutated; no status field or
Review Session/History table exists; and records reconstruct after reopen with deterministic replay.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    AnalysisFindingIdentityPlan,
    EditCandidateIdentityPlan,
    EditReviewDecisionKind,
    EditReviewIdentityPlan,
    LectureAnalysisInputIdentityPlan,
    NormalizedAnalysisFinding,
    NormalizedAnalysisResult,
    NormalizedCandidateResult,
    NormalizedEditCandidate,
    NormalizedModification,
)
from lectureos.application.edit_review import (
    APPROVED_EDIT_DECISION_RESULT_KIND,
    EDIT_REVIEW_DECISION_RESULT_KIND,
)
from lectureos.application.identities import (
    AnalysisFindingId,
    ApprovedEditDecisionId,
    EditCandidateId,
    EditReviewDecisionId,
    EligibleAnalysisInputId,
    TranscriptReadinessEvaluationId,
)
from lectureos.composition import (
    compose_sqlite_analysis_finding_service,
    compose_sqlite_edit_candidate_service,
    compose_sqlite_edit_review_service,
    compose_sqlite_lecture_analysis_input_service,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    SQLiteApprovedEditDecisionRepository,
    SQLiteDomainResultReferenceRepository,
    SQLiteEditCandidateRepository,
    SQLiteEditReviewDecisionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.identities import HumanActorReference
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")
_INPUT = EligibleAnalysisInputId("review-input")
_FINDING = AnalysisFindingId("review-finding")
_ACCEPT_CANDIDATE = EditCandidateId("candidate-accept")
_MODIFY_CANDIDATE = EditCandidateId("candidate-modify")
_REJECT_CANDIDATE = EditCandidateId("candidate-reject")
_ACTOR = HumanActorReference("reviewer:alice")


def _plan(name, *, approved=True):
    return EditReviewIdentityPlan(
        decision_id=EditReviewDecisionId(f"decision-{name}"),
        decision_result_id=DomainResultId(f"decision-{name}-result"),
        approved_id=ApprovedEditDecisionId(f"approved-{name}") if approved else None,
        approved_result_id=DomainResultId(f"approved-{name}-result") if approved else None,
    )


def _seed_candidates(connection, execution, run_id, execution_id):
    input_service = compose_sqlite_lecture_analysis_input_service(connection, execution)
    input_service.record_input(
        source_readiness_id=_READY,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=LectureAnalysisInputIdentityPlan(
            input_id=_INPUT,
            input_result_id=DomainResultId("review-input-result"),
        ),
    )
    finding_service = compose_sqlite_analysis_finding_service(connection, execution)
    finding_service.record_findings(
        source_input_id=_INPUT,
        run_id=run_id,
        unit_execution_id=execution_id,
        result=NormalizedAnalysisResult(
            source_timeline_id=SourceTimelineId(TIMELINE_ID),
            findings=(
                NormalizedAnalysisFinding(
                    finding_type="low_educational_value",
                    evidence="an off-topic aside appears mid-lecture",
                ),
            ),
        ),
        identities=(
            AnalysisFindingIdentityPlan(
                finding_id=_FINDING,
                finding_result_id=DomainResultId("review-finding-result"),
            ),
        ),
    )
    candidate_service = compose_sqlite_edit_candidate_service(connection, execution)
    candidate_service.record_candidates(
        source_finding_id=_FINDING,
        run_id=run_id,
        unit_execution_id=execution_id,
        result=NormalizedCandidateResult(
            source_timeline_id=SourceTimelineId(TIMELINE_ID),
            candidates=(
                NormalizedEditCandidate(
                    candidate_type="non_lecture_region",
                    rationale="propose review of a possible non-lecture region",
                    range_start=0.5,
                    range_end=1.5,
                ),
                NormalizedEditCandidate(
                    candidate_type="redundant_restatement",
                    rationale="a repeated explanation could be shortened",
                    range_start=1.0,
                    range_end=2.0,
                ),
                NormalizedEditCandidate(
                    candidate_type="delivery_concern",
                    rationale="a possible clarity concern worth reviewing",
                    range_start=0.0,
                    range_end=1.0,
                ),
            ),
        ),
        identities=(
            EditCandidateIdentityPlan(
                candidate_id=_ACCEPT_CANDIDATE,
                candidate_result_id=DomainResultId("candidate-accept-result"),
            ),
            EditCandidateIdentityPlan(
                candidate_id=_MODIFY_CANDIDATE,
                candidate_result_id=DomainResultId("candidate-modify-result"),
            ),
            EditCandidateIdentityPlan(
                candidate_id=_REJECT_CANDIDATE,
                candidate_result_id=DomainResultId("candidate-reject-result"),
            ),
        ),
    )


def _modification():
    return NormalizedModification(
        approved_range_start=0.75,
        approved_range_end=1.25,
        approved_candidate_type="condense_repetition",
        approved_rationale="approved: condense the repeated explanation",
    )


def _review_all(connection, execution, run_id, execution_id):
    service = compose_sqlite_edit_review_service(connection, execution)
    accepted = service.record_decision(
        source_candidate_id=_ACCEPT_CANDIDATE,
        run_id=run_id,
        unit_execution_id=execution_id,
        decision_kind="accept",
        actor=_ACTOR,
        identities=_plan("accept"),
    )
    modified = service.record_decision(
        source_candidate_id=_MODIFY_CANDIDATE,
        run_id=run_id,
        unit_execution_id=execution_id,
        decision_kind="modify",
        actor=_ACTOR,
        identities=_plan("modify"),
        modification=_modification(),
    )
    rejected = service.record_decision(
        source_candidate_id=_REJECT_CANDIDATE,
        run_id=run_id,
        unit_execution_id=execution_id,
        decision_kind="reject",
        actor=_ACTOR,
        identities=_plan("reject", approved=False),
    )
    return accepted, modified, rejected


def _record_reviews(connection, execution, run_id, execution_id):
    _seed_candidates(connection, execution, run_id, execution_id)
    return _review_all(connection, execution, run_id, execution_id)


def run_edit_review_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(
            connection
        )
        _seed_candidates(connection, execution, run_id, execution_id)
        candidate_repo = SQLiteEditCandidateRepository(connection)
        candidate_accept_before = candidate_repo.get(_ACCEPT_CANDIDATE)
        candidate_modify_before = candidate_repo.get(_MODIFY_CANDIDATE)

        accepted, modified, rejected = _review_all(
            connection, execution, run_id, execution_id
        )

        candidate_accept = candidate_repo.get(_ACCEPT_CANDIDATE)
        candidate_modify = candidate_repo.get(_MODIFY_CANDIDATE)
        candidates_unmutated = (
            candidate_accept == candidate_accept_before
            and candidate_modify == candidate_modify_before
        )

        # Accept snapshot equals the Candidate's review-relevant values.
        accept_snapshot_matches = (
            accepted.approved is not None
            and accepted.approved.approved_range_start == candidate_accept.range_start
            and accepted.approved.approved_range_end == candidate_accept.range_end
            and accepted.approved.approved_candidate_type == candidate_accept.candidate_type
            and accepted.approved.approved_rationale == candidate_accept.rationale
        )
        # Modify snapshot equals the normalized human modification and differs from the Candidate.
        modify_snapshot_matches = (
            modified.approved is not None
            and modified.approved.approved_candidate_type == "condense_repetition"
            and modified.approved.approved_range_start == 0.75
            and modified.approved.approved_candidate_type != candidate_modify.candidate_type
        )
        reject_has_no_approved = rejected.approved is None

        # Provenance chaining: ApprovedEditDecision -> ReviewDecision -> EditCandidate.
        provenance_linked = all(
            item.decision_result.kind == EDIT_REVIEW_DECISION_RESULT_KIND
            and item.decision_result.upstream_results == (candidate.domain_result_id,)
            and item.approved_result.kind == APPROVED_EDIT_DECISION_RESULT_KIND
            and item.approved_result.upstream_results == (item.decision.domain_result_id,)
            and item.approved.source_decision_id == item.decision.identity
            and item.approved.source_candidate_id == candidate.identity
            for item, candidate in (
                (accepted, candidate_accept),
                (modified, candidate_modify),
            )
        )

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        no_deferred_tables = not {
            "review_sessions",
            "edit_review_history",
            "review_items_edit",
            "candidate_reconciliations_edit",
        } & existing_tables
        decision_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(edit_review_decisions)"
            ).fetchall()
        }
        no_status_column = not {"status", "state", "current", "stale", "superseded"} & decision_columns
        connection.close()

        reopened = open_sqlite_database(path)
        decision_repo = SQLiteEditReviewDecisionRepository(reopened)
        approved_repo = SQLiteApprovedEditDecisionRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = (
            decision_repo.get(accepted.decision.identity) == accepted.decision
            and decision_repo.get(rejected.decision.identity) == rejected.decision
            and approved_repo.get(modified.approved.identity) == modified.approved
            and approved_repo.get_for_decision(accepted.decision.identity)
            == accepted.approved
            and approved_repo.get_for_decision(rejected.decision.identity) is None
            and results.get(modified.approved_result.identity) == modified.approved_result
        )
        reopened.close()

        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _, _ = _build_persisted_readiness(replay_connection)
        r_accepted, r_modified, r_rejected = _record_reviews(
            replay_connection, r_execution, r_run, r_exec
        )
        replay_connection.close()
        deterministic_replay = (
            r_accepted.decision == accepted.decision
            and r_accepted.approved == accepted.approved
            and r_modified.approved == modified.approved
            and r_rejected.decision == rejected.decision
        )

        return {
            "candidates_unmutated": candidates_unmutated,
            "accept_snapshot_matches": accept_snapshot_matches,
            "modify_snapshot_matches": modify_snapshot_matches,
            "reject_has_no_approved": reject_has_no_approved,
            "provenance_linked": provenance_linked,
            "no_deferred_tables": no_deferred_tables,
            "no_status_column": no_status_column,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
        }


def main() -> int:
    print(json.dumps(run_edit_review_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
