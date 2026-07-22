"""Insert-only SQLite persistence for canonical Subtitle Reading Revision records.

Serializes one immutable reading revision, its ordered reading units (each with its ordered source
cue provenance and ordered composed lines) and the revision's DomainResultReference in a single
atomic transaction. The durable unit model stores merge (many source cues per unit) and split
(distinct units per cue) losslessly, and inherited timing metadata. Persisting a reading revision
records only the revision and starts no downstream capability.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    SubtitleCandidateCueId,
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.application.subtitle_reading_representation import (
    SUBTITLE_READING_REVISION_RESULT_KIND,
    SubtitleReadingRevision,
    SubtitleReadingUnit,
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

_REQUIRED_VERSION = 13


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Subtitle Reading persistence requires SQLite schema version 13"
        )
    return version


class SQLiteSubtitleReadingRevisionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: SubtitleReadingRevisionId
    ) -> SubtitleReadingRevision | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_candidate_id, source_intake_id,
                       source_readiness_id, source_selection_id, source_applicability_id,
                       source_decision_id, review_item_id, candidate_reference_id,
                       source_transcript_id, source_revision_id, source_media_id,
                       source_timeline_id, validation_id, processing_run_id,
                       unit_execution_id, sequence, reason, previous_reading_revision_id
                FROM subtitle_reading_revisions
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            unit_ids = tuple(
                SubtitleReadingUnitId(value[0])
                for value in self._connection.execute(
                    """
                    SELECT identity FROM subtitle_reading_units
                    WHERE subtitle_reading_revision_id = ?
                    ORDER BY ordinal
                    """,
                    (identity.value,),
                ).fetchall()
            )
            return _restore_revision(row, unit_ids)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Reading Revision: {error}"
            ) from error

    def get_unit(self, identity: SubtitleReadingUnitId) -> SubtitleReadingUnit | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, subtitle_reading_revision_id, source_transcript_id,
                       source_revision_id, source_timeline_id, display_order, start, end
                FROM subtitle_reading_units
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            source_cue_ids = tuple(
                SubtitleCandidateCueId(value[0])
                for value in self._connection.execute(
                    """
                    SELECT subtitle_candidate_cue_id FROM subtitle_reading_unit_source_cues
                    WHERE subtitle_reading_unit_id = ?
                    ORDER BY ordinal
                    """,
                    (identity.value,),
                ).fetchall()
            )
            lines = tuple(
                value[0]
                for value in self._connection.execute(
                    """
                    SELECT line FROM subtitle_reading_unit_lines
                    WHERE subtitle_reading_unit_id = ?
                    ORDER BY ordinal
                    """,
                    (identity.value,),
                ).fetchall()
            )
            return _restore_unit(row, source_cue_ids, lines)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Reading Unit: {error}"
            ) from error


class SQLiteSubtitleReadingCommandPersistence:
    """Owns one atomic v13 transaction persisting a reading revision, its units and Result."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_subtitle_reading(
        self,
        *,
        revision: SubtitleReadingRevision,
        units: tuple[SubtitleReadingUnit, ...],
        revision_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Subtitle Reading persistence requires SQLite schema version 13"
            )
        _validate_reading_linkage(revision, units, revision_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("subtitle_reading_revisions", revision.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Subtitle Reading Revision identity already exists"
                )
            if self._exists("domain_result_references", revision_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "subtitle reading Domain Result identity already exists"
                )
            for unit in units:
                if self._exists("subtitle_reading_units", unit.identity.value):
                    raise PersistenceIdentityCollisionError(
                        "Subtitle Reading Unit identity already exists"
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
                f"could not persist Subtitle Reading Revision: {error}"
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


def _validate_reading_linkage(
    revision: SubtitleReadingRevision,
    units: tuple[SubtitleReadingUnit, ...],
    revision_result: DomainResultReference,
) -> None:
    if revision.domain_result_id != revision_result.identity:
        raise PersistenceError("subtitle reading Domain Result identity mismatch")
    if revision_result.kind != SUBTITLE_READING_REVISION_RESULT_KIND:
        raise PersistenceError("subtitle reading Domain Result kind is invalid")
    if len(revision_result.upstream_results) != 1:
        raise PersistenceError("subtitle reading Domain Result upstream is invalid")
    if not units:
        raise PersistenceError("subtitle reading revision requires at least one unit")
    if revision.unit_ids != tuple(unit.identity for unit in units):
        raise PersistenceError("subtitle reading unit ordering mismatch")
    for unit in units:
        if unit.reading_revision_id != revision.identity:
            raise PersistenceError("subtitle reading unit linkage mismatch")


def _restore_revision(
    row: tuple[object, ...], unit_ids: tuple[SubtitleReadingUnitId, ...]
) -> SubtitleReadingRevision:
    return SubtitleReadingRevision(
        identity=SubtitleReadingRevisionId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_candidate_id=SubtitleCandidateId(row[2]),
        source_intake_id=SubtitleTranscriptIntakeId(row[3]),
        source_readiness_id=TranscriptReadinessEvaluationId(row[4]),
        source_selection_id=TranscriptCurrentSelectionId(row[5]),
        source_applicability_id=TranscriptApplicabilityEvaluationId(row[6]),
        source_decision_id=TranscriptReviewDecisionId(row[7]),
        review_item_id=ReviewItemId(row[8]),
        candidate_reference_id=CandidateReferenceId(row[9]),
        source_transcript_id=TranscriptId(row[10]),
        source_revision_id=TranscriptRevisionId(row[11]),
        source_media_id=SourceMediaId(row[12]),
        source_timeline_id=SourceTimelineId(row[13]),
        validation_id=TranscriptValidationId(row[14]),
        unit_ids=unit_ids,
        run_id=ProcessingRunId(row[15]),
        unit_execution_id=UnitExecutionId(row[16]),
        sequence=row[17],
        reason=row[18],
        previous_reading_revision_id=(
            SubtitleReadingRevisionId(row[19]) if row[19] is not None else None
        ),
    )


def _restore_unit(
    row: tuple[object, ...],
    source_cue_ids: tuple[SubtitleCandidateCueId, ...],
    lines: tuple[str, ...],
) -> SubtitleReadingUnit:
    return SubtitleReadingUnit(
        identity=SubtitleReadingUnitId(row[0]),
        reading_revision_id=SubtitleReadingRevisionId(row[1]),
        source_cue_ids=source_cue_ids,
        source_transcript_id=TranscriptId(row[2]),
        source_revision_id=TranscriptRevisionId(row[3]),
        lines=lines,
        display_order=row[5],
        source_timeline_id=(
            SourceTimelineId(row[4]) if row[4] is not None else None
        ),
        start=row[6],
        end=row[7],
    )


def _insert_revision(
    connection: sqlite3.Connection, record: SubtitleReadingRevision
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_reading_revisions(
            identity, domain_result_id, source_candidate_id, source_intake_id,
            source_readiness_id, source_selection_id, source_applicability_id,
            source_decision_id, review_item_id, candidate_reference_id,
            source_transcript_id, source_revision_id, source_media_id, source_timeline_id,
            validation_id, processing_run_id, unit_execution_id, sequence, reason,
            previous_reading_revision_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
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
            record.previous_reading_revision_id.value
            if record.previous_reading_revision_id
            else None,
        ),
    )


def _insert_unit(
    connection: sqlite3.Connection, unit: SubtitleReadingUnit, ordinal: int
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_reading_units(
            identity, subtitle_reading_revision_id, ordinal, source_transcript_id,
            source_revision_id, source_timeline_id, display_order, start, end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            unit.identity.value,
            unit.reading_revision_id.value,
            ordinal,
            unit.source_transcript_id.value,
            unit.source_revision_id.value,
            unit.source_timeline_id.value if unit.source_timeline_id else None,
            unit.display_order,
            unit.start,
            unit.end,
        ),
    )
    for cue_ordinal, cue_id in enumerate(unit.source_cue_ids):
        connection.execute(
            """
            INSERT INTO subtitle_reading_unit_source_cues(
                subtitle_reading_unit_id, ordinal, subtitle_candidate_cue_id
            ) VALUES (?, ?, ?)
            """,
            (unit.identity.value, cue_ordinal, cue_id.value),
        )
    for line_ordinal, line in enumerate(unit.lines):
        connection.execute(
            """
            INSERT INTO subtitle_reading_unit_lines(
                subtitle_reading_unit_id, ordinal, line
            ) VALUES (?, ?, ?)
            """,
            (unit.identity.value, line_ordinal, line),
        )


__all__ = [
    "SQLiteSubtitleReadingCommandPersistence",
    "SQLiteSubtitleReadingRevisionRepository",
]
