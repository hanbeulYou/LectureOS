"""Typed identities and references owned by the Export domain."""

from dataclasses import dataclass

from lectureos.execution.identities import OpaqueIdentity


@dataclass(frozen=True, slots=True)
class ExportRequestId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class SystemRequesterReference(OpaqueIdentity):
    """Approved system identity, distinct from execution provenance."""


@dataclass(frozen=True, slots=True)
class MaterializationRequestId(OpaqueIdentity):
    pass


@dataclass(frozen=True, slots=True)
class MaterializationResultId(OpaqueIdentity):
    pass
