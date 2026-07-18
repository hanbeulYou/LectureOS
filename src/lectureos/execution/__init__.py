"""Execution-domain contracts derived from the approved implementation design."""

from .boundaries import (
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
from .start_persistence import InMemoryAtomicStartExecutionPersistence

__all__ = [
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
    "InMemoryAtomicStartExecutionPersistence",
    "OutcomeKind",
    "ProcessingRequestBoundary",
    "ProcessingRun",
    "ProcessingState",
    "ProcessingUnit",
    "UnitExecution",
]
