"""Deterministic demonstration of Effective SRT Publication Authority (GOAL-020).

Drives the whole slice with fake provider results and explicit human actors — no LLM, ASR,
network, or model; publication itself never writes a file (the only filesystem writes are the
upstream materialization/delivery fixtures beneath isolated approved roots):

    A. Publish one delivered subtitle: eligibility → immutable record → current → available
    B. Exact replay: reused, no duplicate row
    C. Same target by another actor: repeated intent converges on the established state
    D. Replacement delivery published: new current, prior publication immutable history
    E. Withdraw: append-only, nothing deleted, availability withdrawn
    F. Re-publish after withdrawal: new append-only record, available again
    G. Destination deleted after publication: authority unchanged, availability destination_missing
    H. Destination tampered: authority unchanged, availability destination_mismatch
    I. Historical (superseded) artifact's delivery remains publishable (documented policy)
    J. FAILED/PENDING delivery: ineligible, nothing persisted
    K. Cross-scope/tampered lineage: rejected pre-persistence
    L. Concurrent identical publish: durable-slot convergence
    M. Concurrent publish vs withdraw: explicit conflict, no silent loss
    N. Publication isolation: no URL column, no file write, upstream rows untouched

The committed golden reproduces byte-for-byte.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.effective_srt_publication import (
    EffectiveSrtPublicationError,
    EffectiveSrtPublicationService,
    PublicationAvailability,
    PublicationConflictError,
    PublicationKind,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_selection_service,
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
from lectureos.persistence import initialize_sqlite_database
from lectureos.persistence.effective_srt_publication import (
    SQLiteEffectiveSrtPublicationCommandPersistence,
    SQLiteEffectiveSrtPublicationRepository,
)
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
_SOURCE_TEXTS = ("안녕하세요 여러부", "오늘의 강의입니다")


class _StaleCurrentView:
    """A racing caller's view: the first ``get_current`` misses the just-committed record."""

    def __init__(self, inner, misses: int = 1) -> None:
        self._inner = inner
        self._misses = misses
        self._calls = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def get_current(self, intake_id):
        self._calls += 1
        if self._calls <= self._misses:
            history = self._inner.history(intake_id)
            return history[-2] if len(history) >= 2 else None
        return self._inner.get_current(intake_id)


