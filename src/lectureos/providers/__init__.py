"""Concrete external capability adapters."""

from .openai_transcript_correction import OpenAITranscriptCorrectionAdapter
from .openai_edit_candidate import OpenAIEditCandidateGenerationAdapter

__all__ = [
    "OpenAITranscriptCorrectionAdapter",
    "OpenAIEditCandidateGenerationAdapter",
]
