"""Insert-only SQLite persistence for canonical Subtitle Structural Validation records.

Serializes one immutable validation result, its ordered findings and the validation's
DomainResultReference in a single atomic transaction. Each finding records a stable ``rule``
identifier, a coarse ``category``, a ``blocking`` severity, an explanatory ``description`` and the
affected timed unit (nullable for revision-level findings). Persisting a validation records only the
diagnosis and starts no downstream capability.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleTranscriptIntakeId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.application.subtitle_structural_validation import (
    SUBTITLE_VALIDATION_RESULT_KIND,
    SubtitleValidation,
    SubtitleValidationCategory,
    SubtitleValidationFinding,
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

_REQUIRED_VERSION = 15


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Subtitle Validation persistence requires SQLite schema version 15"
        )
    return version


class SQLiteSubtitleValidationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: SubtitleValidationId) -> SubtitleValidation | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_time_revision_id,
                       source_reading_revision_id, source_candidate_id, source_intake_id,
                       source_readiness_id, source_selection_id, source_applicability_id,
                       source_decision_id, review_item_id, candidate_reference_id,
                       source_transcript_id, source_revision_id, source_media_id,
                       source_timeline_id, source_transcript_validation_id, structural_valid,
                       provenance_complete, timeline_traceable, ordering_consistent,
                       time_consistent, processing_run_id, unit_execution_id, sequence, reason,
                       previous_validation_id
                FROM subtitle_validations
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            finding_ids = tuple(
                SubtitleValidationFindingId(value[0])
                for value in self._connection.execute(
                    """
                    SELECT identity FROM subtitle_validation_findings
                    WHERE subtitle_validation_id = ?
                    ORDER BY ordinal
                    """,
                    (identity.value,),
                ).fetchall()
            )
            return _restore_validation(row, finding_ids)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Validation: {error}"
            ) from error

    def get_finding(
        self, identity: SubtitleValidationFindingId
    ) -> SubtitleValidationFinding | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, subtitle_validation_id, rule, category, blocking,
                       description, target_timed_unit_id
                FROM subtitle_validation_findings
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_finding(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Validation Finding: {error}"
            ) from error


class SQLiteSubtitleValidationCommandPersistence:
    """Owns one atomic v15 transaction persisting a validation, its findings and Result."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_subtitle_validation(
        self,
        *,
        validation: SubtitleValidation,
        findings: tuple[SubtitleValidationFinding, ...],
        validation_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Subtitle Validation persistence requires SQLite schema version 15"
            )
        _validate_validation_linkage(validation, findings, validation_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("subtitle_validations", validation.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Subtitle Validation identity already exists"
                )
            if self._exists("domain_result_references", validation_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "subtitle validation Domain Result identity already exists"
                )
            for finding in findings:
                if self._exists("subtitle_validation_findings", finding.identity.value):
                    raise PersistenceIdentityCollisionError(
                        "Subtitle Validation Finding identity already exists"
                    )
            _insert_validation(self._connection, validation)
            for ordinal, finding in enumerate(findings):
                _insert_finding(self._connection, finding, ordinal)
            _insert_domain_result_reference_record(self._connection, validation_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Subtitle Validation: {error}"
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


def _validate_validation_linkage(
    validation: SubtitleValidation,
    findings: tuple[SubtitleValidationFinding, ...],
    validation_result: DomainResultReference,
) -> None:
    if validation.domain_result_id != validation_result.identity:
        raise PersistenceError("subtitle validation Domain Result identity mismatch")
    if validation_result.kind != SUBTITLE_VALIDATION_RESULT_KIND:
        raise PersistenceError("subtitle validation Domain Result kind is invalid")
    if len(validation_result.upstream_results) != 1:
        raise PersistenceError("subtitle validation Domain Result upstream is invalid")
    if validation.finding_ids != tuple(finding.identity for finding in findings):
        raise PersistenceError("subtitle validation finding ordering mismatch")
    for finding in findings:
        if finding.validation_id != validation.identity:
            raise PersistenceError("subtitle validation finding linkage mismatch")
    # structural_valid must be consistent with the blocking findings it derives from.
    if validation.structural_valid == any(finding.blocking for finding in findings):
        raise PersistenceError(
            "subtitle validation structural_valid must equal the absence of a blocking finding"
        )


def _restore_validation(
    row: tuple[object, ...], finding_ids: tuple[SubtitleValidationFindingId, ...]
) -> SubtitleValidation:
    return SubtitleValidation(
        identity=SubtitleValidationId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_time_revision_id=SubtitleTimeRevisionId(row[2]),
        source_reading_revision_id=SubtitleReadingRevisionId(row[3]),
        source_candidate_id=SubtitleCandidateId(row[4]),
        source_intake_id=SubtitleTranscriptIntakeId(row[5]),
        source_readiness_id=TranscriptReadinessEvaluationId(row[6]),
        source_selection_id=TranscriptCurrentSelectionId(row[7]),
        source_applicability_id=TranscriptApplicabilityEvaluationId(row[8]),
        source_decision_id=TranscriptReviewDecisionId(row[9]),
        review_item_id=ReviewItemId(row[10]),
        candidate_reference_id=CandidateReferenceId(row[11]),
        source_transcript_id=TranscriptId(row[12]),
        source_revision_id=TranscriptRevisionId(row[13]),
        source_media_id=SourceMediaId(row[14]),
        source_timeline_id=SourceTimelineId(row[15]),
        source_transcript_validation_id=TranscriptValidationId(row[16]),
        structural_valid=bool(row[17]),
        provenance_complete=bool(row[18]),
        timeline_traceable=bool(row[19]),
        ordering_consistent=bool(row[20]),
        time_consistent=bool(row[21]),
        finding_ids=finding_ids,
        run_id=ProcessingRunId(row[22]),
        unit_execution_id=UnitExecutionId(row[23]),
        sequence=row[24],
        reason=row[25],
        previous_validation_id=(
            SubtitleValidationId(row[26]) if row[26] is not None else None
        ),
    )


def _restore_finding(row: tuple[object, ...]) -> SubtitleValidationFinding:
    return SubtitleValidationFinding(
        identity=SubtitleValidationFindingId(row[0]),
        validation_id=SubtitleValidationId(row[1]),
        rule=row[2],
        category=SubtitleValidationCategory(row[3]),
        blocking=bool(row[4]),
        description=row[5],
        target_timed_unit_id=(
            SubtitleTimedUnitId(row[6]) if row[6] is not None else None
        ),
    )


def _insert_validation(
    connection: sqlite3.Connection, record: SubtitleValidation
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_validations(
            identity, domain_result_id, source_time_revision_id, source_reading_revision_id,
            source_candidate_id, source_intake_id, source_readiness_id, source_selection_id,
            source_applicability_id, source_decision_id, review_item_id, candidate_reference_id,
            source_transcript_id, source_revision_id, source_media_id, source_timeline_id,
            source_transcript_validation_id, structural_valid, provenance_complete,
            timeline_traceable, ordering_consistent, time_consistent, processing_run_id,
            unit_execution_id, sequence, reason, previous_validation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_time_revision_id.value,
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
            record.source_transcript_validation_id.value,
            int(record.structural_valid),
            int(record.provenance_complete),
            int(record.timeline_traceable),
            int(record.ordering_consistent),
            int(record.time_consistent),
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.reason,
            record.previous_validation_id.value
            if record.previous_validation_id
            else None,
        ),
    )


def _insert_finding(
    connection: sqlite3.Connection, finding: SubtitleValidationFinding, ordinal: int
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_validation_findings(
            identity, subtitle_validation_id, ordinal, rule, category, blocking,
            description, target_timed_unit_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            finding.identity.value,
            finding.validation_id.value,
            ordinal,
            finding.rule,
            finding.category.value,
            int(finding.blocking),
            finding.description,
            finding.target_timed_unit_id.value
            if finding.target_timed_unit_id
            else None,
        ),
    )


__all__ = [
    "SQLiteSubtitleValidationCommandPersistence",
    "SQLiteSubtitleValidationRepository",
]
