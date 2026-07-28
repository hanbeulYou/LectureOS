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


@dataclass(frozen=True, slots=True)
class SubtitleTranscriptIntakeId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleCandidateId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleCandidateCueId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleReadingRevisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleReadingUnitId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleTimeRevisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleTimedUnitId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleValidationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleValidationFindingId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleReviewPreparationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleReviewDecisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleDecisionRevisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleFinalSubtitleId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleApprovedDocumentId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleApprovedUnitId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleSrtMaterializationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EligibleAnalysisInputId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class AnalysisFindingId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class LectureSegmentId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EditCandidateId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EditReviewDecisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class ApprovedEditDecisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class ApprovedEditExportRepresentationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EditExportAssemblyId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EditExportArtifactId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptSourceIntakeId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class ProviderTranscriptAdmissionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class CurrentRawTranscriptSelectionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class CorrectionCandidateAdmissionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class CorrectionCandidateDecisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class CorrectedRevisionGenerationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class CorrectedRevisionSelectionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EffectiveTranscriptConsumptionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleCandidateId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleCueId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleReviewSubjectId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleReviewDecisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleFinalSelectionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EffectiveSubtitleSrtArtifactId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EffectiveSrtMaterializationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EffectiveSrtDeliveryId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class EffectiveSrtPublicationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class LectureAnalysisInputAdmissionId(OpaqueIdentity):
    pass
