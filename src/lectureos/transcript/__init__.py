"""Transcript domain foundation."""

from .models import (
    CorrectionCandidate,
    CorrectedTranscriptRevision,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptApplicability,
    TranscriptSegment,
    TranscriptValidation,
    TranscriptValidationFinding,
)
from .service import TranscriptService
from .validation import TranscriptValidationService

__all__ = [
    "CorrectionCandidate",
    "CorrectedTranscriptRevision",
    "ProviderTranscriptResult",
    "RawTranscript",
    "TranscriptApplicability",
    "TranscriptSegment",
    "TranscriptService",
    "TranscriptValidation",
    "TranscriptValidationFinding",
    "TranscriptValidationService",
]
