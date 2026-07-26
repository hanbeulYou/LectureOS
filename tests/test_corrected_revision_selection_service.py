"""Application tests for Current Corrected Revision Selection (040 §20, GOAL-011)."""

import unittest
from dataclasses import dataclass

from lectureos.application.corrected_revision_selection import (
    CorrectedRevisionSelection,
    CorrectedRevisionSelectionError,
    CorrectedRevisionSelectionService,
    EffectiveKind,
    RevisionNotEligibleError,
    SelectionKind,
    SelectionState,
    derive_selection_identity,
    require_canonical_corrected_revision_id,
)
from lectureos.application.correction_candidate_decision import derive_decision_identity
from lectureos.application.correction_candidate_admission import (
    CorrectionCandidateAdmission,
    CorrectionCandidateSourceType,
)
from lectureos.application.corrected_revision_generation import CorrectedRevisionGeneration
from lectureos.application.correction_candidate_decision import CorrectionCandidateDecision
from lectureos.application.identities import (
    CorrectedRevisionGenerationId,
    CorrectionCandidateAdmissionId,
    CurrentRawTranscriptSelectionId,
    TranscriptSourceIntakeId,
)
from lectureos.application.transcript_source_intake import (
    TranscriptSourceIntake,
    derive_intake_identity,
)
from lectureos.execution.identities import SourceMediaId
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.review.identities import HumanActorReference
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)

_MEDIA = SourceMediaId("sha256:" + "a" * 64)
_INTAKE = derive_intake_identity(_MEDIA)
_RAW = TranscriptId("raw-transcript:" + "1" * 64)
_RAW2 = TranscriptId("raw-transcript:" + "2" * 64)
_CAND_A = CorrectionCandidateId("correction-candidate:" + "a" * 64)
_CAND_B = CorrectionCandidateId("correction-candidate:" + "b" * 64)
_REV_A = TranscriptRevisionId("corrected-revision:" + "a" * 64)
_REV_B = TranscriptRevisionId("corrected-revision:" + "b" * 64)
_REV_OTHER = TranscriptRevisionId("corrected-revision:" + "9" * 64)
_OTHER_INTAKE = TranscriptSourceIntakeId("transcript-source-intake:sha256:" + "b" * 64)


def _generation(revision, candidate, parent=_RAW):
    return CorrectedRevisionGeneration(
        identity=CorrectedRevisionGenerationId("corrected-revision-generation:" + revision.value[-64:]),
        corrected_revision_id=revision,
        correction_candidate_id=candidate,
        authorizing_decision_id=derive_decision_identity(candidate, DecisionKind.ACCEPT, 0),
        parent_raw_transcript_id=parent,
        replaced_segment_id=TranscriptSegmentId("transcript-segment:" + "1" * 64 + ":0"),
        replacement_segment_id=TranscriptSegmentId("transcript-segment:" + "2" * 64 + ":0"),
        content_fingerprint="0" * 64,
    )


def _admission(candidate, intake=_INTAKE):
    return CorrectionCandidateAdmission(
        identity=CorrectionCandidateAdmissionId("correction-candidate-admission:" + candidate.value[-64:]),
        correction_candidate_id=candidate,
        transcript_source_intake_id=intake,
        raw_transcript_id=_RAW,
        segment_id=TranscriptSegmentId("transcript-segment:" + "1" * 64 + ":0"),
        source_type=CorrectionCandidateSourceType.MANUAL,
        source_reference="human",
        candidate_ref="c",
        source_text_snapshot="원본",
        content_fingerprint="0" * 64,
    )


def _decision(candidate, kind, sequence=0, previous=None):
    return CorrectionCandidateDecision(
        identity=derive_decision_identity(candidate, kind, sequence),
        correction_candidate_id=candidate,
        kind=kind,
        reviewer=HumanActorReference("r"),
        sequence=sequence,
        content_fingerprint="0" * 64,
        previous_decision_id=previous,
    )


@dataclass
class _RawSelection:
    raw_transcript_id: TranscriptId
    identity: CurrentRawTranscriptSelectionId = CurrentRawTranscriptSelectionId(
        "current-raw-transcript-selection:" + "0" * 64
    )


