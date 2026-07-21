"""Insert-only SQLite persistence for canonical Transcript Applicability Evaluations.

Serializes one immutable applicability evaluation aggregate together with its
DomainResultReference in a single atomic transaction. The evaluation is a deterministic
derivation from a canonical Human Review Decision; no decision, selection or downstream state
is persisted here.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.application.transcript_applicability_evaluation import (
    APPLICABILITY_EVALUATION_RESULT_KIND,
    ApplicabilityOutcome,
    TranscriptApplicabilityEvaluation,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptRevisionId

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 8


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Transcript Applicability persistence requires SQLite schema version 8"
        )
    return version


class SQLiteTranscriptApplicabilityEvaluationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: TranscriptApplicabilityEvaluationId
    ) -> TranscriptApplicabilityEvaluation | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_decision_id, decision_kind,
                       outcome, review_item_id, candidate_reference_id,
                       source_revision_id, processing_run_id, unit_execution_id,
                       sequence, reason, previous_evaluation_id
                FROM transcript_applicability_evaluations
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_evaluation(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Transcript Applicability Evaluation: {error}"
            ) from error

    def save(self, record: TranscriptApplicabilityEvaluation) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                "Transcript Applicability Evaluation identity already exists"
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _insert_applicability_evaluation(self._connection, record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "Transcript Applicability Evaluation identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist Transcript Applicability Evaluation: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(
                f"could not persist Transcript Applicability Evaluation: {error}"
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


class SQLiteApplicabilityEvaluationCommandPersistence:
    """Owns one atomic v8 transaction persisting an evaluation and its Result reference."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_applicability_evaluation(
        self,
        *,
        evaluation: TranscriptApplicabilityEvaluation,
        evaluation_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Transcript Applicability persistence requires SQLite schema version 8"
            )
        _validate_evaluation_linkage(evaluation, evaluation_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(
                "transcript_applicability_evaluations", evaluation.identity.value
            ):
                raise PersistenceIdentityCollisionError(
                    "Transcript Applicability Evaluation identity already exists"
                )
            if self._exists("domain_result_references", evaluation_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "applicability evaluation Domain Result identity already exists"
                )
            _insert_applicability_evaluation(self._connection, evaluation)
            _insert_domain_result_reference_record(self._connection, evaluation_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Transcript Applicability Evaluation: {error}"
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


def _validate_evaluation_linkage(
    evaluation: TranscriptApplicabilityEvaluation,
    evaluation_result: DomainResultReference,
) -> None:
    if evaluation.domain_result_id != evaluation_result.identity:
        raise PersistenceError("applicability evaluation Domain Result identity mismatch")
    if evaluation_result.kind != APPLICABILITY_EVALUATION_RESULT_KIND:
        raise PersistenceError("applicability evaluation Domain Result kind is invalid")
    if len(evaluation_result.upstream_results) != 1:
        raise PersistenceError("applicability evaluation Domain Result upstream is invalid")


def _restore_evaluation(row: tuple[object, ...]) -> TranscriptApplicabilityEvaluation:
    return TranscriptApplicabilityEvaluation(
        identity=TranscriptApplicabilityEvaluationId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_decision_id=TranscriptReviewDecisionId(row[2]),
        decision_kind=DecisionKind(row[3]),
        outcome=ApplicabilityOutcome(row[4]),
        review_item_id=ReviewItemId(row[5]),
        candidate_reference_id=CandidateReferenceId(row[6]),
        source_revision_id=TranscriptRevisionId(row[7]),
        run_id=ProcessingRunId(row[8]),
        unit_execution_id=UnitExecutionId(row[9]),
        sequence=row[10],
        reason=row[11],
        previous_evaluation_id=(
            TranscriptApplicabilityEvaluationId(row[12]) if row[12] is not None else None
        ),
    )


def _insert_applicability_evaluation(
    connection: sqlite3.Connection, record: TranscriptApplicabilityEvaluation
) -> None:
    connection.execute(
        """
        INSERT INTO transcript_applicability_evaluations(
            identity, domain_result_id, source_decision_id, decision_kind, outcome,
            review_item_id, candidate_reference_id, source_revision_id,
            processing_run_id, unit_execution_id, sequence, reason,
            previous_evaluation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_decision_id.value,
            record.decision_kind.value,
            record.outcome.value,
            record.review_item_id.value,
            record.candidate_reference_id.value,
            record.source_revision_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.reason,
            record.previous_evaluation_id.value
            if record.previous_evaluation_id
            else None,
        ),
    )


__all__ = [
    "SQLiteApplicabilityEvaluationCommandPersistence",
    "SQLiteTranscriptApplicabilityEvaluationRepository",
]