def run_effective_publish_demo(media_fixtures_directory: str | None = None) -> dict:
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
        publisher = compose_sqlite_effective_srt_publication_service(
            connection, str(delivery_root)
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

        def _deliver(artifact, location):
            materialization = materializer.materialize(
                artifact_id=artifact.identity.value,
                relative_location=f"src/{location}",
            ).materialization
            return deliverer.deliver(
                materialization_id=materialization.identity.value,
                relative_location=location,
            ).delivery

        artifact_a = _artifact()
        delivery_a = _deliver(artifact_a, "a.srt")
        content = artifact_a.srt_content.encode("utf-8")

        def _rows() -> int:
            return connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_srt_publications"
            ).fetchone()[0]

        # A: eligibility → publish → immutable record, current, available.
        eligibility = publisher.publication_eligibility(delivery_a.identity.value)
        first = publisher.publish(
            delivery_id=delivery_a.identity.value, publisher="publisher:kim",
            rationale="1차 공개",
        )
        availability_a = publisher.availability(intake_id)

        # B: exact replay — reused, no duplicate row.
        rows_before_replay = _rows()
        replay = publisher.publish(
            delivery_id=delivery_a.identity.value, publisher="publisher:kim",
            rationale="1차 공개",
        )
        replay_added = _rows() - rows_before_replay

        # C: the same target by ANOTHER actor converges on the established authority state
        # (authority is a state, not a command ledger); first-establishing provenance stays.
        other_actor = publisher.publish(
            delivery_id=delivery_a.identity.value, publisher="publisher:choi"
        )

        # D: a replacement delivery is published — new current, prior record immutable history.
        artifact_b = _artifact("B")
        delivery_b = _deliver(artifact_b, "b.srt")
        replaced = publisher.publish(
            delivery_id=delivery_b.identity.value, publisher="publisher:kim"
        )
        current_after_replace = publisher.current(intake_id)
        first_after_replace = publisher.get(first.publication.identity.value)

        # E: withdraw — append-only authority; nothing deleted anywhere.
        delivery_rows_before = connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_srt_delivery_intents"
        ).fetchone()[0]
        withdrawn = publisher.withdraw(
            intake_id=intake_id, publisher="publisher:kim", rationale="검수 이슈"
        )
        availability_withdrawn = publisher.availability(intake_id)
        withdraw_deleted_nothing = (
            connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_srt_delivery_intents"
            ).fetchone()[0] == delivery_rows_before
            and (delivery_root / "b.srt").read_bytes() == content
        )
        withdraw_replay = publisher.withdraw(
            intake_id=intake_id, publisher="publisher:choi"
        )

        # F: re-publish after withdrawal appends a new record; available again.
        republished = publisher.publish(
            delivery_id=delivery_b.identity.value, publisher="publisher:kim"
        )
        availability_republished = publisher.availability(intake_id)

        # G/H: destination deleted, then tampered — authority unchanged; availability derives.
        (delivery_root / "b.srt").unlink()
        availability_missing = publisher.availability(intake_id)
        status_missing = publisher.status(republished.publication.identity.value)
        (delivery_root / "b.srt").write_bytes("변조된 배포본\n".encode("utf-8"))
        availability_tampered = publisher.availability(intake_id)
        history_after_filesystem = publisher.history(intake_id)

        # I: artifact A is superseded (historical), yet its successful delivery remains
        # publishable — publication is authority over one exact delivered realization.
        historical = publisher.publish(
            delivery_id=delivery_a.identity.value, publisher="publisher:kim",
            rationale="역사적 실현 재공개",
        )
        historical_status = publisher.status(historical.publication.identity.value)

        # J: a FAILED delivery is never publishable; nothing persisted.
        (delivery_root / "blocked.srt").write_bytes(b"foreign\n")
        failed_delivery = deliverer.deliver(
            materialization_id=materializer.materialize(
                artifact_id=artifact_b.identity.value, relative_location="src/blocked.srt"
            ).materialization.identity.value,
            relative_location="blocked.srt",
        )
        failed_eligibility = publisher.publication_eligibility(
            failed_delivery.delivery.identity.value
        )
        rows_before_failed = _rows()
        failed_refused = False
        try:
            publisher.publish(
                delivery_id=failed_delivery.delivery.identity.value,
                publisher="publisher:kim",
            )
        except EffectiveSrtPublicationError:
            failed_refused = True
        failed_nothing = _rows() == rows_before_failed

        # K: an unknown/malformed target is rejected pre-persistence.
        unknown_refused = False
        try:
            publisher.publish(
                delivery_id="subtitle-effective-srt-delivery:" + "0" * 64,
                publisher="publisher:kim",
            )
        except EffectiveSrtPublicationError:
            unknown_refused = True

        # L: near-concurrent identical publish converges through the durable authority slot.
        repo = SQLiteEffectiveSrtPublicationRepository(connection)
        racing = EffectiveSrtPublicationService(
            publisher._deliveries, publisher._materializations, publisher._artifacts,
            _StaleCurrentView(repo), SQLiteEffectiveSrtPublicationCommandPersistence(connection),
            publisher._destination,
        )
        rows_before_race = _rows()
        raced = racing.publish(
            delivery_id=delivery_a.identity.value, publisher="publisher:kim",
            rationale="역사적 실현 재공개",
        )
        race_added = _rows() - rows_before_race

        # M: a divergent concurrent command (publish vs withdraw) is an explicit conflict.
        conflicting = EffectiveSrtPublicationService(
            publisher._deliveries, publisher._materializations, publisher._artifacts,
            _StaleCurrentView(repo), SQLiteEffectiveSrtPublicationCommandPersistence(connection),
            publisher._destination,
        )
        divergent_conflict = False
        try:
            conflicting.withdraw(intake_id=intake_id, publisher="publisher:choi")
        except PublicationConflictError:
            divergent_conflict = True

        # N: publication isolation — no URL-ish columns, upstream rows untouched.
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(subtitle_effective_srt_publications)"
            ).fetchall()
        }
        upstream_rows = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("subtitle_effective_srt_artifacts",
                          "subtitle_effective_srt_materializations",
                          "subtitle_effective_srt_delivery_intents")
        }

        history = publisher.history(intake_id)
        connection.close()
        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "intake_id": intake_id,
            "artifact_a_id": artifact_a.identity.value,
            "artifact_b_id": artifact_b.identity.value,
            "delivery_a_id": delivery_a.identity.value,
            "delivery_b_id": delivery_b.identity.value,
            "publication_first_id": first.publication.identity.value,
            "publication_withdraw_id": withdrawn.publication.identity.value,
            "publication_history_kinds": [p.kind.value for p in history],
            "publication_count": len(history),
            # Behavioral checks.
            "publish_records_current_available": eligibility.eligible
            and first.outcome.value == "recorded"
            and first.publication.kind is PublicationKind.PUBLISH
            and first.publication.target_delivery_id == delivery_a.identity
            and first.publication.target_artifact_id == artifact_a.identity
            and availability_a is PublicationAvailability.AVAILABLE,
            "exact_replay_reused": replay.outcome.value == "reused"
            and replay.publication.identity == first.publication.identity
            and replay_added == 0,
            "same_target_other_actor_converges": other_actor.outcome.value == "reused"
            and other_actor.publication.publisher.value == "publisher:kim",
            "replacement_publish_supersedes": replaced.outcome.value == "changed"
            and current_after_replace.target_delivery_id == delivery_b.identity
            and first_after_replace == first.publication,
            "withdraw_appends_and_deletes_nothing": withdrawn.outcome.value == "changed"
            and withdrawn.publication.kind is PublicationKind.WITHDRAW
            and withdrawn.publication.target_delivery_id is None
            and availability_withdrawn is PublicationAvailability.WITHDRAWN
            and withdraw_deleted_nothing
            and withdraw_replay.outcome.value == "reused",
            "republish_after_withdraw_appends": republished.outcome.value == "changed"
            and republished.publication.sequence == withdrawn.publication.sequence + 1
            and availability_republished is PublicationAvailability.AVAILABLE,
            "filesystem_never_mutates_authority": availability_missing
            is PublicationAvailability.DESTINATION_MISSING
            and status_missing.current
            and status_missing.delivery_state.value == "delivered"
            and availability_tampered is PublicationAvailability.DESTINATION_MISMATCH
            and [p.kind.value for p in history_after_filesystem]
            == ["publish", "publish", "withdraw", "publish"],
            "historical_artifact_delivery_publishable": historical.outcome.value == "changed"
            and historical_status.artifact_currentness.value
            == "superseded_by_final_selection"
            and historical_status.current,
            "failed_delivery_not_publishable": failed_delivery.state.value == "failed"
            and not failed_eligibility.eligible
            and failed_eligibility.blocking_reason.value == "delivery_not_delivered"
            and failed_refused and failed_nothing and unknown_refused,
            "concurrent_identical_publish_converges": raced.outcome.value == "reused"
            and raced.publication.identity == historical.publication.identity
            and race_added == 0,
            "divergent_concurrent_command_conflicts": divergent_conflict,
            "publication_isolation": not any(
                c in columns for c in ("url", "public_url", "recipient", "endpoint",
                                       "is_published", "available")
            )
            and upstream_rows["subtitle_effective_srt_artifacts"] == 2
            and upstream_rows["subtitle_effective_srt_delivery_intents"] == 3,
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "intake_id",
        "artifact_a_id",
        "artifact_b_id",
        "delivery_a_id",
        "delivery_b_id",
        "publication_first_id",
        "publication_withdraw_id",
        "publication_history_kinds",
        "publication_count",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_effective_publish_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
