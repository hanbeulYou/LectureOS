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


@dataclass(frozen=True, slots=True)
class LectureAnalysisFindingId(OpaqueIdentity):
    """Effective-transcript generation Analysis Finding (042 §8.2 / PATCH-0030).

    Distinct from the legacy execution-coupled `AnalysisFindingId` (042 §8.1), which anchors to
    an `EligibleAnalysisInput` and requires a running unit execution.
    """


@dataclass(frozen=True, slots=True)
class LectureAnalysisSegmentId(OpaqueIdentity):
    """Effective-transcript generation Lecture Segment (042 §7.2 / PATCH-0031).

    Distinct from the legacy execution-coupled `LectureSegmentId` (042 §7.1), which anchors to
    an `EligibleAnalysisInput` and requires a running unit execution.
    """


@dataclass(frozen=True, slots=True)
class LectureAnalysisEditCandidateId(OpaqueIdentity):
    """Effective-transcript generation Edit Candidate (042 §9.3 / PATCH-0032).

    Distinct from the legacy execution-coupled `EditCandidateId` (042 §9.1), which anchors to a
    legacy `AnalysisFinding` and requires a running unit execution and a `DomainResultReference`.
    """


@dataclass(frozen=True, slots=True)
class LectureReviewDecisionId(OpaqueIdentity):
    """Effective-transcript generation Review Decision (043 §7.5 / PATCH-0033).

    Distinct from the legacy execution-coupled `ReviewDecisionId` (043 §7.4), whose identity is
    caller-owned and which requires a running unit execution, its own Domain Result identity, and a
    per-admission `sequence`.
    """


@dataclass(frozen=True, slots=True)
class LectureReviewAuthorityPositionId(OpaqueIdentity):
    """One position in an effective-generation Review authority history (043 §7.6 / PATCH-0034).

    Scoped to one (Edit Candidate, human actor) pair. Distinct from the `ReviewDecision` it
    references: several positions may reference the same decision, which is what makes a reversed
    judgment representable.
    """


@dataclass(frozen=True, slots=True)
class LectureApprovedEditDecisionId(OpaqueIdentity):
    """Effective-transcript generation Approved Edit Decision (043 §7.5 / PATCH-0033).

    Distinct from the legacy execution-coupled `ApprovedDecisionId` (043 §7.4), which chains
    directly to the legacy `ReviewDecision`'s Domain Result.
    """
