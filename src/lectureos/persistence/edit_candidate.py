"""Insert-only SQLite persistence for durable canonical Edit Candidates (042 §9.1).

Serializes the immutable Edit Candidates admitted from one normalized candidate result together with their
DomainResultReferences in a single atomic transaction. The records are a deterministic derivation from a
canonical Analysis Finding; persisting them records only the Candidates and starts no downstream capability.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.edit_candidate import (
    EDIT_CANDIDATE_RESULT_KIND,
    EditCandidate,
    PreparedEditCandidate,
)
from lectureos.application.identities import (
    AnalysisFindingId,
    EditCandidateId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 26


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Edit Candidate persistence requires SQLite schema version 26"
        )
    return version


class SQLiteEditCandidateRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: EditCandidateId) -> EditCandidate | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_finding_id, source_media_id,
                       source_timeline_id, processing_run_id, unit_execution_id,
                       sequence, candidate_type, rationale, range_start, range_end
                FROM edit_candidates
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_candidate(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Edit Candidate: {error}"
            ) from error


class SQLiteEditCandidateCommandPersistence:
    """Owns one atomic v26 transaction persisting Edit Candidates and their Result references."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_edit_candidates(
        self, *, prepared: tuple[PreparedEditCandidate, ...]
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Edit Candidate persistence requires SQLite schema version 26"
            )
        if not prepared:
            raise PersistenceError("edit candidate persistence requires at least one candidate")
        for record in prepared:
            _validate_candidate_linkage(record)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            for record in prepared:
                if self._exists("edit_candidates", record.candidate.identity.value):
                    raise PersistenceIdentityCollisionError(
                        "Edit Candidate identity already exists"
                    )
                if self._exists(
                    "domain_result_references", record.candidate_result.identity.value
                ):
                    raise PersistenceIdentityCollisionError(
                        "edit candidate Domain Result identity already exists"
                    )
                _insert_candidate(self._connection, record.candidate)
                _insert_domain_result_reference_record(
                    self._connection, record.candidate_result
                )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Edit Candidate: {error}"
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


def _validate_candidate_linkage(record: PreparedEditCandidate) -> None:
    candidate = record.candidate
    result = record.candidate_result
    if candidate.domain_result_id != result.identity:
        raise PersistenceError("edit candidate Domain Result identity mismatch")
    if result.kind != EDIT_CANDIDATE_RESULT_KIND:
        raise PersistenceError("edit candidate Domain Result kind is invalid")
    if len(result.upstream_results) != 1:
        raise PersistenceError("edit candidate Domain Result upstream is invalid")


def _restore_candidate(row: tuple[object, ...]) -> EditCandidate:
    return EditCandidate(
        identity=EditCandidateId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_finding_id=AnalysisFindingId(row[2]),
        source_media_id=SourceMediaId(row[3]),
        source_timeline_id=SourceTimelineId(row[4]),
        run_id=ProcessingRunId(row[5]),
        unit_execution_id=UnitExecutionId(row[6]),
        sequence=row[7],
        candidate_type=row[8],
        rationale=row[9],
        range_start=row[10],
        range_end=row[11],
    )


def _insert_candidate(connection: sqlite3.Connection, record: EditCandidate) -> None:
    connection.execute(
        """
        INSERT INTO edit_candidates(
            identity, domain_result_id, source_finding_id, source_media_id,
            source_timeline_id, processing_run_id, unit_execution_id, sequence,
            candidate_type, rationale, range_start, range_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_finding_id.value,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.candidate_type,
            record.rationale,
            record.range_start,
            record.range_end,
        ),
    )


__all__ = [
    "SQLiteEditCandidateCommandPersistence",
    "SQLiteEditCandidateRepository",
]
