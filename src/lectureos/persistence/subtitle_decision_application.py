"""Insert-only SQLite persistence for canonical Subtitle Decision Revisions (041 §4.7).

Serializes one immutable next-revision aggregate together with its DomainResultReference in a single
atomic transaction. The revision is the only newly created canonical artifact; no existing artifact is
modified. Persisting it records only the applied decision's next revision and starts no downstream
capability.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleDecisionRevisionId,
    SubtitleReadingRevisionId,
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from lectureos.application.subtitle_decision_application import (
    SUBTITLE_DECISION_REVISION_RESULT_KIND,
    SubtitleAppliedOutcome,
    SubtitleDecisionRevision,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 18


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Subtitle Decision Revision persistence requires SQLite schema version 18"
        )
    return version


class SQLiteSubtitleDecisionRevisionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: SubtitleDecisionRevisionId
    ) -> SubtitleDecisionRevision | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_review_decision_id, decision_kind,
                       outcome, applied_text, review_item_id, candidate_reference_id,
                       source_preparation_id, source_validation_id, source_time_revision_id,
                       source_reading_revision_id, source_candidate_id, source_finding_id, rule,
                       target_timed_unit_id, source_transcript_id, source_revision_id,
                       source_media_id, source_timeline_id, processing_run_id, unit_execution_id,
                       sequence, reason, previous_revision_id
                FROM subtitle_decision_revisions
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_revision(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Decision Revision: {error}"
            ) from error


class SQLiteSubtitleDecisionRevisionCommandPersistence:
    """Owns one atomic v18 transaction persisting a decision revision and its Result reference."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_subtitle_decision_revision(
        self,
        *,
        revision: SubtitleDecisionRevision,
        revision_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Subtitle Decision Revision persistence requires SQLite schema version 18"
            )
        _validate_revision_linkage(revision, revision_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("subtitle_decision_revisions", revision.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Subtitle Decision Revision identity already exists"
                )
            if self._exists("domain_result_references", revision_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "subtitle decision revision Domain Result identity already exists"
                )
            _insert_revision(self._connection, revision)
            _insert_domain_result_reference_record(self._connection, revision_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Subtitle Decision Revision: {error}"
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


def _validate_revision_linkage(
    revision: SubtitleDecisionRevision,
    revision_result: DomainResultReference,
) -> None:
    if revision.domain_result_id != revision_result.identity:
        raise PersistenceError("subtitle decision revision Domain Result identity mismatch")
    if revision_result.kind != SUBTITLE_DECISION_REVISION_RESULT_KIND:
        raise PersistenceError("subtitle decision revision Domain Result kind is invalid")
    if len(revision_result.upstream_results) != 1:
        raise PersistenceError("subtitle decision revision Domain Result upstream is invalid")


def _restore_revision(row: tuple[object, ...]) -> SubtitleDecisionRevision:
    return SubtitleDecisionRevision(
        identity=SubtitleDecisionRevisionId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_review_decision_id=SubtitleReviewDecisionId(row[2]),
        decision_kind=DecisionKind(row[3]),
        outcome=SubtitleAppliedOutcome(row[4]),
        review_item_id=ReviewItemId(row[6]),
        candidate_reference_id=CandidateReferenceId(row[7]),
        source_preparation_id=SubtitleReviewPreparationId(row[8]),
        source_validation_id=SubtitleValidationId(row[9]),
        source_time_revision_id=SubtitleTimeRevisionId(row[10]),
        source_reading_revision_id=SubtitleReadingRevisionId(row[11]),
        source_candidate_id=SubtitleCandidateId(row[12]),
        source_finding_id=SubtitleValidationFindingId(row[13]),
        rule=row[14],
        source_transcript_id=TranscriptId(row[16]),
        source_revision_id=TranscriptRevisionId(row[17]),
        source_media_id=SourceMediaId(row[18]),
        source_timeline_id=SourceTimelineId(row[19]),
        run_id=ProcessingRunId(row[20]),
        unit_execution_id=UnitExecutionId(row[21]),
        sequence=row[22],
        reason=row[23],
        target_timed_unit_id=(
            SubtitleTimedUnitId(row[15]) if row[15] is not None else None
        ),
        applied_text=row[5],
        previous_revision_id=(
            SubtitleDecisionRevisionId(row[24]) if row[24] is not None else None
        ),
    )


def _insert_revision(
    connection: sqlite3.Connection, record: SubtitleDecisionRevision
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_decision_revisions(
            identity, domain_result_id, source_review_decision_id, decision_kind, outcome,
            applied_text, review_item_id, candidate_reference_id, source_preparation_id,
            source_validation_id, source_time_revision_id, source_reading_revision_id,
            source_candidate_id, source_finding_id, rule, target_timed_unit_id,
            source_transcript_id, source_revision_id, source_media_id, source_timeline_id,
            processing_run_id, unit_execution_id, sequence, reason, previous_revision_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_review_decision_id.value,
            record.decision_kind.value,
            record.outcome.value,
            record.applied_text,
            record.review_item_id.value,
            record.candidate_reference_id.value,
            record.source_preparation_id.value,
            record.source_validation_id.value,
            record.source_time_revision_id.value,
            record.source_reading_revision_id.value,
            record.source_candidate_id.value,
            record.source_finding_id.value,
            record.rule,
            record.target_timed_unit_id.value if record.target_timed_unit_id else None,
            record.source_transcript_id.value,
            record.source_revision_id.value,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.reason,
            record.previous_revision_id.value if record.previous_revision_id else None,
        ),
    )


__all__ = [
    "SQLiteSubtitleDecisionRevisionCommandPersistence",
    "SQLiteSubtitleDecisionRevisionRepository",
]
