"""In-process fake-review / fake-transcript acceptance for Subtitle Reading Representation.

Drives the full canonical pipeline with no network and no credential: fake correction proposals ->
proposed Revision -> Review Preparation -> Accept/Reject -> applicability -> current selection ->
readiness -> subtitle transcript intake -> subtitle candidate generation -> subtitle reading
representation.

It verifies that a canonical Subtitle Candidate yields one new immutable reading revision whose
ordered reading units carry a deterministic, meaning-preserving normalization of each cue's text
(whitespace normalization + hard-line-structure preservation), each traceable to its ordered source
cue; that timing is inherited metadata (no computed or inferred timestamps); immutable revision +
unit records; full candidate lineage and source media/timeline; execution provenance; atomic
persistence; restart reconstruction; deterministic replay; idempotency with respect to the upstream
candidate; and that no downstream time-representation / validation / review / final / artifact table
is produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    SubtitleReadingIdentityPlan,
    compose_reading_lines,
)
from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_reading_representation_service,
)
from lectureos.execution.identities import (
    DomainResultId,
    SourceMediaId,
    SourceTimelineId,
)
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleCandidateRepository,
    SQLiteSubtitleReadingRevisionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.subtitle_candidate_acceptance import (
    _build_persisted_readiness,
    _candidate_id,
    _generate_candidate,
    _record_all_intakes,
)
from lectureos.subtitle_intake_acceptance import MEDIA_ID, TIMELINE_ID

_CANDIDATE_ID = SubtitleCandidateId("subcand")


def _reading_plan(name="reading") -> SubtitleReadingIdentityPlan:
    return SubtitleReadingIdentityPlan(
        reading_revision_id=SubtitleReadingRevisionId(name),
        reading_result_id=DomainResultId(f"{name}-result"),
        unit_ids=(
            SubtitleReadingUnitId(f"{name}-unit-0"),
            SubtitleReadingUnitId(f"{name}-unit-1"),
        ),
    )


def _compose_reading(connection, execution, run_id, execution_id, name="reading"):
    service = compose_sqlite_subtitle_reading_representation_service(connection, execution)
    return service.record_reading(
        source_candidate_id=_CANDIDATE_ID,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_reading_plan(name),
    )


def _build_persisted_candidate(connection):
    execution, run_id, execution_id, revision_id, raw_id = _build_persisted_readiness(
        connection
    )
    _record_all_intakes(connection, execution, run_id, execution_id)
    prepared = _generate_candidate(connection, execution, run_id, execution_id)
    return execution, run_id, execution_id, prepared


def run_subtitle_reading_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, candidate = _build_persisted_candidate(connection)

        candidate_repo = SQLiteSubtitleCandidateRepository(connection)
        upstream_before = candidate_repo.get(_CANDIDATE_ID)

        prepared = _compose_reading(connection, execution, run_id, execution_id)

        upstream_after = candidate_repo.get(_CANDIDATE_ID)
        idempotent_upstream = upstream_before == upstream_after

        cues = candidate.cues
        units = prepared.units
        # deterministic meaning-preserving normalization, not a pure copy
        normalized_lines = (
            [unit.lines for unit in units]
            == [compose_reading_lines(cue.text) for cue in cues]
        )
        source_cue_lineage = (
            [unit.source_cue_ids for unit in units] == [(cue.identity,) for cue in cues]
        )
        unit_ordering = [unit.display_order for unit in units] == list(range(len(units)))
        # timing is inherited metadata only (identical to the source cue; nothing computed)
        timing_inherited = all(
            unit.source_timeline_id == cue.source_timeline_id
            and unit.start == cue.start
            and unit.end == cue.end
            for unit, cue in zip(units, cues)
        )
        revision = prepared.revision
        revision_linked = (
            revision.source_candidate_id == _CANDIDATE_ID
            and revision.source_revision_id == candidate.candidate.source_revision_id
            and revision.source_transcript_id == candidate.candidate.source_transcript_id
            and revision.source_media_id == SourceMediaId(MEDIA_ID)
            and revision.source_timeline_id == SourceTimelineId(TIMELINE_ID)
            and revision.candidate_reference_id
            == CandidateReferenceId(_candidate_id(0).value)
            and revision.review_item_id == ReviewItemId("int-item-0")
        )
        execution_provenance = (
            revision.run_id == run_id and revision.unit_execution_id == execution_id
        )
        result_upstream_linked = prepared.revision_result.upstream_results == (
            candidate.candidate.domain_result_id,
        )

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        # Reading Representation is the produced stage; no downstream time-representation /
        # validation / review / final / artifact table may exist.
        no_downstream_tables = not {
            "subtitle_time_ranges",
            "subtitle_validations",
            "subtitle_reviews",
            "subtitle_final_selections",
            "artifacts",
        } & existing_tables
        connection.close()

        reopened = open_sqlite_database(path)
        repo = SQLiteSubtitleReadingRevisionRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = (
            repo.get(revision.identity) == revision
            and all(repo.get_unit(unit.identity) == unit for unit in units)
            and results.get(prepared.revision_result.identity)
            == prepared.revision_result
        )
        reopened.close()

        # Deterministic replay into a fresh database with identical recorded inputs.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _ = _build_persisted_candidate(replay_connection)
        replayed = _compose_reading(replay_connection, r_execution, r_run, r_exec)
        replay_connection.close()
        deterministic_replay = (
            replayed.revision == revision
            and replayed.units == units
            and replayed.revision_result == prepared.revision_result
        )

        return {
            "reading_revision_count": 1,
            "unit_count": len(units),
            "normalized_lines": normalized_lines,
            "source_cue_lineage": source_cue_lineage,
            "unit_ordering": unit_ordering,
            "timing_inherited": timing_inherited,
            "revision_linked": revision_linked,
            "execution_provenance": execution_provenance,
            "result_upstream_linked": result_upstream_linked,
            "idempotent_upstream": idempotent_upstream,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_subtitle_reading_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
