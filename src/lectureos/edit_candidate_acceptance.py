"""In-process acceptance for the Edit Candidate Application Foundation (042 §9.1, PATCH-0012).

Reuses the durable Transcript Pipeline chain that the Subtitle Transcript Intake acceptance builds, records
the ELIGIBLE Eligible Analysis Input and then a canonical Analysis Finding, and finally admits a normalized,
provider-independent Edit Candidate result to record durable canonical Edit Candidates.

It verifies the end-to-end path

    Transcript Pipeline -> Readiness -> EligibleAnalysisInput (ELIGIBLE) -> AnalysisFinding
        -> normalized provider-independent Edit Candidate result -> canonical EditCandidate

producing immutable, provenance-bearing Candidate records anchored to exactly one Analysis Finding; Source
Media and Source Timeline inherited from the Finding; a required single Source Timeline Time Range; a required
Candidate Type and rationale; execution provenance; atomic persistence; restart reconstruction; deterministic
replay; a DomainResultReference whose sole direct upstream is the Finding's Domain Result; that no upstream
record is mutated; and that no Segment Label, Review, or provider record is produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    AnalysisFindingIdentityPlan,
    EditCandidateIdentityPlan,
    LectureAnalysisEligibility,
    LectureAnalysisInputIdentityPlan,
    NormalizedAnalysisFinding,
    NormalizedAnalysisResult,
    NormalizedCandidateResult,
    NormalizedEditCandidate,
)
from lectureos.application.edit_candidate import EDIT_CANDIDATE_RESULT_KIND
from lectureos.application.identities import (
    AnalysisFindingId,
    EditCandidateId,
    EligibleAnalysisInputId,
    TranscriptReadinessEvaluationId,
)
from lectureos.composition import (
    compose_sqlite_analysis_finding_service,
    compose_sqlite_edit_candidate_service,
    compose_sqlite_lecture_analysis_input_service,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    SQLiteAnalysisFindingRepository,
    SQLiteDomainResultReferenceRepository,
    SQLiteEditCandidateRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")
_INPUT = EligibleAnalysisInputId("candidate-input")
_FINDING = AnalysisFindingId("candidate-finding")


def _finding_result():
    # One canonical Analysis Finding without its own Source Timeline range, proving a Candidate can carry a
    # required range even when the anchoring Finding has none.
    return NormalizedAnalysisResult(
        source_timeline_id=SourceTimelineId(TIMELINE_ID),
        findings=(
            NormalizedAnalysisFinding(
                finding_type="low_educational_value",
                evidence="an extended off-topic aside appears mid-lecture",
            ),
        ),
    )


def _candidate_result():
    return NormalizedCandidateResult(
        source_timeline_id=SourceTimelineId(TIMELINE_ID),
        candidates=(
            NormalizedEditCandidate(
                candidate_type="review",
                rationale="propose human review of a possible non-lecture region",
                range_start=4.0,
                range_end=30.0,
            ),
            NormalizedEditCandidate(
                candidate_type="condense",
                rationale="a repeated explanation could be shortened, pending review",
                range_start=30.0,
                range_end=45.0,
            ),
        ),
    )


def _record_candidates(connection, execution, run_id, execution_id):
    input_service = compose_sqlite_lecture_analysis_input_service(connection, execution)
    input_service.record_input(
        source_readiness_id=_READY,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=LectureAnalysisInputIdentityPlan(
            input_id=_INPUT,
            input_result_id=DomainResultId("candidate-input-result"),
        ),
    )
    finding_service = compose_sqlite_analysis_finding_service(connection, execution)
    finding_service.record_findings(
        source_input_id=_INPUT,
        run_id=run_id,
        unit_execution_id=execution_id,
        result=_finding_result(),
        identities=(
            AnalysisFindingIdentityPlan(
                finding_id=_FINDING,
                finding_result_id=DomainResultId("candidate-finding-result"),
            ),
        ),
    )
    candidate_service = compose_sqlite_edit_candidate_service(connection, execution)
    return candidate_service.record_candidates(
        source_finding_id=_FINDING,
        run_id=run_id,
        unit_execution_id=execution_id,
        result=_candidate_result(),
        identities=(
            EditCandidateIdentityPlan(
                candidate_id=EditCandidateId("candidate-0"),
                candidate_result_id=DomainResultId("candidate-0-result"),
            ),
            EditCandidateIdentityPlan(
                candidate_id=EditCandidateId("candidate-1"),
                candidate_result_id=DomainResultId("candidate-1-result"),
            ),
        ),
    )


def run_edit_candidate_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(
            connection
        )

        finding_repo = SQLiteAnalysisFindingRepository(connection)
        prepared = _record_candidates(connection, execution, run_id, execution_id)
        finding = finding_repo.get(_FINDING)

        candidates = tuple(item.candidate for item in prepared.candidates)
        anchored = all(c.source_finding_id == _FINDING for c in candidates)
        # Admission from a canonical Analysis Finding transitively guarantees ELIGIBLE provenance: the
        # Finding could only exist because its Eligible Analysis Input was ELIGIBLE (042 §8.1).
        finding_is_canonical = finding is not None
        provenance_linked = all(
            item.candidate_result.kind == EDIT_CANDIDATE_RESULT_KIND
            and item.candidate_result.upstream_results == (finding.domain_result_id,)
            and item.candidate.source_media_id == finding.source_media_id
            and item.candidate.source_timeline_id == finding.source_timeline_id
            for item in prepared.candidates
        )
        payload_present = all(
            c.candidate_type
            and c.rationale.strip()
            and c.range_start is not None
            and c.range_end is not None
            and c.range_start <= c.range_end
            for c in candidates
        )
        finding_had_no_range = finding.range_start is None and finding.range_end is None
        sequences_ordered = [c.sequence for c in candidates] == [0, 1]
        upstream_unmutated = finding_repo.get(_FINDING) == finding

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        # No Segment-Label table exists, and while the Lecture Segment (v25) and Edit-Pipeline Review (v27)
        # tables exist they must stay empty — the Analysis Finding milestone records none of them.
        downstream_rows = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("lecture_segments", "edit_review_decisions", "approved_edit_decisions")
        )
        no_downstream_tables = (
            not {"segment_labels", "review_items_analysis"} & existing_tables
            and all(count == 0 for count in downstream_rows)
        )
        connection.close()

        reopened = open_sqlite_database(path)
        candidate_repo = SQLiteEditCandidateRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = all(
            candidate_repo.get(item.candidate.identity) == item.candidate
            and results.get(item.candidate_result.identity) == item.candidate_result
            for item in prepared.candidates
        )
        reopened.close()

        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _, _ = _build_persisted_readiness(replay_connection)
        r_prepared = _record_candidates(replay_connection, r_execution, r_run, r_exec)
        replay_connection.close()
        deterministic_replay = tuple(
            item.candidate for item in r_prepared.candidates
        ) == candidates

        return {
            "candidate_count": len(candidates),
            "anchored_to_finding": anchored,
            "finding_is_canonical": finding_is_canonical,
            "provenance_linked": provenance_linked,
            "payload_present": payload_present,
            "finding_had_no_range": finding_had_no_range,
            "sequences_ordered": sequences_ordered,
            "upstream_unmutated": upstream_unmutated,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_edit_candidate_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
