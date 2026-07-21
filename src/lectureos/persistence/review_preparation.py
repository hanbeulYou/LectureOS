"""Insert-only SQLite persistence for canonical Transcript Review Preparation.

Serializes the Application-owned preparation aggregate together with the reused review
records (Candidate References, Review Context, Review Items) and the preparation's
DomainResultReference in one atomic transaction. It stores no Review Decision state.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import TranscriptReviewPreparationId
from lectureos.application.transcript_review_preparation import (
    REVIEW_PREPARATION_RESULT_KIND,
    ReviewItemGroup,
    TranscriptReviewPreparation,
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
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 6


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Transcript Review Preparation persistence requires SQLite schema version 6"
        )
    return version


class SQLiteReviewCandidateReferenceRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: CandidateReferenceId) -> CandidateReference | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, kind, source_domain, domain_result_id,
                       source_media_id, source_timeline_id, processing_run_id,
                       unit_execution_id, revision_reference, applicability
                FROM review_candidate_references
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return _restore_candidate_reference(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Candidate Reference: {error}"
            ) from error

    def save(self, record: CandidateReference) -> None:
        _save_single(
            self._connection,
            self.get,
            record,
            _insert_candidate_reference,
            "Candidate Reference",
        )


class SQLiteReviewContextRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: ReviewContextId) -> ReviewContext | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, source_media_id, source_timeline_id, blocking_reason
                FROM review_contexts
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return ReviewContext(
                identity=ReviewContextId(row[0]),
                source_media_id=SourceMediaId(row[1]) if row[1] is not None else None,
                source_timeline_id=(
                    SourceTimelineId(row[2]) if row[2] is not None else None
                ),
                domain_result_references=tuple(
                    DomainResultId(value)
                    for value in _ordered_child(
                        self._connection,
                        "review_context_domain_results",
                        "review_context_id",
                        "domain_result_id",
                        row[0],
                        "Review Context domain results",
                    )
                ),
                evidence_references=_ordered_child(
                    self._connection,
                    "review_context_evidence",
                    "review_context_id",
                    "evidence",
                    row[0],
                    "Review Context evidence",
                ),
                blocking_reason=row[3],
            )
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Review Context: {error}"
            ) from error

    def save(self, record: ReviewContext) -> None:
        _save_single(
            self._connection,
            self.get,
            record,
            _insert_review_context,
            "Review Context",
        )


class SQLiteReviewItemRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: ReviewItemId) -> ReviewItem | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, candidate_reference_id, context_id,
                       applicability_at_creation, processing_run_id, unit_execution_id
                FROM review_items
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return ReviewItem(
                identity=ReviewItemId(row[0]),
                candidate_id=CandidateReferenceId(row[1]),
                context_id=ReviewContextId(row[2]),
                applicability_at_creation=row[3],
                run_id=ProcessingRunId(row[4]) if row[4] is not None else None,
                unit_execution_id=(
                    UnitExecutionId(row[5]) if row[5] is not None else None
                ),
            )
        except sqlite3.Error as error:
            raise PersistenceError(f"could not read Review Item: {error}") from error

    def save(self, record: ReviewItem) -> None:
        _save_single(
            self._connection, self.get, record, _insert_review_item, "Review Item"
        )


class SQLiteTranscriptReviewPreparationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: TranscriptReviewPreparationId
    ) -> TranscriptReviewPreparation | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_transcript_id,
                       source_revision_id, processing_run_id, unit_execution_id,
                       source_media_id, source_timeline_id, context_id, item_count,
                       structural_valid, provenance_complete, ordering_valid
                FROM transcript_review_preparations
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return TranscriptReviewPreparation(
                identity=TranscriptReviewPreparationId(row[0]),
                domain_result_id=DomainResultId(row[1]),
                source_transcript_id=TranscriptId(row[2]),
                source_revision_id=TranscriptRevisionId(row[3]),
                run_id=ProcessingRunId(row[4]),
                unit_execution_id=UnitExecutionId(row[5]),
                source_media_id=SourceMediaId(row[6]),
                source_timeline_id=SourceTimelineId(row[7]),
                context_id=ReviewContextId(row[8]),
                candidate_reference_ids=tuple(
                    CandidateReferenceId(value)
                    for value in _ordered_child(
                        self._connection,
                        "transcript_review_preparation_candidates",
                        "transcript_review_preparation_id",
                        "candidate_reference_id",
                        row[0],
                        "review preparation candidates",
                    )
                ),
                ordered_item_ids=tuple(
                    ReviewItemId(value)
                    for value in _ordered_child(
                        self._connection,
                        "transcript_review_preparation_items",
                        "transcript_review_preparation_id",
                        "review_item_id",
                        row[0],
                        "review preparation items",
                    )
                ),
                groups=self._restore_groups(row[0]),
                item_count=row[9],
                structural_valid=bool(row[10]),
                provenance_complete=bool(row[11]),
                ordering_valid=bool(row[12]),
            )
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Transcript Review Preparation: {error}"
            ) from error

    def _restore_groups(self, identity_value: str) -> tuple[ReviewItemGroup, ...]:
        rows = self._connection.execute(
            """
            SELECT ordinal, group_key, review_item_id
            FROM transcript_review_preparation_groups
            WHERE transcript_review_preparation_id = ?
            ORDER BY ordinal
            """,
            (identity_value,),
        ).fetchall()
        if tuple(row[0] for row in rows) != tuple(range(len(rows))):
            raise PersistenceError("review preparation group ordering is corrupt")
        grouped: dict[str, list[ReviewItemId]] = {}
        for _, group_key, review_item_id in rows:
            grouped.setdefault(group_key, []).append(ReviewItemId(review_item_id))
        return tuple(
            ReviewItemGroup(group_key=key, review_item_ids=tuple(members))
            for key, members in grouped.items()
        )

    def save(self, record: TranscriptReviewPreparation) -> None:
        _save_single(
            self._connection,
            self.get,
            record,
            _insert_review_preparation,
            "Transcript Review Preparation",
        )


class SQLiteReviewPreparationCommandPersistence:
    """Owns one atomic v6 transaction persisting an entire review preparation."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_review_preparation(
        self,
        *,
        preparation: TranscriptReviewPreparation,
        preparation_result: DomainResultReference,
        context: ReviewContext,
        candidate_references: tuple[CandidateReference, ...],
        review_items: tuple[ReviewItem, ...],
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Transcript Review Preparation persistence requires SQLite schema version 6"
            )
        _validate_preparation_linkage(
            preparation, preparation_result, context, candidate_references, review_items
        )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            self._require_absent(preparation, preparation_result, context, review_items)
            self._require_candidate_references_absent(candidate_references)
            for reference in candidate_references:
                _insert_candidate_reference(self._connection, reference)
            _insert_review_context(self._connection, context)
            for item in review_items:
                _insert_review_item(self._connection, item)
            _insert_review_preparation(self._connection, preparation)
            _insert_domain_result_reference_record(self._connection, preparation_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Transcript Review Preparation: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _require_absent(
        self, preparation, preparation_result, context, review_items
    ) -> None:
        if self._exists("transcript_review_preparations", preparation.identity.value):
            raise PersistenceIdentityCollisionError(
                "Transcript Review Preparation identity already exists"
            )
        if self._exists("domain_result_references", preparation_result.identity.value):
            raise PersistenceIdentityCollisionError(
                "review preparation Domain Result identity already exists"
            )
        if self._exists("review_contexts", context.identity.value):
            raise PersistenceIdentityCollisionError(
                "Review Context identity already exists"
            )
        for item in review_items:
            if self._exists("review_items", item.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Review Item identity already exists"
                )

    def _require_candidate_references_absent(self, candidate_references) -> None:
        for reference in candidate_references:
            if self._exists("review_candidate_references", reference.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Candidate Reference identity already exists"
                )

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
    preparation, preparation_result, context, candidate_references, review_items
) -> None:
    if preparation.domain_result_id != preparation_result.identity:
        raise PersistenceError("review preparation Domain Result identity mismatch")
    if preparation_result.kind != REVIEW_PREPARATION_RESULT_KIND:
        raise PersistenceError("review preparation Domain Result kind is invalid")
    if len(preparation_result.upstream_results) != 1:
        raise PersistenceError("review preparation Domain Result upstream is invalid")
    if context.identity != preparation.context_id:
        raise PersistenceError("review preparation Review Context identity mismatch")
    count = preparation.item_count
    if len(candidate_references) != count or len(review_items) != count:
        raise PersistenceError("review preparation record counts must match item count")
    reference_ids = {reference.identity for reference in candidate_references}
    if reference_ids != set(preparation.candidate_reference_ids):
        raise PersistenceError("review preparation candidate references are inconsistent")
    if {item.identity for item in review_items} != set(preparation.ordered_item_ids):
        raise PersistenceError("review preparation review items are inconsistent")
    for item in review_items:
        if item.candidate_id not in reference_ids:
            raise PersistenceError("review item references an unknown candidate")
        if item.context_id != context.identity:
            raise PersistenceError("review item references an unknown context")