class _Fakes:
    def __init__(self):
        self.generations = {
            _REV_A.value: _generation(_REV_A, _CAND_A),
            _REV_B.value: _generation(_REV_B, _CAND_B),
            _REV_OTHER.value: _generation(_REV_OTHER, CorrectionCandidateId("correction-candidate:" + "e" * 64)),
        }
        self.admissions = {
            _CAND_A.value: _admission(_CAND_A),
            _CAND_B.value: _admission(_CAND_B),
            ("correction-candidate:" + "e" * 64): _admission(
                CorrectionCandidateId("correction-candidate:" + "e" * 64), intake=_OTHER_INTAKE
            ),
        }
        self.decisions = {
            _CAND_A.value: _decision(_CAND_A, DecisionKind.ACCEPT),
            _CAND_B.value: _decision(_CAND_B, DecisionKind.ACCEPT),
            ("correction-candidate:" + "e" * 64): _decision(
                CorrectionCandidateId("correction-candidate:" + "e" * 64), DecisionKind.ACCEPT
            ),
        }
        self.raw_selection = _RawSelection(_RAW)
        self.by_identity = {}
        self.by_intake = {}
        self.persist_calls = 0
        self.known_intakes = {_INTAKE.value, _OTHER_INTAKE.value}

    # intake query
    def get(self, identity):
        if isinstance(identity, TranscriptSourceIntakeId):
            if identity.value in self.known_intakes:
                return TranscriptSourceIntake(identity, _MEDIA)
            return None
        return self.by_identity.get(identity.value)

    # generation query
    def get_by_revision(self, revision_id):
        return self.generations.get(revision_id.value)

    # admission query
    def get_by_candidate(self, candidate_id):
        return self.admissions.get(candidate_id.value)

    # decision query / raw-selection query (dispatch on argument type)
    def get_current(self, key):
        if isinstance(key, CorrectionCandidateId):
            return self.decisions.get(key.value)
        rows = self.by_intake.get(key.value)
        if rows is not None or key.value in self.by_intake:
            return max(rows, key=lambda s: s.sequence) if rows else None
        # raw selection query path
        return self.raw_selection

    # selection query — disambiguated wrappers used via composition below
    def history(self, intake_id):
        rows = self.by_intake.get(intake_id.value, [])
        return tuple(sorted(rows, key=lambda s: s.sequence))

    def persist_selection(self, *, selection):
        self.persist_calls += 1
        if selection.identity.value in self.by_identity:
            raise PersistenceIdentityCollisionError("identity exists")
        rows = self.by_intake.setdefault(selection.transcript_source_intake_id.value, [])
        if any(r.sequence == selection.sequence for r in rows):
            raise PersistenceIdentityCollisionError("sequence exists")
        self.by_identity[selection.identity.value] = selection
        rows.append(selection)


class _SelectionQueryView:
    """Selection query facade over _Fakes so get_current is unambiguous."""

    def __init__(self, fakes):
        self._fakes = fakes

    def get(self, identity):
        return self._fakes.by_identity.get(identity.value)

    def get_current(self, intake_id):
        rows = self._fakes.by_intake.get(intake_id.value)
        return max(rows, key=lambda s: s.sequence) if rows else None

    def history(self, intake_id):
        return self._fakes.history(intake_id)


class _RawSelectionView:
    def __init__(self, fakes):
        self._fakes = fakes

    def get_current(self, intake_id):
        return self._fakes.raw_selection


def _service(fakes):
    return CorrectedRevisionSelectionService(
        fakes, fakes, fakes, fakes, _RawSelectionView(fakes), _SelectionQueryView(fakes), fakes
    )


class IdentityAndModelTests(unittest.TestCase):
    def test_revision_id_validation(self):
        self.assertEqual(require_canonical_corrected_revision_id(_REV_A.value), _REV_A)
        for bad in ("nope", "corrected-revision:xyz", "raw-transcript:" + "1" * 64):
            with self.assertRaises(CorrectedRevisionSelectionError):
                require_canonical_corrected_revision_id(bad)

    def test_identity_is_deterministic_and_input_sensitive(self):
        a = derive_selection_identity(_INTAKE, SelectionKind.CORRECTED_REVISION, _REV_A, 0)
        self.assertEqual(a, derive_selection_identity(_INTAKE, SelectionKind.CORRECTED_REVISION, _REV_A, 0))
        self.assertNotEqual(a, derive_selection_identity(_INTAKE, SelectionKind.CORRECTED_REVISION, _REV_B, 0))
        self.assertNotEqual(a, derive_selection_identity(_INTAKE, SelectionKind.RAW_FALLBACK, None, 0))
        self.assertNotEqual(a, derive_selection_identity(_INTAKE, SelectionKind.CORRECTED_REVISION, _REV_A, 1))

    def test_kind_revision_consistency_enforced(self):
        with self.assertRaises(ValueError):  # fallback with revision
            CorrectedRevisionSelection(
                identity=derive_selection_identity(_INTAKE, SelectionKind.RAW_FALLBACK, None, 0),
                transcript_source_intake_id=_INTAKE, kind=SelectionKind.RAW_FALLBACK,
                reviewer=HumanActorReference("r"), sequence=0, corrected_revision_id=_REV_A,
            )
        with self.assertRaises(ValueError):  # corrected without revision
            CorrectedRevisionSelection(
                identity=derive_selection_identity(_INTAKE, SelectionKind.CORRECTED_REVISION, None, 0),
                transcript_source_intake_id=_INTAKE, kind=SelectionKind.CORRECTED_REVISION,
                reviewer=HumanActorReference("r"), sequence=0,
            )


