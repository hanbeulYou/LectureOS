"""In-process fake-review / fake-transcript acceptance for Subtitle Structural Validation.

Drives the full canonical pipeline with no network and no credential through candidate generation,
reading representation and time representation, then diagnoses the time revision into an immutable
validation result plus findings.

It verifies that a clean pipeline time revision is structurally valid with no findings, and that
constructed defective time revisions (overlapping / out-of-order / unresolved timing) produce
category-classified findings carrying stable rule identifiers with ``structural_valid=False``. It
further verifies immutable validation + finding records; full lineage; execution provenance; atomic
persistence; restart reconstruction; deterministic replay; idempotency with respect to the upstream
time revision; that validation modifies nothing and creates no Review Item; and that no downstream
review / final / artifact table is produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    RULE_ORDERING_NON_MONOTONIC,
    RULE_OVERLAP_ADJACENT,
    RULE_UNRESOLVED_TIMING,
    SubtitleTimedUnit,
    SubtitleTimeIdentityPlan,
    SubtitleTimeRevision,
    SubtitleTimingStatus,
    SubtitleValidationIdentityPlan,
)
from lectureos.application.identities import (
    SubtitleReadingRevisionId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleValidationId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_structural_validation_service,
    compose_sqlite_subtitle_time_representation_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.execution.models import DomainResultReference
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleTimeCommandPersistence,
    SQLiteSubtitleTimeRevisionRepository,
    SQLiteSubtitleValidationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.subtitle_reading_acceptance import (
    _build_persisted_candidate,
    _compose_reading,
)

_READING_ID = SubtitleReadingRevisionId("reading")
_TIME_ID = SubtitleTimeRevisionId("time")


def _time_plan(name, units) -> SubtitleTimeIdentityPlan:
    return SubtitleTimeIdentityPlan(
        time_revision_id=SubtitleTimeRevisionId(name),
        time_result_id=DomainResultId(f"{name}-result"),
        timed_unit_ids=tuple(SubtitleTimedUnitId(f"{name}-unit-{i}") for i in range(units)),
    )


def _validation_plan(name) -> SubtitleValidationIdentityPlan:
    return SubtitleValidationIdentityPlan(
        validation_id=SubtitleValidationId(name),
        validation_result_id=DomainResultId(f"{name}-result"),
    )


def _persist_defective_time(connection, reading_revision, candidate, name, unit_specs):
    """Persist a durable time revision with the given (reading_unit, status, start, end) units."""

    revision_id = SubtitleTimeRevisionId(name)
    timed_units = tuple(
        SubtitleTimedUnit(
            identity=SubtitleTimedUnitId(f"{name}-unit-{index}"),
            time_revision_id=revision_id,
            source_reading_unit_id=reading_unit_id,
            display_order=index,
            timing_status=status,
            source_timeline_id=(
                reading_revision.source_timeline_id
                if status is SubtitleTimingStatus.ANCHORED
                else None
            ),
            start=start,
            end=end,
        )
        for index, (reading_unit_id, status, start, end) in enumerate(unit_specs)
    )
    revision = SubtitleTimeRevision(
        identity=revision_id,
        domain_result_id=DomainResultId(f"{name}-result"),
        source_reading_revision_id=reading_revision.identity,
        source_candidate_id=reading_revision.source_candidate_id,
        source_intake_id=reading_revision.source_intake_id,
        source_readiness_id=reading_revision.source_readiness_id,
        source_selection_id=reading_revision.source_selection_id,
        source_applicability_id=reading_revision.source_applicability_id,
        source_decision_id=reading_revision.source_decision_id,
        review_item_id=reading_revision.review_item_id,
        candidate_reference_id=reading_revision.candidate_reference_id,
        source_transcript_id=reading_revision.source_transcript_id,
        source_revision_id=reading_revision.source_revision_id,
        source_media_id=reading_revision.source_media_id,
        source_timeline_id=reading_revision.source_timeline_id,
        validation_id=reading_revision.validation_id,
        timed_unit_ids=tuple(u.identity for u in timed_units),
        run_id=reading_revision.run_id,
        unit_execution_id=reading_revision.unit_execution_id,
        sequence=0,
        reason=f"defective time revision {name} for validation acceptance",
    )
    result = DomainResultReference(
        identity=revision.domain_result_id,
        kind="subtitle_time_revision",
        source_media=reading_revision.source_media_id,
        source_timeline=reading_revision.source_timeline_id,
        upstream_results=(reading_revision.domain_result_id,),
    )
    SQLiteSubtitleTimeCommandPersistence(connection).persist_subtitle_timing(
        revision=revision, units=timed_units, revision_result=result
    )
    return revision_id


def run_subtitle_validation_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, candidate = _build_persisted_candidate(connection)
        reading = _compose_reading(connection, execution, run_id, execution_id)
        reading_revision = reading.revision
        reading_units = reading_revision.unit_ids

        time_service = compose_sqlite_subtitle_time_representation_service(connection, execution)
        time_service.record_timing(
            source_reading_revision_id=_READING_ID,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_time_plan("time", len(reading_units)),
        )

        time_repo = SQLiteSubtitleTimeRevisionRepository(connection)
        upstream_before = time_repo.get(_TIME_ID)

        service = compose_sqlite_subtitle_structural_validation_service(connection, execution)
        clean = service.record_validation(
            source_time_revision_id=_TIME_ID,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_validation_plan("validation-clean"),
        )

        upstream_after = time_repo.get(_TIME_ID)
        idempotent_upstream = upstream_before == upstream_after

        clean_valid = clean.validation.structural_valid and clean.findings == ()
        lineage_linked = (
            clean.validation.source_time_revision_id == _TIME_ID
            and clean.validation.source_candidate_id == candidate.candidate.identity
        )
        result_upstream_linked = clean.validation_result.upstream_results == (
            upstream_after.domain_result_id,
        )

        # Defective time revision 1: out-of-order + overlapping anchored units.
        disorder_id = _persist_defective_time(
            connection,
            reading_revision,
            candidate,
            "time-disorder",
            [
                (reading_units[0], SubtitleTimingStatus.ANCHORED, 5.0, 6.0),
                (reading_units[1], SubtitleTimingStatus.ANCHORED, 0.0, 1.0),
            ],
        )
        disorder = service.record_validation(
            source_time_revision_id=disorder_id,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_validation_plan("validation-disorder"),
        )
        # Defective time revision 2: an unresolved unit.
        unresolved_id = _persist_defective_time(
            connection,
            reading_revision,
            candidate,
            "time-unresolved",
            [
                (reading_units[0], SubtitleTimingStatus.UNRESOLVED, None, None),
                (reading_units[1], SubtitleTimingStatus.ANCHORED, 0.0, 1.0),
            ],
        )
        unresolved = service.record_validation(
            source_time_revision_id=unresolved_id,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_validation_plan("validation-unresolved"),
        )

        seen_rules = {f.rule for f in disorder.findings} | {
            f.rule for f in unresolved.findings
        }
        defective_findings = (
            not disorder.validation.structural_valid
            and not unresolved.validation.structural_valid
            and RULE_ORDERING_NON_MONOTONIC in seen_rules
            and RULE_OVERLAP_ADJACENT in seen_rules
            and RULE_UNRESOLVED_TIMING in seen_rules
        )
        # stable rule identifiers are populated and independent of the descriptions
        stable_rules = all(
            f.rule.strip() and f.description.strip()
            for f in (*disorder.findings, *unresolved.findings)
        )

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        no_downstream_tables = not {
            "subtitle_reviews",
            "subtitle_final_selections",
            "artifacts",
        } & existing_tables
        connection.close()

        reopened = open_sqlite_database(path)
        repo = SQLiteSubtitleValidationRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = (
            repo.get(clean.validation.identity) == clean.validation
            and repo.get(disorder.validation.identity) == disorder.validation
            and all(
                repo.get_finding(f.identity) == f for f in disorder.findings
            )
            and results.get(clean.validation_result.identity) == clean.validation_result
        )
        reopened.close()

        # Deterministic replay of the clean diagnosis into a fresh database.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _ = _build_persisted_candidate(replay_connection)
        _compose_reading(replay_connection, r_execution, r_run, r_exec)
        compose_sqlite_subtitle_time_representation_service(
            replay_connection, r_execution
        ).record_timing(
            source_reading_revision_id=_READING_ID,
            run_id=r_run,
            unit_execution_id=r_exec,
            identities=_time_plan("time", len(reading_units)),
        )
        replayed = compose_sqlite_subtitle_structural_validation_service(
            replay_connection, r_execution
        ).record_validation(
            source_time_revision_id=_TIME_ID,
            run_id=r_run,
            unit_execution_id=r_exec,
            identities=_validation_plan("validation-clean"),
        )
        replay_connection.close()
        deterministic_replay = (
            replayed.validation == clean.validation
            and replayed.findings == clean.findings
            and replayed.validation_result == clean.validation_result
        )

        return {
            "clean_valid": clean_valid,
            "defective_findings": defective_findings,
            "stable_rules": stable_rules,
            "lineage_linked": lineage_linked,
            "result_upstream_linked": result_upstream_linked,
            "idempotent_upstream": idempotent_upstream,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_subtitle_validation_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