def _save_single(connection, getter, record, inserter, label: str) -> None:
    if getter(record.identity) is not None:
        raise PersistenceIdentityCollisionError(f"{label} identity already exists")
    try:
        connection.execute("BEGIN IMMEDIATE")
        inserter(connection, record)
        connection.execute("COMMIT")
    except sqlite3.IntegrityError as error:
        _rollback(connection)
        if getter(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                f"{label} identity already exists"
            ) from error
        raise PersistenceError(f"could not persist {label}: {error}") from error
    except sqlite3.Error as error:
        _rollback(connection)
        raise PersistenceError(f"could not persist {label}: {error}") from error
    except Exception:
        _rollback(connection)
        raise


def _rollback(connection: sqlite3.Connection) -> None:
    if connection.in_transaction:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass


def _ordered_child(
    connection, table, parent_column, value_column, identity_value, label
) -> tuple[str, ...]:
    rows = connection.execute(
        f"""
        SELECT ordinal, {value_column}
        FROM {table}
        WHERE {parent_column} = ?
        ORDER BY ordinal
        """,
        (identity_value,),
    ).fetchall()
    if tuple(row[0] for row in rows) != tuple(range(len(rows))):
        raise PersistenceError(f"{label} ordering is corrupt")
    return tuple(row[1] for row in rows)


