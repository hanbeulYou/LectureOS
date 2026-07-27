"""Deterministic demonstration of Explicit Effective SRT Delivery (GOAL-019).

Drives the whole slice with fake provider results and explicit human actors — no LLM, ASR,
network, or model; the only filesystem writes land beneath isolated approved roots:

    A. First delivery: exact materialized bytes copied beneath the Delivery Root, immutable
       intent + verified DELIVERED outcome
    B. Exact replay: reused, no destination rewrite, no new intent
    C. Pre-existing identical destination bytes: truthful successful delivery (idempotent
       physical agreement)
    D. Pre-existing different bytes without --overwrite: honest FAILED outcome, file untouched
    E. Explicit overwrite: new append-only attempt, destination replaced, DELIVERED
    F. Destination deleted after success: history immutable, status reports missing, a new
       explicit request creates the next attempt and restores the bytes
    G. Source materialization file missing: ineligible pre-intent, nothing persisted, no write
    H. Tampered source bytes: fingerprint mismatch pre-intent, nothing persisted, no write
    I. Historical superseded artifact: its successful materialization remains deliverable
    J. Escaping destination: refused pre-intent, nothing persisted, no write
    K. Dangling PENDING intent + matching destination: explicit reconcile appends DELIVERED
    L. Dangling PENDING intent + missing/different destination: honest FAILED, never overwrites
    M. Near-concurrent identical requests: durable-intent coordination converges without a
       second write
    N. Legacy and publication isolation: no legacy export/materialization rows, no URL column

The committed golden reproduces byte-for-byte.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.effective_srt_delivery import (
    DeliveryFailureCategory,
    DeliveryState,
    EffectiveSrtDelivery,
    EffectiveSrtDeliveryError,
    derive_delivery_identity,
)
from lectureos.application.effective_srt_materialization import (
    MaterializationState,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_srt_delivery_service,
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
from lectureos.persistence.effective_srt_delivery import (
    SQLiteEffectiveSrtDeliveryCommandPersistence,
)
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
_SOURCE_TEXTS = ("안녕하세요 여러부", "오늘의 강의입니다")


class _StaleLatestView:
    """A racing caller's view: the first ``get_latest`` misses the just-committed attempt."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self._missed = False

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def get_latest(self, materialization_id, relative_location):
        if not self._missed:
            self._missed = True
            return None
        return self._inner.get_latest(materialization_id, relative_location)


