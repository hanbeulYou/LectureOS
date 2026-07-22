"""Insert-only SQLite persistence for durable canonical Analysis Findings (042 §8.1).

Serializes the immutable Analysis Findings admitted from one normalized analysis result together with their
DomainResultReferences in a single atomic transaction. The records are a deterministic derivation from a
canonical Eligible Analysis Input; persisting them records only the Findings and starts no downstream
capability.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.analysis_finding import (
    ANALYSIS_FINDING_RESULT_KIND,
    AnalysisFinding,
    PreparedAnalysisFinding,
)
from lectureos.application.identities import (
    AnalysisFindingId,
    EligibleAnalysisInputId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 24


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Analysis Finding persistence requires SQLite schema version 24"
        )
    return version


class SQLiteAnalysisFindingRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: AnalysisFindingId) -> AnalysisFinding | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_input_id, finding_type,
                       evidence, source_media_id, source_timeline_id, processing_run_id,
                       unit_execution_id, sequence, confidence, uncertainty,
                       range_start, range_end
                FROM analysis_findings
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_finding(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Analysis Finding: {error}"
            ) from error


class SQLiteAnalysisFindingCommandPersistence:
    """Owns one atomic v24 transaction persisting Analysis Findings and their Result references."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_analysis_findings(
        self, *, prepared: tuple[PreparedAnalysisFinding, ...]
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Analysis Finding persistence requires SQLite schema version 24"
            )
        if not prepared:
            raise PersistenceError("analysis finding persistence requires at least one finding")
        for record in prepared:
            _validate_finding_linkage(record)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            for record in prepared:
                if self._exists("analysis_findings", record.finding.identity.value):
                    raise PersistenceIdentityCollisionError(
                        "Analysis Finding identity already exists"
                    )
                if self._exists(
                    "domain_result_references", record.finding_result.identity.value
                ):
                    raise PersistenceIdentityCollisionError(
                        "analysis finding Domain Result identity already exists"
                    )
                _insert_finding(self._connection, record.finding)
                _insert_domain_result_reference_record(
                    self._connection, record.finding_result
                )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Analysis Finding: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, table: str, identity_value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM {table} WHERE identity = ?",
                (identity_value,),
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _validate_finding_linkage(record: PreparedAnalysisFinding) -> None:
    finding = record.finding
    result = record.finding_result
    if finding.domain_result_id != result.identity:
        raise PersistenceError("analysis finding Domain Result identity mismatch")
    if result.kind != ANALYSIS_FINDING_RESULT_KIND:
        raise PersistenceError("analysis finding Domain Result kind is invalid")
    if len(result.upstream_results) != 1:
        raise PersistenceError("analysis finding Domain Result upstream is invalid")


def _restore_finding(row: tuple[object, ...]) -> AnalysisFinding:
    return AnalysisFinding(
        identity=AnalysisFindingId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_input_id=EligibleAnalysisInputId(row[2]),
        finding_type=row[3],
        evidence=row[4],
        source_media_id=SourceMediaId(row[5]),
        source_timeline_id=SourceTimelineId(row[6]),
        run_id=ProcessingRunId(row[7]),
        unit_execution_id=UnitExecutionId(row[8]),
        sequence=row[9],
        confidence=row[10],
        uncertainty=row[11],
        range_start=row[12],
        range_end=row[13],
    )


def _insert_finding(connection: sqlite3.Connection, record: AnalysisFinding) -> None:
    connection.execute(
        """
        INSERT INTO analysis_findings(
            identity, domain_result_id, source_input_id, finding_type, evidence,
            source_media_id, source_timeline_id, processing_run_id, unit_execution_id,
            sequence, confidence, uncertainty, range_start, range_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_input_id.value,
            record.finding_type,
            record.evidence,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.confidence,
            record.uncertainty,
            record.range_start,
            record.range_end,
        ),
    )


__all__ = [
    "SQLiteAnalysisFindingCommandPersistence",
    "SQLiteAnalysisFindingRepository",
]
