"""In-process fake-review / fake-transcript acceptance for Subtitle Time Representation.

Drives the full canonical pipeline with no network and no credential through subtitle candidate
generation and reading representation, then composes a subtitle time revision that anchors each
reading unit's authoritative display Time Range to the Source-Timeline basis of its source cues.

It verifies the durable one-to-one pipeline (each timed unit ANCHORED to its cue range), a durable
merged-unit case (one reading unit over two source cues anchors the minimal enclosing span), and the
UNRESOLVED derivation for an untimed basis; immutable revision + unit records; full candidate lineage
and source media/timeline; execution provenance; atomic persistence; restart reconstruction;
deterministic replay; idempotency with respect to the upstream reading revision; and that no
downstream validation / review / final / artifact table is produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    SubtitleReadingRevision,
    SubtitleReadingUnit,
    SubtitleTimeIdentityPlan,
    SubtitleTimingStatus,
    anchor_source_timeline_extent,
)
from lectureos.application.identities import (
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_time_representation_service,
)
from lectureos.execution.identities import DomainResultId, SourceMediaId, SourceTimelineId
from lectureos.execution.models import DomainResultReference
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleCandidateRepository,
    SQLiteSubtitleReadingCommandPersistence,
    SQLiteSubtitleReadingRevisionRepository,
    SQLiteSubtitleTimeRevisionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.subtitle_intake_acceptance import MEDIA_ID, TIMELINE_ID
from lectureos.subtitle_reading_acceptance import (
    _build_persisted_candidate,
    _compose_reading,
)

_READING_ID = SubtitleReadingRevisionId("reading")
_MERGED_READING_ID = SubtitleReadingRevisionId("merged-reading")


def _time_plan(name, units) -> SubtitleTimeIdentityPlan:
    return SubtitleTimeIdentityPlan(
        time_revision_id=SubtitleTimeRevisionId(name),
        time_result_id=DomainResultId(f"{name}-result"),
        timed_unit_ids=tuple(SubtitleTimedUnitId(f"{name}-unit-{i}") for i in range(units)),
    )


def _persist_merged_reading(connection, reading_revision, candidate):
    """Persist a durable reading revision whose single unit merges both source cues."""

    cue_ids = candidate.candidate.cue_ids
    merged_unit = SubtitleReadingUnit(
        identity=SubtitleReadingUnitId("merged-unit"),
        reading_revision_id=_MERGED_READING_ID,
        source_cue_ids=cue_ids,
        source_transcript_id=reading_revision.source_transcript_id,
        source_revision_id=reading_revision.source_revision_id,
        lines=("merged reading unit",),
        display_order=0,
    )
    merged_revision = SubtitleReadingRevision(
        identity=_MERGED_READING_ID,
        domain_result_id=DomainResultId("merged-reading-result"),
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
        unit_ids=(merged_unit.identity,),
        run_id=reading_revision.run_id,
        unit_execution_id=reading_revision.unit_execution_id,
        sequence=0,
        reason="merged reading revision for time acceptance",
    )
    merged_result = DomainResultReference(
        identity=merged_revision.domain_result_id,
        kind="subtitle_reading_revision",
        source_media=reading_revision.source_media_id,
        source_timeline=reading_revision.source_timeline_id,
        upstream_results=(candidate.candidate.domain_result_id,),
    )
    SQLiteSubtitleReadingCommandPersistence(connection).persist_subtitle_reading(
        revision=merged_revision, units=(merged_unit,), revision_result=merged_result
    )


def run_subtitle_time_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, candidate = _build_persisted_candidate(connection)
        reading = _compose_reading(connection, execution, run_id, execution_id)

        candidate_repo = SQLiteSubtitleCandidateRepository(connection)
        expected_cue_ranges = [
            (candidate_repo.get_cue(cid).start, candidate_repo.get_cue(cid).end)
            for cid in candidate.candidate.cue_ids
        ]

        reading_repo = SQLiteSubtitleReadingRevisionRepository(connection)
        upstream_before = reading_repo.get(_READING_ID)

        service = compose_sqlite_subtitle_time_representation_service(connection, execution)
        prepared = service.record_timing(
            source_reading_revision_id=_READING_ID,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_time_plan("time", 2),
        )

        upstream_after = reading_repo.get(_READING_ID)
        idempotent_upstream = upstream_before == upstream_after

        units = prepared.units
        all_anchored = all(u.timing_status is SubtitleTimingStatus.ANCHORED for u in units)
        # one-to-one units anchor to their own cue range (carry-through of the source-timeline basis)
        one_to_one_anchored = (
            [(u.start, u.end) for u in units] == expected_cue_ranges
        )
        unit_ordering = [u.display_order for u in units] == list(range(len(units)))
        reading_unit_linked = [u.source_reading_unit_id for u in units] == list(
            reading.revision.unit_ids
        )
        revision = prepared.revision
        revision_linked = (
            revision.source_reading_revision_id == _READING_ID
            and revision.source_candidate_id == candidate.candidate.identity
            and revision.source_media_id == SourceMediaId(MEDIA_ID)
            and revision.source_timeline_id == SourceTimelineId(TIMELINE_ID)
            and revision.candidate_reference_id == reading.revision.candidate_reference_id
            and revision.review_item_id == ReviewItemId("int-item-0")
        )
        execution_provenance = (
            revision.run_id == run_id and revision.unit_execution_id == execution_id
        )
        result_upstream_linked = prepared.revision_result.upstream_results == (
            reading.revision.domain_result_id,
        )

        # Durable merged-unit proof: one reading unit over both source cues anchors the minimal
        # enclosing source-timeline span.
        _persist_merged_reading(connection, reading.revision, candidate)
        merged_prepared = service.record_timing(
            source_reading_revision_id=_MERGED_READING_ID,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_time_plan("merged-time", 1),
        )
        merged_unit = merged_prepared.units[0]
        expected_span = (
            min(r[0] for r in expected_cue_ranges),
            max(r[1] for r in expected_cue_ranges),
        )
        merged_span_anchored = (
            merged_unit.timing_status is SubtitleTimingStatus.ANCHORED
            and (merged_unit.start, merged_unit.end) == expected_span
        )

        # UNRESOLVED derivation for an untimed basis (deterministic, provider-free).
        sample_cue = candidate_repo.get_cue(candidate.candidate.cue_ids[0])
        untimed_cue = type(sample_cue)(
            identity=sample_cue.identity,
            candidate_id=sample_cue.candidate_id,
            source_transcript_id=sample_cue.source_transcript_id,
            source_revision_id=sample_cue.source_revision_id,
            source_segment_ids=sample_cue.source_segment_ids,
            text=sample_cue.text,
            display_order=sample_cue.display_order,
            source_timeline_id=None,
            start=None,
            end=None,
        )
        unresolved_status, _, _, _ = anchor_source_timeline_extent((untimed_cue,))
        unresolved_derivation = unresolved_status is SubtitleTimingStatus.UNRESOLVED

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        # Time Representation is the produced stage; no downstream validation / review / final /
        # artifact table may exist.
        no_downstream_tables = not {
            "subtitle_structural_validations",
            "subtitle_reviews",
            "subtitle_final_selections",
            "artifacts",
        } & existing_tables
        connection.close()

        reopened = open_sqlite_database(path)
        repo = SQLiteSubtitleTimeRevisionRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = (
            repo.get(revision.identity) == revision
            and all(repo.get_unit(u.identity) == u for u in units)
            and results.get(prepared.revision_result.identity) == prepared.revision_result
            and repo.get_unit(merged_unit.identity) == merged_unit
        )
        reopened.close()

        # Deterministic replay of the one-to-one composition into a fresh database.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _ = _build_persisted_candidate(replay_connection)
        _compose_reading(replay_connection, r_execution, r_run, r_exec)
        r_service = compose_sqlite_subtitle_time_representation_service(
            replay_connection, r_execution
        )
        replayed = r_service.record_timing(
            source_reading_revision_id=_READING_ID,
            run_id=r_run,
            unit_execution_id=r_exec,
            identities=_time_plan("time", 2),
        )
        replay_connection.close()
        deterministic_replay = (
            replayed.revision == revision
            and replayed.units == units
            and replayed.revision_result == prepared.revision_result
        )

        return {
            "time_revision_count": 1,
            "unit_count": len(units),
            "all_anchored": all_anchored,
            "one_to_one_anchored": one_to_one_anchored,
            "merged_span_anchored": merged_span_anchored,
            "unresolved_derivation": unresolved_derivation,
            "unit_ordering": unit_ordering,
            "reading_unit_linked": reading_unit_linked,
            "revision_linked": revision_linked,
            "execution_provenance": execution_provenance,
            "result_upstream_linked": result_upstream_linked,
            "idempotent_upstream": idempotent_upstream,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_subtitle_time_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
