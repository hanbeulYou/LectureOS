"""Application-owned atomic persistence ports for Transcript commands."""

from typing import Protocol

from lectureos.execution.models import DomainResultReference
from lectureos.execution.repositories import DomainResultReferenceRepository

from .models import (
    CorrectionCandidate,
    CorrectedTranscriptRevision,
    RawTranscript,
    TranscriptSegment,
)
from .repositories import (
    CorrectionCandidateRepository,
    CorrectedTranscriptRevisionRepository,
    RawTranscriptRepository,
    TranscriptSegmentRepository,
)


class AtomicRawTranscriptPersistence(Protocol):
    def persist_raw_transcript(
        self,
        *,
        transcript: RawTranscript,
        segments: tuple[TranscriptSegment, ...],
        result: DomainResultReference,
    ) -> None: ...


class InMemoryAtomicRawTranscriptPersistence:
    """Default command adapter preserving current in-process behavior."""

    def __init__(
        self,
        transcripts: RawTranscriptRepository,
        segments: TranscriptSegmentRepository,
        results: DomainResultReferenceRepository,
    ) -> None:
        self._transcripts = transcripts
        self._segments = segments
        self._results = results

    def persist_raw_transcript(
        self,
        *,
        transcript: RawTranscript,
        segments: tuple[TranscriptSegment, ...],
        result: DomainResultReference,
    ) -> None:
        for segment in segments:
            self._segments.save(segment)
        self._transcripts.save(transcript)
        self._results.save(result)


class AtomicCorrectionCandidatePersistence(Protocol):
    def persist_correction_candidate(
        self,
        *,
        candidate: CorrectionCandidate,
        result: DomainResultReference,
    ) -> None: ...


class InMemoryAtomicCorrectionCandidatePersistence:
    def __init__(
        self,
        candidates: CorrectionCandidateRepository,
        results: DomainResultReferenceRepository,
    ) -> None:
        self._candidates = candidates
        self._results = results

    def persist_correction_candidate(
        self,
        *,
        candidate: CorrectionCandidate,
        result: DomainResultReference,
    ) -> None:
        self._candidates.save(candidate)
        self._results.save(result)


class AtomicCorrectedTranscriptRevisionPersistence(Protocol):
    def persist_corrected_revision(
        self,
        *,
        revision: CorrectedTranscriptRevision,
        segments: tuple[TranscriptSegment, ...],
        result: DomainResultReference,
    ) -> None: ...


class InMemoryAtomicCorrectedTranscriptRevisionPersistence:
    def __init__(
        self,
        revisions: CorrectedTranscriptRevisionRepository,
        segments: TranscriptSegmentRepository,
        results: DomainResultReferenceRepository,
    ) -> None:
        self._revisions = revisions
        self._segments = segments
        self._results = results

    def persist_corrected_revision(
        self,
        *,
        revision: CorrectedTranscriptRevision,
        segments: tuple[TranscriptSegment, ...],
        result: DomainResultReference,
    ) -> None:
        for segment in segments:
            if self._segments.get(segment.identity) is None:
                self._segments.save(segment)
        self._revisions.save(revision)
        self._results.save(result)
