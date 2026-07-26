"""Domain and application tests for Current Raw Transcript Selection and readiness (040 §16)."""

import unittest

from lectureos.application.current_raw_transcript_selection import (
    CurrentRawTranscriptSelection,
    CurrentRawTranscriptSelectionService,
    RawTranscriptCandidate,
    RawTranscriptSelectionError,
    TranscriptIntakeReadiness,
    derive_selection_identity,
    require_canonical_raw_transcript_id,
)
from lectureos.application.identities import TranscriptSourceIntakeId
from lectureos.application.transcript_source_intake import (
    TranscriptSourceIntake,
    derive_intake_identity,
)
from lectureos.execution.identities import SourceMediaId
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.transcript.identities import TranscriptId

_MEDIA = SourceMediaId("sha256:" + "a" * 64)
_INTAKE = derive_intake_identity(_MEDIA).value
_RAW_A = "raw-transcript:" + "1" * 64
_RAW_B = "raw-transcript:" + "2" * 64
_RAW_OTHER = "raw-transcript:" + "9" * 64


class _FakeIntakeQuery:
    def __init__(self, known=True):
        self._known = known

    def get(self, identity):
        if not self._known:
            return None
        return TranscriptSourceIntake(TranscriptSourceIntakeId(identity.value), _MEDIA)


class _FakeCandidateQuery:
    def __init__(self, by_intake, owners):
        self._by_intake = by_intake  # intake_value -> tuple[RawTranscriptCandidate]
        self._owners = owners        # raw_transcript_value -> intake_value

    def candidates(self, intake_id):
        return self._by_intake.get(intake_id.value, ())

    def owning_intake(self, raw_transcript_id):
        owner = self._owners.get(raw_transcript_id.value)
        return TranscriptSourceIntakeId(owner) if owner is not None else None


class _FakeSelectionStore:
    def __init__(self):
        self.by_identity = {}
        self.by_intake = {}  # intake_value -> list of selections in insert order

    def get(self, identity):
        return self.by_identity.get(identity.value)

    def get_current(self, intake_id):
        rows = self.by_intake.get(intake_id.value)
        if not rows:
            return None
        return max(rows, key=lambda s: s.sequence)

    def persist_selection(self, *, selection):
        if selection.identity.value in self.by_identity:
            raise PersistenceIdentityCollisionError("identity exists")
        rows = self.by_intake.setdefault(selection.transcript_source_intake_id.value, [])
        if any(r.sequence == selection.sequence for r in rows):
            raise PersistenceIdentityCollisionError("sequence exists")
        self.by_identity[selection.identity.value] = selection
        rows.append(selection)


def _candidate(rt):
    return RawTranscriptCandidate(
        raw_transcript_id=TranscriptId(rt),
        provider_reference="fake",
        provider_model="tiny",
        declared_language="ko",
        segment_count=2,
    )


def _service(*, intake=True, candidates=(_RAW_A, _RAW_B), store=None):
    by_intake = {_INTAKE: tuple(_candidate(rt) for rt in candidates)}
    owners = {rt: _INTAKE for rt in candidates}
    owners[_RAW_OTHER] = "transcript-source-intake:sha256:" + "b" * 64
    store = store if store is not None else _FakeSelectionStore()
    service = CurrentRawTranscriptSelectionService(
        _FakeIntakeQuery(known=intake),
        _FakeCandidateQuery(by_intake, owners),
        store,
        store,
    )
    return service, store


class SelectionIdentityTests(unittest.TestCase):
    def test_raw_transcript_id_validation(self):
        self.assertEqual(require_canonical_raw_transcript_id(_RAW_A).value, _RAW_A)
        for bad in ("nope", "raw-transcript:xyz", "raw-transcript:" + "1" * 63, "sha256:" + "1" * 64):
            with self.assertRaises(RawTranscriptSelectionError):
                require_canonical_raw_transcript_id(bad)

    def test_selection_identity_is_deterministic_and_sequence_sensitive(self):
        intake = TranscriptSourceIntakeId(_INTAKE)
        rt = TranscriptId(_RAW_A)
        self.assertEqual(derive_selection_identity(intake, rt, 0), derive_selection_identity(intake, rt, 0))
        self.assertNotEqual(derive_selection_identity(intake, rt, 0), derive_selection_identity(intake, rt, 1))

    def test_selection_record_enforces_derivation_and_sequence_rules(self):
        intake = TranscriptSourceIntakeId(_INTAKE)
        rt = TranscriptId(_RAW_A)
        good = CurrentRawTranscriptSelection(
            identity=derive_selection_identity(intake, rt, 0),
            transcript_source_intake_id=intake,
            raw_transcript_id=rt,
            sequence=0,
        )
        self.assertEqual(good.sequence, 0)
        with self.assertRaises(ValueError):  # sequence 0 must have no previous
            CurrentRawTranscriptSelection(
                identity=derive_selection_identity(intake, rt, 0),
                transcript_source_intake_id=intake,
                raw_transcript_id=rt,
                sequence=0,
                previous_selection_id=derive_selection_identity(intake, rt, 0),
            )
        with self.assertRaises(ValueError):  # wrong identity derivation
            CurrentRawTranscriptSelection(
                identity=derive_selection_identity(intake, rt, 5),
                transcript_source_intake_id=intake,
                raw_transcript_id=rt,
                sequence=0,
            )


