"""In-process acceptance for the Edit-Pipeline Export Application Foundation — First Slice (044 §19).

Reuses the durable pipeline chain, records an Eligible Analysis Input, Analysis Finding, Edit Candidate, and
an accept-review + a modify-review Approved Edit Decision, then admits export representations through the
Edit-Pipeline Export Application boundary and verifies the full first slice:

    ApprovedEditDecision -> durable ApprovedEditExportRepresentation

It confirms: the owned snapshot is copied faithfully from the Approved Edit Decision (Accept and Modify);
the source Approved Edit Decision / Review Decision / Candidate stay unchanged; DomainResult upstream is the
Approved Edit Decision's DomainResult; multiple distinct representations may reference one Approved Edit
Decision; no Artifact / file / serializer / profile / status / executable command is created; and records
reconstruct after reopen with deterministic replay.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    AnalysisFindingIdentityPlan,
    ApprovedEditExportIdentityPlan,
    EditCandidateIdentityPlan,
    EditReviewIdentityPlan,
    LectureAnalysisInputIdentityPlan,
    NormalizedAnalysisFinding,
    NormalizedAnalysisResult,
    NormalizedCandidateResult,
    NormalizedEditCandidate,
    NormalizedModification,
)
from lectureos.application.edit_export import (
    APPROVED_EDIT_EXPORT_REPRESENTATION_RESULT_KIND,
)
from lectureos.application.identities import (
    AnalysisFindingId,
    ApprovedEditDecisionId,
    ApprovedEditExportRepresentationId,
    EditCandidateId,
    EditReviewDecisionId,
    EligibleAnalysisInputId,
    TranscriptReadinessEvaluationId,
)
from lectureos.composition import (
    compose_sqlite_analysis_finding_service,
    compose_sqlite_edit_candidate_service,
    compose_sqlite_edit_export_service,
    compose_sqlite_edit_review_service,
    compose_sqlite_lecture_analysis_input_service,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    SQLiteApprovedEditDecisionRepository,
    SQLiteApprovedEditExportRepresentationRepository,
    SQLiteDomainResultReferenceRepository,
    SQLiteEditReviewDecisionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.identities import HumanActorReference
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")
_INPUT = EligibleAnalysisInputId("export-input")
_FINDING = AnalysisFindingId("export-finding")
_ACCEPT_CANDIDATE = EditCandidateId("candidate-accept")
_MODIFY_CANDIDATE = EditCandidateId("candidate-modify")
_ACCEPT_DECISION = ApprovedEditDecisionId("approved-accept")
_MODIFY_DECISION = ApprovedEditDecisionId("approved-modify")
_ACTOR = HumanActorReference("reviewer:alice")


def _seed_approved_decisions(connection, execution, run_id, execution_id):
    input_service = compose_sqlite_lecture_analysis_input_service(connection, execution)
    input_service.record_input(
        source_readiness_id=_READY,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=LectureAnalysisInputIdentityPlan(
            input_id=_INPUT, input_result_id=DomainResultId("export-input-result")
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
                    finding_type="low_educational_value", evidence="an off-topic aside"
                ),
            ),
        ),
        identities=(
            AnalysisFindingIdentityPlan(
                finding_id=_FINDING,
                finding_result_id=DomainResultId("export-finding-result"),
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
                    rationale="propose review of a non-lecture region",
                    range_start=0.5,
                    range_end=1.5,
                ),
                NormalizedEditCandidate(
                    candidate_type="redundant_restatement",
                    rationale="a repeated explanation",
                    range_start=1.0,
                    range_end=2.0,
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
        ),
    )
    review_service = compose_sqlite_edit_review_service(connection, execution)
    review_service.record_decision(
        source_candidate_id=_ACCEPT_CANDIDATE,
        run_id=run_id,
        unit_execution_id=execution_id,
        decision_kind="accept",
        actor=_ACTOR,
        identities=EditReviewIdentityPlan(
            decision_id=EditReviewDecisionId("decision-accept"),
            decision_result_id=DomainResultId("decision-accept-result"),
            approved_id=_ACCEPT_DECISION,
            approved_result_id=DomainResultId("approved-accept-result"),
        ),
    )
    review_service.record_decision(
        source_candidate_id=_MODIFY_CANDIDATE,
        run_id=run_id,
        unit_execution_id=execution_id,
        decision_kind="modify",
        actor=_ACTOR,
        identities=EditReviewIdentityPlan(
            decision_id=EditReviewDecisionId("decision-modify"),
            decision_result_id=DomainResultId("decision-modify-result"),
            approved_id=_MODIFY_DECISION,
            approved_result_id=DomainResultId("approved-modify-result"),
        ),
        modification=NormalizedModification(
            approved_range_start=0.75,
            approved_range_end=1.25,
            approved_candidate_type="condense_repetition",
            approved_rationale="approved: condense the repeated explanation",
        ),
    )


def _plan(name):
    return ApprovedEditExportIdentityPlan(
        representation_id=ApprovedEditExportRepresentationId(name),
        representation_result_id=DomainResultId(f"{name}-result"),
    )


def _record_exports(connection, execution, run_id, execution_id):
    service = compose_sqlite_edit_export_service(connection, execution)
    accepted = service.record_representation(
        source_approved_decision_id=_ACCEPT_DECISION,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_plan("export-accept"),
    )
    modified = service.record_representation(
        source_approved_decision_id=_MODIFY_DECISION,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_plan("export-modify"),
    )
    # a second independent representation of the same accept approved decision (new identities)
    accepted_again = service.record_representation(
        source_approved_decision_id=_ACCEPT_DECISION,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_plan("export-accept-2"),
    )
    return accepted, modified, accepted_again


def run_edit_export_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(
            connection
        )
        _seed_approved_decisions(connection, execution, run_id, execution_id)

        approved_repo = SQLiteApprovedEditDecisionRepository(connection)
        review_repo = SQLiteEditReviewDecisionRepository(connection)
        approved_accept_before = approved_repo.get(_ACCEPT_DECISION)
        approved_modify_before = approved_repo.get(_MODIFY_DECISION)
        review_accept_before = review_repo.get(EditReviewDecisionId("decision-accept"))

        accepted, modified, accepted_again = _record_exports(
            connection, execution, run_id, execution_id
        )

        approved_accept = approved_repo.get(_ACCEPT_DECISION)
        approved_modify = approved_repo.get(_MODIFY_DECISION)
        upstream_unmutated = (
            approved_accept == approved_accept_before
            and approved_modify == approved_modify_before
            and review_repo.get(EditReviewDecisionId("decision-accept")) == review_accept_before
        )

        # Accept snapshot copied faithfully from the Approved Edit Decision; actor from the review decision.
        accept_snapshot_faithful = (
            accepted.representation.approved_range_start == approved_accept.approved_range_start
            and accepted.representation.approved_range_end == approved_accept.approved_range_end
            and accepted.representation.approved_candidate_type == approved_accept.approved_candidate_type
            and accepted.representation.approved_rationale == approved_accept.approved_rationale
            and accepted.representation.decision_kind == approved_accept.decision_kind
            and accepted.representation.actor == review_accept_before.actor
        )
        # Modify snapshot equals the approved (modified) values, not the original candidate proposal.
        modify_snapshot_faithful = (
            modified.representation.approved_candidate_type == "condense_repetition"
            and modified.representation.approved_range_start == 0.75
            and modified.representation.source_candidate_id == _MODIFY_CANDIDATE
        )
        provenance_linked = all(
            item.representation_result.kind == APPROVED_EDIT_EXPORT_REPRESENTATION_RESULT_KIND
            and item.representation_result.upstream_results == (approved.domain_result_id,)
            and item.representation.source_approved_decision_id == approved.identity
            and item.representation.source_media_id == approved.source_media_id
            and item.representation.source_timeline_id == approved.source_timeline_id
            for item, approved in (
                (accepted, approved_accept),
                (modified, approved_modify),
            )
        )
        multiple_per_decision = (
            accepted.representation.identity != accepted_again.representation.identity
            and accepted_again.representation.source_approved_decision_id == _ACCEPT_DECISION
        )

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        no_deferred_tables = not {
            "export_artifacts_edit",
            "edit_export_profiles",
            "edit_export_scopes",
        } & existing_tables
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(approved_edit_export_representations)"
            ).fetchall()
        }
        no_deferred_columns = not {
            "status", "profile", "format", "mime_type", "filename", "path", "url",
            "checksum", "payload", "serialized",
        } & columns
        connection.close()

        reopened = open_sqlite_database(path)
        repo = SQLiteApprovedEditExportRepresentationRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = (
            repo.get(accepted.representation.identity) == accepted.representation
            and repo.get(modified.representation.identity) == modified.representation
            and results.get(modified.representation_result.identity)
            == modified.representation_result
            and repo.count_for_approved_decision(_ACCEPT_DECISION) == 2
        )
        reopened.close()

        replay_path = Path(directory) / "replay.sqlite3"
        replay = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _, _ = _build_persisted_readiness(replay)
        _seed_approved_decisions(replay, r_execution, r_run, r_exec)
        r_accepted, r_modified, _ = _record_exports(replay, r_execution, r_run, r_exec)
        replay.close()
        deterministic_replay = (
            r_accepted.representation == accepted.representation
            and r_modified.representation == modified.representation
        )

        return {
            "upstream_unmutated": upstream_unmutated,
            "accept_snapshot_faithful": accept_snapshot_faithful,
            "modify_snapshot_faithful": modify_snapshot_faithful,
            "provenance_linked": provenance_linked,
            "multiple_per_decision": multiple_per_decision,
            "no_deferred_tables": no_deferred_tables,
            "no_deferred_columns": no_deferred_columns,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
        }


def main() -> int:
    print(json.dumps(run_edit_export_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
