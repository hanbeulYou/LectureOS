"""In-process fake-review / fake-transcript acceptance for Subtitle Review Preparation.

Drives the full canonical pipeline (candidate → reading → time → validation → review preparation) with
no network and no credential, and confirms that Review Preparation materializes canonical human-review
work from validation findings without deciding anything.

It verifies that a clean validation yields a valid empty preparation (zero items), and that a defective
validation yields exactly one OPEN common Review Item per finding — each traced to its source finding
and stable rule — reconstructed exactly after restart, replayed identically, idempotent with respect to
the upstream validation, with no Review Decision recorded and no downstream final/artifact table.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    SubtitleReviewPreparationIdentityPlan,
    SubtitleReviewTargetIdentityPlan,
    SubtitleTimeIdentityPlan,
    SubtitleTimingStatus,
    SubtitleValidationIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleReadingRevisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleValidationId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_review_preparation_service,
    compose_sqlite_subtitle_structural_validation_service,
    compose_sqlite_subtitle_time_representation_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteReviewItemRepository,
    SQLiteSubtitleReviewPreparationRepository,
    SQLiteSubtitleValidationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.identities import (
    CandidateReferenceId,
    ReviewContextId,
    ReviewItemId,
)
from lectureos.subtitle_reading_acceptance import (
    _build_persisted_candidate,
    _compose_reading,
)
from lectureos.subtitle_validation_acceptance import _persist_defective_time

_READING_ID = SubtitleReadingRevisionId("reading")
_TIME_ID = SubtitleTimeRevisionId("time")
_CLEAN_VALIDATION_ID = SubtitleValidationId("validation-clean")
_DISORDER_VALIDATION_ID = SubtitleValidationId("validation-disorder")


def _time_plan(units) -> SubtitleTimeIdentityPlan:
    return SubtitleTimeIdentityPlan(
        time_revision_id=_TIME_ID,
        time_result_id=DomainResultId("time-result"),
        timed_unit_ids=tuple(SubtitleTimedUnitId(f"time-unit-{i}") for i in range(units)),
    )


def _prep_plan(name, count) -> SubtitleReviewPreparationIdentityPlan:
    return SubtitleReviewPreparationIdentityPlan(
        preparation_id=SubtitleReviewPreparationId(name),
        preparation_result_id=DomainResultId(f"{name}-result"),
        context_id=ReviewContextId(f"{name}-context"),
        targets=tuple(
            SubtitleReviewTargetIdentityPlan(
                candidate_reference_id=CandidateReferenceId(f"{name}-ref-{i}"),
                review_item_id=ReviewItemId(f"{name}-item-{i}"),
            )
            for i in range(count)
        ),
    )


def _build_through_validations(connection):
    """Build candidate → reading → time → clean validation + a defective validation with findings."""

    execution, run_id, execution_id, candidate = _build_persisted_candidate(connection)
    reading = _compose_reading(connection, execution, run_id, execution_id)
    reading_units = reading.revision.unit_ids

    time_service = compose_sqlite_subtitle_time_representation_service(connection, execution)
    time_service.record_timing(
        source_reading_revision_id=_READING_ID,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_time_plan(len(reading_units)),
    )
    validation_service = compose_sqlite_subtitle_structural_validation_service(connection, execution)
    validation_service.record_validation(
        source_time_revision_id=_TIME_ID,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=SubtitleValidationIdentityPlan(
            validation_id=_CLEAN_VALIDATION_ID,
            validation_result_id=DomainResultId("validation-clean-result"),
        ),
    )
    disorder_time_id = _persist_defective_time(
        connection,
        reading.revision,
        candidate,
        "time-disorder",
        [
            (reading_units[0], SubtitleTimingStatus.ANCHORED, 5.0, 6.0),
            (reading_units[1], SubtitleTimingStatus.ANCHORED, 0.0, 1.0),
        ],
    )
    disorder_validation = validation_service.record_validation(
        source_time_revision_id=disorder_time_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=SubtitleValidationIdentityPlan(
            validation_id=_DISORDER_VALIDATION_ID,
            validation_result_id=DomainResultId("validation-disorder-result"),
        ),
    )
    return execution, run_id, execution_id, disorder_validation.findings


def run_subtitle_review_preparation_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, findings = _build_through_validations(connection)

        review_service = compose_sqlite_subtitle_review_preparation_service(connection, execution)
        empty = review_service.generate_review(
            source_validation_id=_CLEAN_VALIDATION_ID,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_prep_plan("prep-clean", 0),
        )
        empty_valid = empty.preparation.item_count == 0 and empty.review_items == ()

        validation_repo = SQLiteSubtitleValidationRepository(connection)
        upstream_before = validation_repo.get(_DISORDER_VALIDATION_ID)
        disorder = review_service.generate_review(
            source_validation_id=_DISORDER_VALIDATION_ID,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_prep_plan("prep-disorder", len(findings)),
        )
        upstream_after = validation_repo.get(_DISORDER_VALIDATION_ID)
        idempotent_upstream = upstream_before == upstream_after

        one_item_per_finding = (
            disorder.preparation.item_count == len(findings)
            and len(disorder.review_items) == len(findings)
            and len(findings) >= 1
        )
        items_open = all(item.decision_references == () for item in disorder.review_items)
        finding_traced = (
            [link.source_finding_id for link in disorder.preparation.item_links]
            == [finding.identity for finding in findings]
            and [link.rule for link in disorder.preparation.item_links]
            == [finding.rule for finding in findings]
        )
        candidate_reference_kind = all(
            reference.kind == "subtitle_validation_finding"
            and reference.source_domain == "subtitle"
            for reference in disorder.candidate_references
        )
        result_upstream_linked = disorder.preparation_result.upstream_results == (
            upstream_after.domain_result_id,
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
        prep_repo = SQLiteSubtitleReviewPreparationRepository(reopened)
        item_repo = SQLiteReviewItemRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = (
            prep_repo.get(empty.preparation.identity) == empty.preparation
            and prep_repo.get(disorder.preparation.identity) == disorder.preparation
            and all(item_repo.get(item.identity) == item for item in disorder.review_items)
            and results.get(disorder.preparation_result.identity)
            == disorder.preparation_result
        )
        # review items remain OPEN after restart (no decision recorded)
        no_decision = all(
            item_repo.get(item.identity).decision_references == ()
            for item in disorder.review_items
        )
        reopened.close()

        # Deterministic replay into a fresh database with identical recorded inputs.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, r_findings = _build_through_validations(replay_connection)
        r_service = compose_sqlite_subtitle_review_preparation_service(
            replay_connection, r_execution
        )
        replayed_empty = r_service.generate_review(
            source_validation_id=_CLEAN_VALIDATION_ID,
            run_id=r_run,
            unit_execution_id=r_exec,
            identities=_prep_plan("prep-clean", 0),
        )
        replayed_disorder = r_service.generate_review(
            source_validation_id=_DISORDER_VALIDATION_ID,
            run_id=r_run,
            unit_execution_id=r_exec,
            identities=_prep_plan("prep-disorder", len(r_findings)),
        )
        replay_connection.close()
        deterministic_replay = (
            replayed_empty.preparation == empty.preparation
            and replayed_disorder.preparation == disorder.preparation
            and replayed_disorder.review_items == disorder.review_items
            and replayed_disorder.preparation_result == disorder.preparation_result
        )

        return {
            "empty_valid": empty_valid,
            "one_item_per_finding": one_item_per_finding,
            "items_open": items_open,
            "finding_traced": finding_traced,
            "candidate_reference_kind": candidate_reference_kind,
            "result_upstream_linked": result_upstream_linked,
            "idempotent_upstream": idempotent_upstream,
            "restart_reconstructed": restart_reconstructed,
            "no_decision": no_decision,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_subtitle_review_preparation_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
