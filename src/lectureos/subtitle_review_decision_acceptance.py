"""In-process fake-review / fake-transcript acceptance for Subtitle Human Review Decision.

Drives the full canonical pipeline (candidate → reading → time → validation → review preparation) with
no network and no credential, then records Human Accept, an append-only Modify, and Reject judgements
against the prepared common Review Items and confirms the decisions are recorded — never applied.

It verifies subtitle provenance and DomainResult chaining on each decision, append-only supersession
(a second decision on one item references the first), exact restart reconstruction, deterministic
replay, idempotency with respect to the upstream preparation and review items, and that nothing is
applied — the review items stay OPEN and no subtitle-revision / final / artifact table is produced.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lectureos.application import (
    SubtitleReviewDecisionIdentityPlan,
    SubtitleReviewPreparationIdentityPlan,
    SubtitleReviewTargetIdentityPlan,
    SubtitleTimingStatus,
    SubtitleValidationIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleValidationId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_review_decision_service,
    compose_sqlite_subtitle_review_preparation_service,
    compose_sqlite_subtitle_structural_validation_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteReviewItemRepository,
    SQLiteSubtitleReviewDecisionRepository,
    SQLiteSubtitleReviewPreparationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.identities import (
    CandidateReferenceId,
    HumanActorReference,
    ReviewContextId,
    ReviewItemId,
)
from lectureos.review.models import DecisionKind
from lectureos.subtitle_reading_acceptance import (
    _build_persisted_candidate,
    _compose_reading,
)
from lectureos.subtitle_validation_acceptance import _persist_defective_time

_PREP_ID = SubtitleReviewPreparationId("prep")
_ACCEPT_AT = datetime(2026, 7, 22, 22, 0, tzinfo=timezone.utc)
_MODIFY_AT = datetime(2026, 7, 22, 22, 5, tzinfo=timezone.utc)
_REJECT_AT = datetime(2026, 7, 22, 22, 10, tzinfo=timezone.utc)
_REVIEWER = HumanActorReference("fake:reviewer")


def _prep_plan(count):
    return SubtitleReviewPreparationIdentityPlan(
        preparation_id=_PREP_ID,
        preparation_result_id=DomainResultId("prep-result"),
        context_id=ReviewContextId("prep-context"),
        targets=tuple(
            SubtitleReviewTargetIdentityPlan(
                candidate_reference_id=CandidateReferenceId(f"prep-ref-{i}"),
                review_item_id=ReviewItemId(f"prep-item-{i}"),
            )
            for i in range(count)
        ),
    )


def _build_persisted_preparation(connection):
    execution, run_id, execution_id, candidate = _build_persisted_candidate(connection)
    reading = _compose_reading(connection, execution, run_id, execution_id)
    units = reading.revision.unit_ids
    disorder_time_id = _persist_defective_time(
        connection,
        reading.revision,
        candidate,
        "time-disorder",
        [
            (units[0], SubtitleTimingStatus.ANCHORED, 5.0, 6.0),
            (units[1], SubtitleTimingStatus.ANCHORED, 0.0, 1.0),
        ],
    )
    validation = compose_sqlite_subtitle_structural_validation_service(
        connection, execution
    ).record_validation(
        source_time_revision_id=disorder_time_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=SubtitleValidationIdentityPlan(
            validation_id=SubtitleValidationId("validation"),
            validation_result_id=DomainResultId("validation-result"),
        ),
    )
    prep = compose_sqlite_subtitle_review_preparation_service(
        connection, execution
    ).generate_review(
        source_validation_id=SubtitleValidationId("validation"),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_prep_plan(len(validation.findings)),
    )
    return execution, run_id, execution_id, prep


def _record_all_decisions(connection, execution, run_id, execution_id, prep):
    service = compose_sqlite_subtitle_review_decision_service(connection, execution)
    items = prep.review_items
    accept = service.record_decision(
        preparation_id=_PREP_ID,
        review_item_id=items[0].identity,
        reviewer=_REVIEWER,
        kind=DecisionKind.ACCEPT,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=SubtitleReviewDecisionIdentityPlan(
            decision_id=SubtitleReviewDecisionId("decision-accept"),
            decision_result_id=DomainResultId("decision-accept-result"),
            decided_at=_ACCEPT_AT,
        ),
    )
    # append-only supersession: a second decision on the same item references the first
    modify = service.record_decision(
        preparation_id=_PREP_ID,
        review_item_id=items[0].identity,
        reviewer=_REVIEWER,
        kind=DecisionKind.MODIFY,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=SubtitleReviewDecisionIdentityPlan(
            decision_id=SubtitleReviewDecisionId("decision-modify"),
            decision_result_id=DomainResultId("decision-modify-result"),
            decided_at=_MODIFY_AT,
        ),
        sequence=1,
        previous_decision_id=accept.decision.identity,
        modified_text="corrected subtitle line",
    )
    reject = service.record_decision(
        preparation_id=_PREP_ID,
        review_item_id=items[1].identity,
        reviewer=_REVIEWER,
        kind=DecisionKind.REJECT,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=SubtitleReviewDecisionIdentityPlan(
            decision_id=SubtitleReviewDecisionId("decision-reject"),
            decision_result_id=DomainResultId("decision-reject-result"),
            decided_at=_REJECT_AT,
        ),
    )
    return (accept, modify, reject)


def run_subtitle_review_decision_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, prep = _build_persisted_preparation(connection)
        items = prep.review_items
        links = prep.preparation.item_links

        prep_repo = SQLiteSubtitleReviewPreparationRepository(connection)
        item_repo = SQLiteReviewItemRepository(connection)
        prep_before = prep_repo.get(_PREP_ID)
        items_before = tuple(item_repo.get(item.identity) for item in items)

        accept, modify, reject = _record_all_decisions(
            connection, execution, run_id, execution_id, prep
        )

        prep_after = prep_repo.get(_PREP_ID)
        items_after = tuple(item_repo.get(item.identity) for item in items)
        idempotent_upstream = prep_before == prep_after and items_before == items_after
        # nothing applied: review items remain OPEN (no decisions attached to them)
        items_still_open = all(item.decision_references == () for item in items_after)

        kinds_recorded = (
            accept.decision.kind is DecisionKind.ACCEPT
            and modify.decision.kind is DecisionKind.MODIFY
            and reject.decision.kind is DecisionKind.REJECT
        )
        append_only = (
            modify.decision.previous_decision_id == accept.decision.identity
            and modify.decision.sequence == 1
            and modify.decision.modified_text == "corrected subtitle line"
        )
        provenance_linked = all(
            decision.decision.source_preparation_id == _PREP_ID
            and decision.decision.source_validation_id == SubtitleValidationId("validation")
            and decision.decision_result.kind == "subtitle_review_decision"
            and decision.decision_result.upstream_results
            == (prep.preparation.domain_result_id,)
            for decision in (accept, modify, reject)
        )
        # each decision traces to the source finding + rule of its review item
        item_link = {link.review_item_id: link for link in links}
        finding_traced = (
            accept.decision.source_finding_id
            == item_link[items[0].identity].source_finding_id
            and accept.decision.rule == item_link[items[0].identity].rule
            and reject.decision.source_finding_id
            == item_link[items[1].identity].source_finding_id
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
        decision_repo = SQLiteSubtitleReviewDecisionRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = all(
            decision_repo.get(decision.decision.identity) == decision.decision
            and results.get(decision.decision_result.identity)
            == decision.decision_result
            for decision in (accept, modify, reject)
        )
        reopened.close()

        # Deterministic replay into a fresh database.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, r_prep = _build_persisted_preparation(replay_connection)
        r_accept, r_modify, r_reject = _record_all_decisions(
            replay_connection, r_execution, r_run, r_exec, r_prep
        )
        replay_connection.close()
        deterministic_replay = (
            r_accept.decision == accept.decision
            and r_modify.decision == modify.decision
            and r_reject.decision == reject.decision
        )

        return {
            "decision_count": 3,
            "kinds_recorded": kinds_recorded,
            "append_only": append_only,
            "provenance_linked": provenance_linked,
            "finding_traced": finding_traced,
            "idempotent_upstream": idempotent_upstream,
            "items_still_open": items_still_open,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_subtitle_review_decision_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
