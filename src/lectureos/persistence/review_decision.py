"""Insert-only SQLite persistence for canonical Transcript Human Review Decisions.

Serializes one immutable decision aggregate together with its DomainResultReference in a
single atomic transaction. The decision timestamp is stored verbatim from the caller-supplied
value so that reconstruction and deterministic replay are exact. No decision automation or
downstream state is persisted.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from lectureos.application.identities import TranscriptReviewDecisionId
from lectureos.application.transcript_review_decision import (
    REVIEW_DECISION_RESULT_KIND,
    TranscriptReviewDecision,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.review.identities import CandidateReferenceId, HumanActorReference, ReviewItemId
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptRevisionId

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 7


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Transcript Review Decision persistence requires SQLite schema version 7"
        )
    return version


class SQLiteTranscriptReviewDecisionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: TranscriptReviewDecisionId
    ) -> TranscriptReviewDecision | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, review_item_id,
                       candidate_reference_id, source_revision_id, reviewer, kind,
                       decided_at, processing_run_id, unit_execution_id, sequence,
                       previous_decision_id, rationale, modified_text
                FROM transcript_review_decisions
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_decision(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Transcript Review Decision: {error}"
            ) from error

    def save(self, record: TranscriptReviewDecision) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                "Transcript Review Decision identity already exists"
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _insert_review_decision(self._connection, record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "Transcript Review Decision identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist Transcript Review Decision: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(
                f"could not persist Transcript Review Decision: {error}"
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


class SQLiteReviewDecisionCommandPersistence:
    """Owns one atomic v7 transaction persisting a decision and its Result reference."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_review_decision(
        self,
        *,
        decision: TranscriptReviewDecision,
        decision_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Transcript Review Decision persistence requires SQLite schema version 7"
            )
        _validate_decision_linkage(decision, decision_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("transcript_review_decisions", decision.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Transcript Review Decision identity already exists"
                )
            if self._exists("domain_result_references", decision_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "review decision Domain Result identity already exists"
                )
            _insert_review_decision(self._connection, decision)
            _insert_domain_result_reference_record(self._connection, decision_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Transcript Review Decision: {error}"
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


def _validate_decision_linkage(
    decision: TranscriptReviewDecision, decision_result: DomainResultReference
) -> None:
    if decision.domain_result_id != decision_result.identity:
        raise PersistenceError("review decision Domain Result identity mismatch")
    if decision_result.kind != REVIEW_DECISION_RESULT_KIND:
        raise PersistenceError("review decision Domain Result kind is invalid")
    if len(decision_result.upstream_results) != 1:
        raise PersistenceError("review decision Domain Result upstream is invalid")


def _restore_decision(row: tuple[object, ...]) -> TranscriptReviewDecision:
    return TranscriptReviewDecision(
        identity=TranscriptReviewDecisionId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        review_item_id=ReviewItemId(row[2]),
        candidate_reference_id=CandidateReferenceId(row[3]),
        source_revision_id=TranscriptRevisionId(row[4]),
        reviewer=HumanActorReference(row[5]),
        kind=DecisionKind(row[6]),
        decided_at=datetime.fromisoformat(row[7]),
        run_id=ProcessingRunId(row[8]),
        unit_execution_id=UnitExecutionId(row[9]),
        sequence=row[10],
        previous_decision_id=(
            TranscriptReviewDecisionId(row[11]) if row[11] is not None else None
        ),
        rationale=row[12],
        modified_text=row[13],
    )


def _insert_review_decision(
    connection: sqlite3.Connection, record: TranscriptReviewDecision
) -> None:
    connection.execute(
        """
        INSERT INTO transcript_review_decisions(
            identity, domain_result_id, review_item_id, candidate_reference_id,
            source_revision_id, reviewer, kind, decided_at, processing_run_id,
            unit_execution_id, sequence, previous_decision_id, rationale, modified_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.review_item_id.value,
            record.candidate_reference_id.value,
            record.source_revision_id.value,
            record.reviewer.value,
            record.kind.value,
            record.decided_at.isoformat(),
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.previous_decision_id.value if record.previous_decision_id else None,
            record.rationale,
            record.modified_text,
        ),
    )


__all__ = [
    "SQLiteReviewDecisionCommandPersistence",
    "SQLiteTranscriptReviewDecisionRepository",
]
