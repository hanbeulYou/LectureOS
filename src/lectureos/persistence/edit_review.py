"""Insert-only SQLite persistence for the Edit-Pipeline Review Application Foundation (043 §7.4).

Serializes one immutable human Review admission — an EditReviewDecision and, for accept/modify, one
ApprovedEditDecision — together with their DomainResultReferences in a single atomic transaction. Reject
persists only the decision. The records are a deterministic derivation from a canonical Edit Candidate;
persisting them records only the review outcome and starts no downstream capability.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.edit_review import (
    APPROVED_EDIT_DECISION_RESULT_KIND,
    EDIT_REVIEW_DECISION_RESULT_KIND,
    ApprovedEditDecision,
    EditReviewDecision,
    EditReviewDecisionKind,
    PreparedEditReview,
)
from lectureos.application.identities import (
    ApprovedEditDecisionId,
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

_REQUIRED_VERSION = 27


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Edit Review persistence requires SQLite schema version 27"
        )
    return version


class SQLiteEditReviewDecisionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: EditReviewDecisionId) -> EditReviewDecision | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_candidate_id, decision_kind,
                       actor, source_media_id, source_timeline_id, processing_run_id,
                       unit_execution_id, sequence
                FROM edit_review_decisions
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_decision(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Edit Review Decision: {error}"
            ) from error


class SQLiteApprovedEditDecisionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: ApprovedEditDecisionId) -> ApprovedEditDecision | None:
        return self._fetch("identity = ?", identity.value)

    def get_for_decision(
        self, decision_id: EditReviewDecisionId
    ) -> ApprovedEditDecision | None:
        return self._fetch("source_decision_id = ?", decision_id.value)

    def _fetch(self, predicate: str, value: str) -> ApprovedEditDecision | None:
        try:
            row = self._connection.execute(
                f"""
                SELECT identity, domain_result_id, source_decision_id, source_candidate_id,
                       decision_kind, approved_range_start, approved_range_end,
                       approved_candidate_type, approved_rationale, source_media_id,
                       source_timeline_id, processing_run_id, unit_execution_id, sequence
                FROM approved_edit_decisions
                WHERE {predicate}
                """,
                (value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_approved(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Approved Edit Decision: {error}"
            ) from error


class SQLiteEditReviewCommandPersistence:
    """Owns one atomic v27 transaction persisting a Review admission and its Result references."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_edit_review(self, *, prepared: PreparedEditReview) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Edit Review persistence requires SQLite schema version 27"
            )
        _validate_review_linkage(prepared)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("edit_review_decisions", prepared.decision.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Edit Review Decision identity already exists"
                )
            if self._exists(
                "domain_result_references", prepared.decision_result.identity.value
            ):
                raise PersistenceIdentityCollisionError(
                    "edit review decision Domain Result identity already exists"
                )
            if prepared.approved is not None:
                if self._exists(
                    "approved_edit_decisions", prepared.approved.identity.value
                ):
                    raise PersistenceIdentityCollisionError(
                        "Approved Edit Decision identity already exists"
                    )
                if self._exists(
                    "domain_result_references", prepared.approved_result.identity.value
                ):
                    raise PersistenceIdentityCollisionError(
                        "approved edit decision Domain Result identity already exists"
                    )
            _insert_decision(self._connection, prepared.decision)
            _insert_domain_result_reference_record(
                self._connection, prepared.decision_result
            )
            if prepared.approved is not None:
                _insert_approved(self._connection, prepared.approved)
                _insert_domain_result_reference_record(
                    self._connection, prepared.approved_result
                )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Edit Review Decision: {error}"
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


def _validate_review_linkage(prepared: PreparedEditReview) -> None:
    decision = prepared.decision
    if decision.domain_result_id != prepared.decision_result.identity:
        raise PersistenceError("edit review decision Domain Result identity mismatch")
    if prepared.decision_result.kind != EDIT_REVIEW_DECISION_RESULT_KIND:
        raise PersistenceError("edit review decision Domain Result kind is invalid")
    if len(prepared.decision_result.upstream_results) != 1:
        raise PersistenceError("edit review decision Domain Result upstream is invalid")
    approving = decision.decision_kind in (
        EditReviewDecisionKind.ACCEPT,
        EditReviewDecisionKind.MODIFY,
    )
    if approving != (prepared.approved is not None):
        raise PersistenceError(
            "accept/modify require an approved record; reject requires none"
        )
    if prepared.approved is not None:
        approved = prepared.approved
        if approved.domain_result_id != prepared.approved_result.identity:
            raise PersistenceError("approved edit decision Domain Result identity mismatch")
        if prepared.approved_result.kind != APPROVED_EDIT_DECISION_RESULT_KIND:
            raise PersistenceError("approved edit decision Domain Result kind is invalid")
        if prepared.approved_result.upstream_results != (decision.domain_result_id,):
            raise PersistenceError(
                "approved edit decision Domain Result upstream must be the review decision"
            )
        if approved.source_decision_id != decision.identity:
            raise PersistenceError("approved edit decision must reference its review decision")


def _restore_decision(row: tuple[object, ...]) -> EditReviewDecision:
    return EditReviewDecision(
        identity=EditReviewDecisionId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_candidate_id=EditCandidateId(row[2]),
        decision_kind=EditReviewDecisionKind(row[3]),
        actor=HumanActorReference(row[4]),
        source_media_id=SourceMediaId(row[5]),
        source_timeline_id=SourceTimelineId(row[6]),
        run_id=ProcessingRunId(row[7]),
        unit_execution_id=UnitExecutionId(row[8]),
        sequence=row[9],
    )


def _restore_approved(row: tuple[object, ...]) -> ApprovedEditDecision:
    return ApprovedEditDecision(
        identity=ApprovedEditDecisionId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_decision_id=EditReviewDecisionId(row[2]),
        source_candidate_id=EditCandidateId(row[3]),
        decision_kind=EditReviewDecisionKind(row[4]),
        approved_range_start=row[5],
        approved_range_end=row[6],
        approved_candidate_type=row[7],
        approved_rationale=row[8],
        source_media_id=SourceMediaId(row[9]),
        source_timeline_id=SourceTimelineId(row[10]),
        run_id=ProcessingRunId(row[11]),
        unit_execution_id=UnitExecutionId(row[12]),
        sequence=row[13],
    )


def _insert_decision(connection: sqlite3.Connection, record: EditReviewDecision) -> None:
    connection.execute(
        """
        INSERT INTO edit_review_decisions(
            identity, domain_result_id, source_candidate_id, decision_kind, actor,
            source_media_id, source_timeline_id, processing_run_id, unit_execution_id,
            sequence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_candidate_id.value,
            record.decision_kind.value,
            record.actor.value,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
        ),
    )


def _insert_approved(connection: sqlite3.Connection, record: ApprovedEditDecision) -> None:
    connection.execute(
        """
        INSERT INTO approved_edit_decisions(
            identity, domain_result_id, source_decision_id, source_candidate_id,
            decision_kind, approved_range_start, approved_range_end,
            approved_candidate_type, approved_rationale, source_media_id,
            source_timeline_id, processing_run_id, unit_execution_id, sequence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_decision_id.value,
            record.source_candidate_id.value,
            record.decision_kind.value,
            record.approved_range_start,
            record.approved_range_end,
            record.approved_candidate_type,
            record.approved_rationale,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
        ),
    )


__all__ = [
    "SQLiteApprovedEditDecisionRepository",
    "SQLiteEditReviewCommandPersistence",
    "SQLiteEditReviewDecisionRepository",
]
