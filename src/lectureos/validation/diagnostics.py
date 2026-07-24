"""Structured, deterministic diagnostics for repository validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    """Diagnostic severity, ordered from least to most serious."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class RepositoryHealth(str, Enum):
    """Overall repository health derived from the diagnostics."""

    HEALTHY = "healthy"
    WARNINGS = "warnings"
    ERRORS = "errors"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One deterministic validation finding.

    - ``code``: a stable machine-readable identifier (e.g. ``DANGLING_REFERENCE``).
    - ``severity``: :class:`Severity`.
    - ``location``: where the finding is (typically ``table:identity`` or ``table.column``).
    - ``message``: a human-readable explanation.
    """

    code: str
    severity: Severity
    location: str
    message: str

    def _sort_key(self) -> tuple[str, str, str]:
        return (self.code, self.location, self.message)

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "location": self.location,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """The result of validating one repository. Diagnostics are held in deterministic order."""

    schema_version: int | None
    objects_checked: int
    diagnostics: tuple[Diagnostic, ...]

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity is Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity is Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity is Severity.INFO)

    @property
    def health(self) -> RepositoryHealth:
        if self.error_count:
            return RepositoryHealth.ERRORS
        if self.warning_count:
            return RepositoryHealth.WARNINGS
        return RepositoryHealth.HEALTHY

    @property
    def ok(self) -> bool:
        """True when the repository has no error-severity diagnostics."""

        return self.error_count == 0

    def as_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "objects_checked": self.objects_checked,
            "health": self.health.value,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "diagnostics": [d.as_dict() for d in self.diagnostics],
        }


def build_report(
    *,
    schema_version: int | None,
    objects_checked: int,
    diagnostics,
) -> ValidationReport:
    """Assemble a report with diagnostics sorted deterministically."""

    ordered = tuple(sorted(diagnostics, key=lambda d: d._sort_key()))
    return ValidationReport(
        schema_version=schema_version,
        objects_checked=objects_checked,
        diagnostics=ordered,
    )


__all__ = [
    "Diagnostic",
    "RepositoryHealth",
    "Severity",
    "ValidationReport",
    "build_report",
]
