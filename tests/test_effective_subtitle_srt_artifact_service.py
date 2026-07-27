"""Application tests for Effective Subtitle SRT Artifact generation (GOAL-017)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.effective_subtitle_srt_artifact import (
    ArtifactCurrentness,
    EffectiveSubtitleSrtArtifactError,
    EffectiveSubtitleSrtArtifactService,
    ExportBlockingReason,
    FinalSelectionNotExportableError,
    SrtArtifactConflictError,
    derive_srt_artifact_identity,
    derive_srt_content_fingerprint,
    serialize_effective_cues,
)
from lectureos.application.identities import (
    EffectiveSubtitleCandidateId,
    EffectiveSubtitleFinalSelectionId,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.application.srt_payload import serialize_srt_cues
from lectureos.composition import (
    compose_sqlite_corrected_revision_selection_service,
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
from lectureos.persistence import (
    SQLiteEffectiveSubtitleSrtArtifactCommandPersistence,
    SQLiteEffectiveSubtitleSrtArtifactRepository,
    initialize_sqlite_database,
)

_SEL = EffectiveSubtitleFinalSelectionId("subtitle-effective-final-selection:" + "a" * 64)
_SEL2 = EffectiveSubtitleFinalSelectionId("subtitle-effective-final-selection:" + "b" * 64)
_CAND = EffectiveSubtitleCandidateId("subtitle-effective-candidate:" + "a" * 64)


class SerializationAndIdentityTests(unittest.TestCase):
    def test_srt_serialization_contract(self):
        payload = serialize_srt_cues([(0.0, 1.0, "하나"), (1.0, 2.5, "둘\n셋")])
        self.assertEqual(
            payload,
            "1\n00:00:00,000 --> 00:00:01,000\n하나\n\n"
            "2\n00:00:01,000 --> 00:00:02,500\n둘\n셋\n",
        )
        self.assertEqual(serialize_srt_cues([]), "")
        with self.assertRaises(ValueError):  # collapsed duration
            serialize_srt_cues([(1.0, 1.0, "x")])
        with self.assertRaises(ValueError):  # negative time
            serialize_srt_cues([(-1.0, 1.0, "x")])

    def test_identity_deterministic_and_input_sensitive(self):
        fingerprint = derive_srt_content_fingerprint("1\n00:00:00,000 --> 00:00:01,000\nx\n")
        base = derive_srt_artifact_identity(_SEL, _CAND, fingerprint)
        self.assertEqual(base, derive_srt_artifact_identity(_SEL, _CAND, fingerprint))
        self.assertTrue(base.value.startswith("subtitle-effective-srt-artifact:"))
        self.assertNotEqual(base, derive_srt_artifact_identity(_SEL2, _CAND, fingerprint))
        other = derive_srt_content_fingerprint("other")
        self.assertNotEqual(base, derive_srt_artifact_identity(_SEL, _CAND, other))


class EffectiveSubtitleSrtArtifactServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.connection = initialize_sqlite_database(self.base / "lectureos.sqlite3")
        source = self.base / "a.bin"
        source.write_bytes(b"srt-artifact \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        self.provider = compose_sqlite_provider_transcript_admission_service(self.connection)
        self.raw_selection = compose_sqlite_current_raw_transcript_selection_service(self.connection)
        self.revision_selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        self.generation = compose_sqlite_effective_subtitle_generation_service(self.connection)
        self.preparation = compose_sqlite_effective_subtitle_review_preparation_service(self.connection)
        self.decisions = compose_sqlite_effective_subtitle_review_decision_service(self.connection)
        self.selection = compose_sqlite_effective_subtitle_final_selection_service(self.connection)
        self.export = compose_sqlite_effective_subtitle_srt_artifact_service(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _admit_raw(self, ref: str) -> str:
        return self.provider.admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": ref,
                 "segments": [{"start": 0.0, "end": 1.0, "text": "원본"}]}
            ),
        ).admission.raw_transcript_id.value

    def _select(self, ref="A"):
        raw = self._admit_raw(ref)
        self.raw_selection.select(self.intake, raw)
        if ref != "A":
            self.revision_selection.select_raw_fallback(
                intake_id=self.intake, reviewer="s:kim"
            )
        candidate = self.generation.generate(intake_id=self.intake).candidate
        subject = self.preparation.prepare_review(candidate_id=candidate.identity.value).subject
        self.decisions.decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        return candidate, self.selection.select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        ).selection

    def test_eligibility_and_export_with_exact_payload(self):
        candidate, sel = self._select()
        report = self.export.export_eligibility(sel.identity.value)
        self.assertTrue(report.eligible)
        result = self.export.generate_srt_artifact(final_selection_id=sel.identity.value)
        self.assertEqual(result.outcome.value, "created")
        self.assertEqual(result.artifact.final_selection_id, sel.identity)
        self.assertEqual(result.artifact.candidate_id, candidate.identity)
        self.assertEqual(
            result.artifact.srt_content, "1\n00:00:00,000 --> 00:00:01,000\n원본\n"
        )
        self.assertEqual(result.artifact.cue_count, 1)
        self.assertIs(result.currentness, ArtifactCurrentness.CURRENT)
        cues = self.generation.cues(candidate.identity.value)
        self.assertEqual(serialize_effective_cues(cues), result.artifact.srt_content)

    def test_missing_selection_blocks(self):
        report = self.export.export_eligibility(
            "subtitle-effective-final-selection:" + "0" * 64
        )
        self.assertFalse(report.eligible)
        self.assertIs(report.blocking_reason, ExportBlockingReason.SELECTION_NOT_FOUND)
        with self.assertRaises(FinalSelectionNotExportableError):
            self.export.generate_srt_artifact(
                final_selection_id="subtitle-effective-final-selection:" + "0" * 64
            )

    def test_superseded_selection_blocks_new_export(self):
        _, sel_a = self._select()
        first = self.export.generate_srt_artifact(final_selection_id=sel_a.identity.value)
        _, sel_b = self._select("B")
        report = self.export.export_eligibility(sel_a.identity.value)
        self.assertFalse(report.eligible)
        self.assertIs(report.blocking_reason, ExportBlockingReason.SELECTION_NOT_CURRENT)
        with self.assertRaises(FinalSelectionNotExportableError):
            self.export.generate_srt_artifact(final_selection_id=sel_a.identity.value)
        # Historical artifact remains immutable and derives superseded.
        persisted = self.export.get(first.artifact.identity.value)
        self.assertEqual(persisted, first.artifact)
        self.assertIs(
            self.export.currentness(persisted),
            ArtifactCurrentness.SUPERSEDED_BY_FINAL_SELECTION,
        )
        second = self.export.generate_srt_artifact(final_selection_id=sel_b.identity.value)
        self.assertNotEqual(second.artifact.identity, first.artifact.identity)
        # Byte-identical payloads under different selections stay distinct.
        self.assertEqual(
            second.artifact.content_fingerprint, first.artifact.content_fingerprint
        )

    def test_stale_selection_blocks(self):
        _, sel = self._select()
        raw2 = self._admit_raw("B")
        self.raw_selection.select(self.intake, raw2)  # candidate source stale
        report = self.export.export_eligibility(sel.identity.value)
        self.assertFalse(report.eligible)
        self.assertIs(report.blocking_reason, ExportBlockingReason.SELECTION_NOT_APPLICABLE)
        with self.assertRaises(FinalSelectionNotExportableError):
            self.export.generate_srt_artifact(final_selection_id=sel.identity.value)
        self.assertEqual(self.export.list_for_intake(self.intake), ())

    def test_exact_replay_reuses(self):
        _, sel = self._select()
        first = self.export.generate_srt_artifact(final_selection_id=sel.identity.value)
        replay = self.export.generate_srt_artifact(final_selection_id=sel.identity.value)
        self.assertEqual(replay.outcome.value, "reused")
        self.assertEqual(replay.artifact, first.artifact)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_srt_artifacts"
            ).fetchone()[0],
            1,
        )

    def test_near_concurrent_identical_generation_converges(self):
        _, sel = self._select()
        self.export.generate_srt_artifact(final_selection_id=sel.identity.value)

        class _RacingView:
            def __init__(self, inner):
                self._inner = inner
                self._missed = False

            def get(self, identity):
                if not self._missed:
                    self._missed = True
                    return None
                return self._inner.get(identity)

            def get_for_selection(self, final_selection_id):
                return self._inner.get_for_selection(final_selection_id)

            def list_for_intake(self, intake_id):
                return self._inner.list_for_intake(intake_id)

        racing = EffectiveSubtitleSrtArtifactService(
            self.selection,
            self.generation,
            _RacingView(SQLiteEffectiveSubtitleSrtArtifactRepository(self.connection)),
            SQLiteEffectiveSubtitleSrtArtifactCommandPersistence(self.connection),
        )
        result = racing.generate_srt_artifact(final_selection_id=sel.identity.value)
        self.assertEqual(result.outcome.value, "reused")
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_srt_artifacts"
            ).fetchone()[0],
            1,
        )

    def test_divergent_payload_at_anchor_is_explicit_conflict(self):
        _, sel = self._select()
        self.export.generate_srt_artifact(final_selection_id=sel.identity.value)
        # Tamper the stored payload (self-consistent fingerprint+identity for the tampered
        # content so the model restores) occupying the same replay anchor.
        tampered_content = "1\n00:00:00,000 --> 00:00:01,000\n조작\n"
        tampered_fingerprint = derive_srt_content_fingerprint(tampered_content)
        tampered_identity = derive_srt_artifact_identity(
            sel.identity, sel.candidate_id, tampered_fingerprint
        )
        self.connection.execute("PRAGMA foreign_keys = OFF")
        try:
            self.connection.execute(
                "UPDATE subtitle_effective_srt_artifacts "
                "SET identity = ?, content_fingerprint = ?, srt_content = ?",
                (tampered_identity.value, tampered_fingerprint, tampered_content),
            )
        finally:
            self.connection.execute("PRAGMA foreign_keys = ON")
        with self.assertRaises(SrtArtifactConflictError):
            self.export.generate_srt_artifact(final_selection_id=sel.identity.value)

    def test_authority_change_derives_staleness_without_mutation(self):
        _, sel = self._select()
        result = self.export.generate_srt_artifact(final_selection_id=sel.identity.value)
        raw2 = self._admit_raw("B")
        self.raw_selection.select(self.intake, raw2)
        self.assertIs(
            self.export.currentness(result.artifact),
            ArtifactCurrentness.STALE_DUE_TO_CANDIDATE_SOURCE,
        )
        self.assertEqual(
            self.export.get(result.artifact.identity.value), result.artifact
        )

    def test_no_physical_or_legacy_records(self):
        _, sel = self._select()
        self.export.generate_srt_artifact(final_selection_id=sel.identity.value)
        for table in ("subtitle_srt_artifacts", "subtitle_srt_materializations"):
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
                table,
            )
        columns = {
            row[1]
            for row in self.connection.execute(
                "PRAGMA table_info(subtitle_effective_srt_artifacts)"
            ).fetchall()
        }
        for forbidden in ("physical_path", "filename", "url", "materialized"):
            self.assertNotIn(forbidden, columns)


if __name__ == "__main__":
    unittest.main()
