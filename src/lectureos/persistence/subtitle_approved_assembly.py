"""Insert-only SQLite persistence for canonical Approved Subtitle Documents (044 §Export, PATCH-0006).

Serializes one immutable approved document, its ordered approved units (each with their approved lines)
and the document's DomainResultReference in a single atomic transaction. The approved document is the
only newly created canonical artifact; no existing artifact is modified. Persisting it records the
canonical Export Input and starts no downstream capability (no artifact, file, or export format).
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    SubtitleApprovedDocumentId,
    SubtitleApprovedUnitId,
    SubtitleCandidateId,
    SubtitleFinalSubtitleId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
)
from lectureos.application.subtitle_approved_assembly import (
    SUBTITLE_APPROVED_DOCUMENT_RESULT_KIND,
    SubtitleApprovedDocument,
    SubtitleApprovedUnit,
    SubtitleApprovedUnitOrigin,
    SubtitleExportEligibility,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 20


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Subtitle Approved Document persistence requires SQLite schema version 20"
        )
    return version


class SQLiteSubtitleApprovedDocumentRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: SubtitleApprovedDocumentId
    ) -> SubtitleApprovedDocument | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_time_revision_id,
                       source_reading_revision_id, eligibility, ineligibility_reason,
                       source_candidate_id, source_transcript_id, source_revision_id,
                       source_media_id, source_timeline_id, omitted_unit_count,
                       processing_run_id, unit_execution_id, sequence, reason,
                       previous_document_id
                FROM subtitle_approved_documents
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            unit_ids = tuple(
                SubtitleApprovedUnitId(value[0])
                for value in self._connection.execute(
                    """
                    SELECT identity FROM subtitle_approved_units
                    WHERE subtitle_approved_document_id = ?
                    ORDER BY ordinal
                    """,
                    (identity.value,),
                ).fetchall()
            )
            return _restore_document(row, unit_ids)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Approved Document: {error}"
            ) from error

    def get_unit(
        self, identity: SubtitleApprovedUnitId
    ) -> SubtitleApprovedUnit | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, subtitle_approved_document_id, source_timed_unit_id,
                       source_reading_unit_id, origin, display_order, start, end,
                       source_final_subtitle_id
                FROM subtitle_approved_units
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            lines = tuple(
                value[0]
                for value in self._connection.execute(
                    """
                    SELECT line FROM subtitle_approved_unit_lines
                    WHERE subtitle_approved_unit_id = ?
                    ORDER BY ordinal
                    """,
                    (identity.value,),
                ).fetchall()
            )
            return _restore_unit(row, lines)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Approved Unit: {error}"
            ) from error


class SQLiteSubtitleApprovedDocumentCommandPersistence:
    """Owns one atomic v20 transaction persisting an approved document, its units and Result."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_subtitle_approved_document(
        self,
        *,
        document: SubtitleApprovedDocument,
        units: tuple[SubtitleApprovedUnit, ...],
        document_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Subtitle Approved Document persistence requires SQLite schema version 20"
            )
        _validate_document_linkage(document, units, document_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("subtitle_approved_documents", document.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Subtitle Approved Document identity already exists"
                )
            if self._exists("domain_result_references", document_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "subtitle approved document Domain Result identity already exists"
                )
            for unit in units:
                if self._exists("subtitle_approved_units", unit.identity.value):
                    raise PersistenceIdentityCollisionError(
                        "Subtitle Approved Unit identity already exists"
                    )
            _insert_document(self._connection, document)
            for ordinal, unit in enumerate(units):
                _insert_unit(self._connection, unit, ordinal)
            _insert_domain_result_reference_record(self._connection, document_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Subtitle Approved Document: {error}"
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


def _validate_document_linkage(
    document: SubtitleApprovedDocument,
    units: tuple[SubtitleApprovedUnit, ...],
    document_result: DomainResultReference,
) -> None:
    if document.domain_result_id != document_result.identity:
        raise PersistenceError("subtitle approved document Domain Result identity mismatch")
    if document_result.kind != SUBTITLE_APPROVED_DOCUMENT_RESULT_KIND:
        raise PersistenceError("subtitle approved document Domain Result kind is invalid")
    if len(document_result.upstream_results) != 1:
        raise PersistenceError("subtitle approved document Domain Result upstream is invalid")
    if document.approved_unit_ids != tuple(unit.identity for unit in units):
        raise PersistenceError("subtitle approved document unit ordering mismatch")
    for unit in units:
        if unit.document_id != document.identity:
            raise PersistenceError("subtitle approved unit linkage mismatch")


def _restore_document(
    row: tuple[object, ...], unit_ids: tuple[SubtitleApprovedUnitId, ...]
) -> SubtitleApprovedDocument:
    return SubtitleApprovedDocument(
        identity=SubtitleApprovedDocumentId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_time_revision_id=SubtitleTimeRevisionId(row[2]),
        source_reading_revision_id=SubtitleReadingRevisionId(row[3]),
        eligibility=SubtitleExportEligibility(row[4]),
        source_candidate_id=SubtitleCandidateId(row[6]),
        source_transcript_id=TranscriptId(row[7]),
        source_revision_id=TranscriptRevisionId(row[8]),
        source_media_id=SourceMediaId(row[9]),
        source_timeline_id=SourceTimelineId(row[10]),
        approved_unit_ids=unit_ids,
        omitted_unit_count=row[11],
        run_id=ProcessingRunId(row[12]),
        unit_execution_id=UnitExecutionId(row[13]),
        sequence=row[14],
        reason=row[15],
        ineligibility_reason=row[5],
        previous_document_id=(
            SubtitleApprovedDocumentId(row[16]) if row[16] is not None else None
        ),
    )


def _restore_unit(
    row: tuple[object, ...], lines: tuple[str, ...]
) -> SubtitleApprovedUnit:
    return SubtitleApprovedUnit(
        identity=SubtitleApprovedUnitId(row[0]),
        document_id=SubtitleApprovedDocumentId(row[1]),
        source_timed_unit_id=SubtitleTimedUnitId(row[2]),
        source_reading_unit_id=SubtitleReadingUnitId(row[3]),
        origin=SubtitleApprovedUnitOrigin(row[4]),
        display_order=row[5],
        start=row[6],
        end=row[7],
        lines=lines,
        source_final_subtitle_id=(
            SubtitleFinalSubtitleId(row[8]) if row[8] is not None else None
        ),
    )


def _insert_document(
    connection: sqlite3.Connection, record: SubtitleApprovedDocument
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_approved_documents(
            identity, domain_result_id, source_time_revision_id, source_reading_revision_id,
            eligibility, ineligibility_reason, source_candidate_id, source_transcript_id,
            source_revision_id, source_media_id, source_timeline_id, omitted_unit_count,
            processing_run_id, unit_execution_id, sequence, reason, previous_document_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_time_revision_id.value,
            record.source_reading_revision_id.value,
            record.eligibility.value,
            record.ineligibility_reason,
            record.source_candidate_id.value,
            record.source_transcript_id.value,
            record.source_revision_id.value,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.omitted_unit_count,
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.reason,
            record.previous_document_id.value if record.previous_document_id else None,
        ),
    )


def _insert_unit(
    connection: sqlite3.Connection, unit: SubtitleApprovedUnit, ordinal: int
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_approved_units(
            identity, subtitle_approved_document_id, ordinal, source_timed_unit_id,
            source_reading_unit_id, origin, display_order, start, end, source_final_subtitle_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            unit.identity.value,
            unit.document_id.value,
            ordinal,
            unit.source_timed_unit_id.value,
            unit.source_reading_unit_id.value,
            unit.origin.value,
            unit.display_order,
            unit.start,
            unit.end,
            unit.source_final_subtitle_id.value if unit.source_final_subtitle_id else None,
        ),
    )
    for line_ordinal, line in enumerate(unit.lines):
        connection.execute(
            """
            INSERT INTO subtitle_approved_unit_lines(
                subtitle_approved_unit_id, ordinal, line
            ) VALUES (?, ?, ?)
            """,
            (unit.identity.value, line_ordinal, line),
        )


__all__ = [
    "SQLiteSubtitleApprovedDocumentCommandPersistence",
    "SQLiteSubtitleApprovedDocumentRepository",
]
