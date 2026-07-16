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
from .applicability import (
    CurrentTranscriptSelection,
    RevisionApplicabilityRecord,
    RevisionTarget,
    TranscriptApplicabilityIntegrityError,
    TranscriptApplicabilityKind,
    TranscriptApplicabilityService,
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
    "CurrentTranscriptSelection",
    "RevisionApplicabilityRecord",
    "RevisionTarget",
    "TranscriptApplicabilityIntegrityError",
    "TranscriptApplicabilityKind",
    "TranscriptApplicabilityService",
]
