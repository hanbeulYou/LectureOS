"""Insert-only SQLite persistence for canonical Transcript Ready State evaluations.

Serializes one immutable readiness aggregate together with its DomainResultReference in a single
atomic transaction. Readiness is a deterministic derivation from canonical upstream records;
persisting it records only the readiness evaluation and starts no downstream capability.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.application.transcript_applicability_evaluation import ApplicabilityOutcome
from lectureos.application.transcript_current_selection import CurrentSelectionOutcome
from lectureos.application.transcript_readiness_evaluation import (
    READINESS_EVALUATION_RESULT_KIND,
    ReadinessOutcome,
    ReadinessReasonCode,
    TranscriptReadinessEvaluation,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.transcript.identities import TranscriptRevisionId, TranscriptValidationId

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 10


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Transcript Ready State persistence requires SQLite schema version 10"
        )
    return version


class SQLiteTranscriptReadinessEvaluationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: TranscriptReadinessEvaluationId
    ) -> TranscriptReadinessEvaluation | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_selection_id, selection_outcome,
                       source_applicability_id, applicability_outcome, source_decision_id,
                       review_item_id, candidate_reference_id, source_revision_id,
                       validation_id, structural_valid, outcome, reason_code,
                       processing_run_id, unit_execution_id, sequence, reason,
                       previous_readiness_id
                FROM transcript_readiness_evaluations
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_readiness(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Transcript Ready State evaluation: {error}"
            ) from error

    def save(self, record: TranscriptReadinessEvaluation) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                "Transcript Ready State evaluation identity already exists"
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _insert_readiness_evaluation(self._connection, record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "Transcript Ready State evaluation identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist Transcript Ready State evaluation: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(
                f"could not persist Transcript Ready State evaluation: {error}"
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


class SQLiteReadinessEvaluationCommandPersistence:
    """Owns one atomic v10 transaction persisting a readiness record and its Result."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_readiness_evaluation(
        self,
        *,
        readiness: TranscriptReadinessEvaluation,
        readiness_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Transcript Ready State persistence requires SQLite schema version 10"
            )
        _validate_readiness_linkage(readiness, readiness_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(
                "transcript_readiness_evaluations", readiness.identity.value
            ):
                raise PersistenceIdentityCollisionError(
                    "Transcript Ready State evaluation identity already exists"
                )
            if self._exists("domain_result_references", readiness_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "readiness evaluation Domain Result identity already exists"
                )
            _insert_readiness_evaluation(self._connection, readiness)
            _insert_domain_result_reference_record(self._connection, readiness_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Transcript Ready State evaluation: {error}"
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


def _validate_readiness_linkage(
    readiness: TranscriptReadinessEvaluation,
    readiness_result: DomainResultReference,
) -> None:
    if readiness.domain_result_id != readiness_result.identity:
        raise PersistenceError("readiness evaluation Domain Result identity mismatch")
    if readiness_result.kind != READINESS_EVALUATION_RESULT_KIND:
        raise PersistenceError("readiness evaluation Domain Result kind is invalid")
    if len(readiness_result.upstream_results) != 1:
        raise PersistenceError("readiness evaluation Domain Result upstream is invalid")


def _restore_readiness(row: tuple[object, ...]) -> TranscriptReadinessEvaluation:
    return TranscriptReadinessEvaluation(
        identity=TranscriptReadinessEvaluationId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_selection_id=TranscriptCurrentSelectionId(row[2]),
        selection_outcome=CurrentSelectionOutcome(row[3]),
        source_applicability_id=TranscriptApplicabilityEvaluationId(row[4]),
        applicability_outcome=ApplicabilityOutcome(row[5]),
        source_decision_id=TranscriptReviewDecisionId(row[6]),
        review_item_id=ReviewItemId(row[7]),
        candidate_reference_id=CandidateReferenceId(row[8]),
        source_revision_id=TranscriptRevisionId(row[9]),
        validation_id=TranscriptValidationId(row[10]),
        structural_valid=bool(row[11]),
        outcome=ReadinessOutcome(row[12]),
        reason_code=ReadinessReasonCode(row[13]),
        run_id=ProcessingRunId(row[14]),
        unit_execution_id=UnitExecutionId(row[15]),
        sequence=row[16],
        reason=row[17],
        previous_readiness_id=(
            TranscriptReadinessEvaluationId(row[18]) if row[18] is not None else None
        ),
    )


def _insert_readiness_evaluation(
    connection: sqlite3.Connection, record: TranscriptReadinessEvaluation
) -> None:
    connection.execute(
        """
        INSERT INTO transcript_readiness_evaluations(
            identity, domain_result_id, source_selection_id, selection_outcome,
            source_applicability_id, applicability_outcome, source_decision_id,
            review_item_id, candidate_reference_id, source_revision_id, validation_id,
            structural_valid, outcome, reason_code, processing_run_id, unit_execution_id,
            sequence, reason, previous_readiness_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_selection_id.value,
            record.selection_outcome.value,
            record.source_applicability_id.value,
            record.applicability_outcome.value,
            record.source_decision_id.value,
            record.review_item_id.value,
            record.candidate_reference_id.value,
            record.source_revision_id.value,
            record.validation_id.value,
            int(record.structural_valid),
            record.outcome.value,
            record.reason_code.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.reason,
            record.previous_readiness_id.value
            if record.previous_readiness_id
            else None,
        ),
    )


__all__ = [
    "SQLiteReadinessEvaluationCommandPersistence",
    "SQLiteTranscriptReadinessEvaluationRepository",
]
