"""Insert-only SQLite persistence for canonical Subtitle Review Preparation records.

Serializes one immutable `SubtitleReviewPreparation`, the common Review records it materializes
(one `CandidateReference` + one open `ReviewItem` per finding, and a shared `ReviewContext`) and the
preparation's DomainResultReference in a single atomic transaction. The common Review records are
written to the shared review tables via the common insert helpers (no duplication of the common Review
lifecycle); a clean validation persists an empty preparation (parent + context + Domain Result only).
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleReviewPreparationId,
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
from lectureos.application.subtitle_review_preparation import (
    SUBTITLE_REVIEW_PREPARATION_RESULT_KIND,
    SubtitleReviewItemLink,
    SubtitleReviewPreparation,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.review.identities import (
    CandidateReferenceId,
    ReviewContextId,
    ReviewItemId,
)
from lectureos.review.models import CandidateReference, ReviewContext, ReviewItem
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
from .review_preparation import (
    _insert_candidate_reference,
    _insert_review_context,
    _insert_review_item,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 16


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Subtitle Review Preparation persistence requires SQLite schema version 16"
        )
    return version


class SQLiteSubtitleReviewPreparationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: SubtitleReviewPreparationId
    ) -> SubtitleReviewPreparation | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_validation_id,
                       source_time_revision_id, source_reading_revision_id, source_candidate_id,
                       source_intake_id, source_readiness_id, source_selection_id,
                       source_applicability_id, source_decision_id, source_review_item_id,
                       source_candidate_reference_id, source_transcript_id, source_revision_id,
                       source_media_id, source_timeline_id, source_transcript_validation_id,
                       context_id, item_count, source_structural_valid, provenance_complete,
                       processing_run_id, unit_execution_id, sequence, reason,
                       previous_preparation_id
                FROM subtitle_review_preparations
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            item_links = tuple(
                SubtitleReviewItemLink(
                    review_item_id=ReviewItemId(value[0]),
                    candidate_reference_id=CandidateReferenceId(value[1]),
                    source_finding_id=SubtitleValidationFindingId(value[2]),
                    rule=value[3],
                    target_timed_unit_id=(
                        SubtitleTimedUnitId(value[4]) if value[4] is not None else None
                    ),
                )
                for value in self._connection.execute(
                    """
                    SELECT review_item_id, candidate_reference_id, source_finding_id, rule,
                           target_timed_unit_id
                    FROM subtitle_review_preparation_items
                    WHERE subtitle_review_preparation_id = ?
                    ORDER BY ordinal
                    """,
                    (identity.value,),
                ).fetchall()
            )
            return _restore_preparation(row, item_links)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Review Preparation: {error}"
            ) from error


class SQLiteSubtitleReviewPreparationCommandPersistence:
    """Owns one atomic v16 transaction persisting a preparation and its common Review records."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_subtitle_review_preparation(
        self,
        *,
        preparation: SubtitleReviewPreparation,
        preparation_result: DomainResultReference,
        context: ReviewContext,
        candidate_references: tuple[CandidateReference, ...],
        review_items: tuple[ReviewItem, ...],
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Subtitle Review Preparation persistence requires SQLite schema version 16"
            )
        _validate_preparation_linkage(
            preparation, preparation_result, context, candidate_references, review_items
        )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("subtitle_review_preparations", preparation.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Subtitle Review Preparation identity already exists"
                )
            if self._exists("domain_result_references", preparation_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "subtitle review preparation Domain Result identity already exists"
                )
            if self._exists("review_contexts", context.identity.value):
                raise PersistenceIdentityCollisionError(
                    "review context identity already exists"
                )
            for reference in candidate_references:
                if self._exists("review_candidate_references", reference.identity.value):
                    raise PersistenceIdentityCollisionError(
                        "review candidate reference identity already exists"
                    )
            for item in review_items:
                if self._exists("review_items", item.identity.value):
                    raise PersistenceIdentityCollisionError(
                        "review item identity already exists"
                    )
            for reference in candidate_references:
                _insert_candidate_reference(self._connection, reference)
            _insert_review_context(self._connection, context)
            for item in review_items:
                _insert_review_item(self._connection, item)
            _insert_preparation(self._connection, preparation)
            for ordinal, link in enumerate(preparation.item_links):
                _insert_preparation_item(self._connection, preparation, link, ordinal)
            _insert_domain_result_reference_record(self._connection, preparation_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Subtitle Review Preparation: {error}"
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


def _validate_preparation_linkage(
    preparation: SubtitleReviewPreparation,
    preparation_result: DomainResultReference,
    context: ReviewContext,
    candidate_references: tuple[CandidateReference, ...],
    review_items: tuple[ReviewItem, ...],
) -> None:
    if preparation.domain_result_id != preparation_result.identity:
        raise PersistenceError("subtitle review preparation Domain Result identity mismatch")
    if preparation_result.kind != SUBTITLE_REVIEW_PREPARATION_RESULT_KIND:
        raise PersistenceError("subtitle review preparation Domain Result kind is invalid")
    if len(preparation_result.upstream_results) != 1:
        raise PersistenceError("subtitle review preparation Domain Result upstream is invalid")
    if context.identity != preparation.context_id:
        raise PersistenceError("subtitle review preparation context identity mismatch")
    if (
        len(review_items) != preparation.item_count
        or len(candidate_references) != preparation.item_count
    ):
        raise PersistenceError("subtitle review preparation item cardinality mismatch")
    for link, item, reference in zip(
        preparation.item_links, review_items, candidate_references
    ):
        if link.review_item_id != item.identity:
            raise PersistenceError("subtitle review preparation review item mismatch")
        if link.candidate_reference_id != reference.identity:
            raise PersistenceError("subtitle review preparation candidate reference mismatch")
        if item.candidate_id != reference.identity:
            raise PersistenceError("subtitle review preparation item target mismatch")
        if item.context_id != preparation.context_id:
            raise PersistenceError("subtitle review preparation item context mismatch")


def _restore_preparation(
    row: tuple[object, ...], item_links: tuple[SubtitleReviewItemLink, ...]
) -> SubtitleReviewPreparation:
    return SubtitleReviewPreparation(
        identity=SubtitleReviewPreparationId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_validation_id=SubtitleValidationId(row[2]),
        source_time_revision_id=SubtitleTimeRevisionId(row[3]),
        source_reading_revision_id=SubtitleReadingRevisionId(row[4]),
        source_candidate_id=SubtitleCandidateId(row[5]),
        source_intake_id=SubtitleTranscriptIntakeId(row[6]),
        source_readiness_id=TranscriptReadinessEvaluationId(row[7]),
        source_selection_id=TranscriptCurrentSelectionId(row[8]),
        source_applicability_id=TranscriptApplicabilityEvaluationId(row[9]),
        source_decision_id=TranscriptReviewDecisionId(row[10]),
        source_review_item_id=ReviewItemId(row[11]),
        source_candidate_reference_id=CandidateReferenceId(row[12]),
        source_transcript_id=TranscriptId(row[13]),
        source_revision_id=TranscriptRevisionId(row[14]),
        source_media_id=SourceMediaId(row[15]),
        source_timeline_id=SourceTimelineId(row[16]),
        source_transcript_validation_id=TranscriptValidationId(row[17]),
        context_id=ReviewContextId(row[18]),
        item_links=item_links,
        item_count=row[19],
        source_structural_valid=bool(row[20]),
        provenance_complete=bool(row[21]),
        run_id=ProcessingRunId(row[22]),
        unit_execution_id=UnitExecutionId(row[23]),
        sequence=row[24],
        reason=row[25],
        previous_preparation_id=(
            SubtitleReviewPreparationId(row[26]) if row[26] is not None else None
        ),
    )


def _insert_preparation(
    connection: sqlite3.Connection, record: SubtitleReviewPreparation
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_review_preparations(
            identity, domain_result_id, source_validation_id, source_time_revision_id,
            source_reading_revision_id, source_candidate_id, source_intake_id,
            source_readiness_id, source_selection_id, source_applicability_id,
            source_decision_id, source_review_item_id, source_candidate_reference_id,
            source_transcript_id, source_revision_id, source_media_id, source_timeline_id,
            source_transcript_validation_id, context_id, item_count, source_structural_valid,
            provenance_complete, processing_run_id, unit_execution_id, sequence, reason,
            previous_preparation_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_validation_id.value,
            record.source_time_revision_id.value,
            record.source_reading_revision_id.value,
            record.source_candidate_id.value,
            record.source_intake_id.value,
            record.source_readiness_id.value,
            record.source_selection_id.value,
            record.source_applicability_id.value,
            record.source_decision_id.value,
            record.source_review_item_id.value,
            record.source_candidate_reference_id.value,
            record.source_transcript_id.value,
            record.source_revision_id.value,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.source_transcript_validation_id.value,
            record.context_id.value,
            record.item_count,
            int(record.source_structural_valid),
            int(record.provenance_complete),
            record.run_id.value,
            record.unit_execution_id.value,
            record.sequence,
            record.reason,
            record.previous_preparation_id.value
            if record.previous_preparation_id
            else None,
        ),
    )


def _insert_preparation_item(
    connection: sqlite3.Connection,
    preparation: SubtitleReviewPreparation,
    link: SubtitleReviewItemLink,
    ordinal: int,
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_review_preparation_items(
            subtitle_review_preparation_id, ordinal, review_item_id, candidate_reference_id,
            source_finding_id, rule, target_timed_unit_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            preparation.identity.value,
            ordinal,
            link.review_item_id.value,
            link.candidate_reference_id.value,
            link.source_finding_id.value,
            link.rule,
            link.target_timed_unit_id.value if link.target_timed_unit_id else None,
        ),
    )


__all__ = [
    "SQLiteSubtitleReviewPreparationCommandPersistence",
    "SQLiteSubtitleReviewPreparationRepository",
]
