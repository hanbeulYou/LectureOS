"""Subtitle persistence contracts."""

from lectureos.execution.repositories import InMemoryRepository, Repository

from .identities import (
    SubtitleCandidateId,
    SubtitleCueId,
    SubtitleRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from .models import (
    SubtitleCandidate,
    SubtitleCue,
    SubtitleRevision,
    SubtitleValidation,
    SubtitleValidationFinding,
)

SubtitleCueRepository = Repository[SubtitleCueId, SubtitleCue]
SubtitleCandidateRepository = Repository[SubtitleCandidateId, SubtitleCandidate]
SubtitleRevisionRepository = Repository[SubtitleRevisionId, SubtitleRevision]
SubtitleValidationRepository = Repository[SubtitleValidationId, SubtitleValidation]
SubtitleValidationFindingRepository = Repository[
    SubtitleValidationFindingId, SubtitleValidationFinding
]

__all__ = ["InMemoryRepository"]
