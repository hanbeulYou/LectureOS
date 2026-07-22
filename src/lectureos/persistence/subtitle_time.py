"""Insert-only SQLite persistence for canonical Subtitle Time Revision records.

Serializes one immutable time revision, its ordered timed units and the revision's
DomainResultReference in a single atomic transaction. Each timed unit records a Source-Timeline
anchored display Time Range (status ``anchored``) or an explicit ``unresolved`` state with no range.
Persisting a time revision records only the revision and starts no downstream capability.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.application.subtitle_time_representation import (
    SUBTITLE_TIME_REVISION_RESULT_KIND,
    SubtitleTimeRevision,
    SubtitleTimedUnit,
    SubtitleTimingStatus,
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
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptValidationId,
)

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 14


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Subtitle Time persistence requires SQLite schema version 14"
        )
    return version


class SQLiteSubtitleTimeRevisionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: SubtitleTimeRevisionId) -> SubtitleTimeRevision | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_reading_revision_id,
                       source_candidate_id, source_intake_id, source_readiness_id,
                       source_selection_id, source_applicability_id, source_decision_id,
                       review_item_id, candidate_reference_id, source_transcript_id,
                       source_revision_id, source_media_id, source_timeline_id, validation_id,
                       processing_run_id, unit_execution_id, sequence, reason,
                       previous_time_revision_id
                FROM subtitle_time_revisions
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            unit_ids = tuple(
                SubtitleTimedUnitId(value[0])
                for value in self._connection.execute(
                    """
                    SELECT identity FROM subtitle_timed_units
                    WHERE subtitle_time_revision_id = ?
                    ORDER BY ordinal
                    """,
                    (identity.value,),
                ).fetchall()
            )
            return _restore_revision(row, unit_ids)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Time Revision: {error}"
            ) from error

    def get_unit(self, identity: SubtitleTimedUnitId) -> SubtitleTimedUnit | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, subtitle_time_revision_id, source_reading_unit_id,
                       timing_status, source_timeline_id, display_order, start, end
                FROM subtitle_timed_units
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_unit(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Timed Unit: {error}"
            ) from error


class SQLiteSubtitleTimeCommandPersistence:
    """Owns one atomic v14 transaction persisting a time revision, its units and Result."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_subtitle_timing(
        self,
        *,
        revision: SubtitleTimeRevision,
        units: tuple[SubtitleTimedUnit, ...],
        revision_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Subtitle Time persistence requires SQLite schema version 14"
            )
        _validate_timing_linkage(revision, units, revision_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("subtitle_time_revisions", revision.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Subtitle Time Revision identity already exists"
                )
            if self._exists("domain_result_references", revision_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "subtitle time Domain Result identity already exists"
                )
            for unit in units:
                if self._exists("subtitle_timed_units", unit.identity.value):
                    raise PersistenceIdentityCollisionError(
                        "Subtitle Timed Unit identity already exists"
                    )
            _insert_revision(self._connection, revision)
            for ordinal, unit in enumerate(units):
                _insert_unit(self._connection, unit, ordinal)
            _insert_domain_result_reference_record(self._connection, revision_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Subtitle Time Revision: {error}"
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


def _validate_timing_linkage(
    revision: SubtitleTimeRevision,
    units: tuple[SubtitleTimedUnit, ...],
    revision_result: DomainResultReference,
) -> None:
    if revision.domain_result_id != revision_result.identity:
        raise PersistenceError("subtitle time Domain Result identity mismatch")
    if revision_result.kind != SUBTITLE_TIME_REVISION_RESULT_KIND:
        raise PersistenceError("subtitle time Domain Result kind is invalid")
    if len(revision_result.upstream_results) != 1:
        raise PersistenceError("subtitle time Domain Result upstream is invalid")
    if not units:
        raise PersistenceError("subtitle time revision requires at least one unit")
    if revision.timed_unit_ids != tuple(unit.identity for unit in units):
        raise PersistenceError("subtitle timed unit ordering mismatch")
    for unit in units:
        if unit.time_revision_id != revision.identity:
            raise PersistenceError("subtitle timed unit linkage mismatch")


def _restore_revision(
    row: tuple[object, ...], unit_ids: tuple[SubtitleTimedUnitId, ...]
) -> SubtitleTimeRevision:
    return SubtitleTimeRevision(
        identity=SubtitleTimeRevisionId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_reading_revision_id=SubtitleReadingRevisionId(row[2]),
        source_candidate_id=SubtitleCandidateId(row[3]),
        source_intake_id=SubtitleTranscriptIntakeId(row[4]),
        source_readiness_id=TranscriptReadinessEvaluationId(row[5]),
        source_selection_id=TranscriptCurrentSelectionId(row[6]),
        source_applicability_id=TranscriptApplicabilityEvaluationId(row[7]),
        source_decision_id=TranscriptReviewDecisionId(row[8]),
        review_item_id=ReviewItemId(row[9]),
        candidate_reference_id=CandidateReferenceId(row[10]),
        source_transcript_id=TranscriptId(row[11]),
        source_revision_id=TranscriptRevisionId(row[12]),
        source_media_id=SourceMediaId(row[13]),
        source_timeline_id=SourceTimelineId(row[14]),
        validation_id=TranscriptValidationId(row[15]),
        timed_unit_ids=unit_ids,
        run_id=ProcessingRunId(row[16]),
        unit_execution_id=UnitExecutionId(row[17]),
        sequence=row[18],
        reason=row[19],
        previous_time_revision_id=(
            SubtitleTimeRevisionId(row[20]) if row[20] is not None else None
        ),
    )


def _restore_unit(row: tuple[object, ...]) -> SubtitleTimedUnit:
    return SubtitleTimedUnit(
        identity=SubtitleTimedUnitId(row[0]),
        time_revision_id=SubtitleTimeRevisionId(row[1]),
        source_reading_unit_id=SubtitleReadingUnitId(row[2]),
        display_order=row[5],
        timing_status=SubtitleTimingStatus(row[3]),
        source_timeline_id=(
            SourceTimelineId(row[4]) if row[4] is not None else None
        ),
        start=row[6],
        end=row[7],
    )


def _insert_revision(
    connection: sqlite3.Connection, record: SubtitleTimeRevision
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_time_revisions(
            identity, domain_result_id, source_reading_revision_id, source_candidate_id,
            source_intake_id, source_readiness_id, source_selection_id,
            source_applicability_id, source_decision_id, review_item_id,
            candidate_reference_id, source_transcript_id, source_revision_id,
            source_media_id, source_timeline_id, validation_id, processing_run_id,
            unit_execution_id, sequence, reason, previous_time_revision_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_reading_revision_id.value,
            record.source_candidate_id.value,
            record.source_intake_id.value,
            record.source_readiness_id.value,
            record.source_selection_id.value,
            record.source_applicability_id.value,
            record.source_decision_id.value,
            record.review_item_id.value,
            record.candidate_reference_id.value,
            record.source_transcript_id.value,
            record.source_revision_id.value,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.validation_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.reason,
            record.previous_time_revision_id.value
            if record.previous_time_revision_id
            else None,
        ),
    )


def _insert_unit(
    connection: sqlite3.Connection, unit: SubtitleTimedUnit, ordinal: int
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_timed_units(
            identity, subtitle_time_revision_id, ordinal, source_reading_unit_id,
            timing_status, source_timeline_id, display_order, start, end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            unit.identity.value,
            unit.time_revision_id.value,
            ordinal,
            unit.source_reading_unit_id.value,
            unit.timing_status.value,
            unit.source_timeline_id.value if unit.source_timeline_id else None,
            unit.display_order,
            unit.start,
            unit.end,
        ),
    )


__all__ = [
    "SQLiteSubtitleTimeCommandPersistence",
    "SQLiteSubtitleTimeRevisionRepository",
]
