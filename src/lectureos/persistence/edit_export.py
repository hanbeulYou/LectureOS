"""Insert-only SQLite persistence for the Edit-Pipeline Export Application Foundation (044 §19).

Serializes one immutable Approved Edit Decision Export Representation together with its DomainResultReference
in a single atomic transaction. The record is a deterministic derivation from a canonical Approved Edit
Decision; persisting it records only the export representation and starts no downstream capability. Multiple
distinct representations may reference the same Approved Edit Decision.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.edit_export import (
    APPROVED_EDIT_EXPORT_REPRESENTATION_RESULT_KIND,
    ApprovedEditExportRepresentation,
    PreparedApprovedEditExport,
)
from lectureos.application.edit_review import EditReviewDecisionKind
from lectureos.application.identities import (
    ApprovedEditDecisionId,
    ApprovedEditExportRepresentationId,
    EditCandidateId,
    EditReviewDecisionId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.review.identities import HumanActorReference

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 28


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Edit Export persistence requires SQLite schema version 28"
        )
    return version


class SQLiteApprovedEditExportRepresentationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: ApprovedEditExportRepresentationId
    ) -> ApprovedEditExportRepresentation | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_approved_decision_id,
                       source_review_decision_id, source_candidate_id, decision_kind,
                       approved_range_start, approved_range_end, approved_candidate_type,
                       approved_rationale, actor, source_media_id, source_timeline_id,
                       processing_run_id, unit_execution_id, sequence
                FROM approved_edit_export_representations
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Approved Edit Export Representation: {error}"
            ) from error

    def count_for_approved_decision(self, decision_id: ApprovedEditDecisionId) -> int:
        try:
            return self._connection.execute(
                "SELECT COUNT(*) FROM approved_edit_export_representations "
                "WHERE source_approved_decision_id = ?",
                (decision_id.value,),
            ).fetchone()[0]
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not count export representations: {error}"
            ) from error


class SQLiteApprovedEditExportCommandPersistence:
    """Owns one atomic v28 transaction persisting an export representation and its Result reference."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_export_representation(
        self, *, prepared: PreparedApprovedEditExport
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Edit Export persistence requires SQLite schema version 28"
            )
        _validate_export_linkage(prepared)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(
                "approved_edit_export_representations",
                prepared.representation.identity.value,
            ):
                raise PersistenceIdentityCollisionError(
                    "Approved Edit Export Representation identity already exists"
                )
            if self._exists(
                "domain_result_references",
                prepared.representation_result.identity.value,
            ):
                raise PersistenceIdentityCollisionError(
                    "export representation Domain Result identity already exists"
                )
            _insert_representation(self._connection, prepared.representation)
            _insert_domain_result_reference_record(
                self._connection, prepared.representation_result
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Approved Edit Export Representation: {error}"
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


def _validate_export_linkage(prepared: PreparedApprovedEditExport) -> None:
    representation = prepared.representation
    result = prepared.representation_result
    if representation.domain_result_id != result.identity:
        raise PersistenceError("export representation Domain Result identity mismatch")
    if result.kind != APPROVED_EDIT_EXPORT_REPRESENTATION_RESULT_KIND:
        raise PersistenceError("export representation Domain Result kind is invalid")
    if len(result.upstream_results) != 1:
        # single direct upstream: the approved decision's Domain Result (set by the Application service)
        raise PersistenceError("export representation Domain Result upstream is invalid")


def _restore(row: tuple[object, ...]) -> ApprovedEditExportRepresentation:
    return ApprovedEditExportRepresentation(
        identity=ApprovedEditExportRepresentationId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_approved_decision_id=ApprovedEditDecisionId(row[2]),
        source_review_decision_id=EditReviewDecisionId(row[3]),
        source_candidate_id=EditCandidateId(row[4]),
        decision_kind=EditReviewDecisionKind(row[5]),
        approved_range_start=row[6],
        approved_range_end=row[7],
        approved_candidate_type=row[8],
        approved_rationale=row[9],
        actor=HumanActorReference(row[10]),
        source_media_id=SourceMediaId(row[11]),
        source_timeline_id=SourceTimelineId(row[12]),
        run_id=ProcessingRunId(row[13]),
        unit_execution_id=UnitExecutionId(row[14]),
        sequence=row[15],
    )


def _insert_representation(
    connection: sqlite3.Connection, record: ApprovedEditExportRepresentation
) -> None:
    connection.execute(
        """
        INSERT INTO approved_edit_export_representations(
            identity, domain_result_id, source_approved_decision_id,
            source_review_decision_id, source_candidate_id, decision_kind,
            approved_range_start, approved_range_end, approved_candidate_type,
            approved_rationale, actor, source_media_id, source_timeline_id,
            processing_run_id, unit_execution_id, sequence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_approved_decision_id.value,
            record.source_review_decision_id.value,
            record.source_candidate_id.value,
            record.decision_kind.value,
            record.approved_range_start,
            record.approved_range_end,
            record.approved_candidate_type,
            record.approved_rationale,
            record.actor.value,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
        ),
    )


__all__ = [
    "SQLiteApprovedEditExportCommandPersistence",
    "SQLiteApprovedEditExportRepresentationRepository",
]
