"""Insert-only SQLite persistence for canonical Transcript Current Selections.

Serializes one immutable current-selection aggregate together with its DomainResultReference in
a single atomic transaction. The selection is a deterministic derivation from a canonical
Applicability evaluation; it records only which Revision is currently selected and never a
Transcript Ready state.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReviewDecisionId,
)
from lectureos.application.transcript_applicability_evaluation import ApplicabilityOutcome
from lectureos.application.transcript_current_selection import (
    CURRENT_SELECTION_RESULT_KIND,
    CurrentSelectionOutcome,
    TranscriptCurrentSelection,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import TranscriptRevisionId

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 9


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Transcript Current Selection persistence requires SQLite schema version 9"
        )
    return version


class SQLiteTranscriptCurrentSelectionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: TranscriptCurrentSelectionId
    ) -> TranscriptCurrentSelection | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_applicability_id,
                       applicability_outcome, outcome, source_decision_id,
                       review_item_id, candidate_reference_id, source_revision_id,
                       processing_run_id, unit_execution_id, sequence, reason,
                       previous_selection_id
                FROM transcript_current_selections
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_selection(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Transcript Current Selection: {error}"
            ) from error

    def save(self, record: TranscriptCurrentSelection) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                "Transcript Current Selection identity already exists"
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _insert_current_selection(self._connection, record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "Transcript Current Selection identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist Transcript Current Selection: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(
                f"could not persist Transcript Current Selection: {error}"
            ) from error
        except Exception:
            self._rollback()
            raise

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


class SQLiteCurrentSelectionCommandPersistence:
    """Owns one atomic v9 transaction persisting a selection and its Result reference."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_current_selection(
        self,
        *,
        selection: TranscriptCurrentSelection,
        selection_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Transcript Current Selection persistence requires SQLite schema version 9"
            )
        _validate_selection_linkage(selection, selection_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(
                "transcript_current_selections", selection.identity.value
            ):
                raise PersistenceIdentityCollisionError(
                    "Transcript Current Selection identity already exists"
                )
            if self._exists("domain_result_references", selection_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "current selection Domain Result identity already exists"
                )
            _insert_current_selection(self._connection, selection)
            _insert_domain_result_reference_record(self._connection, selection_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Transcript Current Selection: {error}"
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


def _validate_selection_linkage(
    selection: TranscriptCurrentSelection,
    selection_result: DomainResultReference,
) -> None:
    if selection.domain_result_id != selection_result.identity:
        raise PersistenceError("current selection Domain Result identity mismatch")
    if selection_result.kind != CURRENT_SELECTION_RESULT_KIND:
        raise PersistenceError("current selection Domain Result kind is invalid")
    if len(selection_result.upstream_results) != 1:
        raise PersistenceError("current selection Domain Result upstream is invalid")


def _restore_selection(row: tuple[object, ...]) -> TranscriptCurrentSelection:
    return TranscriptCurrentSelection(
        identity=TranscriptCurrentSelectionId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_applicability_id=TranscriptApplicabilityEvaluationId(row[2]),
        applicability_outcome=ApplicabilityOutcome(row[3]),
        outcome=CurrentSelectionOutcome(row[4]),
        source_decision_id=TranscriptReviewDecisionId(row[5]),
        review_item_id=ReviewItemId(row[6]),
        candidate_reference_id=CandidateReferenceId(row[7]),
        source_revision_id=TranscriptRevisionId(row[8]),
        run_id=ProcessingRunId(row[9]),
        unit_execution_id=UnitExecutionId(row[10]),
        sequence=row[11],
        reason=row[12],
        previous_selection_id=(
            TranscriptCurrentSelectionId(row[13]) if row[13] is not None else None
        ),
    )


def _insert_current_selection(
    connection: sqlite3.Connection, record: TranscriptCurrentSelection
) -> None:
    connection.execute(
        """
        INSERT INTO transcript_current_selections(
            identity, domain_result_id, source_applicability_id, applicability_outcome,
            outcome, source_decision_id, review_item_id, candidate_reference_id,
            source_revision_id, processing_run_id, unit_execution_id, sequence, reason,
            previous_selection_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_applicability_id.value,
            record.applicability_outcome.value,
            record.outcome.value,
            record.source_decision_id.value,
            record.review_item_id.value,
            record.candidate_reference_id.value,
            record.source_revision_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.reason,
            record.previous_selection_id.value
            if record.previous_selection_id
            else None,
        ),
    )


__all__ = [
    "SQLiteCurrentSelectionCommandPersistence",
    "SQLiteTranscriptCurrentSelectionRepository",
]
