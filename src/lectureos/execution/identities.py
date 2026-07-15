"""Opaque identities for records that must not be mixed accidentally."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OpaqueIdentity:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("identity must not be empty")


@dataclass(frozen=True, slots=True)
class ProcessingRunId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class ProcessingUnitId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class UnitExecutionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class DomainResultId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class ReviewDecisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class ApprovedEditDecisionId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class ArtifactId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SourceMediaId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SourceTimelineId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class FailureId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class DiagnosticId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class WorkingContextReference(OpaqueIdentity):
    """Working-model reference; not a canonical Project or Lecture identity."""


@dataclass(frozen=True, slots=True)
class ConfigurationReference(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class CapabilityReference(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class PluginReference(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class InputReference(OpaqueIdentity):
    pass
