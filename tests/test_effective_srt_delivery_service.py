"""Application tests for Explicit Effective SRT Delivery (GOAL-019)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_srt_delivery import (
    DeliveryFailureCategory,
    DeliveryState,
    EffectiveSrtDelivery,
    EffectiveSrtDeliveryConflictError,
    EffectiveSrtDeliveryError,
    default_delivery_location,
    derive_delivery_identity,
)
from lectureos.application.effective_srt_materialization import (
    MATERIALIZATION_STORAGE_KIND,
    EffectiveSrtMaterialization,
    derive_materialization_identity,
)
from lectureos.application.identities import (
    EffectiveSrtMaterializationId,
    EffectiveSubtitleSrtArtifactId,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
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
from lectureos.persistence import (
    SQLiteEffectiveSrtDeliveryCommandPersistence,
    SQLiteEffectiveSrtMaterializationCommandPersistence,
    initialize_sqlite_database,
)

_MAT = EffectiveSrtMaterializationId(
    "subtitle-effective-srt-materialization:" + "a" * 64
)
_ART = EffectiveSubtitleSrtArtifactId("subtitle-effective-srt-artifact:" + "b" * 64)


class IdentityTests(unittest.TestCase):
    def test_identity_deterministic_and_input_sensitive(self):
        a = derive_delivery_identity(_MAT, _ART, "a.srt", "c" * 64, 0, False)
        self.assertEqual(
            a, derive_delivery_identity(_MAT, _ART, "a.srt", "c" * 64, 0, False)
        )
        self.assertTrue(a.value.startswith("subtitle-effective-srt-delivery:"))
        other_mat = EffectiveSrtMaterializationId(
            "subtitle-effective-srt-materialization:" + "0" * 64
        )
        self.assertNotEqual(
            a, derive_delivery_identity(other_mat, _ART, "a.srt", "c" * 64, 0, False)
        )
        self.assertNotEqual(
            a, derive_delivery_identity(_MAT, _ART, "b.srt", "c" * 64, 0, False)
        )
        self.assertNotEqual(
            a, derive_delivery_identity(_MAT, _ART, "a.srt", "c" * 64, 1, False)
        )
        self.assertNotEqual(
            a, derive_delivery_identity(_MAT, _ART, "a.srt", "c" * 64, 0, True)
        )
        self.assertNotEqual(
            a, derive_delivery_identity(_MAT, _ART, "a.srt", "d" * 64, 0, False)
        )

    def test_default_location_policy(self):
        self.assertEqual(default_delivery_location(_ART), f"{_ART.value}.srt")


class EffectiveSrtDeliveryServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.storage_root = self.base / "storage"
        self.delivery_root = self.base / "delivered"
        self.storage_root.mkdir()
        self.delivery_root.mkdir()
        self.connection = initialize_sqlite_database(self.base / "lectureos.sqlite3")
        source = self.base / "a.bin"
        source.write_bytes(b"deliver \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            intake, raw.raw_transcript_id.value
        )
        candidate = compose_sqlite_effective_subtitle_generation_service(self.connection).generate(
            intake_id=intake
        ).candidate
        subject = compose_sqlite_effective_subtitle_review_preparation_service(
            self.connection
        ).prepare_review(candidate_id=candidate.identity.value).subject
        compose_sqlite_effective_subtitle_review_decision_service(self.connection).decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        selection = compose_sqlite_effective_subtitle_final_selection_service(
            self.connection
        ).select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        ).selection
        self.artifact = compose_sqlite_effective_subtitle_srt_artifact_service(
            self.connection
        ).generate_srt_artifact(final_selection_id=selection.identity.value).artifact
        self.materializer = compose_sqlite_effective_srt_materialization_service(
            self.connection, str(self.storage_root)
        )
        self.source = self.materializer.materialize(
            artifact_id=self.artifact.identity.value
        ).materialization
        self.content = self.artifact.srt_content.encode("utf-8")
        self.deliverer = compose_sqlite_effective_srt_delivery_service(
            self.connection, str(self.storage_root), str(self.delivery_root)
        )

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_srt_delivery_intents"
        ).fetchone()[0]

    def _outcome_count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_srt_delivery_outcomes"
        ).fetchone()[0]

    # -- eligibility ----------------------------------------------------------------------------------

    def test_successful_materialization_with_matching_source_is_eligible(self):
        report = self.deliverer.delivery_eligibility(self.source.identity.value)
        self.assertTrue(report.eligible)
        self.assertIsNone(report.blocking_reason)
        self.assertEqual(report.materialization_state.value, "materialized")
        self.assertEqual(self._count(), 0)  # eligibility is derived, never persisted

    def test_unknown_and_pending_and_failed_materializations_are_ineligible(self):
        unknown = self.deliverer.delivery_eligibility(
            "subtitle-effective-srt-materialization:" + "0" * 64
        )
        self.assertEqual(unknown.blocking_reason.value, "materialization_not_found")
        # PENDING: a dangling materialization intent without an outcome.
        pending_intent = EffectiveSrtMaterialization(
            identity=derive_materialization_identity(
                self.artifact.identity, "pending/src.srt", 0
            ),
            artifact_id=self.artifact.identity,
            storage_kind=MATERIALIZATION_STORAGE_KIND,
            relative_location="pending/src.srt",
            payload_fingerprint=self.artifact.content_fingerprint,
            sequence=0,
        )
        SQLiteEffectiveSrtMaterializationCommandPersistence(
            self.connection
        ).persist_materialization_intent(materialization=pending_intent)
        pending = self.deliverer.delivery_eligibility(pending_intent.identity.value)
        self.assertEqual(
            pending.blocking_reason.value, "materialization_not_materialized"
        )
        # FAILED: a collision against an existing different file.
        (self.storage_root / "failed.srt").write_bytes(b"foreign\n")
        failed_record = self.materializer.materialize(
            artifact_id=self.artifact.identity.value, relative_location="failed.srt"
        )
        self.assertEqual(failed_record.state.value, "failed")
        failed = self.deliverer.delivery_eligibility(
            failed_record.materialization.identity.value
        )
        self.assertEqual(
            failed.blocking_reason.value, "materialization_not_materialized"
        )

    def test_missing_and_tampered_source_files_are_ineligible(self):
        gone = self.materializer.materialize(
            artifact_id=self.artifact.identity.value, relative_location="gone/src.srt"
        ).materialization
        (self.storage_root / "gone/src.srt").unlink()
        report = self.deliverer.delivery_eligibility(gone.identity.value)
        self.assertEqual(report.blocking_reason.value, "source_file_missing")
        tampered = self.materializer.materialize(
            artifact_id=self.artifact.identity.value,
            relative_location="tampered/src.srt",
        ).materialization
        (self.storage_root / "tampered/src.srt").write_bytes(b"tampered\n")
        report = self.deliverer.delivery_eligibility(tampered.identity.value)
        self.assertEqual(report.blocking_reason.value, "source_file_mismatch")

    def test_source_swapped_between_verification_and_copy_blocks_pre_intent(self):
        # TOCTOU guard: the bytes actually read for the copy are re-verified against the
        # artifact fingerprint immediately before the intent — a source file replaced after
        # eligibility passed can never be recorded or delivered.
        class _SwappingReader:
            def __init__(self, inner):
                self._inner = inner
                self._reads = 0

            def __getattr__(self, name):
                return getattr(self._inner, name)

            def read(self, *, relative_location):
                self._reads += 1
                real = self._inner.read(relative_location=relative_location)
                if self._reads >= 2 and real is not None:
                    return b"swapped after verification\n"
                return real

        service = compose_sqlite_effective_srt_delivery_service(
            self.connection, str(self.storage_root), str(self.delivery_root)
        )
        service._source = _SwappingReader(service._source)
        with self.assertRaises(EffectiveSrtDeliveryError):
            service.deliver(materialization_id=self.source.identity.value)
        self.assertEqual(self._count(), 0)
        self.assertFalse(
            (self.delivery_root / f"{self.artifact.identity.value}.srt").exists()
        )

    def test_unsupported_delivery_kind_is_ineligible(self):
        report = self.deliverer.delivery_eligibility(
            self.source.identity.value, delivery_kind="http_upload"
        )
        self.assertEqual(report.blocking_reason.value, "unsupported_delivery_kind")
        with self.assertRaises(EffectiveSrtDeliveryError):
            self.deliverer.deliver(
                materialization_id=self.source.identity.value,
                delivery_kind="http_upload",
            )
        self.assertEqual(self._count(), 0)

    # -- record-first delivery ------------------------------------------------------------------------

    def test_first_delivery_copies_exact_bytes_record_first(self):
        record = self.deliverer.deliver(materialization_id=self.source.identity.value)
        self.assertEqual(record.kind.value, "created")
        self.assertIs(record.state, DeliveryState.DELIVERED)
        self.assertEqual(record.outcome.byte_length, len(self.content))
        self.assertEqual(
            record.outcome.delivered_payload_fingerprint,
            self.artifact.content_fingerprint,
        )
        path = self.delivery_root / record.delivery.relative_location
        self.assertEqual(path.read_bytes(), self.content)
        self.assertEqual(
            record.delivery.expected_payload_fingerprint,
            self.artifact.content_fingerprint,
        )
        self.assertEqual(record.delivery.artifact_id, self.artifact.identity)
        self.assertEqual(record.delivery.materialization_id, self.source.identity)

    def test_replay_reuses_without_new_row_or_rewrite(self):
        first = self.deliverer.deliver(materialization_id=self.source.identity.value)
        path = self.delivery_root / first.delivery.relative_location
        stat_before = path.stat().st_mtime_ns
        replay = self.deliverer.deliver(materialization_id=self.source.identity.value)
        self.assertEqual(replay.kind.value, "reused")
        self.assertEqual(replay.delivery.identity, first.delivery.identity)
        self.assertEqual(self._count(), 1)
        self.assertEqual(path.stat().st_mtime_ns, stat_before)

    def test_missing_destination_after_success_creates_new_attempt(self):
        first = self.deliverer.deliver(materialization_id=self.source.identity.value)
        path = self.delivery_root / first.delivery.relative_location
        path.unlink()
        self.assertIs(self.deliverer.state(first.delivery), DeliveryState.DELIVERED)
        again = self.deliverer.deliver(materialization_id=self.source.identity.value)
        self.assertEqual(again.kind.value, "created")
        self.assertEqual(again.delivery.sequence, first.delivery.sequence + 1)
        self.assertEqual(again.delivery.previous_delivery_id, first.delivery.identity)
        self.assertEqual(path.read_bytes(), self.content)

    def test_existing_identical_destination_is_truthful_success(self):
        (self.delivery_root / "same.srt").write_bytes(self.content)
        record = self.deliverer.deliver(
            materialization_id=self.source.identity.value, relative_location="same.srt"
        )
        self.assertEqual(record.kind.value, "created")
        self.assertIs(record.state, DeliveryState.DELIVERED)

    def test_existing_different_destination_records_failed_and_retry_appends(self):
        (self.delivery_root / "other.srt").write_bytes(b"foreign\n")
        blocked = self.deliverer.deliver(
            materialization_id=self.source.identity.value, relative_location="other.srt"
        )
        self.assertIs(blocked.state, DeliveryState.FAILED)
        self.assertIs(
            blocked.outcome.failure_category,
            DeliveryFailureCategory.DESTINATION_EXISTS_DIFFERENT,
        )
        self.assertEqual((self.delivery_root / "other.srt").read_bytes(), b"foreign\n")
        # The durable intent survived the destination-side failure (record-first honesty).
        self.assertIsNotNone(self.deliverer.get(blocked.delivery.identity.value))
        # A FAILED attempt is history; a new explicit request appends the next attempt.
        retry = self.deliverer.deliver(
            materialization_id=self.source.identity.value, relative_location="other.srt"
        )
        self.assertEqual(retry.delivery.sequence, blocked.delivery.sequence + 1)
        self.assertIs(retry.state, DeliveryState.FAILED)

    def test_explicit_overwrite_replaces_as_new_attempt(self):
        (self.delivery_root / "other.srt").write_bytes(b"foreign\n")
        blocked = self.deliverer.deliver(
            materialization_id=self.source.identity.value, relative_location="other.srt"
        )
        overwritten = self.deliverer.deliver(
            materialization_id=self.source.identity.value,
            relative_location="other.srt",
            overwrite=True,
        )
        self.assertIs(overwritten.state, DeliveryState.DELIVERED)
        self.assertEqual(
            overwritten.delivery.sequence, blocked.delivery.sequence + 1
        )
        self.assertEqual(
            overwritten.delivery.previous_delivery_id, blocked.delivery.identity
        )
        self.assertTrue(overwritten.delivery.overwrite)
        self.assertEqual(
            (self.delivery_root / "other.srt").read_bytes(), self.content
        )

    def test_escaping_and_absolute_destinations_refused_pre_intent(self):
        for bad in ("../escape.srt", "/abs.srt", "  "):
            with self.assertRaises(EffectiveSrtDeliveryError):
                self.deliverer.deliver(
                    materialization_id=self.source.identity.value,
                    relative_location=bad,
                )
        self.assertEqual(self._count(), 0)

    def test_source_destination_aliasing_refused_pre_intent(self):
        aliased = compose_sqlite_effective_srt_delivery_service(
            self.connection, str(self.storage_root), str(self.storage_root)
        )
        with self.assertRaises(EffectiveSrtDeliveryError):
            aliased.deliver(
                materialization_id=self.source.identity.value,
                relative_location=self.source.relative_location,
            )
        self.assertEqual(self._count(), 0)

    def test_dangling_delivery_intent_is_completed_not_duplicated(self):
        location = default_delivery_location(self.artifact.identity)
        intent = EffectiveSrtDelivery(
            identity=derive_delivery_identity(
                self.source.identity, self.artifact.identity, location,
                self.artifact.content_fingerprint, 0, False,
            ),
            materialization_id=self.source.identity,
            artifact_id=self.artifact.identity,
            delivery_kind="local_copy",
            delivery_contract_version=1,
            relative_location=location,
            expected_payload_fingerprint=self.artifact.content_fingerprint,
            sequence=0,
            overwrite=False,
        )
        SQLiteEffectiveSrtDeliveryCommandPersistence(
            self.connection
        ).persist_delivery_intent(delivery=intent)
        record = self.deliverer.deliver(materialization_id=self.source.identity.value)
        self.assertEqual(record.delivery.identity, intent.identity)
        self.assertIs(record.state, DeliveryState.DELIVERED)
        self.assertEqual(self._count(), 1)

    # -- reconciliation -------------------------------------------------------------------------------

    def _dangling(self, location: str) -> EffectiveSrtDelivery:
        intent = EffectiveSrtDelivery(
            identity=derive_delivery_identity(
                self.source.identity, self.artifact.identity, location,
                self.artifact.content_fingerprint, 0, False,
            ),
            materialization_id=self.source.identity,
            artifact_id=self.artifact.identity,
            delivery_kind="local_copy",
            delivery_contract_version=1,
            relative_location=location,
            expected_payload_fingerprint=self.artifact.content_fingerprint,
            sequence=0,
            overwrite=False,
        )
        SQLiteEffectiveSrtDeliveryCommandPersistence(
            self.connection
        ).persist_delivery_intent(delivery=intent)
        return intent

    def test_reconcile_matching_missing_and_differing_destinations(self):
        matching = self._dangling("recon/match.srt")
        (self.delivery_root / "recon").mkdir()
        (self.delivery_root / "recon/match.srt").write_bytes(self.content)
        record = self.deliverer.reconcile(matching.identity.value)
        self.assertEqual(record.kind.value, "created")
        self.assertIs(record.state, DeliveryState.DELIVERED)
        self.assertEqual(record.outcome.byte_length, len(self.content))

        missing = self._dangling("recon/missing.srt")
        record = self.deliverer.reconcile(missing.identity.value)
        self.assertIs(record.state, DeliveryState.FAILED)
        self.assertIs(
            record.outcome.failure_category,
            DeliveryFailureCategory.DESTINATION_MISSING,
        )

        differing = self._dangling("recon/differ.srt")
        (self.delivery_root / "recon/differ.srt").write_bytes(b"foreign\n")
        record = self.deliverer.reconcile(differing.identity.value)
        self.assertIs(record.state, DeliveryState.FAILED)
        self.assertIs(
            record.outcome.failure_category,
            DeliveryFailureCategory.VERIFICATION_FAILED,
        )
        # Reconciliation observes only — it never overwrites the destination.
        self.assertEqual(
            (self.delivery_root / "recon/differ.srt").read_bytes(), b"foreign\n"
        )

    def test_terminal_delivery_cannot_reconcile_into_another_outcome(self):
        first = self.deliverer.deliver(materialization_id=self.source.identity.value)
        outcomes_before = self._outcome_count()
        record = self.deliverer.reconcile(first.delivery.identity.value)
        self.assertEqual(record.kind.value, "reused")
        self.assertEqual(self._outcome_count(), outcomes_before)
        with self.assertRaises(EffectiveSrtDeliveryError):
            self.deliverer.reconcile("subtitle-effective-srt-delivery:" + "0" * 64)

    # -- concurrency ----------------------------------------------------------------------------------

    def test_identical_concurrent_requests_converge_on_canonical_record(self):
        first = self.deliverer.deliver(materialization_id=self.source.identity.value)

        class _StaleLatestView:
            def __init__(self, inner):
                self._inner = inner
                self._missed = False

            def __getattr__(self, name):
                return getattr(self._inner, name)

            def get_latest(self, materialization_id, relative_location):
                if not self._missed:
                    self._missed = True
                    return None
                return self._inner.get_latest(materialization_id, relative_location)

        racing = compose_sqlite_effective_srt_delivery_service(
            self.connection, str(self.storage_root), str(self.delivery_root)
        )
        racing._deliveries = _StaleLatestView(racing._deliveries)
        # Delete the destination so the racer cannot short-circuit into byte-level reuse;
        # convergence must come from the durable intent slot alone.
        (self.delivery_root / first.delivery.relative_location).unlink()
        raced = racing.deliver(materialization_id=self.source.identity.value)
        self.assertEqual(raced.kind.value, "reused")
        self.assertEqual(raced.delivery.identity, first.delivery.identity)
        self.assertEqual(self._count(), 1)

    def test_divergent_competing_request_raises_explicit_conflict(self):
        # A self-consistent competing intent occupies the sequence-0 slot with a divergent
        # payload (explicit overwrite policy) — no silent loss, no last-write-wins.
        location = default_delivery_location(self.artifact.identity)
        competing = EffectiveSrtDelivery(
            identity=derive_delivery_identity(
                self.source.identity, self.artifact.identity, location,
                self.artifact.content_fingerprint, 0, True,
            ),
            materialization_id=self.source.identity,
            artifact_id=self.artifact.identity,
            delivery_kind="local_copy",
            delivery_contract_version=1,
            relative_location=location,
            expected_payload_fingerprint=self.artifact.content_fingerprint,
            sequence=0,
            overwrite=True,
        )
        class _StaleLatestView:
            def __init__(self, inner):
                self._inner = inner
                self._missed = False

            def __getattr__(self, name):
                return getattr(self._inner, name)

            def get_latest(self, materialization_id, relative_location):
                if not self._missed:
                    self._missed = True
                    return None
                return self._inner.get_latest(materialization_id, relative_location)

        SQLiteEffectiveSrtDeliveryCommandPersistence(
            self.connection
        ).persist_delivery_intent(delivery=competing)
        racing = compose_sqlite_effective_srt_delivery_service(
            self.connection, str(self.storage_root), str(self.delivery_root)
        )
        racing._deliveries = _StaleLatestView(racing._deliveries)
        with self.assertRaises(EffectiveSrtDeliveryConflictError):
            racing.deliver(materialization_id=self.source.identity.value)
        self.assertEqual(self._count(), 1)

    def test_different_destinations_remain_independent(self):
        a = self.deliverer.deliver(
            materialization_id=self.source.identity.value, relative_location="a/x.srt"
        )
        b = self.deliverer.deliver(
            materialization_id=self.source.identity.value, relative_location="b/x.srt"
        )
        self.assertNotEqual(a.delivery.identity, b.delivery.identity)
        self.assertEqual(a.delivery.sequence, 0)
        self.assertEqual(b.delivery.sequence, 0)

    # -- status ---------------------------------------------------------------------------------------

    def test_status_separates_history_from_filesystem_observation(self):
        first = self.deliverer.deliver(materialization_id=self.source.identity.value)
        (self.delivery_root / first.delivery.relative_location).unlink()
        status = self.deliverer.status(first.delivery)
        self.assertIs(status.delivery_state, DeliveryState.DELIVERED)
        self.assertEqual(status.source_file_agreement, "matches")
        self.assertEqual(status.destination_file_agreement, "missing")
        self.assertEqual(status.artifact_currentness.value, "current")
        self.assertEqual(status.materialization_state.value, "materialized")


if __name__ == "__main__":
    unittest.main()
