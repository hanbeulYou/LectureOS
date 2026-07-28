"""Application tests for Effective SRT Publication Authority (GOAL-020)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_srt_publication import (
    EffectiveSrtPublication,
    EffectiveSrtPublicationError,
    EffectiveSrtPublicationService,
    PublicationAvailability,
    PublicationConflictError,
    PublicationKind,
    derive_publication_identity,
)
from lectureos.application.identities import (
    EffectiveSrtDeliveryId,
    TranscriptSourceIntakeId,
)
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
from lectureos.persistence import (
    SQLiteEffectiveSrtPublicationCommandPersistence,
    SQLiteEffectiveSrtPublicationRepository,
    initialize_sqlite_database,
)
from lectureos.review.identities import HumanActorReference

_INTAKE = TranscriptSourceIntakeId("transcript-source-intake:sha256:" + "a" * 64)
_DELIVERY = EffectiveSrtDeliveryId("subtitle-effective-srt-delivery:" + "b" * 64)


class IdentityTests(unittest.TestCase):
    def test_identity_deterministic_and_input_sensitive(self):
        a = derive_publication_identity(_INTAKE, PublicationKind.PUBLISH, _DELIVERY, 0)
        self.assertEqual(
            a, derive_publication_identity(_INTAKE, PublicationKind.PUBLISH, _DELIVERY, 0)
        )
        self.assertTrue(a.value.startswith("subtitle-effective-srt-publication:"))
        other_intake = TranscriptSourceIntakeId(
            "transcript-source-intake:sha256:" + "0" * 64
        )
        self.assertNotEqual(
            a, derive_publication_identity(other_intake, PublicationKind.PUBLISH, _DELIVERY, 0)
        )
        self.assertNotEqual(
            a, derive_publication_identity(_INTAKE, PublicationKind.WITHDRAW, None, 0)
        )
        other_delivery = EffectiveSrtDeliveryId(
            "subtitle-effective-srt-delivery:" + "1" * 64
        )
        self.assertNotEqual(
            a, derive_publication_identity(_INTAKE, PublicationKind.PUBLISH, other_delivery, 0)
        )
        self.assertNotEqual(
            a, derive_publication_identity(_INTAKE, PublicationKind.PUBLISH, _DELIVERY, 1)
        )


class _StaleCurrentView:
    """A racing caller's view: ``get_current`` misses the just-committed record once."""

    def __init__(self, inner):
        self._inner = inner
        self._missed = False

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def get_current(self, intake_id):
        if not self._missed:
            self._missed = True
            history = self._inner.history(intake_id)
            return history[-2] if len(history) >= 2 else None
        return self._inner.get_current(intake_id)


class EffectiveSrtPublicationServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.storage_root = self.base / "storage"
        self.delivery_root = self.base / "delivered"
        self.storage_root.mkdir()
        self.delivery_root.mkdir()
        self.connection = initialize_sqlite_database(self.base / "lectureos.sqlite3")
        source = self.base / "a.bin"
        source.write_bytes(b"publish \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(self.connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(self.connection).select(
            self.intake, raw.raw_transcript_id.value
        )
        candidate = compose_sqlite_effective_subtitle_generation_service(self.connection).generate(
            intake_id=self.intake
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
        self.deliverer = compose_sqlite_effective_srt_delivery_service(
            self.connection, str(self.storage_root), str(self.delivery_root)
        )
        self.delivery = self._deliver("a.srt")
        self.publisher = compose_sqlite_effective_srt_publication_service(
            self.connection, str(self.delivery_root)
        )

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _deliver(self, location: str):
        materialization = self.materializer.materialize(
            artifact_id=self.artifact.identity.value,
            relative_location=f"src/{location}",
        ).materialization
        return self.deliverer.deliver(
            materialization_id=materialization.identity.value,
            relative_location=location,
        ).delivery

    def _count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_effective_srt_publications"
        ).fetchone()[0]

    # -- eligibility ----------------------------------------------------------------------------------

    def test_delivered_delivery_is_eligible_and_nothing_persisted(self):
        report = self.publisher.publication_eligibility(self.delivery.identity.value)
        self.assertTrue(report.eligible)
        self.assertEqual(report.delivery_state.value, "delivered")
        self.assertEqual(report.destination_observation, "matches")
        self.assertEqual(
            report.transcript_source_intake_id.value, self.intake
        )
        self.assertEqual(self._count(), 0)

    def test_unknown_failed_and_pending_deliveries_are_ineligible(self):
        unknown = self.publisher.publication_eligibility(
            "subtitle-effective-srt-delivery:" + "0" * 64
        )
        self.assertEqual(unknown.blocking_reason.value, "delivery_not_found")
        with self.assertRaises(EffectiveSrtPublicationError):
            self.publisher.publication_eligibility("not-a-delivery")
        # FAILED: collision against a pre-existing different destination.
        (self.delivery_root / "failed.srt").write_bytes(b"foreign\n")
        failed = self._deliver("failed.srt")
        report = self.publisher.publication_eligibility(failed.identity.value)
        self.assertEqual(report.blocking_reason.value, "delivery_not_delivered")
        with self.assertRaises(EffectiveSrtPublicationError):
            self.publisher.publish(
                delivery_id=failed.identity.value, publisher="publisher:kim"
            )
        self.assertEqual(self._count(), 0)

    def test_destination_policy_blocks_new_publish_when_root_supplied(self):
        path = self.delivery_root / self.delivery.relative_location
        path.unlink()
        report = self.publisher.publication_eligibility(self.delivery.identity.value)
        self.assertEqual(report.blocking_reason.value, "destination_missing")
        path.write_bytes(b"tampered\n")
        report = self.publisher.publication_eligibility(self.delivery.identity.value)
        self.assertEqual(report.blocking_reason.value, "destination_mismatch")
        # Without a Delivery Root, the repository-proven DELIVERED record suffices — the
        # documented conservative policy observes only when observation is possible.
        blind = compose_sqlite_effective_srt_publication_service(self.connection)
        report = blind.publication_eligibility(self.delivery.identity.value)
        self.assertTrue(report.eligible)
        self.assertEqual(report.destination_observation, "not_observed")

    # -- human authority ------------------------------------------------------------------------------

    def test_publisher_must_be_explicit_and_non_empty(self):
        for bad in ("", "   "):
            with self.assertRaises(EffectiveSrtPublicationError):
                self.publisher.publish(
                    delivery_id=self.delivery.identity.value, publisher=bad
                )
            with self.assertRaises(EffectiveSrtPublicationError):
                self.publisher.withdraw(intake_id=self.intake, publisher=bad)
        self.assertEqual(self._count(), 0)

    def test_same_target_by_another_actor_converges_preserving_provenance(self):
        first = self.publisher.publish(
            delivery_id=self.delivery.identity.value, publisher="publisher:kim"
        )
        other = self.publisher.publish(
            delivery_id=self.delivery.identity.value, publisher="publisher:choi"
        )
        self.assertEqual(other.outcome.value, "reused")
        self.assertEqual(other.publication.identity, first.publication.identity)
        self.assertEqual(other.publication.publisher.value, "publisher:kim")
        self.assertEqual(self._count(), 1)

    # -- vocabulary and model rules -------------------------------------------------------------------

    def test_publish_requires_target_and_withdraw_forbids_it(self):
        with self.assertRaises(ValueError):
            EffectiveSrtPublication(
                identity=derive_publication_identity(
                    TranscriptSourceIntakeId(self.intake),
                    PublicationKind.PUBLISH, None, 0,
                ),
                transcript_source_intake_id=TranscriptSourceIntakeId(self.intake),
                kind=PublicationKind.PUBLISH,
                publisher=HumanActorReference("p:x"),
                sequence=0,
                content_fingerprint="0" * 64,
            )
        with self.assertRaises(ValueError):
            EffectiveSrtPublication(
                identity=derive_publication_identity(
                    TranscriptSourceIntakeId(self.intake),
                    PublicationKind.WITHDRAW, self.delivery.identity, 0,
                ),
                transcript_source_intake_id=TranscriptSourceIntakeId(self.intake),
                kind=PublicationKind.WITHDRAW,
                publisher=HumanActorReference("p:x"),
                sequence=0,
                content_fingerprint="0" * 64,
                target_delivery_id=self.delivery.identity,
                target_artifact_id=self.artifact.identity,
            )

    def test_withdraw_requires_existing_publication_history(self):
        with self.assertRaises(EffectiveSrtPublicationError):
            self.publisher.withdraw(intake_id=self.intake, publisher="publisher:kim")
        self.assertEqual(self._count(), 0)

    # -- replay, repeated intent, and history ---------------------------------------------------------

    def test_exact_replay_reuses_without_duplicate_row(self):
        first = self.publisher.publish(
            delivery_id=self.delivery.identity.value, publisher="publisher:kim",
            rationale="공개",
        )
        replay = self.publisher.publish(
            delivery_id=self.delivery.identity.value, publisher="publisher:kim",
            rationale="공개",
        )
        self.assertEqual(first.outcome.value, "recorded")
        self.assertEqual(replay.outcome.value, "reused")
        self.assertEqual(self._count(), 1)

    def test_replacement_withdraw_and_republish_append(self):
        first = self.publisher.publish(
            delivery_id=self.delivery.identity.value, publisher="publisher:kim"
        )
        second_delivery = self._deliver("b.srt")
        replaced = self.publisher.publish(
            delivery_id=second_delivery.identity.value, publisher="publisher:kim"
        )
        self.assertEqual(replaced.outcome.value, "changed")
        self.assertEqual(replaced.publication.sequence, 1)
        self.assertEqual(
            replaced.publication.previous_publication_id, first.publication.identity
        )
        withdrawn = self.publisher.withdraw(
            intake_id=self.intake, publisher="publisher:kim"
        )
        self.assertEqual(withdrawn.outcome.value, "changed")
        self.assertIs(withdrawn.publication.kind, PublicationKind.WITHDRAW)
        self.assertIsNone(withdrawn.publication.target_delivery_id)
        again = self.publisher.withdraw(intake_id=self.intake, publisher="publisher:x")
        self.assertEqual(again.outcome.value, "reused")
        # Publishing the SAME target after withdrawal is a genuinely new authority
        # transition and appends.
        republished = self.publisher.publish(
            delivery_id=self.delivery.identity.value, publisher="publisher:kim"
        )
        self.assertEqual(republished.outcome.value, "changed")
        self.assertEqual(republished.publication.sequence, 3)
        history = self.publisher.history(self.intake)
        self.assertEqual([p.sequence for p in history], [0, 1, 2, 3])
        self.assertEqual(
            [p.kind.value for p in history],
            ["publish", "publish", "withdraw", "publish"],
        )
        current = self.publisher.current(self.intake)
        self.assertEqual(current.identity, republished.publication.identity)
        # Prior records remain byte-identical immutable history.
        self.assertEqual(
            self.publisher.get(first.publication.identity.value), first.publication
        )

    # -- availability ---------------------------------------------------------------------------------

    def test_availability_derives_and_never_mutates_history(self):
        self.assertIs(
            self.publisher.availability(self.intake),
            PublicationAvailability.NOT_PUBLISHED,
        )
        published = self.publisher.publish(
            delivery_id=self.delivery.identity.value, publisher="publisher:kim"
        )
        self.assertIs(
            self.publisher.availability(self.intake), PublicationAvailability.AVAILABLE
        )
        path = self.delivery_root / self.delivery.relative_location
        path.unlink()
        self.assertIs(
            self.publisher.availability(self.intake),
            PublicationAvailability.DESTINATION_MISSING,
        )
        path.write_bytes(b"tampered\n")
        self.assertIs(
            self.publisher.availability(self.intake),
            PublicationAvailability.DESTINATION_MISMATCH,
        )
        status = self.publisher.status(published.publication.identity.value)
        self.assertTrue(status.current)
        self.assertEqual(status.delivery_state.value, "delivered")
        self.assertEqual(status.destination_observation, "differs")
        blind = compose_sqlite_effective_srt_publication_service(self.connection)
        self.assertIs(
            blind.availability(self.intake), PublicationAvailability.NOT_OBSERVED
        )
        self.publisher.withdraw(intake_id=self.intake, publisher="publisher:kim")
        self.assertIs(
            self.publisher.availability(self.intake), PublicationAvailability.WITHDRAWN
        )
        self.assertEqual(self._count(), 2)

    # -- concurrency ----------------------------------------------------------------------------------

    def _racing_service(self):
        repo = SQLiteEffectiveSrtPublicationRepository(self.connection)
        return EffectiveSrtPublicationService(
            self.publisher._deliveries,
            self.publisher._materializations,
            self.publisher._artifacts,
            _StaleCurrentView(repo),
            SQLiteEffectiveSrtPublicationCommandPersistence(self.connection),
            self.publisher._destination,
        )

    def test_identical_concurrent_publish_converges(self):
        first = self.publisher.publish(
            delivery_id=self.delivery.identity.value, publisher="publisher:kim",
            rationale="공개",
        )
        raced = self._racing_service().publish(
            delivery_id=self.delivery.identity.value, publisher="publisher:kim",
            rationale="공개",
        )
        self.assertEqual(raced.outcome.value, "reused")
        self.assertEqual(raced.publication.identity, first.publication.identity)
        self.assertEqual(self._count(), 1)

    def test_divergent_concurrent_command_raises_explicit_conflict(self):
        self.publisher.publish(
            delivery_id=self.delivery.identity.value, publisher="publisher:kim"
        )
        second_delivery = self._deliver("b.srt")
        self.publisher.publish(
            delivery_id=second_delivery.identity.value, publisher="publisher:kim"
        )
        # A racing withdraw whose stale view still sees the older publish appends into the
        # occupied sequence slot — an explicit conflict, never silent loss of either command.
        with self.assertRaises(PublicationConflictError):
            self._racing_service().withdraw(
                intake_id=self.intake, publisher="publisher:choi"
            )
        self.assertEqual(self._count(), 2)
        # The same slot with divergent provenance (another actor's payload) also conflicts.
        with self.assertRaises(PublicationConflictError):
            self._racing_service().publish(
                delivery_id=second_delivery.identity.value, publisher="publisher:choi"
            )
        self.assertEqual(self._count(), 2)


if __name__ == "__main__":
    unittest.main()
