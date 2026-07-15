"""Execution-domain contracts derived from the approved implementation design."""

from .boundaries import ExecutionQueryBoundary, HumanDecisionBoundary, ProcessingRequestBoundary
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

__all__ = [
    "Diagnostic",
    "DomainResultReference",
    "ExecutionIntent",
    "ExecutionOutcome",
    "ExecutionQueryBoundary",
    "ExecutionService",
    "Failure",
    "FailureCategory",
    "HumanDecisionBoundary",
    "OutcomeKind",
    "ProcessingRequestBoundary",
    "ProcessingRun",
    "ProcessingState",
    "ProcessingUnit",
    "UnitExecution",
]