class ReplayMatrixTests(unittest.TestCase):
    def test_no_history_select_revision_records(self):
        fakes = _Fakes()
        result = _service(fakes).select_revision(revision_id=_REV_A.value, reviewer="s:kim")
        self.assertEqual(result.outcome.value, "recorded")
        self.assertEqual(result.selection.sequence, 0)

    def test_no_history_fallback_records(self):
        fakes = _Fakes()
        result = _service(fakes).select_raw_fallback(intake_id=_INTAKE.value, reviewer="s:kim")
        self.assertEqual(result.outcome.value, "recorded")
        self.assertEqual(result.selection.kind, SelectionKind.RAW_FALLBACK)
        self.assertIsNone(result.selection.corrected_revision_id)

    def test_same_revision_reuses(self):
        fakes = _Fakes()
        service = _service(fakes)
        service.select_revision(revision_id=_REV_A.value, reviewer="s:kim")
        again = service.select_revision(revision_id=_REV_A.value, reviewer="s:lee")
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(len(fakes.by_identity), 1)

    def test_different_revision_appends(self):
        fakes = _Fakes()
        service = _service(fakes)
        service.select_revision(revision_id=_REV_A.value, reviewer="s:kim")
        changed = service.select_revision(revision_id=_REV_B.value, reviewer="s:kim")
        self.assertEqual(changed.outcome.value, "changed")
        self.assertEqual(changed.selection.sequence, 1)
        self.assertEqual(changed.previous.corrected_revision_id, _REV_A)

    def test_fallback_after_revision_appends_and_replays(self):
        fakes = _Fakes()
        service = _service(fakes)
        service.select_revision(revision_id=_REV_A.value, reviewer="s:kim")
        fallback = service.select_raw_fallback(intake_id=_INTAKE.value, reviewer="s:kim")
        self.assertEqual(fallback.outcome.value, "changed")
        again = service.select_raw_fallback(intake_id=_INTAKE.value, reviewer="s:lee")
        self.assertEqual(again.outcome.value, "reused")
        back = service.select_revision(revision_id=_REV_A.value, reviewer="s:kim")
        self.assertEqual(back.outcome.value, "changed")
        self.assertEqual(back.selection.sequence, 2)
        self.assertEqual(len(fakes.by_identity), 3)  # full history preserved

    def test_near_concurrent_identical_converges(self):
        fakes = _Fakes()
        original = fakes.persist_selection

        def racing(**kwargs):
            original(**kwargs)
            raise PersistenceIdentityCollisionError("won by another writer")

        fakes.persist_selection = racing
        result = _service(fakes).select_revision(revision_id=_REV_A.value, reviewer="s:kim")
        self.assertEqual(result.outcome.value, "reused")

    def test_divergent_concurrency_surfaces_conflict(self):
        fakes = _Fakes()
        # Simulate a racer that wrote a DIFFERENT selection at our sequence.
        racer = CorrectedRevisionSelection(
            identity=derive_selection_identity(_INTAKE, SelectionKind.CORRECTED_REVISION, _REV_B, 0),
            transcript_source_intake_id=_INTAKE, kind=SelectionKind.CORRECTED_REVISION,
            reviewer=HumanActorReference("racer"), sequence=0, corrected_revision_id=_REV_B,
        )

        def racing(**kwargs):
            fakes.by_identity[racer.identity.value] = racer
            fakes.by_intake.setdefault(_INTAKE.value, []).append(racer)
            raise PersistenceIdentityCollisionError("sequence taken by different choice")

        fakes.persist_selection = racing
        with self.assertRaises(PersistenceIdentityCollisionError):
            _service(fakes).select_revision(revision_id=_REV_A.value, reviewer="s:kim")


