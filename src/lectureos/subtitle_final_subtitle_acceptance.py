"""In-process fake-review / fake-transcript acceptance for Subtitle Final Subtitle (041 §4.8).

Drives the full canonical pipeline (candidate → reading → time → validation → review preparation →
human review decision → decision application) with no network and no credential, then deterministically
selects the authoritative Final Subtitle from each applied Subtitle decision revision.

It verifies each Final Subtitle's deterministic outcome (Accept→FINAL, Modify→FINAL with the applied
text, Reject→NOT_FINAL), its provenance and DomainResult chaining to the decision revision, that no
existing canonical artifact is mutated (decision revision / review decision / validation / preparation /
review item byte-identical before and after), exact restart reconstruction, deterministic replay, and
that no downstream export / artifact table is produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    SubtitleFinalOutcome,
    SubtitleFinalSubtitleIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleDecisionRevisionId,
    SubtitleFinalSubtitleId,
    SubtitleReviewDecisionId,
    SubtitleValidationId,
)
from lectureos.composition import compose_sqlite_subtitle_final_subtitle_service
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteReviewItemRepository,
    SQLiteSubtitleDecisionRevisionRepository,
    SQLiteSubtitleFinalSubtitleRepository,
    SQLiteSubtitleReviewDecisionRepository,
    SQLiteSubtitleReviewPreparationRepository,
    SQLiteSubtitleValidationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.subtitle_decision_application_acceptance import (
    _ACCEPT,
    _MODIFY,
    _REJECT,
    _PREP_ID,
    _VALIDATION_ID,
    _apply_all,
    _build_persisted_decisions,
)

_ACCEPT_REVISION = SubtitleDecisionRevisionId("revision-accept")
_MODIFY_REVISION = SubtitleDecisionRevisionId("revision-modify")
_REJECT_REVISION = SubtitleDecisionRevisionId("revision-reject")


def _final_plan(name):
    return SubtitleFinalSubtitleIdentityPlan(
        final_id=SubtitleFinalSubtitleId(name),
        final_result_id=DomainResultId(f"{name}-result"),
    )


def _build_persisted_revisions(connection):
    execution, run_id, execution_id, prep, decisions = _build_persisted_decisions(
        connection
    )
    revisions = _apply_all(connection, execution, run_id, execution_id)
    return execution, run_id, execution_id, prep, decisions, revisions


def _select_all(connection, execution, run_id, execution_id):
    service = compose_sqlite_subtitle_final_subtitle_service(connection, execution)

    def select(revision_id, name):
        return service.record_final(
            source_decision_revision_id=revision_id,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_final_plan(name),
        )

    return (
        select(_ACCEPT_REVISION, "final-accept"),
        select(_MODIFY_REVISION, "final-modify"),
        select(_REJECT_REVISION, "final-reject"),
    )


def run_subtitle_final_subtitle_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        (
            execution,
            run_id,
            execution_id,
            prep,
            decisions,
            revisions,
        ) = _build_persisted_revisions(connection)
        accept_rev, modify_rev, reject_rev = revisions

        revision_repo = SQLiteSubtitleDecisionRevisionRepository(connection)
        decision_repo = SQLiteSubtitleReviewDecisionRepository(connection)
        validation_repo = SQLiteSubtitleValidationRepository(connection)
        prep_repo = SQLiteSubtitleReviewPreparationRepository(connection)
        item_repo = SQLiteReviewItemRepository(connection)
        review_items = prep.review_items
        upstream_before = (
            revision_repo.get(_ACCEPT_REVISION),
            revision_repo.get(_MODIFY_REVISION),
            revision_repo.get(_REJECT_REVISION),
            decision_repo.get(_ACCEPT),
            decision_repo.get(_MODIFY),
            decision_repo.get(_REJECT),
            validation_repo.get(_VALIDATION_ID),
            prep_repo.get(_PREP_ID),
            tuple(item_repo.get(item.identity) for item in review_items),
        )

        accept, modify, reject = _select_all(
            connection, execution, run_id, execution_id
        )

        upstream_after = (
            revision_repo.get(_ACCEPT_REVISION),
            revision_repo.get(_MODIFY_REVISION),
            revision_repo.get(_REJECT_REVISION),
            decision_repo.get(_ACCEPT),
            decision_repo.get(_MODIFY),
            decision_repo.get(_REJECT),
            validation_repo.get(_VALIDATION_ID),
            prep_repo.get(_PREP_ID),
            tuple(item_repo.get(item.identity) for item in review_items),
        )
        no_upstream_mutation = upstream_before == upstream_after

        outcomes_correct = (
            accept.final.final_outcome is SubtitleFinalOutcome.FINAL
            and modify.final.final_outcome is SubtitleFinalOutcome.FINAL
            and reject.final.final_outcome is SubtitleFinalOutcome.NOT_FINAL
        )
        modify_applied_text = modify.final.applied_text == "corrected subtitle line"
        accept_reject_no_text = (
            accept.final.applied_text is None and reject.final.applied_text is None
        )
        provenance_linked = (
            accept.final.source_decision_revision_id == _ACCEPT_REVISION
            and modify.final.source_decision_revision_id == _MODIFY_REVISION
            and reject.final.source_decision_revision_id == _REJECT_REVISION
            and all(
                f.final_result.kind == "subtitle_final_subtitle"
                and f.final_result.upstream_results == (r.revision.domain_result_id,)
                for f, r in (
                    (accept, accept_rev),
                    (modify, modify_rev),
                    (reject, reject_rev),
                )
            )
        )
        target_traced = all(
            f.final.source_finding_id == r.revision.source_finding_id
            and f.final.rule == r.revision.rule
            and f.final.source_review_decision_id == r.revision.source_review_decision_id
            for f, r in (
                (accept, accept_rev),
                (modify, modify_rev),
                (reject, reject_rev),
            )
        )

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        no_downstream_tables = not {
            "subtitle_exports",
            "artifacts",
        } & existing_tables
        connection.close()

        reopened = open_sqlite_database(path)
        final_repo = SQLiteSubtitleFinalSubtitleRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = all(
            final_repo.get(f.final.identity) == f.final
            and results.get(f.final_result.identity) == f.final_result
            for f in (accept, modify, reject)
        )
        reopened.close()

        # Deterministic replay into a fresh database.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _, _, _ = _build_persisted_revisions(
            replay_connection
        )
        r_accept, r_modify, r_reject = _select_all(
            replay_connection, r_execution, r_run, r_exec
        )
        replay_connection.close()
        deterministic_replay = (
            r_accept.final == accept.final
            and r_modify.final == modify.final
            and r_reject.final == reject.final
        )

        return {
            "final_count": 3,
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
    print(json.dumps(run_subtitle_final_subtitle_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
