"""Application tests for First Corrected Transcript Revision generation (040 §19, GOAL-010)."""

import unittest
from dataclasses import dataclass, field

from lectureos.application.corrected_revision_generation import (
    CandidateNotAcceptedError,
    CandidateNotApplicableError,
    CorrectedRevisionConflictError,
    CorrectedRevisionGenerationError,
    CorrectedRevisionGenerationService,
    derive_generation_digest,
)
from lectureos.application.correction_candidate_admission import (
    CorrectionCandidateAdmission,
    CorrectionCandidateSourceType,
)
from lectureos.application.correction_candidate_decision import (
    CorrectionCandidateDecision,
    derive_decision_identity,
)
from lectureos.application.identities import (
    CorrectionCandidateAdmissionId,
    TranscriptSourceIntakeId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.review.identities import HumanActorReference
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import CorrectionCandidate, RawTranscript, TranscriptSegment

_MEDIA = SourceMediaId("sha256:" + "a" * 64)
_INTAKE = TranscriptSourceIntakeId("transcript-source-intake:" + _MEDIA.value)
_RAW = TranscriptId("raw-transcript:" + "1" * 64)
_RAW2 = TranscriptId("raw-transcript:" + "2" * 64)
_SEG0 = TranscriptSegmentId("transcript-segment:" + "1" * 64 + ":0")
_SEG1 = TranscriptSegmentId("transcript-segment:" + "1" * 64 + ":1")
_CAND = CorrectionCandidateId("correction-candidate:" + "c" * 64)
_TIMELINE = SourceTimelineId("source-timeline:" + _MEDIA.value)
_SOURCE_TEXT = "안녕하세요 여러부"


def _segment(seg_id, text, order, start, end):
    return TranscriptSegment(
        identity=seg_id, transcript_id=_RAW, source_timeline_id=_TIMELINE,
        text=text, source_order=order, start=start, end=end,
    )


def _raw_transcript():
    return RawTranscript(
        identity=_RAW,
        domain_result_id=DomainResultId("domain-result:raw:x"),
        source_media_id=_MEDIA,
        source_timeline_id=_TIMELINE,
        provider_result_id=ProviderTranscriptResultId("provider-transcript-result:x"),
        run_id=ProcessingRunId("run:x"),
        unit_execution_id=UnitExecutionId("exec:x"),
        segment_ids=(_SEG0, _SEG1),
    )


def _admission():
    return CorrectionCandidateAdmission(
        identity=CorrectionCandidateAdmissionId("correction-candidate-admission:" + "d" * 64),
        correction_candidate_id=_CAND,
        transcript_source_intake_id=_INTAKE,
        raw_transcript_id=_RAW,
        segment_id=_SEG0,
        source_type=CorrectionCandidateSourceType.MANUAL,
        source_reference="human:editor",
        candidate_ref="c1",
        source_text_snapshot=_SOURCE_TEXT,
        content_fingerprint="0" * 64,
    )


def _candidate(proposed="안녕하세요 여러분"):
    return CorrectionCandidate(
        identity=_CAND,
        domain_result_id=DomainResultId("domain-result:cand:x"),
        transcript_id=_RAW,
        segment_id=_SEG0,
        proposed_text=proposed,
        rationale="fix",
        run_id=ProcessingRunId("run:c"),
        unit_execution_id=UnitExecutionId("exec:c"),
    )


def _decision(kind, sequence=0, previous=None):
    return CorrectionCandidateDecision(
        identity=derive_decision_identity(_CAND, kind, sequence),
        correction_candidate_id=_CAND,
        kind=kind,
        reviewer=HumanActorReference("r:kim"),
        sequence=sequence,
        content_fingerprint="0" * 64,
        previous_decision_id=previous,
    )


@dataclass
class _Selection:
    raw_transcript_id: TranscriptId


class _Fakes:
    """One bundle of injectable fakes with sensible healthy defaults."""

    def __init__(self):
        self.admission = _admission()
        self.candidate_record = _candidate()
        self.current_decision = _decision(DecisionKind.ACCEPT)
        self.current_selection = _Selection(_RAW)
        self.raw = _raw_transcript()
        self.segments = {
            _SEG0.value: _segment(_SEG0, _SOURCE_TEXT, 0, 0.0, 2.5),
            _SEG1.value: _segment(_SEG1, "오늘 강의를 시작합니다", 1, 2.5, 5.0),
        }
        self.generations = {}
        self.revisions = {}
        self.persist_calls = 0

    # admission query
    def get_by_candidate(self, candidate_id):
        return self.admission if candidate_id == _CAND else None

    def candidate(self, candidate_id):
        return self.candidate_record if candidate_id == _CAND else None

    # decision query
    def get_current(self, key):
        # Serves both decision query (candidate id) and selection query (intake id).
        if isinstance(key, CorrectionCandidateId):
            return self.current_decision
        return self.current_selection

    # raw transcript / segment queries
    def get(self, identity):
        if isinstance(identity, TranscriptId):
            return self.raw if identity == _RAW else None
        if isinstance(identity, TranscriptSegmentId):
            return self.segments.get(identity.value)
        return self.generations.get(identity.value)

    # generation query
    def revision(self, revision_id):
        return self.revisions.get(revision_id.value)

    def generations_for_candidate(self, candidate_id):
        return tuple(
            g for g in self.generations.values() if g.correction_candidate_id == candidate_id
        )

    # persistence
    def persist_corrected_revision_generation(self, *, generation, revision, replacement_segment, result):
        self.persist_calls += 1
        if generation.identity.value in self.generations:
            raise PersistenceIdentityCollisionError("exists")
        self.generations[generation.identity.value] = generation
        self.revisions[revision.identity.value] = revision
        self.segments[replacement_segment.identity.value] = replacement_segment


def _service(fakes):
    return CorrectedRevisionGenerationService(
        fakes, fakes, fakes, fakes, fakes, fakes, fakes
    )


class GenerationEligibilityTests(unittest.TestCase):
    def test_accepted_candidate_creates_one_revision(self):
        fakes = _Fakes()
        result = _service(fakes).generate(candidate_id=_CAND.value)
        self.assertEqual(result.outcome, "created")
        self.assertEqual(len(fakes.revisions), 1)
        self.assertEqual(result.generation.authorizing_decision_id, fakes.current_decision.identity)

    def test_undecided_candidate_blocked(self):
        fakes = _Fakes()
        fakes.current_decision = None
        with self.assertRaises(CandidateNotAcceptedError):
            _service(fakes).generate(candidate_id=_CAND.value)
        self.assertEqual(fakes.persist_calls, 0)

    def test_rejected_candidate_blocked(self):
        fakes = _Fakes()
        fakes.current_decision = _decision(DecisionKind.REJECT)
        with self.assertRaises(CandidateNotAcceptedError):
            _service(fakes).generate(candidate_id=_CAND.value)
        self.assertEqual(fakes.persist_calls, 0)

    def test_accept_then_reject_blocks_new_generation(self):
        fakes = _Fakes()
        service = _service(fakes)
        service.generate(candidate_id=_CAND.value)
        fakes.current_decision = _decision(
            DecisionKind.REJECT, 1, previous=fakes.current_decision.identity
        )
        with self.assertRaises(CandidateNotAcceptedError):
            service.generate(candidate_id=_CAND.value)
        self.assertEqual(len(fakes.revisions), 1)  # historical revision preserved

    def test_reject_then_accept_permits_generation(self):
        fakes = _Fakes()
        reject = _decision(DecisionKind.REJECT)
        fakes.current_decision = _decision(DecisionKind.ACCEPT, 1, previous=reject.identity)
        result = _service(fakes).generate(candidate_id=_CAND.value)
        self.assertEqual(result.outcome, "created")

    def test_distinct_accepting_decisions_yield_distinct_revisions(self):
        fakes = _Fakes()
        service = _service(fakes)
        first = service.generate(candidate_id=_CAND.value)
        reject = _decision(DecisionKind.REJECT, 1, previous=fakes.current_decision.identity)
        fakes.current_decision = _decision(DecisionKind.ACCEPT, 2, previous=reject.identity)
        second = service.generate(candidate_id=_CAND.value)
        self.assertNotEqual(first.revision.identity, second.revision.identity)
        self.assertEqual(
            first.generation.content_fingerprint, second.generation.content_fingerprint
        )  # identical content, distinct entity identity


class ApplicabilityTests(unittest.TestCase):
    def test_unknown_candidate_rejected(self):
        fakes = _Fakes()
        with self.assertRaises(CorrectedRevisionGenerationError):
            _service(fakes).generate(candidate_id="correction-candidate:" + "0" * 64)

    def test_malformed_candidate_rejected(self):
        with self.assertRaises(CorrectedRevisionGenerationError):
            _service(_Fakes()).generate(candidate_id="nope")

    def test_selection_switched_away_blocked(self):
        fakes = _Fakes()
        fakes.current_selection = _Selection(_RAW2)
        with self.assertRaises(CandidateNotApplicableError):
            _service(fakes).generate(candidate_id=_CAND.value)
        self.assertEqual(fakes.persist_calls, 0)

    def test_no_selection_blocked(self):
        fakes = _Fakes()
        fakes.current_selection = None
        with self.assertRaises(CandidateNotApplicableError):
            _service(fakes).generate(candidate_id=_CAND.value)

    def test_missing_raw_transcript_blocked(self):
        fakes = _Fakes()
        fakes.raw = None
        with self.assertRaises(CandidateNotApplicableError):
            _service(fakes).generate(candidate_id=_CAND.value)

    def test_target_segment_not_in_transcript_blocked(self):
        fakes = _Fakes()
        fakes.raw = RawTranscript(
            identity=_RAW,
            domain_result_id=DomainResultId("domain-result:raw:x"),
            source_media_id=_MEDIA,
            source_timeline_id=_TIMELINE,
            provider_result_id=ProviderTranscriptResultId("provider-transcript-result:x"),
            run_id=ProcessingRunId("run:x"),
            unit_execution_id=UnitExecutionId("exec:x"),
            segment_ids=(_SEG1,),  # target _SEG0 missing
        )
        with self.assertRaises(CandidateNotApplicableError):
            _service(fakes).generate(candidate_id=_CAND.value)

    def test_missing_segment_record_blocked(self):
        fakes = _Fakes()
        del fakes.segments[_SEG0.value]
        with self.assertRaises(CandidateNotApplicableError):
            _service(fakes).generate(candidate_id=_CAND.value)

    def test_stale_source_snapshot_blocked(self):
        fakes = _Fakes()
        fakes.segments[_SEG0.value] = _segment(_SEG0, "DRIFTED TEXT", 0, 0.0, 2.5)
        with self.assertRaises(CandidateNotApplicableError):
            _service(fakes).generate(candidate_id=_CAND.value)
        self.assertEqual(fakes.persist_calls, 0)


class ApplicationSemanticsTests(unittest.TestCase):
    def test_exact_replacement_and_preservation(self):
        fakes = _Fakes()
        result = _service(fakes).generate(candidate_id=_CAND.value)
        revision = result.revision
        self.assertEqual(len(revision.segment_ids), 2)
        replacement = fakes.segments[revision.segment_ids[0].value]
        self.assertEqual(replacement.text, "안녕하세요 여러분")
        self.assertEqual(replacement.replaces_segment_id, _SEG0)
        self.assertEqual(replacement.start, 0.0)
        self.assertEqual(replacement.end, 2.5)
        self.assertEqual(replacement.source_order, 0)
        self.assertEqual(revision.segment_ids[1], _SEG1)  # unaffected segment referenced unchanged
        self.assertEqual(revision.parent_raw_transcript_id, _RAW)
        self.assertEqual(revision.correction_candidate_ids, (_CAND,))
        self.assertEqual(revision.applicability.value, "undetermined")  # not current

    def test_source_segment_never_mutated(self):
        fakes = _Fakes()
        before = fakes.segments[_SEG0.value]
        _service(fakes).generate(candidate_id=_CAND.value)
        self.assertEqual(fakes.segments[_SEG0.value], before)

    def test_deterministic_identity(self):
        a = _Fakes()
        b = _Fakes()
        r1 = _service(a).generate(candidate_id=_CAND.value)
        r2 = _service(b).generate(candidate_id=_CAND.value)
        self.assertEqual(r1.revision.identity, r2.revision.identity)
        self.assertEqual(r1.generation.identity, r2.generation.identity)
        self.assertEqual(r1.generation.content_fingerprint, r2.generation.content_fingerprint)


class ReplayAndConflictTests(unittest.TestCase):
    def test_identical_replay_reuses(self):
        fakes = _Fakes()
        service = _service(fakes)
        first = service.generate(candidate_id=_CAND.value)
        again = service.generate(candidate_id=_CAND.value)
        self.assertEqual(again.outcome, "reused")
        self.assertEqual(again.revision.identity, first.revision.identity)
        self.assertEqual(fakes.persist_calls, 1)

    def test_conflicting_content_at_same_anchor_fails(self):
        fakes = _Fakes()
        service = _service(fakes)
        service.generate(candidate_id=_CAND.value)
        # Simulate diverged content: the candidate's proposed text changes (impossible in the real
        # immutable repository; models corruption / a stale read).
        fakes.candidate_record = _candidate(proposed="완전히 다른 제안")
        with self.assertRaises(CorrectedRevisionConflictError):
            service.generate(candidate_id=_CAND.value)

    def test_near_concurrent_collision_converges(self):
        fakes = _Fakes()

        original = fakes.persist_corrected_revision_generation

        def racing(**kwargs):
            original(**kwargs)
            raise PersistenceIdentityCollisionError("won by another writer")

        fakes.persist_corrected_revision_generation = racing
        result = _service(fakes).generate(candidate_id=_CAND.value)
        self.assertEqual(result.outcome, "reused")

    def test_persistence_required(self):
        fakes = _Fakes()
        service = CorrectedRevisionGenerationService(
            fakes, fakes, fakes, fakes, fakes, fakes, None
        )
        with self.assertRaises(RuntimeError):
            service.generate(candidate_id=_CAND.value)


if __name__ == "__main__":
    unittest.main()
