"""Typed identities for cross-domain application records."""

from dataclasses import dataclass

from lectureos.execution.identities import OpaqueIdentity


@dataclass(frozen=True, slots=True)
class TranscriptCorrectionApplicationResultId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleDecisionApplicationResultId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleTextReplacementId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptReviewPreparationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptReviewDecisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptApplicabilityEvaluationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptCurrentSelectionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptReadinessEvaluationId(OpaqueIdentity):
    pass
