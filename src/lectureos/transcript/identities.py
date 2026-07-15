"""Opaque identities owned by the Transcript domain."""

from dataclasses import dataclass

from lectureos.execution.identities import OpaqueIdentity


@dataclass(frozen=True, slots=True)
class TranscriptId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptSegmentId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptRevisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class ProviderTranscriptResultId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class CorrectionCandidateId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptValidationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class TranscriptValidationFindingId(OpaqueIdentity):
    pass
