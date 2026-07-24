"""Read-only repository integrity validation for LectureOS.

This subsystem verifies that persisted repository state is internally consistent — identities, references,
DomainResult lineage, and the edit-export pipeline invariants — before higher-level workflows run. It is
strictly read-only: it opens the database with `PRAGMA query_only = ON` and issues only SELECT/PRAGMA
statements. It never mutates repository state and is deliberately independent of the application/business
services (it consumes the persisted store; it does not run the domain logic that produced it).
"""

from __future__ import annotations

from .diagnostics import (
    Diagnostic,
    RepositoryHealth,
    Severity,
    ValidationReport,
)
from .repository_validator import validate_database, validate_repository

__all__ = [
    "Diagnostic",
    "RepositoryHealth",
    "Severity",
    "ValidationReport",
    "validate_database",
    "validate_repository",
]