def _restore_candidate_reference(row: tuple[object, ...]) -> CandidateReference:
    return CandidateReference(
        identity=CandidateReferenceId(row[0]),
        kind=row[1],
        source_domain=row[2],
        domain_result_id=DomainResultId(row[3]) if row[3] is not None else None,
        source_media_id=SourceMediaId(row[4]) if row[4] is not None else None,
        source_timeline_id=SourceTimelineId(row[5]) if row[5] is not None else None,
        run_id=ProcessingRunId(row[6]) if row[6] is not None else None,
        unit_execution_id=UnitExecutionId(row[7]) if row[7] is not None else None,
        revision_reference=row[8],
        applicability=row[9],
    )


def _insert_candidate_reference(
    connection: sqlite3.Connection, record: CandidateReference
) -> None:
    connection.execute(
        """
        INSERT INTO review_candidate_references(
            identity, kind, source_domain, domain_result_id, source_media_id,
            source_timeline_id, processing_run_id, unit_execution_id,
            revision_reference, applicability
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.kind,
            record.source_domain,
            record.domain_result_id.value if record.domain_result_id else None,
            record.source_media_id.value if record.source_media_id else None,
            record.source_timeline_id.value if record.source_timeline_id else None,
            record.run_id.value if record.run_id else None,
            record.unit_execution_id.value if record.unit_execution_id else None,
            record.revision_reference,
            record.applicability,
        ),
    )


def _insert_review_context(
    connection: sqlite3.Connection, record: ReviewContext
) -> None:
    if record.validation_references or record.diagnostic_references or record.previous_history_references:
        raise PersistenceError(
            "review preparation context must not carry decision-stage references"
        )
    connection.execute(
        """
        INSERT INTO review_contexts(
            identity, source_media_id, source_timeline_id, blocking_reason
        ) VALUES (?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.source_media_id.value if record.source_media_id else None,
            record.source_timeline_id.value if record.source_timeline_id else None,
            record.blocking_reason,
        ),
    )
    connection.executemany(
        """
        INSERT INTO review_context_domain_results(
            review_context_id, ordinal, domain_result_id
        ) VALUES (?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, reference.value)
            for ordinal, reference in enumerate(record.domain_result_references)
        ),
    )
    connection.executemany(
        """
        INSERT INTO review_context_evidence(
            review_context_id, ordinal, evidence
        ) VALUES (?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, evidence)
            for ordinal, evidence in enumerate(record.evidence_references)
        ),
    )


def _insert_review_item(connection: sqlite3.Connection, record: ReviewItem) -> None:
    if record.decision_references or record.stale_references or record.conflict_references:
        raise PersistenceError(
            "review preparation item must not carry decision-stage references"
        )
    connection.execute(
        """
        INSERT INTO review_items(
            identity, candidate_reference_id, context_id,
            applicability_at_creation, processing_run_id, unit_execution_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.candidate_id.value,
            record.context_id.value,
            record.applicability_at_creation,
            record.run_id.value if record.run_id else None,
            record.unit_execution_id.value if record.unit_execution_id else None,
        ),
    )


def _insert_review_preparation(
    connection: sqlite3.Connection, record: TranscriptReviewPreparation
) -> None:
    connection.execute(
        """
        INSERT INTO transcript_review_preparations(
            identity, domain_result_id, source_transcript_id, source_revision_id,
            processing_run_id, unit_execution_id, source_media_id, source_timeline_id,
            context_id, item_count, structural_valid, provenance_complete,
            ordering_valid
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_transcript_id.value,
            record.source_revision_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.context_id.value,
            record.item_count,
            int(record.structural_valid),
            int(record.provenance_complete),
            int(record.ordering_valid),
        ),
    )
    connection.executemany(
        """
        INSERT INTO transcript_review_preparation_items(
            transcript_review_preparation_id, ordinal, review_item_id
        ) VALUES (?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, item_id.value)
            for ordinal, item_id in enumerate(record.ordered_item_ids)
        ),
    )
    connection.executemany(
        """
        INSERT INTO transcript_review_preparation_candidates(
            transcript_review_preparation_id, ordinal, candidate_reference_id
        ) VALUES (?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, reference_id.value)
            for ordinal, reference_id in enumerate(record.candidate_reference_ids)
        ),
    )
    connection.executemany(
        """
        INSERT INTO transcript_review_preparation_groups(
            transcript_review_preparation_id, ordinal, group_key, review_item_id
        ) VALUES (?, ?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, group.group_key, item_id.value)
            for ordinal, (group, item_id) in enumerate(
                (group, item_id)
                for group in record.groups
                for item_id in group.review_item_ids
            )
        ),
    )


__all__ = [
    "SQLiteReviewCandidateReferenceRepository",
    "SQLiteReviewContextRepository",
    "SQLiteReviewItemRepository",
    "SQLiteReviewPreparationCommandPersistence",
    "SQLiteTranscriptReviewPreparationRepository",
]
