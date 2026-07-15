"""Transcript domain foundation."""

from .models import (
    CorrectionCandidate,
    CorrectedTranscriptRevision,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptApplicability,
    TranscriptSegment,
    TranscriptValidation,
)
from .service import TranscriptService

__all__ = [
    "CorrectionCandidate",
    "CorrectedTranscriptRevision",
    "ProviderTranscriptResult",
    "RawTranscript",
    "TranscriptApplicability",
    "TranscriptSegment",
    "TranscriptService",
    "TranscriptValidation",
]
