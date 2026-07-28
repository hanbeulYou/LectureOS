"""Deterministic release demonstration of the Effective Subtitle Pipeline v1 (GOAL-021).

One connected scenario over production services and real persistence — no LLM, ASR, network, or
model; the only filesystem writes are the explicit materialization and delivery beneath isolated
approved roots:

    intake → candidate → review subject → Human Accept → final selection → logical SRT artifact
           → physical materialization → verified delivery → publication → derived availability

Every stage is an EXPLICIT command (nothing chains automatically), every cross-stage edge is
verified through typed lineage, and the exact canonical SRT bytes are proven identical across the
logical artifact, the materialized file, and the delivered file. Legacy tables stay untouched and
the repository validates healthy. The committed golden reproduces byte-for-byte; no absolute
paths, timestamps, or machine-specific data appear in the summary.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_srt_delivery_service,
    compose_sqlite_effective_srt_materialization_service,
    compose_sqlite_effective_srt_publication_service,
    compose_sqlite_effective_subtitle_final_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_effective_subtitle_srt_artifact_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import SQLITE_SCHEMA_VERSION, initialize_sqlite_database
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
_SOURCE_TEXTS = ("안녕하세요 여러부", "오늘의 강의입니다")

_EFFECTIVE_STAGE_TABLES = (
    "subtitle_effective_candidates",
    "subtitle_effective_review_subjects",
    "subtitle_effective_review_decisions",
    "subtitle_effective_final_selections",
    "subtitle_effective_srt_artifacts",
    "subtitle_effective_srt_materializations",
    "subtitle_effective_srt_materialization_outcomes",
    "subtitle_effective_srt_delivery_intents",
    "subtitle_effective_srt_delivery_outcomes",
    "subtitle_effective_srt_publications",
)

_LEGACY_TABLES = (
    "subtitle_final_subtitles",
    "subtitle_srt_artifacts",
    "subtitle_srt_materializations",
)


def run_effective_subtitle_release_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        storage_root = Path(directory) / "storage"
        delivery_root = Path(directory) / "delivered"
        storage_root.mkdir()
        delivery_root.mkdir()
        connection = initialize_sqlite_database(database)

        # Stage 0 — Effective Transcript Source Intake (prerequisite contracts).
        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        intake_id = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake_id,
            document=build_provider_transcript_document(
                {"provider": "fake-asr", "model": "tiny", "language": "ko",
                 "provider_result_ref": "A",
                 "segments": [
                     {"start": float(i), "end": float(i) + 1.0, "text": text}
                     for i, text in enumerate(_SOURCE_TEXTS)
                 ]}
            ),
        ).admission.raw_transcript_id.value
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            intake_id, raw
        )

        def _rows(table: str) -> int:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        # No effective-subtitle stage exists before its explicit command.
        no_rows_before_commands = all(_rows(t) == 0 for t in _EFFECTIVE_STAGE_TABLES)

        # Stage 1 — explicit Candidate generation (GOAL-013).
        candidate = compose_sqlite_effective_subtitle_generation_service(connection).generate(
            intake_id=intake_id
        ).candidate
        # Stage 2 — explicit Review Subject preparation (GOAL-014).
        subject = compose_sqlite_effective_subtitle_review_preparation_service(
            connection
        ).prepare_review(candidate_id=candidate.identity.value).subject
        no_decision_after_preparation = _rows("subtitle_effective_review_decisions") == 0
        # Stage 3 — explicit Human Accept (GOAL-015).
        decision = compose_sqlite_effective_subtitle_review_decision_service(connection).decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        ).decision
        no_selection_after_accept = _rows("subtitle_effective_final_selections") == 0
        # Stage 4 — explicit Final Selection (GOAL-016).
        selection = compose_sqlite_effective_subtitle_final_selection_service(
            connection
        ).select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        ).selection
        no_artifact_after_selection = _rows("subtitle_effective_srt_artifacts") == 0
        # Stage 5 — explicit logical SRT Artifact (GOAL-017).
        artifact = compose_sqlite_effective_subtitle_srt_artifact_service(
            connection
        ).generate_srt_artifact(final_selection_id=selection.identity.value).artifact
        no_materialization_after_artifact = (
            _rows("subtitle_effective_srt_materializations") == 0
        )
        # Stage 6 — explicit physical Materialization (GOAL-018).
        materializer = compose_sqlite_effective_srt_materialization_service(
            connection, str(storage_root)
        )
        materialization_record = materializer.materialize(
            artifact_id=artifact.identity.value, relative_location="release/v1.srt"
        )
        materialization = materialization_record.materialization
        no_delivery_after_materialization = (
            _rows("subtitle_effective_srt_delivery_intents") == 0
        )
        # Stage 7 — explicit verified Delivery (GOAL-019).
        deliverer = compose_sqlite_effective_srt_delivery_service(
            connection, str(storage_root), str(delivery_root)
        )
        delivery_record = deliverer.deliver(
            materialization_id=materialization.identity.value,
            relative_location="published/v1.srt",
        )
        delivery = delivery_record.delivery
        no_publication_after_delivery = (
            _rows("subtitle_effective_srt_publications") == 0
        )
        # Stage 8 — explicit Publication (GOAL-020) and derived Availability.
        publisher = compose_sqlite_effective_srt_publication_service(
            connection, str(delivery_root)
        )
        publication = publisher.publish(
            delivery_id=delivery.identity.value, publisher="publisher:kim",
            rationale="Effective Subtitle Pipeline v1 release",
        ).publication
        availability = publisher.availability(intake_id)

        # Cross-stage typed lineage: every transition binds the exact upstream identity.
        canonical_bytes = artifact.srt_content.encode("utf-8")
        materialized_bytes = (storage_root / "release/v1.srt").read_bytes()
        delivered_bytes = (delivery_root / "published/v1.srt").read_bytes()
        lineage_ok = (
            candidate.transcript_source_intake_id.value == intake_id
            and subject.candidate_id == candidate.identity
            and decision.review_subject_id == subject.identity
            and selection.transcript_source_intake_id.value == intake_id
            and selection.candidate_id == candidate.identity
            and selection.review_subject_id == subject.identity
            and selection.supporting_decision_id == decision.identity
            and artifact.transcript_source_intake_id.value == intake_id
            and artifact.final_selection_id == selection.identity
            and artifact.candidate_id == candidate.identity
            and materialization.artifact_id == artifact.identity
            and delivery.materialization_id == materialization.identity
            and delivery.artifact_id == artifact.identity
            and publication.transcript_source_intake_id.value == intake_id
            and publication.target_delivery_id == delivery.identity
            and publication.target_artifact_id == artifact.identity
        )
        exactly_one_row_per_stage = all(
            _rows(t) == 1 for t in _EFFECTIVE_STAGE_TABLES
        )
        legacy_rows = {table: _rows(table) for table in _LEGACY_TABLES}
        connection.close()
        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived release facts (golden).
            "release": "Effective Subtitle Pipeline v1",
            "schema_version": SQLITE_SCHEMA_VERSION,
            "intake_id": intake_id,
            "candidate_id": candidate.identity.value,
            "review_subject_id": subject.identity.value,
            "decision_id": decision.identity.value,
            "decision_kind": decision.kind.value,
            "final_selection_id": selection.identity.value,
            "artifact_id": artifact.identity.value,
            "artifact_fingerprint": artifact.content_fingerprint,
            "srt_payload": artifact.srt_content,
            "materialization_id": materialization.identity.value,
            "materialization_state": materialization_record.state.value,
            "materialization_location": materialization.relative_location,
            "delivery_id": delivery.identity.value,
            "delivery_state": delivery_record.state.value,
            "delivery_location": delivery.relative_location,
            "publication_id": publication.identity.value,
            "publication_kind": publication.kind.value,
            "availability": availability.value,
            "legacy_row_counts": legacy_rows,
            "repository_validation": validation.health.value,
            # Behavioral checks.
            "every_stage_requires_explicit_command": no_rows_before_commands
            and no_decision_after_preparation
            and no_selection_after_accept
            and no_artifact_after_selection
            and no_materialization_after_artifact
            and no_delivery_after_materialization
            and no_publication_after_delivery,
            "typed_lineage_connects_every_stage": lineage_ok,
            "exact_bytes_end_to_end": materialized_bytes == canonical_bytes
            and delivered_bytes == canonical_bytes
            and delivery.expected_payload_fingerprint == artifact.content_fingerprint,
            "exactly_one_record_per_stage": exactly_one_row_per_stage,
            "no_legacy_rows_written": all(v == 0 for v in legacy_rows.values()),
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "release",
        "schema_version",
        "intake_id",
        "candidate_id",
        "review_subject_id",
        "decision_id",
        "decision_kind",
        "final_selection_id",
        "artifact_id",
        "artifact_fingerprint",
        "srt_payload",
        "materialization_id",
        "materialization_state",
        "materialization_location",
        "delivery_id",
        "delivery_state",
        "delivery_location",
        "publication_id",
        "publication_kind",
        "availability",
        "legacy_row_counts",
        "repository_validation",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_effective_subtitle_release_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