def run_effective_deliver_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        storage_root = Path(directory) / "storage"
        delivery_root = Path(directory) / "delivered"
        storage_root.mkdir()
        delivery_root.mkdir()
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
        deliverer = compose_sqlite_effective_srt_delivery_service(
            connection, str(storage_root), str(delivery_root)
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
        source = materializer.materialize(artifact_id=artifact_a.identity.value)
        source_id = source.materialization.identity.value
        content = artifact_a.srt_content.encode("utf-8")

        def _delivery_rows() -> int:
            return connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_srt_delivery_intents"
            ).fetchone()[0]

        # A: first delivery — exact bytes, immutable intent, verified DELIVERED outcome.
        first = deliverer.deliver(materialization_id=source_id)
        first_path = delivery_root / first.delivery.relative_location
        first_bytes = first_path.read_bytes()

        # B: exact replay — reused, no rewrite, no new intent.
        rows_before_replay = _delivery_rows()
        replay = deliverer.deliver(materialization_id=source_id)
        replay_added_rows = _delivery_rows() - rows_before_replay

        # C: a pre-existing IDENTICAL destination file is truthful idempotent success.
        (delivery_root / "manual").mkdir()
        (delivery_root / "manual/same.srt").write_bytes(content)
        identical = deliverer.deliver(
            materialization_id=source_id, relative_location="manual/same.srt"
        )

        # D: a pre-existing DIFFERENT destination refuses without overwrite — honest FAILED
        # outcome, destination untouched.
        foreign = "다른 배포본\n".encode("utf-8")
        (delivery_root / "manual/other.srt").write_bytes(foreign)
        blocked = deliverer.deliver(
            materialization_id=source_id, relative_location="manual/other.srt"
        )
        foreign_untouched = (delivery_root / "manual/other.srt").read_bytes() == foreign

        # E: explicit overwrite replaces the destination as a NEW append-only attempt.
        overwritten = deliverer.deliver(
            materialization_id=source_id,
            relative_location="manual/other.srt",
            overwrite=True,
        )
        overwritten_bytes = (delivery_root / "manual/other.srt").read_bytes()

        # F: deleting the delivered file mutates nothing; a new explicit request re-delivers.
        first_path.unlink()
        after_delete_state = deliverer.state(first.delivery)
        after_delete_status = deliverer.status(first.delivery)
        redelivered = deliverer.deliver(materialization_id=source_id)
        redelivered_bytes = first_path.read_bytes()

        # G: a missing source file blocks pre-intent — nothing persisted, nothing written.
        gone = materializer.materialize(
            artifact_id=artifact_a.identity.value, relative_location="gone/src.srt"
        )
        (storage_root / "gone/src.srt").unlink()
        gone_eligibility = deliverer.delivery_eligibility(
            gone.materialization.identity.value
        )
        rows_before_gone = _delivery_rows()
        source_missing_refused = False
        try:
            deliverer.deliver(
                materialization_id=gone.materialization.identity.value,
                relative_location="gone/out.srt",
            )
        except EffectiveSrtDeliveryError:
            source_missing_refused = True
        gone_nothing = (
            _delivery_rows() == rows_before_gone
            and not (delivery_root / "gone/out.srt").exists()
        )

        # H: tampered source bytes block pre-intent — fingerprint mismatch, nothing persisted.
        tampered = materializer.materialize(
            artifact_id=artifact_a.identity.value, relative_location="tampered/src.srt"
        )
        (storage_root / "tampered/src.srt").write_bytes("변조된 내용\n".encode("utf-8"))
        tampered_eligibility = deliverer.delivery_eligibility(
            tampered.materialization.identity.value
        )
        rows_before_tampered = _delivery_rows()
        tampered_refused = False
        try:
            deliverer.deliver(
                materialization_id=tampered.materialization.identity.value,
                relative_location="tampered/out.srt",
            )
        except EffectiveSrtDeliveryError:
            tampered_refused = True
        tampered_nothing = (
            _delivery_rows() == rows_before_tampered
            and not (delivery_root / "tampered/out.srt").exists()
        )

        # I: artifact B supersedes A; A's successful materialization remains deliverable.
        artifact_b = _artifact("B")
        historical = deliverer.deliver(
            materialization_id=source_id, relative_location="history/a.srt"
        )
        historical_status = deliverer.status(historical.delivery)

        # J: an escaping destination is refused pre-intent — nothing persisted, nothing written.
        rows_before_escape = _delivery_rows()
        escaping_refused = False
        try:
            deliverer.deliver(
                materialization_id=source_id, relative_location="../escape.srt"
            )
        except EffectiveSrtDeliveryError:
            escaping_refused = True
        escape_nothing = _delivery_rows() == rows_before_escape

        # K/L: dangling PENDING intents (as after a crash between intent and write) are closed
        # only by explicit reconciliation — one truthful terminal outcome, never a write.
        intent_persistence = SQLiteEffectiveSrtDeliveryCommandPersistence(connection)

        def _dangling(location: str) -> EffectiveSrtDelivery:
            intent = EffectiveSrtDelivery(
                identity=derive_delivery_identity(
                    source.materialization.identity, artifact_a.identity, location,
                    artifact_a.content_fingerprint, 0, False,
                ),
                materialization_id=source.materialization.identity,
                artifact_id=artifact_a.identity,
                delivery_kind="local_copy",
                delivery_contract_version=1,
                relative_location=location,
                expected_payload_fingerprint=artifact_a.content_fingerprint,
                sequence=0,
                overwrite=False,
            )
            intent_persistence.persist_delivery_intent(delivery=intent)
            return intent

        matching_intent = _dangling("recon/match.srt")
        (delivery_root / "recon").mkdir()
        (delivery_root / "recon/match.srt").write_bytes(content)
        reconciled_match = deliverer.reconcile(matching_intent.identity.value)

        missing_intent = _dangling("recon/missing.srt")
        reconciled_missing = deliverer.reconcile(missing_intent.identity.value)

        differing_intent = _dangling("recon/differ.srt")
        (delivery_root / "recon/differ.srt").write_bytes("전혀 다른 파일\n".encode("utf-8"))
        reconciled_differ = deliverer.reconcile(differing_intent.identity.value)
        differ_untouched = (
            delivery_root / "recon/differ.srt"
        ).read_bytes() == "전혀 다른 파일\n".encode("utf-8")
        reconcile_idempotent = deliverer.reconcile(matching_intent.identity.value)

        # M: a near-concurrent identical request coordinates through the durable intent —
        # the racing caller's stale view collides on the canonical slot and converges on the
        # winner's immutable record without a second destination write.
        from lectureos.application.effective_srt_delivery import (
            EffectiveSrtDeliveryService,
        )
        from lectureos.infrastructure.local_effective_srt_delivery_writer import (
            LocalEffectiveSrtDeliveryWriter,
        )
        from lectureos.persistence import (
            SQLiteEffectiveSrtDeliveryRepository,
            SQLiteEffectiveSrtMaterializationRepository,
        )

        racing = EffectiveSrtDeliveryService(
            export,
            SQLiteEffectiveSrtMaterializationRepository(connection),
            _StaleLatestView(SQLiteEffectiveSrtDeliveryRepository(connection)),
            SQLiteEffectiveSrtDeliveryCommandPersistence(connection),
            LocalEffectiveSrtDeliveryWriter(str(storage_root)),
            LocalEffectiveSrtDeliveryWriter(str(delivery_root)),
        )
        rows_before_race = _delivery_rows()
        raced = racing.deliver(materialization_id=source_id)
        race_added_rows = _delivery_rows() - rows_before_race

        # N: legacy and publication isolation.
        legacy_rows = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("subtitle_srt_materializations", "subtitle_srt_artifacts",
                          "subtitle_final_subtitles")
        }
        intent_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(subtitle_effective_srt_delivery_intents)"
            ).fetchall()
        }

        history = deliverer.list_for_materialization(source_id)
        connection.close()
        validation = validate_database(str(database))
        delivered_files = sorted(
            str(p.relative_to(delivery_root))
            for p in delivery_root.rglob("*.srt") if p.is_file()
        )

        return {
            # Deterministic, content-derived facts (golden).
            "intake_id": intake_id,
            "artifact_a_id": artifact_a.identity.value,
            "artifact_b_id": artifact_b.identity.value,
            "materialization_id": source_id,
            "delivery_first_id": first.delivery.identity.value,
            "delivery_overwrite_id": overwritten.delivery.identity.value,
            "delivered_files": delivered_files,
            "delivery_count_for_materialization": len(history),
            # Behavioral checks.
            "first_delivery_exact_verified_bytes": first.kind.value == "created"
            and first.state is DeliveryState.DELIVERED
            and first_bytes == content
            and first.outcome.byte_length == len(content)
            and first.outcome.delivered_payload_fingerprint
            == artifact_a.content_fingerprint,
            "replay_reuses_without_rewrite": replay.kind.value == "reused"
            and replay.delivery.identity == first.delivery.identity
            and replay_added_rows == 0,
            "identical_destination_truthful_success": identical.kind.value == "created"
            and identical.state is DeliveryState.DELIVERED,
            "different_destination_refuses_without_overwrite": blocked.state
            is DeliveryState.FAILED
            and blocked.outcome.failure_category
            is DeliveryFailureCategory.DESTINATION_EXISTS_DIFFERENT
            and foreign_untouched,
            "explicit_overwrite_replaces_as_new_attempt": overwritten.state
            is DeliveryState.DELIVERED
            and overwritten.delivery.sequence == blocked.delivery.sequence + 1
            and overwritten_bytes == content,
            "deleted_destination_never_mutates_history": after_delete_state
            is DeliveryState.DELIVERED
            and after_delete_status.destination_file_agreement == "missing"
            and redelivered.kind.value == "created"
            and redelivered.delivery.sequence == first.delivery.sequence + 1
            and redelivered_bytes == content,
            "missing_source_blocks_pre_intent": not gone_eligibility.eligible
            and gone_eligibility.blocking_reason.value == "source_file_missing"
            and source_missing_refused and gone_nothing,
            "tampered_source_blocks_pre_intent": not tampered_eligibility.eligible
            and tampered_eligibility.blocking_reason.value == "source_file_mismatch"
            and tampered_refused and tampered_nothing,
            "historical_superseded_artifact_deliverable": historical.state
            is DeliveryState.DELIVERED
            and historical_status.artifact_currentness.value
            == "superseded_by_final_selection"
            and historical_status.materialization_state
            is MaterializationState.MATERIALIZED,
            "escaping_destination_refused": escaping_refused and escape_nothing,
            "reconcile_matching_appends_delivered": reconciled_match.kind.value == "created"
            and reconciled_match.state is DeliveryState.DELIVERED,
            "reconcile_missing_or_differing_honest_failed": reconciled_missing.state
            is DeliveryState.FAILED
            and reconciled_missing.outcome.failure_category
            is DeliveryFailureCategory.DESTINATION_MISSING
            and reconciled_differ.state is DeliveryState.FAILED
            and reconciled_differ.outcome.failure_category
            is DeliveryFailureCategory.VERIFICATION_FAILED
            and differ_untouched
            and reconcile_idempotent.kind.value == "reused",
            "concurrent_identical_requests_converge": raced.kind.value == "reused"
            and raced.state is DeliveryState.DELIVERED
            and raced.delivery.identity == first.delivery.identity
            and race_added_rows == 0,
            "no_legacy_or_publication_rows": all(v == 0 for v in legacy_rows.values())
            and not any(c in intent_columns for c in ("url", "public_url",
                                                      "publication", "recipient")),
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "intake_id",
        "artifact_a_id",
        "artifact_b_id",
        "materialization_id",
        "delivery_first_id",
        "delivery_overwrite_id",
        "delivered_files",
        "delivery_count_for_materialization",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_effective_deliver_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
