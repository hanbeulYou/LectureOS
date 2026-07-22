"""In-process fake-review / fake-transcript acceptance for Subtitle Decision Application (041 §4.7).

Drives the full canonical pipeline (candidate → reading → time → validation → review preparation →
human review decision) with no network and no credential, then deterministically applies the recorded
Accept, Modify and Reject decisions into the next Subtitle revisions.

It verifies each next revision's applied outcome (Accept→ACCEPTED, Reject→REJECTED, Modify→MODIFIED with
the applied text), subtitle provenance and DomainResult chaining, that no existing canonical artifact is
mutated (decision / review item / preparation / validation byte-identical before and after), exact
restart reconstruction, deterministic replay, and that no downstream final / artifact table is produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import SubtitleAppliedOutcome, SubtitleDecisionRevisionIdentityPlan
from lectureos.application.identities import (
    SubtitleDecisionRevisionId,
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleValidationId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_decision_application_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteReviewItemRepository,
    SQLiteSubtitleDecisionRevisionRepository,
    SQLiteSubtitleReviewDecisionRepository,
    SQLiteSubtitleReviewPreparationRepository,
    SQLiteSubtitleValidationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.models import DecisionKind
from lectureos.subtitle_review_decision_acceptance import (
    _PREP_ID,
    _build_persisted_preparation,
    _record_all_decisions,
)

_VALIDATION_ID = SubtitleValidationId("validation")
_ACCEPT = SubtitleReviewDecisionId("decision-accept")
_MODIFY = SubtitleReviewDecisionId("decision-modify")
_REJECT = SubtitleReviewDecisionId("decision-reject")


def _revision_plan(name):
    return SubtitleDecisionRevisionIdentityPlan(
        revision_id=SubtitleDecisionRevisionId(name),
        revision_result_id=DomainResultId(f"{name}-result"),
    )


def _build_persisted_decisions(connection):
    execution, run_id, execution_id, prep = _build_persisted_preparation(connection)
    decisions = _record_all_decisions(connection, execution, run_id, execution_id, prep)
    return execution, run_id, execution_id, prep, decisions


def _apply_all(connection, execution, run_id, execution_id):
    service = compose_sqlite_subtitle_decision_application_service(connection, execution)

    def apply(decision_id, name):
        return service.record_application(
            source_review_decision_id=decision_id,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_revision_plan(name),
        )

    return (
        apply(_ACCEPT, "revision-accept"),
        apply(_MODIFY, "revision-modify"),
        apply(_REJECT, "revision-reject"),
    )


def run_subtitle_decision_application_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, prep, decisions = _build_persisted_decisions(
            connection
        )
        accept_decision, modify_decision, reject_decision = decisions

        decision_repo = SQLiteSubtitleReviewDecisionRepository(connection)
        validation_repo = SQLiteSubtitleValidationRepository(connection)
        prep_repo = SQLiteSubtitleReviewPreparationRepository(connection)
        item_repo = SQLiteReviewItemRepository(connection)
        review_items = prep.review_items
        upstream_before = (
            decision_repo.get(_ACCEPT),
            decision_repo.get(_MODIFY),
            validation_repo.get(_VALIDATION_ID),
            prep_repo.get(_PREP_ID),
            tuple(item_repo.get(item.identity) for item in review_items),
        )

        accept, modify, reject = _apply_all(
            connection, execution, run_id, execution_id
        )

        upstream_after = (
            decision_repo.get(_ACCEPT),
            decision_repo.get(_MODIFY),
            validation_repo.get(_VALIDATION_ID),
            prep_repo.get(_PREP_ID),
            tuple(item_repo.get(item.identity) for item in review_items),
        )
        no_upstream_mutation = upstream_before == upstream_after

        outcomes_correct = (
            accept.revision.outcome is SubtitleAppliedOutcome.ACCEPTED
            and reject.revision.outcome is SubtitleAppliedOutcome.REJECTED
            and modify.revision.outcome is SubtitleAppliedOutcome.MODIFIED
        )
        modify_applied_text = modify.revision.applied_text == "corrected subtitle line"
        accept_reject_no_text = (
            accept.revision.applied_text is None and reject.revision.applied_text is None
        )
        provenance_linked = (
            accept.revision.source_review_decision_id == _ACCEPT
            and modify.revision.source_review_decision_id == _MODIFY
            and reject.revision.source_review_decision_id == _REJECT
            and all(
                r.revision_result.kind == "subtitle_decision_revision"
                and r.revision_result.upstream_results
                == (d.decision.domain_result_id,)
                for r, d in (
                    (accept, accept_decision),
                    (modify, modify_decision),
                    (reject, reject_decision),
                )
            )
        )
        target_traced = all(
            r.revision.source_finding_id == d.decision.source_finding_id
            and r.revision.rule == d.decision.rule
            for r, d in (
                (accept, accept_decision),
                (modify, modify_decision),
                (reject, reject_decision),
            )
        )

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        no_downstream_tables = not {
            "subtitle_final_selections",
            "artifacts",
        } & existing_tables
        connection.close()

        reopened = open_sqlite_database(path)
        revision_repo = SQLiteSubtitleDecisionRevisionRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = all(
            revision_repo.get(r.revision.identity) == r.revision
            and results.get(r.revision_result.identity) == r.revision_result
            for r in (accept, modify, reject)
        )
        reopened.close()

        # Deterministic replay into a fresh database.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _, _ = _build_persisted_decisions(replay_connection)
        r_accept, r_modify, r_reject = _apply_all(
            replay_connection, r_execution, r_run, r_exec
        )
        replay_connection.close()
        deterministic_replay = (
            r_accept.revision == accept.revision
            and r_modify.revision == modify.revision
            and r_reject.revision == reject.revision
        )

        return {
            "revision_count": 3,
            "outcomes_correct": outcomes_correct,
            "modify_applied_text": modify_applied_text,
            "accept_reject_no_text": accept_reject_no_text,
            "provenance_linked": provenance_linked,
            "target_traced": target_traced,
            "no_upstream_mutation": no_upstream_mutation,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_subtitle_decision_application_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
