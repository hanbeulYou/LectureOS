"""Application tests for Effective-Transcript Subtitle Candidate generation (041 §15, GOAL-013)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.corrected_revision_selection import (
    CorrectedRevisionSelectionError,
)
from lectureos.application.effective_subtitle_generation import (
    EffectiveSubtitleGenerationConflictError,
    GENERATOR_KIND,
    GENERATOR_VERSION,
    GENERATION_PARAMETERS_VERSION,
    EffectiveSubtitleGenerationService,
    derive_effective_candidate_identity,
    derive_effective_cue_identity,
)
from lectureos.application.effective_transcript_consumption import (
    ConsumedSourceKind,
    ConsumptionCurrentness,
    InapplicableSelectedRevisionError,
    SUBTITLE_GENERATION_CONSUMER_KIND,
)
from lectureos.application.identities import (
    EffectiveTranscriptConsumptionId,
    TranscriptSourceIntakeId,
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
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_transcript_consumption_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteEffectiveSubtitleCandidateCommandPersistence,
    SQLiteEffectiveSubtitleCandidateRepository,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
)
from lectureos.transcript.identities import TranscriptId

_INTAKE = TranscriptSourceIntakeId("transcript-source-intake:sha256:" + "a" * 64)
_BINDING = EffectiveTranscriptConsumptionId("transcript-consumption:" + "b" * 64)
_BINDING2 = EffectiveTranscriptConsumptionId("transcript-consumption:" + "c" * 64)
_RAW = "raw-transcript:" + "1" * 64


class IdentityTests(unittest.TestCase):
    def test_candidate_identity_deterministic_and_input_sensitive(self):
        base = derive_effective_candidate_identity(
            _INTAKE, _BINDING, ConsumedSourceKind.RAW_TRANSCRIPT, _RAW,
            GENERATOR_KIND, GENERATOR_VERSION, GENERATION_PARAMETERS_VERSION,
        )
        self.assertEqual(
            base,
            derive_effective_candidate_identity(
                _INTAKE, _BINDING, ConsumedSourceKind.RAW_TRANSCRIPT, _RAW,
                GENERATOR_KIND, GENERATOR_VERSION, GENERATION_PARAMETERS_VERSION,
            ),
        )
        self.assertTrue(base.value.startswith("subtitle-effective-candidate:"))
        # different binding
        self.assertNotEqual(base, derive_effective_candidate_identity(
            _INTAKE, _BINDING2, ConsumedSourceKind.RAW_TRANSCRIPT, _RAW,
            GENERATOR_KIND, GENERATOR_VERSION, GENERATION_PARAMETERS_VERSION))
        # different exact source
        self.assertNotEqual(base, derive_effective_candidate_identity(
            _INTAKE, _BINDING, ConsumedSourceKind.RAW_TRANSCRIPT, "raw-transcript:" + "2" * 64,
            GENERATOR_KIND, GENERATOR_VERSION, GENERATION_PARAMETERS_VERSION))
        # different source kind
        self.assertNotEqual(base, derive_effective_candidate_identity(
            _INTAKE, _BINDING, ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION,
            "corrected-revision:" + "1" * 64,
            GENERATOR_KIND, GENERATOR_VERSION, GENERATION_PARAMETERS_VERSION))
        # different generator version / parameters version
        self.assertNotEqual(base, derive_effective_candidate_identity(
            _INTAKE, _BINDING, ConsumedSourceKind.RAW_TRANSCRIPT, _RAW,
            GENERATOR_KIND, 2, GENERATION_PARAMETERS_VERSION))
        self.assertNotEqual(base, derive_effective_candidate_identity(
            _INTAKE, _BINDING, ConsumedSourceKind.RAW_TRANSCRIPT, _RAW,
            GENERATOR_KIND, GENERATOR_VERSION, 2))

    def test_cue_identity_deterministic(self):
        candidate = derive_effective_candidate_identity(
            _INTAKE, _BINDING, ConsumedSourceKind.RAW_TRANSCRIPT, _RAW,
            GENERATOR_KIND, GENERATOR_VERSION, GENERATION_PARAMETERS_VERSION,
        )
        from lectureos.transcript.identities import TranscriptSegmentId

        segment = TranscriptSegmentId("transcript-segment:" + "1" * 64 + ":0")
        a = derive_effective_cue_identity(candidate, 0, segment)
        self.assertEqual(a, derive_effective_cue_identity(candidate, 0, segment))
        self.assertNotEqual(a, derive_effective_cue_identity(candidate, 1, segment))
        self.assertTrue(a.value.startswith("subtitle-effective-cue:"))


class EffectiveSubtitleGenerationServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.connection = initialize_sqlite_database(self.base / "lectureos.sqlite3")
        source = self.base / "a.bin"
        source.write_bytes(b"effective-subtitle \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        self.provider = compose_sqlite_provider_transcript_admission_service(self.connection)
        self.raw_selection = compose_sqlite_current_raw_transcript_selection_service(self.connection)
        self.decisions = compose_sqlite_correction_candidate_decision_service(self.connection)
        self.selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        self.generation = compose_sqlite_effective_subtitle_generation_service(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _admit_raw(self, ref: str, texts=("원본 하나", "원본 둘")) -> str:
        return self.provider.admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": ref,
                 "segments": [
                     {"start": float(i), "end": float(i) + 1.0, "text": text}
                     for i, text in enumerate(texts)
                 ]}
            ),
        ).admission.raw_transcript_id.value

    def _revision_for(self, raw_id: str, proposed: str = "교정 하나") -> tuple[str, str]:
        segment = SQLiteRawTranscriptRepository(self.connection).get(
            TranscriptId(raw_id)
        ).segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(self.connection).get(segment).text
        candidate = compose_sqlite_correction_candidate_admission_service(self.connection).admit(
            intake_id=self.intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw_id, "segment_id": segment.value,
                 "candidate_ref": "c-" + proposed, "source_type": "manual",
                 "source_reference": "human", "proposed_text": proposed,
                 "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate.identity.value
        self.decisions.decide(candidate_id=candidate, kind="accept", reviewer="r:kim")
        revision = compose_sqlite_corrected_revision_generation_service(self.connection).generate(
            candidate_id=candidate
        ).revision.identity.value
        return candidate, revision

    # -- raw source (matrix 1, 2, 8, 10, 12, cue semantics) ------------------------------------------

    def test_generate_from_raw_no_history_with_exact_lineage(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        result = self.generation.generate(intake_id=self.intake)
        candidate = result.candidate
        self.assertEqual(result.outcome.value, "created")
        self.assertIs(candidate.source_kind, ConsumedSourceKind.RAW_TRANSCRIPT)
        self.assertEqual(candidate.source_transcript_identity, raw)
        self.assertEqual(candidate.parent_raw_transcript_id.value, raw)
        self.assertEqual(candidate.generator_kind, GENERATOR_KIND)
        self.assertEqual(candidate.cue_count, 2)
        raw_segments = SQLiteRawTranscriptRepository(self.connection).get(
            TranscriptId(raw)
        ).segment_ids
        self.assertEqual([c.text for c in result.cues], ["원본 하나", "원본 둘"])
        self.assertEqual([c.ordinal for c in result.cues], [0, 1])
        self.assertEqual([(c.start, c.end) for c in result.cues], [(0.0, 1.0), (1.0, 2.0)])
        self.assertEqual([c.source_segment_ids for c in result.cues],
                         [(raw_segments[0],), (raw_segments[1],)])
        # The GOAL-012 binding exists and matches (matrix 7).
        consumption = compose_sqlite_effective_transcript_consumption_service(self.connection)
        binding = consumption.get_binding(candidate.consumption_binding_id)
        self.assertIsNotNone(binding)
        self.assertEqual(binding.consumer_kind, SUBTITLE_GENERATION_CONSUMER_KIND)
        self.assertEqual(binding.content_fingerprint, candidate.source_snapshot_fingerprint)

    def test_generate_under_explicit_raw_fallback(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        self.selection.select_raw_fallback(intake_id=self.intake, reviewer="s:kim")
        result = self.generation.generate(intake_id=self.intake)
        self.assertEqual(result.candidate.source_transcript_identity, raw)
        self.assertIs(result.currentness, ConsumptionCurrentness.CURRENT)

    # -- corrected source (matrix 3, 9, 10, 11, corrected lineage) -----------------------------------

    def test_generate_from_corrected_revision_with_replacement_lineage(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        _, revision = self._revision_for(raw, "교정된 첫")
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        result = self.generation.generate(intake_id=self.intake)
        candidate = result.candidate
        self.assertIs(candidate.source_kind, ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION)
        self.assertEqual(candidate.source_transcript_identity, revision)
        self.assertEqual(candidate.parent_raw_transcript_id.value, raw)
        self.assertEqual(result.cues[0].text, "교정된 첫")
        self.assertEqual(result.cues[1].text, "원본 둘")
        raw_segments = SQLiteRawTranscriptRepository(self.connection).get(
            TranscriptId(raw)
        ).segment_ids
        corrected_segment = result.cues[0].source_segment_ids[0]
        self.assertNotEqual(corrected_segment, raw_segments[0])
        segment_record = SQLiteTranscriptSegmentRepository(self.connection).get(corrected_segment)
        self.assertEqual(segment_record.replaces_segment_id, raw_segments[0])
        self.assertIsNone(segment_record.confidence)
        # Unchanged segment keeps its original canonical identity.
        self.assertEqual(result.cues[1].source_segment_ids[0], raw_segments[1])

    # -- consumability failures (matrix 4, 5) --------------------------------------------------------

    def test_no_current_raw_blocks_generation(self):
        with self.assertRaises(CorrectedRevisionSelectionError):
            self.generation.generate(intake_id=self.intake)
        self.assertEqual(self.generation.list_for_intake(self.intake), ())

    def test_inapplicable_selection_blocks_generation_without_fallback(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        candidate, revision = self._revision_for(raw)
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        self.decisions.decide(candidate_id=candidate, kind="reject", reviewer="r:kim")
        with self.assertRaises(InapplicableSelectedRevisionError):
            self.generation.generate(intake_id=self.intake)
        self.assertEqual(self.generation.list_for_intake(self.intake), ())
        consumption = compose_sqlite_effective_transcript_consumption_service(self.connection)
        self.assertEqual(consumption.bindings(self.intake), ())  # no binding persisted either

    # -- replay (matrix 23-27) -----------------------------------------------------------------------

    def test_identical_replay_reuses_without_duplicates(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        first = self.generation.generate(intake_id=self.intake)
        second = self.generation.generate(intake_id=self.intake)
        self.assertEqual(second.outcome.value, "reused")
        self.assertEqual(first.candidate, second.candidate)
        self.assertEqual(first.cues, second.cues)
        counts = self.connection.execute(
            "SELECT (SELECT COUNT(*) FROM subtitle_effective_candidates), "
            "(SELECT COUNT(*) FROM subtitle_effective_candidate_cues), "
            "(SELECT COUNT(*) FROM subtitle_effective_candidate_cue_segments)"
        ).fetchone()
        self.assertEqual(counts, (1, 2, 2))

    def test_raw_round_trip_reuses_original_candidate(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        s1 = self.generation.generate(intake_id=self.intake)
        _, revision = self._revision_for(raw)
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        s2 = self.generation.generate(intake_id=self.intake)
        self.assertNotEqual(s1.candidate.identity, s2.candidate.identity)
        self.selection.select_raw_fallback(intake_id=self.intake, reviewer="s:kim")
        s1_again = self.generation.generate(intake_id=self.intake)
        self.assertEqual(s1_again.outcome.value, "reused")
        self.assertEqual(s1_again.candidate.identity, s1.candidate.identity)
        self.assertEqual(len(self.generation.list_for_intake(self.intake)), 2)

    def test_same_content_different_source_stays_distinct(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        s1 = self.generation.generate(intake_id=self.intake)
        raw2 = self._admit_raw("B")  # identical content, distinct immutable entity
        self.assertNotEqual(raw, raw2)
        self.raw_selection.select(self.intake, raw2)
        s2 = self.generation.generate(intake_id=self.intake)
        self.assertEqual(s2.outcome.value, "created")
        self.assertNotEqual(s1.candidate.identity, s2.candidate.identity)
        self.assertEqual(
            s1.candidate.source_snapshot_fingerprint,
            s2.candidate.source_snapshot_fingerprint,
        )

    # -- concurrency and conflicts (matrix 40, 41) ----------------------------------------------------

    def test_near_concurrent_identical_generation_converges(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        self.generation.generate(intake_id=self.intake)  # the competing winner

        class _RacingView:
            def __init__(self, inner):
                self._inner = inner
                self._missed = False

            def get(self, identity):
                if not self._missed:
                    self._missed = True
                    return None
                return self._inner.get(identity)

            def cues(self, candidate_id):
                return self._inner.cues(candidate_id)

            def list_for_intake(self, intake_id):
                return self._inner.list_for_intake(intake_id)

        racing = EffectiveSubtitleGenerationService(
            compose_sqlite_effective_transcript_consumption_service(self.connection),
            _RacingView(SQLiteEffectiveSubtitleCandidateRepository(self.connection)),
            SQLiteEffectiveSubtitleCandidateCommandPersistence(self.connection),
        )
        result = racing.generate(intake_id=self.intake)
        self.assertEqual(result.outcome.value, "reused")
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_candidates"
            ).fetchone()[0],
            1,
        )

    def test_divergent_payload_for_same_identity_is_explicit_conflict(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        self.generation.generate(intake_id=self.intake)
        self.connection.execute("PRAGMA foreign_keys = OFF")
        try:
            self.connection.execute(
                "UPDATE subtitle_effective_candidates SET source_snapshot_fingerprint = ?",
                ("f" * 64,),
            )
        finally:
            self.connection.execute("PRAGMA foreign_keys = ON")
        with self.assertRaises(EffectiveSubtitleGenerationConflictError):
            self.generation.generate(intake_id=self.intake)

    # -- immutability and isolation (matrix 14-22, 46-49) --------------------------------------------

    def test_authority_changes_never_rewrite_candidates(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        candidate_a, revision = self._revision_for(raw)
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        s2 = self.generation.generate(intake_id=self.intake)
        history_before = self.selection.history(self.intake)
        self.decisions.decide(candidate_id=candidate_a, kind="reject", reviewer="r:kim")
        raw2 = self._admit_raw("B", ("다른 원본",))
        self.raw_selection.select(self.intake, raw2)
        persisted = [
            c for c in self.generation.list_for_intake(self.intake)
            if c.identity == s2.candidate.identity
        ][0]
        self.assertEqual(persisted, s2.candidate)
        self.assertEqual(self.generation.cues(persisted.identity.value), s2.cues)
        self.assertEqual(self.selection.history(self.intake), history_before)
        # No legacy or downstream record was created.
        for table in ("subtitle_candidates", "subtitle_review_decisions",
                      "subtitle_final_subtitles", "processing_runs", "unit_executions"):
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
                table,
            )

    # -- derived currentness (matrix 50-53) -----------------------------------------------------------

    def test_currentness_current_and_stale_states(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        s1 = self.generation.generate(intake_id=self.intake)
        self.assertIs(self.generation.currentness(s1.candidate), ConsumptionCurrentness.CURRENT)
        candidate_a, revision = self._revision_for(raw)
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        s2 = self.generation.generate(intake_id=self.intake)
        self.assertIs(
            self.generation.currentness(s1.candidate),
            ConsumptionCurrentness.STALE_DUE_TO_CORRECTED_SELECTION_CHANGE,
        )
        self.decisions.decide(candidate_id=candidate_a, kind="reject", reviewer="r:kim")
        self.assertIs(
            self.generation.currentness(s2.candidate),
            ConsumptionCurrentness.STALE_DUE_TO_SELECTED_REVISION_INAPPLICABILITY,
        )
        raw2 = self._admit_raw("B", ("다른 원본",))
        self.selection.select_raw_fallback(intake_id=self.intake, reviewer="s:kim")
        self.raw_selection.select(self.intake, raw2)
        self.assertIs(
            self.generation.currentness(s1.candidate),
            ConsumptionCurrentness.STALE_DUE_TO_RAW_SELECTION_CHANGE,
        )


if __name__ == "__main__":
    unittest.main()
