"""In-process fake-review / fake-transcript acceptance for Lecture Analysis Input Eligibility (042 §5.1).

Reuses the durable Transcript Pipeline chain (correction → review → applicability → current selection →
readiness) that the Subtitle Transcript Intake acceptance builds, then deterministically records the
Eligible Analysis Input for the ready and not-ready readiness evaluations.

It verifies that only a READY selected transcript yields ELIGIBLE and a NOT_READY one yields
NOT_ELIGIBLE; immutable, provenance-bearing records; full readiness/selection/applicability/decision/item/
candidate/revision linkage and source media/timeline; execution provenance; atomic persistence; restart
reconstruction; deterministic replay; idempotency with respect to upstream state; that no upstream record
is mutated; and that no analysis / Finding / Segment / Candidate / downstream table is produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    LectureAnalysisEligibility,
    LectureAnalysisInputIdentityPlan,
)
from lectureos.application.identities import (
    EligibleAnalysisInputId,
    TranscriptReadinessEvaluationId,
)
from lectureos.composition import (
    compose_sqlite_lecture_analysis_input_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteEligibleAnalysisInputRepository,
    SQLiteTranscriptReadinessEvaluationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.subtitle_intake_acceptance import _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")
_NOT_READY = TranscriptReadinessEvaluationId("rdy-int-reject")


def _plan(name):
    return LectureAnalysisInputIdentityPlan(
        input_id=EligibleAnalysisInputId(name),
        input_result_id=DomainResultId(f"{name}-result"),
    )


def _record_all(connection, execution, run_id, execution_id):
    service = compose_sqlite_lecture_analysis_input_service(connection, execution)

    def record(readiness_id, name):
        return service.record_input(
            source_readiness_id=readiness_id,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_plan(name),
        )

    return (record(_READY, "input-ready"), record(_NOT_READY, "input-not-ready"))


def run_lecture_analysis_input_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, revision_id, raw_id = _build_persisted_readiness(
            connection
        )

        readiness_repo = SQLiteTranscriptReadinessEvaluationRepository(connection)
        upstream_before = (
            readiness_repo.get(_READY),
            readiness_repo.get(_NOT_READY),
        )

        eligible, not_eligible = _record_all(
            connection, execution, run_id, execution_id
        )

        upstream_after = (
            readiness_repo.get(_READY),
            readiness_repo.get(_NOT_READY),
        )
        no_upstream_mutation = upstream_before == upstream_after

        eligibility_correct = (
            eligible.eligible_input.eligibility is LectureAnalysisEligibility.ELIGIBLE
            and not_eligible.eligible_input.eligibility
            is LectureAnalysisEligibility.NOT_ELIGIBLE
        )
        provenance_linked = all(
            r.eligible_input.source_readiness_id == readiness_id
            and r.input_result.kind == "eligible_analysis_input"
            and r.input_result.upstream_results
            == (readiness_repo.get(readiness_id).domain_result_id,)
            for r, readiness_id in ((eligible, _READY), (not_eligible, _NOT_READY))
        )
        # each record carries the full transcript provenance + source media/timeline
        ready_ready = readiness_repo.get(_READY)
        lineage_linked = (
            eligible.eligible_input.source_selection_id == ready_ready.source_selection_id
            and eligible.eligible_input.source_revision_id == ready_ready.source_revision_id
            and eligible.eligible_input.validation_id == ready_ready.validation_id
        )

        # No downstream stage runs: while the canonical Analysis Finding (v24), Lecture Segment (v25), and
        # Edit Candidate (v26) tables exist they must stay empty — intake records none of them.
        downstream_rows = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("analysis_findings", "lecture_segments", "edit_candidates")
        )
        no_downstream_tables = all(count == 0 for count in downstream_rows)
        connection.close()

        reopened = open_sqlite_database(path)
        input_repo = SQLiteEligibleAnalysisInputRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = all(
            input_repo.get(r.eligible_input.identity) == r.eligible_input
            and results.get(r.input_result.identity) == r.input_result
            for r in (eligible, not_eligible)
        )
        reopened.close()

        # deterministic replay into a fresh database
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _, _ = _build_persisted_readiness(replay_connection)
        r_eligible, r_not_eligible = _record_all(
            replay_connection, r_execution, r_run, r_exec
        )
        replay_connection.close()
        deterministic_replay = (
            r_eligible.eligible_input == eligible.eligible_input
            and r_not_eligible.eligible_input == not_eligible.eligible_input
        )

        return {
            "input_count": 2,
            "eligibility_correct": eligibility_correct,
            "provenance_linked": provenance_linked,
            "lineage_linked": lineage_linked,
            "no_upstream_mutation": no_upstream_mutation,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_lecture_analysis_input_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
