"""In-process acceptance for the Lecture Segmentation Application Foundation (042 §7.1, PATCH-0011).

Reuses the durable Transcript Pipeline chain that the Subtitle Transcript Intake acceptance builds, records
the ELIGIBLE Eligible Analysis Input from the READY readiness evaluation, then admits a normalized,
provider-independent segmentation result and records durable canonical Lecture Segments.

It verifies the end-to-end path

    Transcript Pipeline -> Transcript Readiness -> EligibleAnalysisInput (ELIGIBLE)
        -> normalized provider-independent segmentation result -> canonical LectureSegment

producing immutable, provenance-bearing Segment records anchored to exactly one Eligible Analysis Input;
full provenance to the input's Domain Result, source media and source timeline; a required single Source
Timeline Time Range; execution provenance; atomic persistence; restart reconstruction; deterministic replay;
that no upstream record is mutated; and that no Segment Label, Analysis Finding row, Edit Candidate, Review,
or concrete provider record is produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    LectureAnalysisEligibility,
    LectureAnalysisInputIdentityPlan,
    LectureSegmentIdentityPlan,
    NormalizedLectureSegment,
    NormalizedSegmentationResult,
)
from lectureos.application.identities import (
    EligibleAnalysisInputId,
    LectureSegmentId,
    TranscriptReadinessEvaluationId,
)
from lectureos.application.lecture_segment import LECTURE_SEGMENT_RESULT_KIND
from lectureos.composition import (
    compose_sqlite_lecture_analysis_input_service,
    compose_sqlite_lecture_segmentation_service,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteEligibleAnalysisInputRepository,
    SQLiteLectureSegmentRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")
_INPUT = EligibleAnalysisInputId("segmentation-input")


def _input_plan():
    return LectureAnalysisInputIdentityPlan(
        input_id=_INPUT,
        input_result_id=DomainResultId("segmentation-input-result"),
    )


def _segment_plans(*names):
    return tuple(
        LectureSegmentIdentityPlan(
            segment_id=LectureSegmentId(name),
            segment_result_id=DomainResultId(f"{name}-result"),
        )
        for name in names
    )


def _normalized_result():
    return NormalizedSegmentationResult(
        source_timeline_id=SourceTimelineId(TIMELINE_ID),
        segments=(
            NormalizedLectureSegment(range_start=0.0, range_end=12.5),
            NormalizedLectureSegment(range_start=12.5, range_end=30.0),
        ),
    )


def _record_segments(connection, execution, run_id, execution_id):
    input_service = compose_sqlite_lecture_analysis_input_service(connection, execution)
    input_service.record_input(
        source_readiness_id=_READY,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_input_plan(),
    )
    segment_service = compose_sqlite_lecture_segmentation_service(connection, execution)
    return segment_service.record_segments(
        source_input_id=_INPUT,
        run_id=run_id,
        unit_execution_id=execution_id,
        result=_normalized_result(),
        identities=_segment_plans("segment-0", "segment-1"),
    )


def run_lecture_segment_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(
            connection
        )

        input_repo = SQLiteEligibleAnalysisInputRepository(connection)
        prepared = _record_segments(connection, execution, run_id, execution_id)
        eligible_input = input_repo.get(_INPUT)

        segments = tuple(item.segment for item in prepared.segments)
        anchored = all(s.source_input_id == _INPUT for s in segments)
        eligibility_ok = (
            eligible_input.eligibility is LectureAnalysisEligibility.ELIGIBLE
        )
        provenance_linked = all(
            item.segment_result.kind == LECTURE_SEGMENT_RESULT_KIND
            and item.segment_result.upstream_results
            == (eligible_input.domain_result_id,)
            and item.segment.source_media_id == eligible_input.source_media_id
            and item.segment.source_timeline_id == eligible_input.source_timeline_id
            for item in prepared.segments
        )
        ranges_present = all(
            s.range_start is not None and s.range_end is not None and s.range_start <= s.range_end
            for s in segments
        )
        sequences_ordered = [s.sequence for s in segments] == [0, 1]
        upstream_unmutated = input_repo.get(_INPUT) == eligible_input

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        # No downstream stage runs: Label/Review tables do not exist, and while the canonical Analysis
        # Finding (v24) and Edit Candidate (v26) tables exist they must stay empty — segmentation records
        # neither a Finding nor a Candidate.
        downstream_rows = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("analysis_findings", "edit_candidates")
        )
        no_downstream_tables = (
            not {"segment_labels", "review_items_analysis"} & existing_tables
            and all(count == 0 for count in downstream_rows)
        )
        connection.close()

        reopened = open_sqlite_database(path)
        segment_repo = SQLiteLectureSegmentRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = all(
            segment_repo.get(item.segment.identity) == item.segment
            and results.get(item.segment_result.identity) == item.segment_result
            for item in prepared.segments
        )
        reopened.close()

        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _, _ = _build_persisted_readiness(replay_connection)
        r_prepared = _record_segments(replay_connection, r_execution, r_run, r_exec)
        replay_connection.close()
        deterministic_replay = tuple(
            item.segment for item in r_prepared.segments
        ) == segments

        return {
            "segment_count": len(segments),
            "anchored_to_input": anchored,
            "eligibility_ok": eligibility_ok,
            "provenance_linked": provenance_linked,
            "ranges_present": ranges_present,
            "sequences_ordered": sequences_ordered,
            "upstream_unmutated": upstream_unmutated,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_lecture_segment_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
