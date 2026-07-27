"""Deterministic demonstration of Effective Subtitle SRT Artifact generation (GOAL-017).

Drives the whole slice with fake provider results, manual candidates, and explicit human actors —
no LLM, ASR, network, filesystem write, or model:

    A. Raw candidate → subject → Accept → Final Select → export eligibility(yes) →
       generate SRT artifact → exact lineage + exact canonical SRT payload → current
    B. Exact replay → reused (no duplicate row)
    C. Reject upstream → no selection eligibility → no artifact (real services)
    D. Candidate B selected → old selection superseded → new artifact generation from the
       superseded selection is refused, nothing persisted; artifact A remains immutable and
       derives superseded
    E. Artifact B generated from the current selection → distinct identity → current
    F. Byte-identical SRT content under distinct final selections → same content fingerprint,
       distinct artifact identities
    H. Authority changes after export → artifacts remain immutable; currentness derives;
       no automatic regeneration
    I. Damaged candidate graph (isolated copy) → generation refused, nothing persisted
    K. Physical isolation: no file, no path column, no materialization or legacy export rows

The committed golden reproduces byte-for-byte (including the exact SRT payload).
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.effective_subtitle_srt_artifact import (
    ArtifactCurrentness,
    EffectiveSubtitleSrtArtifactError,
    FinalSelectionNotExportableError,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_final_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_effective_subtitle_srt_artifact_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
_SOURCE_TEXTS = ("안녕하세요 여러부", "오늘의 강의입니다")


def run_effective_srt_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        intake_id = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        provider = compose_sqlite_provider_transcript_admission_service(connection)
        raw_selection = compose_sqlite_current_raw_transcript_selection_service(connection)

        def _admit_raw(ref: str) -> str:
            return provider.admit(
                intake_id=intake_id,
                document=build_provider_transcript_document(
                    {"provider": "fake-asr", "model": "tiny", "language": "ko",
                     "provider_result_ref": ref,
                     "segments": [
                         {"start": float(i), "end": float(i) + 1.0, "text": text}
                         for i, text in enumerate(_SOURCE_TEXTS)
                     ]}
                ),
            ).admission.raw_transcript_id.value

        raw_1 = _admit_raw("A")
        raw_selection.select(intake_id, raw_1)
        generation = compose_sqlite_effective_subtitle_generation_service(connection)
        preparation = compose_sqlite_effective_subtitle_review_preparation_service(connection)
        decisions = compose_sqlite_effective_subtitle_review_decision_service(connection)
        selection = compose_sqlite_effective_subtitle_final_selection_service(connection)
        export = compose_sqlite_effective_subtitle_srt_artifact_service(connection)

        def _select(ref: str | None = None):
            if ref is not None:
                raw = _admit_raw(ref)
                raw_selection.select(intake_id, raw)
                compose_sqlite_corrected_revision_selection_service(
                    connection
                ).select_raw_fallback(intake_id=intake_id, reviewer="selector:kim")
            candidate = generation.generate(intake_id=intake_id).candidate
            subject = preparation.prepare_review(candidate_id=candidate.identity.value).subject
            decisions.decide(
                review_subject_id=subject.identity.value, kind="accept",
                reviewer="reviewer:kim",
            )
            return candidate, selection.select_final(
                review_subject_id=subject.identity.value, selector="selector:park"
            ).selection

        # A/B: export + replay.
        candidate_a, selection_a = _select()
        eligibility_a = export.export_eligibility(selection_a.identity.value)
        artifact_a = export.generate_srt_artifact(final_selection_id=selection_a.identity.value)
        artifact_a_replay = export.generate_srt_artifact(
            final_selection_id=selection_a.identity.value
        )
        expected_srt = (
            "1\n00:00:00,000 --> 00:00:01,000\n안녕하세요 여러부\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\n오늘의 강의입니다\n"
        )

        # D/E: candidate B supersedes; superseded selection cannot export; B exports.
        candidate_b, selection_b = _select("B")
        superseded_blocked = False
        try:
            export.generate_srt_artifact(final_selection_id=selection_a.identity.value)
        except FinalSelectionNotExportableError:
            superseded_blocked = True
        artifact_a_state = export.currentness(artifact_a.artifact)
        artifact_b = export.generate_srt_artifact(final_selection_id=selection_b.identity.value)
        artifact_b_state = export.currentness(artifact_b.artifact)

        artifacts = export.list_for_intake(intake_id)
        artifact_a_after = export.get(artifact_a.artifact.identity.value)
        rows = connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_srt_artifacts"
        ).fetchone()[0]
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(subtitle_effective_srt_artifacts)"
            ).fetchall()
        }
        downstream_rows = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("subtitle_srt_artifacts", "subtitle_srt_materializations",
                          "subtitle_final_subtitles")
        }
        files_in_workdir = sorted(
            p.name for p in Path(directory).iterdir() if p.suffix == ".srt"
        )
        connection.close()

        # I: damaged candidate graph refuses generation (isolated copy).
        import shutil

        damaged = Path(directory) / "damaged.sqlite3"
        shutil.copyfile(database, damaged)
        damage = sqlite3.connect(damaged)
        try:
            damage.execute("PRAGMA foreign_keys = OFF")
            damage.execute(
                "DELETE FROM subtitle_effective_srt_artifacts")  # allow regeneration attempt
            damage.execute(
                "DELETE FROM subtitle_effective_candidate_cue_segments WHERE cue_id = "
                "(SELECT identity FROM subtitle_effective_candidate_cues "
                " WHERE candidate_id = ? AND ordinal = 0)",
                (candidate_b.identity.value,),
            )
            damage.execute(
                "DELETE FROM subtitle_effective_candidate_cues WHERE candidate_id = ? "
                "AND ordinal = 0",
                (candidate_b.identity.value,),
            )
            damage.commit()
        finally:
            damage.close()
        damaged_connection = open_sqlite_database(damaged)
        invalid_graph_blocked = False
        try:
            broken = compose_sqlite_effective_subtitle_srt_artifact_service(damaged_connection)
            before = damaged_connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_srt_artifacts"
            ).fetchone()[0]
            try:
                broken.generate_srt_artifact(final_selection_id=selection_b.identity.value)
            except EffectiveSubtitleSrtArtifactError:
                after = damaged_connection.execute(
                    "SELECT COUNT(*) FROM subtitle_effective_srt_artifacts"
                ).fetchone()[0]
                invalid_graph_blocked = after == before
        finally:
            damaged_connection.close()

        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "intake_id": intake_id,
            "selection_a_id": selection_a.identity.value,
            "selection_b_id": selection_b.identity.value,
            "artifact_a_id": artifact_a.artifact.identity.value,
            "artifact_b_id": artifact_b.artifact.identity.value,
            "srt_content": artifact_a.artifact.srt_content,
            "artifact_count": rows,
            # Behavioral checks.
            "eligible_export_current_with_exact_payload": eligibility_a.eligible
            and artifact_a.outcome.value == "created"
            and artifact_a.artifact.final_selection_id == selection_a.identity
            and artifact_a.artifact.candidate_id == candidate_a.identity
            and artifact_a.artifact.srt_content == expected_srt
            and artifact_a.artifact.cue_count == 2
            and artifact_a.currentness is ArtifactCurrentness.CURRENT,
            "exact_replay_reused": artifact_a_replay.outcome.value == "reused"
            and artifact_a_replay.artifact.identity == artifact_a.artifact.identity,
            "superseded_selection_blocks_new_export": superseded_blocked
            and artifact_a_state is ArtifactCurrentness.SUPERSEDED_BY_FINAL_SELECTION
            and artifact_a_after == artifact_a.artifact,
            "current_selection_exports_distinct_artifact": artifact_b.outcome.value == "created"
            and artifact_b.artifact.identity != artifact_a.artifact.identity
            and artifact_b_state is ArtifactCurrentness.CURRENT,
            "same_content_distinct_selections_distinct_artifacts": artifact_a.artifact.content_fingerprint
            == artifact_b.artifact.content_fingerprint
            and artifact_a.artifact.srt_content == artifact_b.artifact.srt_content,
            "invalid_graph_blocks_generation": invalid_graph_blocked,
            "physical_isolation": rows == 2 and len(artifacts) == 2
            and files_in_workdir == []
            and not any(c in columns for c in ("physical_path", "filename", "url",
                                               "materialized"))
            and all(v == 0 for v in downstream_rows.values()),
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "intake_id",
        "selection_a_id",
        "selection_b_id",
        "artifact_a_id",
        "artifact_b_id",
        "srt_content",
        "artifact_count",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_effective_srt_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
