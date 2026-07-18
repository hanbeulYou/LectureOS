"""Execution-domain contracts derived from the approved implementation design."""

from .boundaries import (
    AtomicFailureExecutionPersistence,
    AtomicStartExecutionPersistence,
    ExecutionQueryBoundary,
    HumanDecisionBoundary,
    ProcessingRequestBoundary,
)
from .models import (
    Diagnostic,
    DomainResultReference,
    ExecutionIntent,
    ExecutionOutcome,
    Failure,
    FailureCategory,
    OutcomeKind,
    ProcessingRun,
    ProcessingState,
    ProcessingUnit,
    UnitExecution,
)
from .service import ExecutionService
from .failure_persistence import InMemoryAtomicFailureExecutionPersistence
from .start_persistence import InMemoryAtomicStartExecutionPersistence

__all__ = [
    "AtomicFailureExecutionPersistence",
    "AtomicStartExecutionPersistence",
    "Diagnostic",
    "DomainResultReference",
    "ExecutionIntent",
    "ExecutionOutcome",
    "ExecutionQueryBoundary",
    "ExecutionService",
    "Failure",
    "FailureCategory",
    "HumanDecisionBoundary",
    "InMemoryAtomicFailureExecutionPersistence",
    "InMemoryAtomicStartExecutionPersistence",
    "OutcomeKind",
    "ProcessingRequestBoundary",
    "ProcessingRun",
    "ProcessingState",
    "ProcessingUnit",
    "UnitExecution",
]
