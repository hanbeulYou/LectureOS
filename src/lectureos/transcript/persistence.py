"""Application-owned atomic persistence ports for Transcript commands."""

from typing import Protocol

from lectureos.execution.models import DomainResultReference
from lectureos.execution.repositories import DomainResultReferenceRepository

from .models import RawTranscript, TranscriptSegment
from .repositories import RawTranscriptRepository, TranscriptSegmentRepository


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
