"""Release acceptance suite for the Effective Subtitle Pipeline v1 (GOAL-021).

One connected scenario over production services and real persistence — cross-stage lineage,
release-level invariants, full-pipeline replay, blocking-authority boundaries, historical
truth, restart reconstruction, legacy isolation, and cross-stage corruption detection.
Stage-local behavior remains covered by the per-goal suites; this suite proves the slices
form one coherent released system.
"""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_srt_publication import PublicationAvailability
from lectureos.application.effective_subtitle_final_selection import (
    ReviewSubjectNotEligibleError,
)
from lectureos.application.effective_subtitle_srt_artifact import (
    ArtifactCurrentness,
    FinalSelectionNotExportableError,
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
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.validation import validate_database

_STAGE_TABLES = (
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
    "subtitle_srt_materialization_outcomes",
)


class _Pipeline:
    """Production-service pipeline harness over one real SQLite repository."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.database = base / "lectureos.sqlite3"
        self.storage_root = base / "storage"
        self.delivery_root = base / "delivered"
        self.storage_root.mkdir()
        self.delivery_root.mkdir()
        self.connection = initialize_sqlite_database(self.database)
        source = base / "a.bin"
        source.write_bytes(b"release \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(
            str(source)
        ).record
        self.intake = compose_sqlite_transcript_source_intake_service(
            self.connection
        ).admit(media.identity.value).intake.identity.value
        self._provider = compose_sqlite_provider_transcript_admission_service(
            self.connection
        )
        self._raw_selection = compose_sqlite_current_raw_transcript_selection_service(
            self.connection
        )
        self.admit_raw("A")
        self._compose_services()

    def _compose_services(self) -> None:
        c = self.connection
        self.generation = compose_sqlite_effective_subtitle_generation_service(c)
        self.preparation = compose_sqlite_effective_subtitle_review_preparation_service(c)
        self.decisions = compose_sqlite_effective_subtitle_review_decision_service(c)
        self.selection = compose_sqlite_effective_subtitle_final_selection_service(c)
        self.export = compose_sqlite_effective_subtitle_srt_artifact_service(c)
        self.materializer = compose_sqlite_effective_srt_materialization_service(
            c, str(self.storage_root)
        )
        self.deliverer = compose_sqlite_effective_srt_delivery_service(
            c, str(self.storage_root), str(self.delivery_root)
        )
        self.publisher = compose_sqlite_effective_srt_publication_service(
            c, str(self.delivery_root)
        )

    def admit_raw(self, ref: str, fallback: bool = False) -> None:
        raw = self._provider.admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake-asr", "model": "tiny", "language": "ko",
                 "provider_result_ref": ref,
                 "segments": [{"start": 0.0, "end": 1.0, "text": "안녕하세요 여러부"},
                              {"start": 1.0, "end": 2.0, "text": "오늘의 강의입니다"}]}
            ),
        ).admission.raw_transcript_id.value
        self._raw_selection.select(self.intake, raw)
        if fallback:
            compose_sqlite_corrected_revision_selection_service(
                self.connection
            ).select_raw_fallback(intake_id=self.intake, reviewer="selector:kim")

    # -- explicit stage commands ----------------------------------------------------------------------

    def to_subject(self):
        self.candidate = self.generation.generate(intake_id=self.intake).candidate
        self.subject = self.preparation.prepare_review(
            candidate_id=self.candidate.identity.value
        ).subject
        return self.subject

    def decide(self, kind: str, reviewer: str = "reviewer:kim"):
        return self.decisions.decide(
            review_subject_id=self.subject.identity.value, kind=kind, reviewer=reviewer
        )

    def to_artifact(self):
        self.final_selection = self.selection.select_final(
            review_subject_id=self.subject.identity.value, selector="selector:park"
        ).selection
        self.artifact = self.export.generate_srt_artifact(
            final_selection_id=self.final_selection.identity.value
        ).artifact
        return self.artifact

    def to_publication(self):
        self.materialization = self.materializer.materialize(
            artifact_id=self.artifact.identity.value
        ).materialization
        self.delivery = self.deliverer.deliver(
            materialization_id=self.materialization.identity.value
        ).delivery
        self.publication = self.publisher.publish(
            delivery_id=self.delivery.identity.value, publisher="publisher:kim"
        ).publication
        return self.publication

    def run_all(self):
        self.to_subject()
        self.decision = self.decide("accept").decision
        self.to_artifact()
        return self.to_publication()

    # -- observation ----------------------------------------------------------------------------------

    def rows(self, table: str) -> int:
        return self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def snapshot(self) -> dict:
        return {table: self.rows(table) for table in _STAGE_TABLES}

    def reopen(self) -> None:
        self.connection.close()
        self.connection = open_sqlite_database(self.database)
        self._compose_services()

    def close(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass


class EffectiveSubtitlePipelineReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.pipeline = _Pipeline(Path(self.tempdir.name))

    def tearDown(self):
        self.pipeline.close()
        self.tempdir.cleanup()

    # -- Scenario A: full successful pipeline -----------------------------------------------------

    def test_full_pipeline_lineage_bytes_and_availability(self):
        p = self.pipeline
        p.run_all()
        # Typed lineage across every stage.
        self.assertEqual(p.candidate.transcript_source_intake_id.value, p.intake)
        self.assertEqual(p.subject.candidate_id, p.candidate.identity)
        self.assertEqual(p.decision.review_subject_id, p.subject.identity)
        self.assertEqual(p.final_selection.candidate_id, p.candidate.identity)
        self.assertEqual(p.final_selection.review_subject_id, p.subject.identity)
        self.assertEqual(p.final_selection.supporting_decision_id, p.decision.identity)
        self.assertEqual(p.artifact.final_selection_id, p.final_selection.identity)
        self.assertEqual(p.artifact.candidate_id, p.candidate.identity)
        self.assertEqual(p.materialization.artifact_id, p.artifact.identity)
        self.assertEqual(p.delivery.materialization_id, p.materialization.identity)
        self.assertEqual(p.delivery.artifact_id, p.artifact.identity)
        self.assertEqual(p.publication.target_delivery_id, p.delivery.identity)
        self.assertEqual(p.publication.target_artifact_id, p.artifact.identity)
        # Exact canonical bytes end to end.
        canonical = p.artifact.srt_content.encode("utf-8")
        self.assertEqual(
            (p.storage_root / p.materialization.relative_location).read_bytes(),
            canonical,
        )
        self.assertEqual(
            (p.delivery_root / p.delivery.relative_location).read_bytes(), canonical
        )
        self.assertEqual(
            p.delivery.expected_payload_fingerprint, p.artifact.content_fingerprint
        )
        # Derived availability; exactly one record per stage; Scenario J — legacy isolation.
        self.assertIs(
            p.publisher.availability(p.intake), PublicationAvailability.AVAILABLE
        )
        for table in _STAGE_TABLES:
            self.assertEqual(p.rows(table), 1, table)
        for table in _LEGACY_TABLES:
            self.assertEqual(p.rows(table), 0, table)

    def test_identity_namespaces_are_distinct_and_typed(self):
        p = self.pipeline
        p.run_all()
        prefixes = [
            value.split(":")[0]
            for value in (
                p.candidate.identity.value,
                p.subject.identity.value,
                p.decision.identity.value,
                p.final_selection.identity.value,
                p.artifact.identity.value,
                p.materialization.identity.value,
                p.delivery.identity.value,
                p.publication.identity.value,
            )
        ]
        self.assertEqual(len(set(prefixes)), 8, prefixes)

    # -- Scenario B: exact full replay ------------------------------------------------------------

    def test_exact_full_replay_creates_no_new_state(self):
        p = self.pipeline
        p.run_all()
        before = p.snapshot()
        self.assertEqual(
            p.generation.generate(intake_id=p.intake).outcome.value, "reused"
        )
        self.assertEqual(
            p.preparation.prepare_review(
                candidate_id=p.candidate.identity.value
            ).outcome.value,
            "reused",
        )
        self.assertEqual(p.decide("accept").outcome.value, "reused")
        self.assertEqual(
            p.selection.select_final(
                review_subject_id=p.subject.identity.value, selector="selector:park"
            ).outcome.value,
            "reused",
        )
        self.assertEqual(
            p.export.generate_srt_artifact(
                final_selection_id=p.final_selection.identity.value
            ).outcome.value,
            "reused",
        )
        self.assertEqual(
            p.materializer.materialize(
                artifact_id=p.artifact.identity.value
            ).kind.value,
            "reused",
        )
        self.assertEqual(
            p.deliverer.deliver(
                materialization_id=p.materialization.identity.value
            ).kind.value,
            "reused",
        )
        self.assertEqual(
            p.publisher.publish(
                delivery_id=p.delivery.identity.value, publisher="publisher:kim"
            ).outcome.value,
            "reused",
        )
        self.assertEqual(p.snapshot(), before)

    # -- Scenario C: Reject blocks downstream authority -------------------------------------------

    def test_reject_blocks_all_downstream_stages(self):
        p = self.pipeline
        p.to_subject()
        p.decide("reject")
        with self.assertRaises(ReviewSubjectNotEligibleError):
            p.selection.select_final(
                review_subject_id=p.subject.identity.value, selector="selector:park"
            )
        for table in _STAGE_TABLES[3:]:
            self.assertEqual(p.rows(table), 0, table)

    # -- Scenario D: Modify is not Accept ---------------------------------------------------------

    def test_modify_is_not_treated_as_accept(self):
        p = self.pipeline
        p.to_subject()
        p.decide("modify")
        report = p.selection.eligibility(p.subject.identity.value)
        self.assertFalse(report.eligible)
        self.assertEqual(report.blocking_reason.value, "decision_not_accept")
        with self.assertRaises(ReviewSubjectNotEligibleError):
            p.selection.select_final(
                review_subject_id=p.subject.identity.value, selector="selector:park"
            )

    # -- Scenario E: new Accept after a previous decision -----------------------------------------

    def test_new_accept_lineage_after_reject(self):
        p = self.pipeline
        p.to_subject()
        rejected = p.decide("reject").decision
        accepted = p.decide("accept").decision
        self.assertEqual(accepted.sequence, rejected.sequence + 1)
        p.to_artifact()
        # The selection captures the exact NEW supporting Accept; the reject stays history.
        self.assertEqual(p.final_selection.supporting_decision_id, accepted.identity)
        self.assertEqual(
            p.decisions.get(rejected.identity.value).kind.value, "reject"
        )

    # -- Scenario F: replacement candidate --------------------------------------------------------

    def test_replacement_candidate_supersedes_preserving_history(self):
        p = self.pipeline
        p.run_all()
        first_selection = p.final_selection
        first_artifact = p.artifact
        p.admit_raw("B", fallback=True)
        p.to_subject()
        p.decide("accept")
        p.to_artifact()
        self.assertNotEqual(p.final_selection.identity, first_selection.identity)
        self.assertEqual(p.final_selection.sequence, first_selection.sequence + 1)
        self.assertNotEqual(p.artifact.identity, first_artifact.identity)
        # The old artifact remains immutable history and derives superseded.
        self.assertEqual(
            p.export.get(first_artifact.identity.value), first_artifact
        )
        self.assertIs(
            p.export.currentness(first_artifact),
            ArtifactCurrentness.SUPERSEDED_BY_FINAL_SELECTION,
        )
        # A superseded selection cannot generate a NEW artifact.
        with self.assertRaises(FinalSelectionNotExportableError):
            p.export.generate_srt_artifact(
                final_selection_id=first_selection.identity.value
            )

    # -- Scenario G: physical file deletion -------------------------------------------------------

    def test_physical_deletion_preserves_materialization_history(self):
        p = self.pipeline
        p.run_all()
        before = p.snapshot()
        (p.storage_root / p.materialization.relative_location).unlink()
        self.assertEqual(
            p.materializer.state(p.materialization).value, "materialized"
        )
        self.assertIsNone(p.materializer.file_matches(p.materialization))
        self.assertEqual(p.snapshot(), before)

    # -- Scenario H: delivered destination deletion -----------------------------------------------

    def test_destination_deletion_preserves_history_and_derives_availability(self):
        p = self.pipeline
        p.run_all()
        before = p.snapshot()
        (p.delivery_root / p.delivery.relative_location).unlink()
        self.assertEqual(p.deliverer.state(p.delivery).value, "delivered")
        current = p.publisher.current(p.intake)
        self.assertEqual(current.identity, p.publication.identity)
        self.assertIs(
            p.publisher.availability(p.intake),
            PublicationAvailability.DESTINATION_MISSING,
        )
        self.assertEqual(p.snapshot(), before)

    # -- Scenario I: withdraw and republish -------------------------------------------------------

    def test_withdraw_and_republish_append_only(self):
        p = self.pipeline
        p.run_all()
        p.publisher.withdraw(intake_id=p.intake, publisher="publisher:kim")
        self.assertIs(
            p.publisher.availability(p.intake), PublicationAvailability.WITHDRAWN
        )
        republished = p.publisher.publish(
            delivery_id=p.delivery.identity.value, publisher="publisher:kim"
        ).publication
        history = p.publisher.history(p.intake)
        self.assertEqual(
            [record.kind.value for record in history],
            ["publish", "withdraw", "publish"],
        )
        self.assertEqual(p.publisher.current(p.intake).identity, republished.identity)
        self.assertIs(
            p.publisher.availability(p.intake), PublicationAvailability.AVAILABLE
        )
        # Withdrawal deleted nothing: destination bytes and delivery history intact.
        self.assertEqual(
            (p.delivery_root / p.delivery.relative_location).read_bytes(),
            p.artifact.srt_content.encode("utf-8"),
        )

    # -- Scenario K: repository restart reconstruction --------------------------------------------

    def test_restart_reconstructs_every_derived_state(self):
        p = self.pipeline
        p.run_all()
        p.reopen()
        self.assertEqual(
            p.decisions.current(p.subject.identity.value).identity, p.decision.identity
        )
        self.assertEqual(
            p.selection.current(p.intake).identity, p.final_selection.identity
        )
        restored_artifact = p.export.get(p.artifact.identity.value)
        self.assertEqual(restored_artifact, p.artifact)
        self.assertIs(
            p.export.currentness(restored_artifact), ArtifactCurrentness.CURRENT
        )
        restored_materialization = p.materializer.get(p.materialization.identity.value)
        self.assertEqual(
            p.materializer.state(restored_materialization).value, "materialized"
        )
        restored_delivery = p.deliverer.get(p.delivery.identity.value)
        self.assertEqual(p.deliverer.state(restored_delivery).value, "delivered")
        self.assertEqual(
            p.publisher.current(p.intake).identity, p.publication.identity
        )
        self.assertIs(
            p.publisher.availability(p.intake), PublicationAvailability.AVAILABLE
        )

    # -- Scenario L: validation and cross-stage corruption ----------------------------------------

    def test_validation_healthy_and_cross_stage_corruption_detected(self):
        p = self.pipeline
        p.run_all()
        p.connection.close()
        report = validate_database(str(p.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")

        def _corrupt(name: str, statement: str) -> set[str]:
            target = p.base / name
            shutil.copyfile(p.database, target)
            connection = sqlite3.connect(target)
            try:
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute("BEGIN")
                connection.execute(statement)
                connection.execute("COMMIT")
            finally:
                connection.close()
            return {d.code for d in validate_database(str(target)).diagnostics}

        # Cross-stage mismatch 1: a delivery whose artifact lineage disagrees with its
        # materialization.
        codes = _corrupt(
            "cross-delivery.db",
            "UPDATE subtitle_effective_srt_delivery_intents "
            "SET artifact_id = 'subtitle-effective-srt-artifact:" + "0" * 64 + "'",
        )
        self.assertIn("EFFECTIVE_SRT_DELIVERY_ARTIFACT_LINEAGE_MISMATCH", codes)
        # Cross-stage mismatch 2: a publication whose scope disagrees with its target
        # delivery's intake scope.
        codes = _corrupt(
            "cross-publication.db",
            "UPDATE subtitle_effective_srt_publications "
            "SET transcript_source_intake_id = "
            "'transcript-source-intake:sha256:" + "0" * 64 + "'",
        )
        self.assertIn("EFFECTIVE_SRT_PUBLICATION_SCOPE_MISMATCH", codes)
        p.connection = open_sqlite_database(p.database)


if __name__ == "__main__":
    unittest.main()
