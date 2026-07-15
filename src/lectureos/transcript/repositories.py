"""Transcript persistence contracts and in-memory aliases."""

from lectureos.execution.repositories import InMemoryRepository, Repository

from .identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
    TranscriptValidationFindingId,
)
from .models import (
    CorrectionCandidate,
    CorrectedTranscriptRevision,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
    TranscriptValidation,
    TranscriptValidationFinding,
)

ProviderTranscriptResultRepository = Repository[
    ProviderTranscriptResultId, ProviderTranscriptResult
]
RawTranscriptRepository = Repository[TranscriptId, RawTranscript]
CorrectedTranscriptRevisionRepository = Repository[
    TranscriptRevisionId, CorrectedTranscriptRevision
]
TranscriptSegmentRepository = Repository[TranscriptSegmentId, TranscriptSegment]
CorrectionCandidateRepository = Repository[CorrectionCandidateId, CorrectionCandidate]
TranscriptValidationRepository = Repository[TranscriptValidationId, TranscriptValidation]
TranscriptValidationFindingRepository = Repository[
    TranscriptValidationFindingId, TranscriptValidationFinding
]

__all__ = [
    "CorrectionCandidateRepository",
    "CorrectedTranscriptRevisionRepository",
    "InMemoryRepository",
    "ProviderTranscriptResultRepository",
    "RawTranscriptRepository",
    "TranscriptSegmentRepository",
    "TranscriptValidationRepository",
    "TranscriptValidationFindingRepository",
]
