"""Insert-only SQLite persistence for canonical Subtitle Human Review Decisions.

Serializes one immutable decision aggregate together with its DomainResultReference in a single atomic
transaction. The decision timestamp is stored verbatim from the caller-supplied value so that
reconstruction and deterministic replay are exact. No decision automation or downstream state is
persisted — the decision is recorded, never applied.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from lectureos.application.identities import (
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimeRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from lectureos.application.subtitle_review_decision import (
    SUBTITLE_REVIEW_DECISION_RESULT_KIND,
    SubtitleReviewDecision,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.review.identities import (
    CandidateReferenceId,
    HumanActorReference,
    ReviewItemId,
)
from lectureos.review.models import DecisionKind

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 17


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Subtitle Review Decision persistence requires SQLite schema version 17"
        )
    return version


class SQLiteSubtitleReviewDecisionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: SubtitleReviewDecisionId
    ) -> SubtitleReviewDecision | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, review_item_id, candidate_reference_id,
                       source_preparation_id, source_validation_id, source_time_revision_id,
                       source_finding_id, rule, reviewer, kind, decided_at, processing_run_id,
                       unit_execution_id, sequence, previous_decision_id, rationale,
                       modified_text
                FROM subtitle_review_decisions
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_decision(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Review Decision: {error}"
            ) from error


class SQLiteSubtitleReviewDecisionCommandPersistence:
    """Owns one atomic v17 transaction persisting a decision and its Result reference."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_subtitle_review_decision(
        self,
        *,
        decision: SubtitleReviewDecision,
        decision_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Subtitle Review Decision persistence requires SQLite schema version 17"
            )
        _validate_decision_linkage(decision, decision_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("subtitle_review_decisions", decision.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Subtitle Review Decision identity already exists"
                )
            if self._exists("domain_result_references", decision_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "subtitle review decision Domain Result identity already exists"
                )
            _insert_decision(self._connection, decision)
            _insert_domain_result_reference_record(self._connection, decision_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Subtitle Review Decision: {error}"
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
    decision: SubtitleReviewDecision,
    decision_result: DomainResultReference,
) -> None:
    if decision.domain_result_id != decision_result.identity:
        raise PersistenceError("subtitle review decision Domain Result identity mismatch")
    if decision_result.kind != SUBTITLE_REVIEW_DECISION_RESULT_KIND:
        raise PersistenceError("subtitle review decision Domain Result kind is invalid")
    if len(decision_result.upstream_results) != 1:
        raise PersistenceError("subtitle review decision Domain Result upstream is invalid")


def _restore_decision(row: tuple[object, ...]) -> SubtitleReviewDecision:
    return SubtitleReviewDecision(
        identity=SubtitleReviewDecisionId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        review_item_id=ReviewItemId(row[2]),
        candidate_reference_id=CandidateReferenceId(row[3]),
        source_preparation_id=SubtitleReviewPreparationId(row[4]),
        source_validation_id=SubtitleValidationId(row[5]),
        source_time_revision_id=SubtitleTimeRevisionId(row[6]),
        source_finding_id=SubtitleValidationFindingId(row[7]),
        rule=row[8],
        reviewer=HumanActorReference(row[9]),
        kind=DecisionKind(row[10]),
        decided_at=datetime.fromisoformat(row[11]),
        run_id=ProcessingRunId(row[12]),
        unit_execution_id=UnitExecutionId(row[13]),
        sequence=row[14],
        previous_decision_id=(
            SubtitleReviewDecisionId(row[15]) if row[15] is not None else None
        ),
        rationale=row[16],
        modified_text=row[17],
    )


def _insert_decision(
    connection: sqlite3.Connection, record: SubtitleReviewDecision
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_review_decisions(
            identity, domain_result_id, review_item_id, candidate_reference_id,
            source_preparation_id, source_validation_id, source_time_revision_id,
            source_finding_id, rule, reviewer, kind, decided_at, processing_run_id,
            unit_execution_id, sequence, previous_decision_id, rationale, modified_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.review_item_id.value,
            record.candidate_reference_id.value,
            record.source_preparation_id.value,
            record.source_validation_id.value,
            record.source_time_revision_id.value,
            record.source_finding_id.value,
            record.rule,
            record.reviewer.value,
            record.kind.value,
            record.decided_at.isoformat(),
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.previous_decision_id.value
            if record.previous_decision_id
            else None,
            record.rationale,
            record.modified_text,
        ),
    )


__all__ = [
    "SQLiteSubtitleReviewDecisionCommandPersistence",
    "SQLiteSubtitleReviewDecisionRepository",
]
