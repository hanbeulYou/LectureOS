"""Typed identities for Subtitle records."""

from dataclasses import dataclass

from lectureos.execution.identities import OpaqueIdentity


@dataclass(frozen=True, slots=True)
class SubtitleId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleCueId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleCandidateId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleRevisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleRevisionApplicabilityId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class FinalSubtitleSelectionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleValidationId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleValidationFindingId(OpaqueIdentity):
    pass