class CandidateTests(unittest.TestCase):
    def test_zero_candidates(self):
        service, _ = _service(candidates=())
        self.assertEqual(service.candidates(_INTAKE), ())
        self.assertEqual(
            service.readiness(_INTAKE).readiness, TranscriptIntakeReadiness.NOT_READY
        )

    def test_one_and_multiple_candidates_enumerated(self):
        service, _ = _service(candidates=(_RAW_A,))
        self.assertEqual(len(service.candidates(_INTAKE)), 1)
        service2, _ = _service(candidates=(_RAW_A, _RAW_B))
        self.assertEqual(len(service2.candidates(_INTAKE)), 2)

    def test_unknown_intake_rejected(self):
        service, _ = _service(intake=False)
        with self.assertRaises(RawTranscriptSelectionError):
            service.candidates(_INTAKE)

    def test_malformed_intake_rejected(self):
        service, _ = _service()
        with self.assertRaises(RawTranscriptSelectionError):
            service.candidates("not-an-intake")


class SelectionTests(unittest.TestCase):
    def test_initial_selection_created(self):
        service, store = _service()
        result = service.select(_INTAKE, _RAW_A)
        self.assertEqual(result.outcome.value, "created")
        self.assertEqual(result.selection.sequence, 0)
        self.assertIsNone(result.selection.previous_selection_id)
        self.assertEqual(len(store.by_identity), 1)

    def test_repeated_identical_selection_is_idempotent(self):
        service, store = _service()
        service.select(_INTAKE, _RAW_A)
        again = service.select(_INTAKE, _RAW_A)
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(len(store.by_identity), 1)  # no new row

    def test_switching_appends_history(self):
        service, store = _service()
        service.select(_INTAKE, _RAW_A)
        switched = service.select(_INTAKE, _RAW_B, reason="better")
        self.assertEqual(switched.outcome.value, "switched")
        self.assertEqual(switched.selection.sequence, 1)
        self.assertEqual(switched.previous.raw_transcript_id.value, _RAW_A)
        self.assertEqual(len(store.by_identity), 2)  # append-only, prior preserved
        self.assertEqual(service.current(_INTAKE).raw_transcript_id.value, _RAW_B)

    def test_switching_back_creates_new_sequence(self):
        service, store = _service()
        service.select(_INTAKE, _RAW_A)
        service.select(_INTAKE, _RAW_B)
        back = service.select(_INTAKE, _RAW_A)
        self.assertEqual(back.outcome.value, "switched")
        self.assertEqual(back.selection.sequence, 2)
        self.assertEqual(len(store.by_identity), 3)

    def test_unknown_raw_transcript_rejected(self):
        service, store = _service()
        with self.assertRaises(RawTranscriptSelectionError):
            service.select(_INTAKE, "raw-transcript:" + "0" * 64)
        self.assertEqual(len(store.by_identity), 0)

    def test_unrelated_raw_transcript_rejected(self):
        service, store = _service()
        with self.assertRaises(RawTranscriptSelectionError):
            service.select(_INTAKE, _RAW_OTHER)
        self.assertEqual(len(store.by_identity), 0)

    def test_malformed_raw_transcript_rejected(self):
        service, _ = _service()
        with self.assertRaises(RawTranscriptSelectionError):
            service.select(_INTAKE, "garbage")

    def test_near_concurrent_collision_converges(self):
        store = _FakeSelectionStore()

        class _RacingStore(_FakeSelectionStore):
            def persist_selection(self, *, selection):
                # Simulate another writer inserting the same selection first.
                _FakeSelectionStore.persist_selection(self, selection=selection)
                raise PersistenceIdentityCollisionError("won by another writer")

        racing = _RacingStore()
        service, _ = _service(store=racing)
        result = service.select(_INTAKE, _RAW_A)
        self.assertEqual(result.outcome.value, "reused")

    def test_persistence_required(self):
        service = CurrentRawTranscriptSelectionService(
            _FakeIntakeQuery(),
            _FakeCandidateQuery({_INTAKE: (_candidate(_RAW_A),)}, {_RAW_A: _INTAKE}),
            _FakeSelectionStore(),
            None,
        )
        with self.assertRaises(RuntimeError):
            service.select(_INTAKE, _RAW_A)


class ReadinessTests(unittest.TestCase):
    def test_not_ready_without_selection(self):
        service, _ = _service()
        self.assertEqual(
            service.readiness(_INTAKE).readiness, TranscriptIntakeReadiness.NOT_READY
        )

    def test_ready_after_selection(self):
        service, _ = _service()
        service.select(_INTAKE, _RAW_A)
        report = service.readiness(_INTAKE)
        self.assertEqual(report.readiness, TranscriptIntakeReadiness.READY)
        self.assertEqual(report.current_raw_transcript_id.value, _RAW_A)
        self.assertEqual(report.candidate_count, 2)

    def test_error_when_current_selection_lineage_is_lost(self):
        # Current selection points at a raw transcript that no longer resolves to this intake.
        store = _FakeSelectionStore()
        service, _ = _service(store=store)
        service.select(_INTAKE, _RAW_A)
        # Rebuild a service whose candidate query no longer owns _RAW_A for this intake.
        broken = CurrentRawTranscriptSelectionService(
            _FakeIntakeQuery(),
            _FakeCandidateQuery({_INTAKE: ()}, {}),
            store,
            store,
        )
        self.assertEqual(
            broken.readiness(_INTAKE).readiness, TranscriptIntakeReadiness.ERROR
        )


if __name__ == "__main__":
    unittest.main()
