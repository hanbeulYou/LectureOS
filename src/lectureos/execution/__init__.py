"""Execution-domain contracts derived from the approved implementation design."""

from .boundaries import (
    AtomicFailureExecutionPersistence,
    AtomicResultExecutionPersistence,
    AtomicRetryExecutionPersistence,
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
from .failure_persistence import InMemoryAtomicFailureExecutionPersistence
from .result_persistence import InMemoryAtomicResultExecutionPersistence
from .retry_persistence import InMemoryAtomicRetryExecutionPersistence
from .service import ExecutionService
from .start_persistence import InMemoryAtomicStartExecutionPersistence

__all__ = [
    "AtomicFailureExecutionPersistence",
    "AtomicResultExecutionPersistence",
    "AtomicRetryExecutionPersistence",
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
    "InMemoryAtomicResultExecutionPersistence",
    "InMemoryAtomicRetryExecutionPersistence",
    "InMemoryAtomicStartExecutionPersistence",
    "OutcomeKind",
    "ProcessingRequestBoundary",
    "ProcessingRun",
    "ProcessingState",
    "ProcessingUnit",
    "UnitExecution",
]
