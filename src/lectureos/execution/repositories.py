"""Persistence boundaries and dependency-free in-memory implementations."""

from typing import Generic, Protocol, TypeVar

from .identities import (
    DiagnosticId,
    DomainResultId,
    FailureId,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
)
from .models import Diagnostic, DomainResultReference, Failure, ProcessingRun, ProcessingUnit, UnitExecution

IdentityT = TypeVar("IdentityT")
RecordT = TypeVar("RecordT")


class Repository(Protocol[IdentityT, RecordT]):
    def get(self, identity: IdentityT) -> RecordT | None: ...

    def save(self, record: RecordT) -> None: ...


class InMemoryRepository(Generic[IdentityT, RecordT]):
    def __init__(self) -> None:
        self._records: dict[IdentityT, RecordT] = {}

    def get(self, identity: IdentityT) -> RecordT | None:
        return self._records.get(identity)

    def save(self, record: RecordT) -> None:
        identity = getattr(record, "identity")
        self._records[identity] = record

    def all(self) -> tuple[RecordT, ...]:
        return tuple(self._records.values())


ProcessingRunRepository = Repository[ProcessingRunId, ProcessingRun]
ProcessingUnitRepository = Repository[ProcessingUnitId, ProcessingUnit]
UnitExecutionRepository = Repository[UnitExecutionId, UnitExecution]
DomainResultReferenceRepository = Repository[DomainResultId, DomainResultReference]
FailureRepository = Repository[FailureId, Failure]
DiagnosticRepository = Repository[DiagnosticId, Diagnostic]
