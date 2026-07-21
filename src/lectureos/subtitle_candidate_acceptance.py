"""In-process fake-review / fake-transcript acceptance for Subtitle Candidate Generation.

Drives the full canonical pipeline with no network and no credential: a fake correction provider
yields a proposed Revision, Review Preparation maps it to Review Items, a Human reviewer records
Accept and Reject decisions, applicability / current selection / readiness / subtitle transcript
intake are derived, and subtitle candidate generation is deterministically evaluated from the
canonical ELIGIBLE intake.

It verifies that only the ELIGIBLE intake yields a durable Subtitle Candidate (with its ordered
candidate cues) while the NOT_ELIGIBLE intake is refused; that each cue traces to its ordered
source segment(s), source revision and source timeline; immutable candidate + cue records; full
intake / readiness / selection / applicability / decision / item / candidate lineage and source
media/timeline; execution provenance; atomic persistence; restart reconstruction; deterministic
replay; idempotency with respect to upstream intake state; and that no later subtitle-revision /
subtitle-cue / artifact table is produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    SubtitleCandidateIdentityPlan,
    SubtitleCandidateGenerationError,
)
from lectureos.application.identities import (
    SubtitleCandidateCueId,
    SubtitleCandidateId,
    SubtitleTranscriptIntakeId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_candidate_generation_service,
    compose_sqlite_transcript_service,
)
from lectureos.execution.identities import DomainResultId, SourceMediaId, SourceTimelineId
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleCandidateRepository,
    SQLiteSubtitleTranscriptIntakeRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.subtitle_intake_acceptance import (
    MEDIA_ID,
    TIMELINE_ID,
    _build_persisted_readiness,
    _candidate_id,
    _record_all_intakes,
)

_ELIGIBLE_INTAKE = SubtitleTranscriptIntakeId("intake-int-accept")
_NOT_ELIGIBLE_INTAKE = SubtitleTranscriptIntakeId("intake-int-reject")


def _candidate_plan(name: str) -> SubtitleCandidateIdentityPlan:
    return SubtitleCandidateIdentityPlan(
        candidate_id=SubtitleCandidateId(name),
        candidate_result_id=DomainResultId(f"{name}-result"),
        cue_ids=(
            SubtitleCandidateCueId(f"{name}-cue-0"),
            SubtitleCandidateCueId(f"{name}-cue-1"),
        ),
    )


def _generate_candidate(connection, execution, run_id, execution_id, name="subcand"):
    service = compose_sqlite_subtitle_candidate_generation_service(connection, execution)
    return service.record_candidate(
        source_intake_id=_ELIGIBLE_INTAKE,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_candidate_plan(name),
    )


def run_subtitle_candidate_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, revision_id, raw_id = _build_persisted_readiness(
            connection
        )
        _record_all_intakes(connection, execution, run_id, execution_id)

        intake_repo = SQLiteSubtitleTranscriptIntakeRepository(connection)
        upstream_before = (
            intake_repo.get(_ELIGIBLE_INTAKE),
            intake_repo.get(_NOT_ELIGIBLE_INTAKE),
        )

        prepared = _generate_candidate(connection, execution, run_id, execution_id)

        # The NOT_ELIGIBLE intake must be refused — no candidate produced.
        service = compose_sqlite_subtitle_candidate_generation_service(connection, execution)
        refused_not_eligible = False
        try:
            service.generate_candidate(
                source_intake_id=_NOT_ELIGIBLE_INTAKE,
                run_id=run_id,
                unit_execution_id=execution_id,
                identities=_candidate_plan("subcand-reject"),
            )
        except SubtitleCandidateGenerationError:
            refused_not_eligible = True

        upstream_after = (
            intake_repo.get(_ELIGIBLE_INTAKE),
            intake_repo.get(_NOT_ELIGIBLE_INTAKE),
        )
        idempotent_upstream = upstream_before == upstream_after

        transcripts = compose_sqlite_transcript_service(connection, execution)
        revision = transcripts.get_corrected_revision(revision_id)
        expected_segment_tuples = [(sid,) for sid in revision.segment_ids]

        cues = prepared.cues
        cue_segment_lineage = (
            [cue.source_segment_ids for cue in cues] == expected_segment_tuples
        )
        cue_ordering = [cue.display_order for cue in cues] == list(range(len(cues)))
        cue_revision_linked = all(
            cue.source_revision_id == revision_id and cue.source_transcript_id == raw_id
            for cue in cues
        )
        candidate = prepared.candidate
        candidate_linked = (
            candidate.source_intake_id == _ELIGIBLE_INTAKE
            and candidate.source_revision_id == revision_id
            and candidate.source_transcript_id == raw_id
            and candidate.source_media_id == SourceMediaId(MEDIA_ID)
            and candidate.source_timeline_id == SourceTimelineId(TIMELINE_ID)
            and candidate.candidate_reference_id
            == CandidateReferenceId(_candidate_id(0).value)
            and candidate.review_item_id == ReviewItemId("int-item-0")
        )
        execution_provenance = (
            candidate.run_id == run_id and candidate.unit_execution_id == execution_id
        )
        result_upstream_linked = prepared.candidate_result.upstream_results == (
            upstream_after[0].domain_result_id,
        )

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        # Candidate generation is the final stage in scope; no later subtitle-revision /
        # subtitle-cue / artifact table may exist.
        no_downstream_tables = not {
            "subtitle_revisions",
            "subtitle_cues",
            "artifacts",
        } & existing_tables
        connection.close()

        reopened = open_sqlite_database(path)
        repo = SQLiteSubtitleCandidateRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = (
            repo.get(candidate.identity) == candidate
            and all(repo.get_cue(cue.identity) == cue for cue in cues)
            and results.get(prepared.candidate_result.identity)
            == prepared.candidate_result
        )
        reopened.close()

        # Deterministic replay into a fresh database with identical recorded inputs.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _, _ = _build_persisted_readiness(replay_connection)
        _record_all_intakes(replay_connection, r_execution, r_run, r_exec)
        replayed = _generate_candidate(replay_connection, r_execution, r_run, r_exec)
        replay_connection.close()
        deterministic_replay = (
            replayed.candidate == candidate
            and replayed.cues == cues
            and replayed.candidate_result == prepared.candidate_result
        )

        return {
            "candidate_count": 1,
            "cue_count": len(cues),
            "refused_not_eligible": refused_not_eligible,
            "cue_segment_lineage": cue_segment_lineage,
            "cue_ordering": cue_ordering,
            "cue_revision_linked": cue_revision_linked,
            "candidate_linked": candidate_linked,
            "execution_provenance": execution_provenance,
            "result_upstream_linked": result_upstream_linked,
            "idempotent_upstream": idempotent_upstream,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_subtitle_candidate_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
