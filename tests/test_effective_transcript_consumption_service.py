"""Application tests for the Effective Transcript Consumption Boundary (040 §21, GOAL-012)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.corrected_revision_selection import (
    CorrectedRevisionSelectionError,
    SelectionState,
)
from lectureos.application.effective_transcript_consumption import (
    ConsumedSourceKind,
    ConsumptionConflictError,
    ConsumptionCurrentness,
    EffectiveTranscriptConsumption,
    EffectiveTranscriptConsumptionError,
    EffectiveTranscriptConsumptionService,
    InapplicableSelectedRevisionError,
    MANIFEST_CONSUMER_KIND,
    derive_consumption_identity,
)
from lectureos.application.identities import (
    CorrectedRevisionSelectionId,
    CurrentRawTranscriptSelectionId,
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
    compose_sqlite_effective_transcript_consumption_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteRawTranscriptRepository,
    initialize_sqlite_database,
)
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

_INTAKE = TranscriptSourceIntakeId("transcript-source-intake:sha256:" + "a" * 64)
_RAW = TranscriptId("raw-transcript:" + "1" * 64)
_REV = TranscriptRevisionId("corrected-revision:" + "a" * 64)
_RAW_SEL = CurrentRawTranscriptSelectionId("current-raw-transcript-selection:" + "0" * 64)
_COR_SEL = CorrectedRevisionSelectionId("corrected-revision-selection:" + "0" * 64)


class IdentityAndModelTests(unittest.TestCase):
    def test_identity_is_deterministic_and_input_sensitive(self):
        a = derive_consumption_identity(
            MANIFEST_CONSUMER_KIND, _INTAKE, ConsumedSourceKind.RAW_TRANSCRIPT, _RAW.value
        )
        self.assertEqual(
            a,
            derive_consumption_identity(
                MANIFEST_CONSUMER_KIND, _INTAKE, ConsumedSourceKind.RAW_TRANSCRIPT, _RAW.value
            ),
        )
        self.assertTrue(a.value.startswith("transcript-consumption:"))
        self.assertNotEqual(
            a,
            derive_consumption_identity(
                MANIFEST_CONSUMER_KIND, _INTAKE,
                ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION, _REV.value,
            ),
        )
        self.assertNotEqual(
            a,
            derive_consumption_identity(
                "other_consumer", _INTAKE, ConsumedSourceKind.RAW_TRANSCRIPT, _RAW.value
            ),
        )

    def _consumption(self, **overrides):
        forced_identity = overrides.pop("identity", None)
        values = dict(
            consumer_kind=MANIFEST_CONSUMER_KIND,
            transcript_source_intake_id=_INTAKE,
            resolution_state=SelectionState.NO_HISTORY,
            source_kind=ConsumedSourceKind.RAW_TRANSCRIPT,
            parent_raw_transcript_id=_RAW,
            corrected_revision_id=None,
            raw_selection_id=_RAW_SEL,
            corrected_selection_id=None,
            content_fingerprint="0" * 64,
            segment_count=1,
        )
        values.update(overrides)
        source = (
            values["corrected_revision_id"].value
            if values["source_kind"] is ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION
            and values["corrected_revision_id"] is not None
            else values["parent_raw_transcript_id"].value
        )
        identity = forced_identity or derive_consumption_identity(
            values["consumer_kind"], values["transcript_source_intake_id"],
            values["source_kind"], source,
        )
        return EffectiveTranscriptConsumption(identity=identity, **values)

    def test_kind_state_consistency_enforced(self):
        with self.assertRaises(ValueError):  # corrected kind without revision
            self._consumption(
                source_kind=ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION,
                resolution_state=SelectionState.CORRECTED_SELECTED,
                corrected_selection_id=_COR_SEL,
            )
        with self.assertRaises(ValueError):  # raw kind carrying a revision
            self._consumption(corrected_revision_id=_REV)
        with self.assertRaises(ValueError):  # no-history with observed corrected authority
            self._consumption(corrected_selection_id=_COR_SEL)
        with self.assertRaises(ValueError):  # fallback without observed authority
            self._consumption(resolution_state=SelectionState.RAW_FALLBACK)
        with self.assertRaises(ValueError):  # raw kind under corrected state
            self._consumption(
                resolution_state=SelectionState.CORRECTED_SELECTED,
                corrected_selection_id=_COR_SEL,
            )

    def test_identity_derivation_enforced(self):
        wrong = derive_consumption_identity(
            MANIFEST_CONSUMER_KIND, _INTAKE, ConsumedSourceKind.RAW_TRANSCRIPT, "raw-transcript:" + "9" * 64
        )
        with self.assertRaises(ValueError):
            self._consumption(identity=wrong)

    def test_fingerprint_shape_enforced(self):
        with self.assertRaises(ValueError):
            self._consumption(content_fingerprint="xyz")
        with self.assertRaises(ValueError):
            self._consumption(segment_count=-1)


class _RacingConsumptionView:
    """Misses the first identity lookup so a competing insert manifests as a collision."""

    def __init__(self, inner):
        self._inner = inner
        self._missed = False

    def get(self, identity):
        if not self._missed:
            self._missed = True
            return None
        return self._inner.get(identity)

    def list_for_intake(self, intake_id):
        return self._inner.list_for_intake(intake_id)


class EffectiveTranscriptConsumptionServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.connection = initialize_sqlite_database(self.base / "lectureos.sqlite3")
        source = self.base / "a.bin"
        source.write_bytes(b"consumption \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        self.provider = compose_sqlite_provider_transcript_admission_service(self.connection)
        self.raw_selection = compose_sqlite_current_raw_transcript_selection_service(self.connection)
        self.decisions = compose_sqlite_correction_candidate_decision_service(self.connection)
        self.selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        self.consumption = compose_sqlite_effective_transcript_consumption_service(self.connection)

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _admit_raw(self, ref: str, texts: tuple[str, ...] = ("원본 하나", "원본 둘")) -> str:
        segments = [
            {"start": float(i), "end": float(i) + 1.0, "text": text}
            for i, text in enumerate(texts)
        ]
        return self.provider.admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": ref, "segments": segments}
            ),
        ).admission.raw_transcript_id.value

    def _revision_for(self, raw_id: str, proposed: str = "교정 하나") -> tuple[str, str]:
        segment = SQLiteRawTranscriptRepository(self.connection).get(
            TranscriptId(raw_id)
        ).segment_ids[0]
        from lectureos.persistence import SQLiteTranscriptSegmentRepository

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

    # -- resolution states (matrix 1, 2, 3, 5, 9) --------------------------------------------------

    def test_acquire_raw_with_no_history(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        acquired = self.consumption.acquire_input(self.intake)
        self.assertIs(acquired.selection_state, SelectionState.NO_HISTORY)
        self.assertIs(acquired.source_kind, ConsumedSourceKind.RAW_TRANSCRIPT)
        self.assertEqual(acquired.source_transcript_identity, raw)
        self.assertEqual(acquired.parent_raw_transcript_id.value, raw)
        self.assertIsNone(acquired.corrected_selection_id)
        self.assertIsNotNone(acquired.raw_selection_id)

    def test_acquire_raw_with_explicit_fallback_distinguishable(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        self.selection.select_raw_fallback(intake_id=self.intake, reviewer="s:kim")
        acquired = self.consumption.acquire_input(self.intake)
        self.assertIs(acquired.selection_state, SelectionState.RAW_FALLBACK)
        self.assertEqual(acquired.source_transcript_identity, raw)
        self.assertIsNotNone(acquired.corrected_selection_id)

    def test_acquire_applicable_corrected_revision_with_lineage(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        _, revision = self._revision_for(raw)
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        acquired = self.consumption.acquire_input(self.intake)
        self.assertIs(acquired.source_kind, ConsumedSourceKind.CORRECTED_TRANSCRIPT_REVISION)
        self.assertEqual(acquired.source_transcript_identity, revision)
        self.assertEqual(acquired.parent_raw_transcript_id.value, raw)
        self.assertIsNotNone(acquired.corrected_selection_id)

    def test_no_current_raw_fails_explicitly(self):
        with self.assertRaises(CorrectedRevisionSelectionError):
            self.consumption.acquire_input(self.intake)

    def test_inapplicable_selection_blocks_acquisition_no_silent_fallback(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        candidate, revision = self._revision_for(raw)
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        self.decisions.decide(candidate_id=candidate, kind="reject", reviewer="r:kim")
        with self.assertRaises(InapplicableSelectedRevisionError) as ctx:
            self.consumption.acquire_input(self.intake)
        self.assertIn("candidate_not_accepted", str(ctx.exception))
        self.assertIn("no silent", str(ctx.exception))

    # -- snapshot semantics (matrix 10-15) ----------------------------------------------------------

    def test_raw_snapshot_preserves_order_text_and_timing(self):
        raw = self._admit_raw("A", ("첫 문장", "둘째 문장"))
        self.raw_selection.select(self.intake, raw)
        acquired = self.consumption.acquire_input(self.intake)
        self.assertEqual([s.text for s in acquired.segments], ["첫 문장", "둘째 문장"])
        self.assertEqual([s.source_order for s in acquired.segments], [0, 1])
        self.assertEqual([(s.start, s.end) for s in acquired.segments], [(0.0, 1.0), (1.0, 2.0)])
        self.assertIsNone(acquired.segments[0].replaces_segment_id)

    def test_corrected_snapshot_preserves_replacement_lineage_and_timing(self):
        raw = self._admit_raw("A", ("첫 문장", "둘째 문장"))
        self.raw_selection.select(self.intake, raw)
        _, revision = self._revision_for(raw, "교정된 첫 문장")
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        acquired = self.consumption.acquire_input(self.intake)
        self.assertEqual(
            [s.text for s in acquired.segments], ["교정된 첫 문장", "둘째 문장"]
        )
        raw_record = SQLiteRawTranscriptRepository(self.connection).get(TranscriptId(raw))
        self.assertEqual(
            acquired.segments[0].replaces_segment_id, raw_record.segment_ids[0]
        )
        self.assertIsNone(acquired.segments[1].replaces_segment_id)
        self.assertEqual((acquired.segments[0].start, acquired.segments[0].end), (0.0, 1.0))

    def test_snapshots_are_deterministic(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        first = self.consumption.acquire_input(self.intake)
        second = self.consumption.acquire_input(self.intake)
        self.assertEqual(first, second)
        self.assertEqual(first.content_fingerprint, second.content_fingerprint)

    # -- consumption, replay, and conflicts (matrix 16-24) ------------------------------------------

    def test_consume_creates_then_reuses(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        created = self.consumption.consume(intake_id=self.intake)
        reused = self.consumption.consume(intake_id=self.intake)
        self.assertEqual(created.outcome.value, "created")
        self.assertEqual(reused.outcome.value, "reused")
        self.assertEqual(created.consumption.identity, reused.consumption.identity)
        self.assertEqual(len(self.consumption.bindings(self.intake)), 1)

    def test_source_change_creates_distinct_binding_never_reuses(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        first = self.consumption.consume(intake_id=self.intake)
        _, revision = self._revision_for(raw)
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        second = self.consumption.consume(intake_id=self.intake)
        self.assertEqual(second.outcome.value, "created")
        self.assertNotEqual(first.consumption.identity, second.consumption.identity)
        self.assertEqual(second.consumption.source_transcript_identity, revision)
        self.assertEqual(len(self.consumption.bindings(self.intake)), 2)

    def test_same_content_different_source_identity_stays_distinct(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        _, revision = self._revision_for(raw, "교정 하나")
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        corrected_binding = self.consumption.consume(intake_id=self.intake)
        # A second Raw Transcript whose text happens to equal the corrected content: identical
        # content fingerprint, different immutable source entity.
        raw2 = self._admit_raw("B", ("교정 하나", "원본 둘"))
        self.raw_selection.select(self.intake, raw2)
        self.selection.select_raw_fallback(intake_id=self.intake, reviewer="s:kim")
        raw_binding = self.consumption.consume(intake_id=self.intake)
        self.assertEqual(
            raw_binding.consumption.content_fingerprint,
            corrected_binding.consumption.content_fingerprint,
        )
        self.assertNotEqual(
            raw_binding.consumption.identity, corrected_binding.consumption.identity
        )
        self.assertEqual(len(self.consumption.bindings(self.intake)), 2)

    def test_selection_change_after_consumption_never_rewrites_binding(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        _, revision = self._revision_for(raw)
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        bound = self.consumption.consume(intake_id=self.intake)
        self.selection.select_raw_fallback(intake_id=self.intake, reviewer="s:kim")
        after = [
            b for b in self.consumption.bindings(self.intake)
            if b.identity == bound.consumption.identity
        ][0]
        self.assertEqual(after, bound.consumption)

    def test_near_concurrent_identical_requests_converge(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        self.consumption.consume(intake_id=self.intake)  # the competing winner
        from lectureos.persistence import (
            SQLiteEffectiveTranscriptConsumptionCommandPersistence,
            SQLiteEffectiveTranscriptConsumptionRepository,
        )

        racing = EffectiveTranscriptConsumptionService(
            self.consumption._inputs,
            self.selection,
            _RacingConsumptionView(
                SQLiteEffectiveTranscriptConsumptionRepository(self.connection)
            ),
            SQLiteEffectiveTranscriptConsumptionPersistenceProbe(self.connection),
        )
        result = racing.consume(intake_id=self.intake)
        self.assertEqual(result.outcome.value, "reused")
        self.assertEqual(len(self.consumption.bindings(self.intake)), 1)

    def test_fingerprint_conflict_is_explicit(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        self.consumption.consume(intake_id=self.intake)
        # Simulate a corrupted pre-existing binding whose recorded manifest disagrees.
        self.connection.execute("PRAGMA foreign_keys = OFF")
        try:
            self.connection.execute(
                "UPDATE effective_transcript_consumptions SET content_fingerprint = ?",
                ("f" * 64,),
            )
        finally:
            self.connection.execute("PRAGMA foreign_keys = ON")
        with self.assertRaises(ConsumptionConflictError):
            self.consumption.consume(intake_id=self.intake)

    def test_unsupported_consumer_kind_rejected(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        with self.assertRaises(EffectiveTranscriptConsumptionError):
            self.consumption.consume(intake_id=self.intake, consumer_kind="subtitle_generation")

    # -- derived currentness (matrix 25-28, 33) ------------------------------------------------------

    def test_currentness_current_for_effective_source(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        bound = self.consumption.consume(intake_id=self.intake)
        self.assertIs(
            self.consumption.currentness(bound.consumption), ConsumptionCurrentness.CURRENT
        )

    def test_currentness_stale_after_corrected_selection(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        bound = self.consumption.consume(intake_id=self.intake)
        _, revision = self._revision_for(raw)
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        self.assertIs(
            self.consumption.currentness(bound.consumption),
            ConsumptionCurrentness.STALE_DUE_TO_CORRECTED_SELECTION_CHANGE,
        )

    def test_currentness_stale_after_later_reject_binding_intact(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        candidate, revision = self._revision_for(raw)
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        bound = self.consumption.consume(intake_id=self.intake)
        self.decisions.decide(candidate_id=candidate, kind="reject", reviewer="r:kim")
        self.assertIs(
            self.consumption.currentness(bound.consumption),
            ConsumptionCurrentness.STALE_DUE_TO_SELECTED_REVISION_INAPPLICABILITY,
        )
        persisted = self.consumption.bindings(self.intake)[0]
        self.assertEqual(persisted, bound.consumption)

    def test_currentness_stale_after_raw_switch(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        bound = self.consumption.consume(intake_id=self.intake)
        raw2 = self._admit_raw("B", ("다른 원본",))
        self.raw_selection.select(self.intake, raw2)
        self.assertIs(
            self.consumption.currentness(bound.consumption),
            ConsumptionCurrentness.STALE_DUE_TO_RAW_SELECTION_CHANGE,
        )

    def test_currentness_stale_for_corrected_after_raw_switch(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        _, revision = self._revision_for(raw)
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        bound = self.consumption.consume(intake_id=self.intake)
        raw2 = self._admit_raw("B", ("다른 원본",))
        self.raw_selection.select(self.intake, raw2)
        self.assertIs(
            self.consumption.currentness(bound.consumption),
            ConsumptionCurrentness.STALE_DUE_TO_RAW_SELECTION_CHANGE,
        )


def SQLiteEffectiveTranscriptConsumptionPersistenceProbe(connection):
    from lectureos.persistence import (
        SQLiteEffectiveTranscriptConsumptionCommandPersistence,
    )

    return SQLiteEffectiveTranscriptConsumptionCommandPersistence(connection)


if __name__ == "__main__":
    unittest.main()
