"""Deterministic demonstration of Effective SRT Physical Materialization (GOAL-018).

Drives the whole slice with fake provider results and explicit human actors — no LLM, ASR,
network, or model; the only filesystem writes land beneath an isolated approved Storage Root:

    1. First materialization: exact canonical bytes (UTF-8, LF, no BOM) at the default location
    2. Replay: same artifact/location/payload → reused, no rewrite, no new record
    3. Existing different file without --overwrite → honest FAILED outcome, file untouched
    4. Explicit overwrite → new append-only write event replaces the file
    5. Deleted physical file → records immutable; a new explicit act re-realizes the payload
    6. A superseded (historical) artifact remains materializable
    7. Distinct artifacts materialize side by side in one root
    8. Invalid (escaping) path → refused
    9. Repository validation stays healthy throughout (missing files are never corruption)
   10. Legacy isolation: no legacy materialization rows

The committed golden reproduces byte-for-byte.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.effective_srt_materialization import (
    EffectiveSrtMaterializationError,
    MaterializationState,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_srt_materialization_service,
    compose_sqlite_effective_subtitle_final_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_effective_subtitle_srt_artifact_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
_SOURCE_TEXTS = ("안녕하세요 여러부", "오늘의 강의입니다")


def run_effective_materialize_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        storage_root = Path(directory) / "out"
        storage_root.mkdir()
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

        generation = compose_sqlite_effective_subtitle_generation_service(connection)
        preparation = compose_sqlite_effective_subtitle_review_preparation_service(connection)
        decisions = compose_sqlite_effective_subtitle_review_decision_service(connection)
        selection = compose_sqlite_effective_subtitle_final_selection_service(connection)
        export = compose_sqlite_effective_subtitle_srt_artifact_service(connection)
        materializer = compose_sqlite_effective_srt_materialization_service(
            connection, str(storage_root)
        )

        def _artifact(ref: str | None = None):
            if ref is None:
                raw = _admit_raw("A")
                raw_selection.select(intake_id, raw)
            else:
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
            sel = selection.select_final(
                review_subject_id=subject.identity.value, selector="selector:park"
            ).selection
            return export.generate_srt_artifact(final_selection_id=sel.identity.value).artifact

        artifact_a = _artifact()

        # 1: first materialization at the default location; exact canonical bytes.
        first = materializer.materialize(artifact_id=artifact_a.identity.value)
        first_path = storage_root / first.materialization.relative_location
        first_bytes = first_path.read_bytes()

        # 2: replay — reused, no rewrite, no new record.
        replay = materializer.materialize(artifact_id=artifact_a.identity.value)

        # 3: an existing DIFFERENT file at an explicit location refuses without overwrite —
        # the act is recorded as an honest FAILED outcome and the file is untouched.
        foreign_location = "manual/lecture.srt"
        (storage_root / "manual").mkdir()
        (storage_root / foreign_location).write_bytes("다른 내용\n".encode("utf-8"))
        blocked = materializer.materialize(
            artifact_id=artifact_a.identity.value, relative_location=foreign_location
        )
        foreign_untouched = (
            storage_root / foreign_location
        ).read_bytes() == "다른 내용\n".encode("utf-8")

        # 4: explicit overwrite replaces the file as a NEW append-only write event.
        overwritten = materializer.materialize(
            artifact_id=artifact_a.identity.value,
            relative_location=foreign_location,
            overwrite=True,
        )
        overwritten_bytes = (storage_root / foreign_location).read_bytes()

        # 5: deleting the physical file mutates nothing; a new explicit act re-realizes it.
        first_path.unlink()
        after_delete_state = materializer.state(first.materialization)
        rematerialized = materializer.materialize(artifact_id=artifact_a.identity.value)
        rematerialized_bytes = first_path.read_bytes()

        # 6/7: a superseded historical artifact remains materializable, side by side.
        artifact_b = _artifact("B")  # supersedes A's selection; A becomes historical
        historical = materializer.materialize(
            artifact_id=artifact_a.identity.value, relative_location="history/a.srt"
        )
        current_b = materializer.materialize(artifact_id=artifact_b.identity.value)

        # 8: an escaping path is refused outright (nothing persisted for it).
        escaping_refused = False
        try:
            materializer.materialize(
                artifact_id=artifact_a.identity.value, relative_location="../escape.srt"
            )
        except EffectiveSrtMaterializationError:
            escaping_refused = True

        history = materializer.list_for_artifact(artifact_a.identity.value)
        legacy_rows = connection.execute(
            "SELECT COUNT(*) FROM subtitle_srt_materializations"
        ).fetchone()[0]
        connection.close()
        validation = validate_database(str(database))
        srt_files = sorted(
            str(p.relative_to(storage_root))
            for p in storage_root.rglob("*.srt") if p.is_file()
        )

        return {
            # Deterministic, content-derived facts (golden).
            "intake_id": intake_id,
            "artifact_a_id": artifact_a.identity.value,
            "artifact_b_id": artifact_b.identity.value,
            "materialization_first_id": first.materialization.identity.value,
            "materialization_overwrite_id": overwritten.materialization.identity.value,
            "materialized_files": srt_files,
            "materialization_count_a": len(history),
            # Behavioral checks.
            "first_write_exact_canonical_bytes": first.kind.value == "created"
            and first.state is MaterializationState.MATERIALIZED
            and first_bytes == artifact_a.srt_content.encode("utf-8")
            and not first_bytes.startswith(b"\xef\xbb\xbf"),
            "replay_reuses_without_rewrite": replay.kind.value == "reused"
            and replay.materialization.identity == first.materialization.identity,
            "different_file_refuses_without_overwrite": blocked.state
            is MaterializationState.FAILED
            and "Collision" in blocked.outcome.failure_reason
            and foreign_untouched,
            "explicit_overwrite_replaces_as_new_event": overwritten.state
            is MaterializationState.MATERIALIZED
            and overwritten.materialization.sequence == blocked.materialization.sequence + 1
            and overwritten_bytes == artifact_a.srt_content.encode("utf-8"),
            "deleted_file_never_mutates_records": after_delete_state
            is MaterializationState.MATERIALIZED
            and rematerialized.kind.value == "created"
            and rematerialized.materialization.sequence
            == first.materialization.sequence + 1
            and rematerialized_bytes == artifact_a.srt_content.encode("utf-8"),
            "historical_artifact_still_materializable": historical.state
            is MaterializationState.MATERIALIZED
            and current_b.state is MaterializationState.MATERIALIZED,
            "escaping_path_refused": escaping_refused,
            "no_legacy_materialization_rows": legacy_rows == 0,
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "intake_id",
        "artifact_a_id",
        "artifact_b_id",
        "materialization_first_id",
        "materialization_overwrite_id",
        "materialized_files",
        "materialization_count_a",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_effective_materialize_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
