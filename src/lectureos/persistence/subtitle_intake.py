"""Insert-only SQLite persistence for canonical Subtitle Transcript Intake records.

Serializes one immutable intake aggregate together with its DomainResultReference in a single
atomic transaction. Intake is a deterministic derivation from a canonical Readiness Evaluation;
persisting it records only the intake and starts no downstream capability.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.application.subtitle_transcript_intake import (
    SUBTITLE_TRANSCRIPT_INTAKE_RESULT_KIND,
    SubtitleIntakeOutcome,
    SubtitleTranscriptIntake,
)
from lectureos.application.transcript_readiness_evaluation import ReadinessOutcome
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

_REQUIRED_VERSION = 11


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Subtitle Transcript Intake persistence requires SQLite schema version 11"
        )
    return version


class SQLiteSubtitleTranscriptIntakeRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: SubtitleTranscriptIntakeId
    ) -> SubtitleTranscriptIntake | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_readiness_id, readiness_outcome,
                       outcome, source_selection_id, source_applicability_id,
                       source_decision_id, review_item_id, candidate_reference_id,
                       source_transcript_id, source_revision_id, source_media_id,
                       source_timeline_id, validation_id, processing_run_id,
                       unit_execution_id, sequence, reason, previous_intake_id
                FROM subtitle_transcript_intakes
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_intake(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Transcript Intake: {error}"
            ) from error

    def save(self, record: SubtitleTranscriptIntake) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                "Subtitle Transcript Intake identity already exists"
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _insert_subtitle_intake(self._connection, record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "Subtitle Transcript Intake identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist Subtitle Transcript Intake: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(
                f"could not persist Subtitle Transcript Intake: {error}"
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


class SQLiteSubtitleIntakeCommandPersistence:
    """Owns one atomic v11 transaction persisting an intake and its Result reference."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_subtitle_intake(
        self,
        *,
        intake: SubtitleTranscriptIntake,
        intake_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Subtitle Transcript Intake persistence requires SQLite schema version 11"
            )
        _validate_intake_linkage(intake, intake_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("subtitle_transcript_intakes", intake.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Subtitle Transcript Intake identity already exists"
                )
            if self._exists("domain_result_references", intake_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "subtitle intake Domain Result identity already exists"
                )
            _insert_subtitle_intake(self._connection, intake)
            _insert_domain_result_reference_record(self._connection, intake_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Subtitle Transcript Intake: {error}"
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


def _validate_intake_linkage(
    intake: SubtitleTranscriptIntake,
    intake_result: DomainResultReference,
) -> None:
    if intake.domain_result_id != intake_result.identity:
        raise PersistenceError("subtitle intake Domain Result identity mismatch")
    if intake_result.kind != SUBTITLE_TRANSCRIPT_INTAKE_RESULT_KIND:
        raise PersistenceError("subtitle intake Domain Result kind is invalid")
    if len(intake_result.upstream_results) != 1:
        raise PersistenceError("subtitle intake Domain Result upstream is invalid")


def _restore_intake(row: tuple[object, ...]) -> SubtitleTranscriptIntake:
    return SubtitleTranscriptIntake(
        identity=SubtitleTranscriptIntakeId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_readiness_id=TranscriptReadinessEvaluationId(row[2]),
        readiness_outcome=ReadinessOutcome(row[3]),
        outcome=SubtitleIntakeOutcome(row[4]),
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
        run_id=ProcessingRunId(row[15]),
        unit_execution_id=UnitExecutionId(row[16]),
        sequence=row[17],
        reason=row[18],
        previous_intake_id=(
            SubtitleTranscriptIntakeId(row[19]) if row[19] is not None else None
        ),
    )


def _insert_subtitle_intake(
    connection: sqlite3.Connection, record: SubtitleTranscriptIntake
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_transcript_intakes(
            identity, domain_result_id, source_readiness_id, readiness_outcome, outcome,
            source_selection_id, source_applicability_id, source_decision_id,
            review_item_id, candidate_reference_id, source_transcript_id,
            source_revision_id, source_media_id, source_timeline_id, validation_id,
            processing_run_id, unit_execution_id, sequence, reason, previous_intake_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_readiness_id.value,
            record.readiness_outcome.value,
            record.outcome.value,
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
            record.previous_intake_id.value if record.previous_intake_id else None,
        ),
    )


__all__ = [
    "SQLiteSubtitleIntakeCommandPersistence",
    "SQLiteSubtitleTranscriptIntakeRepository",
]