class EligibilityTests(unittest.TestCase):
    def test_unknown_revision_rejected(self):
        fakes = _Fakes()
        with self.assertRaises(CorrectedRevisionSelectionError):
            _service(fakes).select_revision(
                revision_id="corrected-revision:" + "0" * 64, reviewer="s"
            )
        self.assertEqual(fakes.persist_calls, 0)

    def test_rejected_candidate_revision_not_newly_selectable(self):
        fakes = _Fakes()
        accept = fakes.decisions[_CAND_A.value]
        fakes.decisions[_CAND_A.value] = _decision(
            _CAND_A, DecisionKind.REJECT, 1, previous=accept.identity
        )
        with self.assertRaises(RevisionNotEligibleError):
            _service(fakes).select_revision(revision_id=_REV_A.value, reviewer="s")
        self.assertEqual(fakes.persist_calls, 0)

    def test_parent_not_current_revision_not_newly_selectable(self):
        fakes = _Fakes()
        fakes.raw_selection = _RawSelection(_RAW2)
        with self.assertRaises(RevisionNotEligibleError):
            _service(fakes).select_revision(revision_id=_REV_A.value, reviewer="s")

    def test_blank_reviewer_rejected(self):
        fakes = _Fakes()
        with self.assertRaises(CorrectedRevisionSelectionError):
            _service(fakes).select_revision(revision_id=_REV_A.value, reviewer="  ")

    def test_persistence_required(self):
        fakes = _Fakes()
        service = CorrectedRevisionSelectionService(
            fakes, fakes, fakes, fakes, _RawSelectionView(fakes), _SelectionQueryView(fakes), None
        )
        with self.assertRaises(RuntimeError):
            service.select_revision(revision_id=_REV_A.value, reviewer="s")


class StateAndResolverTests(unittest.TestCase):
    def test_no_history_state_and_resolution(self):
        fakes = _Fakes()
        service = _service(fakes)
        self.assertEqual(service.selection_state(_INTAKE.value), SelectionState.NO_HISTORY)
        effective = service.resolve_effective_transcript(_INTAKE.value)
        self.assertEqual(effective.selection_state, SelectionState.NO_HISTORY)
        self.assertEqual(effective.effective_kind, EffectiveKind.RAW_TRANSCRIPT)
        self.assertEqual(effective.raw_transcript_id, _RAW)

    def test_fallback_state_distinguishable_from_no_history(self):
        fakes = _Fakes()
        service = _service(fakes)
        service.select_raw_fallback(intake_id=_INTAKE.value, reviewer="s")
        self.assertEqual(service.selection_state(_INTAKE.value), SelectionState.RAW_FALLBACK)
        effective = service.resolve_effective_transcript(_INTAKE.value)
        self.assertEqual(effective.selection_state, SelectionState.RAW_FALLBACK)
        self.assertEqual(effective.effective_kind, EffectiveKind.RAW_TRANSCRIPT)

    def test_selected_applicable_resolution(self):
        fakes = _Fakes()
        service = _service(fakes)
        service.select_revision(revision_id=_REV_A.value, reviewer="s")
        effective = service.resolve_effective_transcript(_INTAKE.value)
        self.assertEqual(effective.effective_kind, EffectiveKind.CORRECTED_REVISION)
        self.assertEqual(effective.corrected_revision_id, _REV_A)

    def test_later_reject_yields_explicit_inapplicable_not_silent_fallback(self):
        fakes = _Fakes()
        service = _service(fakes)
        service.select_revision(revision_id=_REV_A.value, reviewer="s")
        accept = fakes.decisions[_CAND_A.value]
        fakes.decisions[_CAND_A.value] = _decision(
            _CAND_A, DecisionKind.REJECT, 1, previous=accept.identity
        )
        effective = service.resolve_effective_transcript(_INTAKE.value)
        self.assertEqual(effective.effective_kind, EffectiveKind.INAPPLICABLE_SELECTION)
        self.assertEqual(effective.inapplicability_reason, "candidate_not_accepted")
        self.assertEqual(effective.corrected_revision_id, _REV_A)
        # history unchanged
        self.assertEqual(len(service.history(_INTAKE.value)), 1)

    def test_raw_selection_change_yields_explicit_inapplicable(self):
        fakes = _Fakes()
        service = _service(fakes)
        service.select_revision(revision_id=_REV_A.value, reviewer="s")
        fakes.raw_selection = _RawSelection(_RAW2)
        effective = service.resolve_effective_transcript(_INTAKE.value)
        self.assertEqual(effective.effective_kind, EffectiveKind.INAPPLICABLE_SELECTION)
        self.assertEqual(effective.inapplicability_reason, "parent_raw_transcript_not_current")
        self.assertEqual(effective.raw_transcript_id, _RAW2)
        # selection authority unchanged (no auto-clear)
        self.assertEqual(service.current(_INTAKE.value).corrected_revision_id, _REV_A)


if __name__ == "__main__":
    unittest.main()
