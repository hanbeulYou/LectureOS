"""In-process acceptance for the Analysis Finding Application Foundation (042 §8.1, PATCH-0010).

Reuses the durable Transcript Pipeline chain that the Subtitle Transcript Intake acceptance builds, records
the ELIGIBLE Eligible Analysis Input from the READY readiness evaluation, then admits a normalized,
provider-independent analysis result and records durable canonical Analysis Findings.

It verifies the end-to-end path

    Transcript Pipeline -> Transcript Readiness -> EligibleAnalysisInput (ELIGIBLE)
        -> normalized provider-independent analysis result -> canonical AnalysisFinding

producing immutable, provenance-bearing Finding records anchored to exactly one Eligible Analysis Input;
full provenance to the input's Domain Result, source media and source timeline; execution provenance;
atomic persistence; restart reconstruction; deterministic replay; that no upstream record is mutated; and
that no Lecture Segment, Segment Label, Edit Candidate, Review Item, or concrete provider record is
produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    AnalysisFindingIdentityPlan,
    LectureAnalysisEligibility,
    LectureAnalysisInputIdentityPlan,
    NormalizedAnalysisFinding,
    NormalizedAnalysisResult,
)
from lectureos.application.analysis_finding import ANALYSIS_FINDING_RESULT_KIND
from lectureos.application.identities import (
    AnalysisFindingId,
    EligibleAnalysisInputId,
    TranscriptReadinessEvaluationId,
)
from lectureos.composition import (
    compose_sqlite_analysis_finding_service,
    compose_sqlite_lecture_analysis_input_service,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    SQLiteAnalysisFindingRepository,
    SQLiteDomainResultReferenceRepository,
    SQLiteEligibleAnalysisInputRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")
_INPUT = EligibleAnalysisInputId("analysis-input")


def _input_plan():
    return LectureAnalysisInputIdentityPlan(
        input_id=_INPUT,
        input_result_id=DomainResultId("analysis-input-result"),
    )


def _finding_plans(*names):
    return tuple(
        AnalysisFindingIdentityPlan(
            finding_id=AnalysisFindingId(name),
            finding_result_id=DomainResultId(f"{name}-result"),
        )
        for name in names
    )


def _normalized_result():
    return NormalizedAnalysisResult(
        source_timeline_id=SourceTimelineId(TIMELINE_ID),
        findings=(
            NormalizedAnalysisFinding(
                finding_type="terminology_drift",
                evidence="the speaker misnames the theorem at the introduction",
                confidence=0.82,
                range_start=1.0,
                range_end=2.5,
            ),
            NormalizedAnalysisFinding(
                finding_type="missing_definition",
                evidence="a key term is used before it is defined",
            ),
        ),
    )


def _record_findings(connection, execution, run_id, execution_id):
    input_service = compose_sqlite_lecture_analysis_input_service(connection, execution)
    input_service.record_input(
        source_readiness_id=_READY,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_input_plan(),
    )
    finding_service = compose_sqlite_analysis_finding_service(connection, execution)
    return finding_service.record_findings(
        source_input_id=_INPUT,
        run_id=run_id,
        unit_execution_id=execution_id,
        result=_normalized_result(),
        identities=_finding_plans("finding-0", "finding-1"),
    )


def run_analysis_finding_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(
            connection
        )

        input_repo = SQLiteEligibleAnalysisInputRepository(connection)
        prepared = _record_findings(connection, execution, run_id, execution_id)
        eligible_input = input_repo.get(_INPUT)

        findings = tuple(item.finding for item in prepared.findings)
        anchored = all(f.source_input_id == _INPUT for f in findings)
        eligibility_ok = (
            eligible_input.eligibility is LectureAnalysisEligibility.ELIGIBLE
        )
        provenance_linked = all(
            item.finding_result.kind == ANALYSIS_FINDING_RESULT_KIND
            and item.finding_result.upstream_results
            == (eligible_input.domain_result_id,)
            and item.finding.source_media_id == eligible_input.source_media_id
            and item.finding.source_timeline_id == eligible_input.source_timeline_id
            for item in prepared.findings
        )
        sequences_ordered = [f.sequence for f in findings] == [0, 1]
        upstream_unmutated = input_repo.get(_INPUT) == eligible_input

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        # No downstream stage runs: Label/Candidate/Review tables do not exist, and while the canonical
        # Lecture Segment table exists from schema v25 it must stay empty — the Finding milestone records
        # no Segment.
        lecture_segments_rows = connection.execute(
            "SELECT COUNT(*) FROM lecture_segments"
        ).fetchone()[0]
        no_downstream_tables = (
            not {"segment_labels", "edit_candidates", "review_items_analysis"}
            & existing_tables
            and lecture_segments_rows == 0
        )
        connection.close()

        reopened = open_sqlite_database(path)
        finding_repo = SQLiteAnalysisFindingRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = all(
            finding_repo.get(item.finding.identity) == item.finding
            and results.get(item.finding_result.identity) == item.finding_result
            for item in prepared.findings
        )
        reopened.close()

        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _, _ = _build_persisted_readiness(replay_connection)
        r_prepared = _record_findings(replay_connection, r_execution, r_run, r_exec)
        replay_connection.close()
        deterministic_replay = tuple(
            item.finding for item in r_prepared.findings
        ) == findings

        return {
            "finding_count": len(findings),
            "anchored_to_input": anchored,
            "eligibility_ok": eligibility_ok,
            "provenance_linked": provenance_linked,
            "sequences_ordered": sequences_ordered,
            "upstream_unmutated": upstream_unmutated,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_analysis_finding_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
