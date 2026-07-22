"""Insert-only SQLite persistence for canonical Subtitle Final Subtitles (041 §4.8).

Serializes one immutable Final Subtitle selection together with its DomainResultReference in a single
atomic transaction. The Final Subtitle is the only newly created canonical artifact; no existing artifact
is modified. Persisting it distinguishes the authoritative subtitle representation and starts no
downstream capability.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleDecisionRevisionId,
    SubtitleFinalSubtitleId,
    SubtitleReadingRevisionId,
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from lectureos.application.subtitle_decision_application import SubtitleAppliedOutcome
from lectureos.application.subtitle_final_subtitle import (
    SUBTITLE_FINAL_SUBTITLE_RESULT_KIND,
    SubtitleFinalOutcome,
    SubtitleFinalSubtitle,
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

_REQUIRED_VERSION = 19


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Subtitle Final Subtitle persistence requires SQLite schema version 19"
        )
    return version


class SQLiteSubtitleFinalSubtitleRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: SubtitleFinalSubtitleId) -> SubtitleFinalSubtitle | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_decision_revision_id, decision_kind,
                       applied_outcome, final_outcome, applied_text, source_review_decision_id,
                       review_item_id, candidate_reference_id, source_preparation_id,
                       source_validation_id, source_time_revision_id, source_reading_revision_id,
                       source_candidate_id, source_finding_id, rule, target_timed_unit_id,
                       source_transcript_id, source_revision_id, source_media_id, source_timeline_id,
                       processing_run_id, unit_execution_id, sequence, reason, previous_final_id
                FROM subtitle_final_subtitles
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_final(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Final Subtitle: {error}"
            ) from error

    def list_for_time_revision(
        self, identity: SubtitleTimeRevisionId
    ) -> tuple[SubtitleFinalSubtitle, ...]:
        """All finalized decisions for one subtitle document, ordered by append sequence."""

        try:
            rows = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_decision_revision_id, decision_kind,
                       applied_outcome, final_outcome, applied_text, source_review_decision_id,
                       review_item_id, candidate_reference_id, source_preparation_id,
                       source_validation_id, source_time_revision_id, source_reading_revision_id,
                       source_candidate_id, source_finding_id, rule, target_timed_unit_id,
                       source_transcript_id, source_revision_id, source_media_id, source_timeline_id,
                       processing_run_id, unit_execution_id, sequence, reason, previous_final_id
                FROM subtitle_final_subtitles
                WHERE source_time_revision_id = ?
                ORDER BY sequence, identity
                """,
                (identity.value,),
            ).fetchall()
            return tuple(_restore_final(row) for row in rows)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Final Subtitles: {error}"
            ) from error


class SQLiteSubtitleFinalSubtitleCommandPersistence:
    """Owns one atomic v19 transaction persisting a Final Subtitle and its Result reference."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_subtitle_final_subtitle(
        self,
        *,
        final: SubtitleFinalSubtitle,
        final_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Subtitle Final Subtitle persistence requires SQLite schema version 19"
            )
        _validate_final_linkage(final, final_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("subtitle_final_subtitles", final.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Subtitle Final Subtitle identity already exists"
                )
            if self._exists("domain_result_references", final_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "subtitle final subtitle Domain Result identity already exists"
                )
            _insert_final(self._connection, final)
            _insert_domain_result_reference_record(self._connection, final_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Subtitle Final Subtitle: {error}"
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


def _validate_final_linkage(
    final: SubtitleFinalSubtitle,
    final_result: DomainResultReference,
) -> None:
    if final.domain_result_id != final_result.identity:
        raise PersistenceError("subtitle final subtitle Domain Result identity mismatch")
    if final_result.kind != SUBTITLE_FINAL_SUBTITLE_RESULT_KIND:
        raise PersistenceError("subtitle final subtitle Domain Result kind is invalid")
    if len(final_result.upstream_results) != 1:
        raise PersistenceError("subtitle final subtitle Domain Result upstream is invalid")


def _restore_final(row: tuple[object, ...]) -> SubtitleFinalSubtitle:
    return SubtitleFinalSubtitle(
        identity=SubtitleFinalSubtitleId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_decision_revision_id=SubtitleDecisionRevisionId(row[2]),
        decision_kind=DecisionKind(row[3]),
        applied_outcome=SubtitleAppliedOutcome(row[4]),
        final_outcome=SubtitleFinalOutcome(row[5]),
        source_review_decision_id=SubtitleReviewDecisionId(row[7]),
        review_item_id=ReviewItemId(row[8]),
        candidate_reference_id=CandidateReferenceId(row[9]),
        source_preparation_id=SubtitleReviewPreparationId(row[10]),
        source_validation_id=SubtitleValidationId(row[11]),
        source_time_revision_id=SubtitleTimeRevisionId(row[12]),
        source_reading_revision_id=SubtitleReadingRevisionId(row[13]),
        source_candidate_id=SubtitleCandidateId(row[14]),
        source_finding_id=SubtitleValidationFindingId(row[15]),
        rule=row[16],
        source_transcript_id=TranscriptId(row[18]),
        source_revision_id=TranscriptRevisionId(row[19]),
        source_media_id=SourceMediaId(row[20]),
        source_timeline_id=SourceTimelineId(row[21]),
        run_id=ProcessingRunId(row[22]),
        unit_execution_id=UnitExecutionId(row[23]),
        sequence=row[24],
        reason=row[25],
        target_timed_unit_id=(
            SubtitleTimedUnitId(row[17]) if row[17] is not None else None
        ),
        applied_text=row[6],
        previous_final_id=(
            SubtitleFinalSubtitleId(row[26]) if row[26] is not None else None
        ),
    )


def _insert_final(connection: sqlite3.Connection, record: SubtitleFinalSubtitle) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_final_subtitles(
            identity, domain_result_id, source_decision_revision_id, decision_kind,
            applied_outcome, final_outcome, applied_text, source_review_decision_id,
            review_item_id, candidate_reference_id, source_preparation_id, source_validation_id,
            source_time_revision_id, source_reading_revision_id, source_candidate_id,
            source_finding_id, rule, target_timed_unit_id, source_transcript_id, source_revision_id,
            source_media_id, source_timeline_id, processing_run_id, unit_execution_id, sequence,
            reason, previous_final_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_decision_revision_id.value,
            record.decision_kind.value,
            record.applied_outcome.value,
            record.final_outcome.value,
            record.applied_text,
            record.source_review_decision_id.value,
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
            record.previous_final_id.value if record.previous_final_id else None,
        ),
    )


__all__ = [
    "SQLiteSubtitleFinalSubtitleCommandPersistence",
    "SQLiteSubtitleFinalSubtitleRepository",
]
