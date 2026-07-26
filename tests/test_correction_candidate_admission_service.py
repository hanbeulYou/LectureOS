"""Domain and application tests for Transcript Correction Candidate Admission (040 §17)."""

import unittest
from dataclasses import dataclass

from lectureos.application.correction_candidate_admission import (
    CorrectionCandidateAdmissionError,
    CorrectionCandidateAdmissionService,
    CorrectionCandidateConflictError,
    CorrectionCandidateInput,
    CorrectionCandidateSourceType,
    CorrectionCandidateView,
    IntakeNotReadyError,
    RawTranscriptNotCurrentError,
    SegmentLineageError,
    SourceTextMismatchError,
    build_correction_candidate_input,
    require_canonical_segment_id,
)
from lectureos.application.identities import TranscriptSourceIntakeId
from lectureos.application.transcript_source_intake import (
    TranscriptSourceIntake,
    derive_intake_identity,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import RawTranscript, TranscriptSegment

_MEDIA = SourceMediaId("sha256:" + "a" * 64)
_INTAKE = derive_intake_identity(_MEDIA).value
_RAW = "raw-transcript:" + "1" * 64
_RAW2 = "raw-transcript:" + "2" * 64
_SEG = "transcript-segment:" + "1" * 64 + ":0"
_SEG_OTHER = "transcript-segment:" + "2" * 64 + ":0"
_SOURCE_TEXT = "안녕하세요 여러부"


@dataclass
class _Selection:
    raw_transcript_id: TranscriptId


class _FakeIntakeQuery:
    def __init__(self, known=True):
        self._known = known

    def get(self, identity):
        return TranscriptSourceIntake(TranscriptSourceIntakeId(identity.value), _MEDIA) if self._known else None


class _FakeSelectionQuery:
    def __init__(self, current=_RAW):
        self._current = current

    def get_current(self, intake_id):
        return _Selection(TranscriptId(self._current)) if self._current else None


class _FakeSegmentQuery:
    def __init__(self, segments):
        self._segments = segments  # id -> TranscriptSegment

    def get(self, identity):
        return self._segments.get(identity.value)


class _FakeRawTranscriptQuery:
    def get(self, identity):
        return RawTranscript(
            identity=identity,
            domain_result_id=DomainResultId("domain-result:raw:x"),
            source_media_id=_MEDIA,
            source_timeline_id=SourceTimelineId("source-timeline:" + _MEDIA.value),
            provider_result_id=ProviderTranscriptResultId("provider-transcript-result:x"),
            run_id=ProcessingRunId("run:x"),
            unit_execution_id=UnitExecutionId("exec:x"),
            segment_ids=(TranscriptSegmentId(_SEG),),
        )


class _FakeAdmissionStore:
    def __init__(self):
        self.admissions = {}
        self.candidates = {}
        self.calls = 0

    def get(self, identity):
        return self.admissions.get(identity.value)

    def candidate(self, candidate_id):
        return self.candidates.get(candidate_id.value)

    def candidates_for_intake(self, intake_id, current_raw):
        views = []
        for admission in self.admissions.values():
            if admission.transcript_source_intake_id != intake_id:
                continue
            candidate = self.candidates[admission.correction_candidate_id.value]
            views.append(
                CorrectionCandidateView(
                    correction_candidate_id=admission.correction_candidate_id,
                    raw_transcript_id=admission.raw_transcript_id,
                    segment_id=admission.segment_id,
                    source_type=admission.source_type,
                    source_reference=admission.source_reference,
                    candidate_ref=admission.candidate_ref,
                    source_text=admission.source_text_snapshot,
                    proposed_text=candidate.proposed_text,
                    applicable_to_current_selection=(
                        current_raw is not None
                        and admission.raw_transcript_id == current_raw
                    ),
                )
            )
        return tuple(views)

    def persist_correction_candidate_admission(self, *, admission, candidate, result):
        self.calls += 1
        if admission.identity.value in self.admissions:
            raise PersistenceIdentityCollisionError("exists")
        self.admissions[admission.identity.value] = admission
        self.candidates[candidate.identity.value] = candidate


def _segment(text=_SOURCE_TEXT, transcript=_RAW, seg_id=_SEG):
    return TranscriptSegment(
        identity=TranscriptSegmentId(seg_id),
        transcript_id=TranscriptId(transcript),
        source_timeline_id=SourceTimelineId("source-timeline:" + _MEDIA.value),
        text=text,
        source_order=0,
        start=0.0,
        end=1.0,
    )


def _service(*, intake=True, current=_RAW, segments=None, store=None):
    segments = segments if segments is not None else {_SEG: _segment()}
    store = store if store is not None else _FakeAdmissionStore()
    service = CorrectionCandidateAdmissionService(
        _FakeIntakeQuery(intake),
        _FakeSelectionQuery(current),
        _FakeSegmentQuery(segments),
        _FakeRawTranscriptQuery(),
        store,
        store,
    )
    return service, store


def _input(ref="c1", proposed="안녕하세요 여러분", snapshot=_SOURCE_TEXT, raw=_RAW, seg=_SEG,
           source_type="manual", rationale="fix"):
    return CorrectionCandidateInput(
        raw_transcript_id=raw,
        segment_id=seg,
        candidate_ref=ref,
        source_type=CorrectionCandidateSourceType(source_type),
        source_reference="human:editor-1",
        proposed_text=proposed,
        source_text_snapshot=snapshot,
        rationale=rationale,
    )


class InputContractTests(unittest.TestCase):
    def test_valid_document(self):
        doc = build_correction_candidate_input({
            "raw_transcript_id": _RAW, "segment_id": _SEG, "candidate_ref": "c1",
            "source_type": "manual", "source_reference": "human", "proposed_text": "fixed",
            "source_text_snapshot": "orig", "rationale": "why",
        })
        self.assertEqual(doc.source_type, CorrectionCandidateSourceType.MANUAL)

    def test_unknown_field_rejected(self):
        with self.assertRaises(CorrectionCandidateAdmissionError):
            build_correction_candidate_input({
                "raw_transcript_id": _RAW, "segment_id": _SEG, "candidate_ref": "c1",
                "source_type": "manual", "source_reference": "h", "proposed_text": "x",
                "source_text_snapshot": "o", "rationale": "w", "confidence": 0.9,
            })

    def test_bad_source_type_rejected(self):
        with self.assertRaises(CorrectionCandidateAdmissionError):
            build_correction_candidate_input({
                "raw_transcript_id": _RAW, "segment_id": _SEG, "candidate_ref": "c1",
                "source_type": "wizard", "source_reference": "h", "proposed_text": "x",
                "source_text_snapshot": "o", "rationale": "w",
            })

    def test_empty_proposed_text_rejected(self):
        with self.assertRaises(CorrectionCandidateAdmissionError):
            _input(proposed="   ")

    def test_noop_rejected(self):
        with self.assertRaises(CorrectionCandidateAdmissionError):
            _input(proposed=_SOURCE_TEXT, snapshot=_SOURCE_TEXT)

    def test_segment_identity_validation(self):
        self.assertEqual(require_canonical_segment_id(_SEG).value, _SEG)
        for bad in ("nope", "transcript-segment:xyz", "transcript-segment:" + "1" * 64, _RAW):
            with self.assertRaises(CorrectionCandidateAdmissionError):
                require_canonical_segment_id(bad)


class AdmissionServiceTests(unittest.TestCase):
    def test_not_ready_rejected(self):
        service, store = _service(current=None)
        with self.assertRaises(IntakeNotReadyError):
            service.admit(intake_id=_INTAKE, candidate=_input())
        self.assertEqual(store.calls, 0)

    def test_valid_admission(self):
        service, store = _service()
        result = service.admit(intake_id=_INTAKE, candidate=_input())
        self.assertTrue(result.created)
        self.assertEqual(result.candidate.proposed_text, "안녕하세요 여러분")
        self.assertEqual(result.candidate.transcript_id.value, _RAW)
        self.assertEqual(result.candidate.segment_id.value, _SEG)
        self.assertTrue(result.candidate.identity.value.startswith("correction-candidate:"))

    def test_unknown_intake_rejected(self):
        service, _ = _service(intake=False)
        with self.assertRaises(CorrectionCandidateAdmissionError):
            service.admit(intake_id=_INTAKE, candidate=_input())

    def test_malformed_intake_rejected(self):
        service, _ = _service()
        with self.assertRaises(CorrectionCandidateAdmissionError):
            service.admit(intake_id="nope", candidate=_input())

    def test_raw_transcript_not_current_rejected(self):
        service, _ = _service(current=_RAW)
        with self.assertRaises(RawTranscriptNotCurrentError):
            service.admit(intake_id=_INTAKE, candidate=_input(raw=_RAW2, seg=_SEG_OTHER))

    def test_unknown_segment_rejected(self):
        service, _ = _service(segments={})
        with self.assertRaises(SegmentLineageError):
            service.admit(intake_id=_INTAKE, candidate=_input())

    def test_segment_from_another_raw_transcript_rejected(self):
        service, _ = _service(segments={_SEG: _segment(transcript=_RAW2)})
        with self.assertRaises(SegmentLineageError):
            service.admit(intake_id=_INTAKE, candidate=_input())

    def test_source_text_mismatch_rejected(self):
        service, store = _service()
        with self.assertRaises(SourceTextMismatchError):
            service.admit(intake_id=_INTAKE, candidate=_input(snapshot="WRONG", proposed="fix"))
        self.assertEqual(store.calls, 0)

    def test_deterministic_identity(self):
        s1, _ = _service()
        s2, _ = _service()
        r1 = s1.admit(intake_id=_INTAKE, candidate=_input())
        r2 = s2.admit(intake_id=_INTAKE, candidate=_input())
        self.assertEqual(r1.candidate.identity, r2.candidate.identity)

    def test_repeated_identical_admission_idempotent(self):
        service, store = _service()
        first = service.admit(intake_id=_INTAKE, candidate=_input())
        again = service.admit(intake_id=_INTAKE, candidate=_input())
        self.assertFalse(again.created)
        self.assertEqual(store.calls, 1)
        self.assertEqual(again.candidate.identity, first.candidate.identity)

    def test_same_ref_conflicting_payload_rejected(self):
        service, _ = _service()
        service.admit(intake_id=_INTAKE, candidate=_input(ref="c1", proposed="안녕하세요 여러분"))
        with self.assertRaises(CorrectionCandidateConflictError):
            service.admit(intake_id=_INTAKE, candidate=_input(ref="c1", proposed="다른 제안"))

    def test_multiple_distinct_candidates_per_segment(self):
        service, store = _service()
        a = service.admit(intake_id=_INTAKE, candidate=_input(ref="c1", proposed="제안 1"))
        b = service.admit(intake_id=_INTAKE, candidate=_input(ref="c2", proposed="제안 2"))
        self.assertNotEqual(a.candidate.identity, b.candidate.identity)
        self.assertEqual(store.calls, 2)

    def test_external_source_supported(self):
        service, _ = _service()
        result = service.admit(intake_id=_INTAKE, candidate=_input(source_type="external"))
        self.assertTrue(result.created)

    def test_near_concurrent_collision_converges(self):
        class _RacingStore(_FakeAdmissionStore):
            def persist_correction_candidate_admission(self, *, admission, candidate, result):
                _FakeAdmissionStore.persist_correction_candidate_admission(
                    self, admission=admission, candidate=candidate, result=result
                )
                raise PersistenceIdentityCollisionError("won")

        racing = _RacingStore()
        service, _ = _service(store=racing)
        result = service.admit(intake_id=_INTAKE, candidate=_input())
        self.assertFalse(result.created)

    def test_persistence_required(self):
        service = CorrectionCandidateAdmissionService(
            _FakeIntakeQuery(), _FakeSelectionQuery(), _FakeSegmentQuery({_SEG: _segment()}),
            _FakeRawTranscriptQuery(), _FakeAdmissionStore(), None,
        )
        with self.assertRaises(RuntimeError):
            service.admit(intake_id=_INTAKE, candidate=_input())

    def test_candidate_query_applicability(self):
        service, _ = _service()
        service.admit(intake_id=_INTAKE, candidate=_input(ref="c1", proposed="p1"))
        views = service.candidates(_INTAKE)
        self.assertEqual(len(views), 1)
        self.assertTrue(views[0].applicable_to_current_selection)


if __name__ == "__main__":
    unittest.main()
