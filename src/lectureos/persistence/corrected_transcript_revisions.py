"""Insert-only SQLite repository for CorrectedTranscriptRevision lineage."""

from __future__ import annotations

import sqlite3

from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    ReviewDecisionId,
    UnitExecutionId,
)
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import (
    CorrectedTranscriptRevision,
    TranscriptApplicability,
)

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection


class SQLiteCorrectedTranscriptRevisionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        if validate_sqlite_connection(connection) < 5:
            raise SchemaFeatureUnavailableError(
                "CorrectedTranscriptRevision persistence requires SQLite schema version 5"
            )
        self._connection = connection

    def get(
        self, identity: TranscriptRevisionId
    ) -> CorrectedTranscriptRevision | None:
        try:
            row = self._connection.execute(
                _REVISION_SELECT + " WHERE identity = ?",
                (identity.value,),
            ).fetchone()
            return self._restore(row) if row is not None else None
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read CorrectedTranscriptRevision: {error}"
            ) from error

    def save(self, record: CorrectedTranscriptRevision) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                "CorrectedTranscriptRevision identity already exists"
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _insert_corrected_transcript_revision(self._connection, record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "CorrectedTranscriptRevision identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist CorrectedTranscriptRevision: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(
                f"could not persist CorrectedTranscriptRevision: {error}"
            ) from error
        except Exception:
            self._rollback()
            raise

    def all(self) -> tuple[CorrectedTranscriptRevision, ...]:
        try:
            rows = self._connection.execute(_REVISION_SELECT + " ORDER BY rowid").fetchall()
            return tuple(self._restore(row) for row in rows)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list CorrectedTranscriptRevisions: {error}"
            ) from error

    def _restore(self, row: tuple[object, ...]) -> CorrectedTranscriptRevision:
        identity = TranscriptRevisionId(row[0])
        return CorrectedTranscriptRevision(
            identity=identity,
            transcript_id=TranscriptId(row[1]),
            domain_result_id=DomainResultId(row[2]),
            run_id=ProcessingRunId(row[3]),
            unit_execution_id=UnitExecutionId(row[4]),
            segment_ids=tuple(
                TranscriptSegmentId(value)
                for value in self._child_values(
                    "corrected_transcript_revision_segments",
                    "transcript_segment_id",
                    identity,
                )
            ),
            parent_raw_transcript_id=(TranscriptId(row[5]) if row[5] is not None else None),
            parent_revision_id=(
                TranscriptRevisionId(row[6]) if row[6] is not None else None
            ),
            correction_candidate_ids=tuple(
                CorrectionCandidateId(value)
                for value in self._child_values(
                    "corrected_transcript_revision_candidates",
                    "correction_candidate_id",
                    identity,
                )
            ),
            decision_reference=(ReviewDecisionId(row[7]) if row[7] is not None else None),
            validation_id=(TranscriptValidationId(row[8]) if row[8] is not None else None),
            applicability=TranscriptApplicability(row[9]),
        )

    def _child_values(
        self,
        table: str,
        value_column: str,
        identity: TranscriptRevisionId,
    ) -> tuple[str, ...]:
        rows = self._connection.execute(
            f"""
            SELECT ordinal, {value_column}
            FROM {table}
            WHERE transcript_revision_id = ?
            ORDER BY ordinal
            """,
            (identity.value,),
        ).fetchall()
        if tuple(row[0] for row in rows) != tuple(range(len(rows))):
            raise PersistenceError(
                f"CorrectedTranscriptRevision child ordering is corrupt: {table}"
            )
        return tuple(row[1] for row in rows)

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


_REVISION_SELECT = """
SELECT identity, transcript_id, domain_result_id, processing_run_id,
       unit_execution_id, parent_raw_transcript_id, parent_revision_id,
       decision_reference, validation_id, applicability
FROM corrected_transcript_revisions
"""


def _insert_corrected_transcript_revision(
    connection: sqlite3.Connection, record: CorrectedTranscriptRevision
) -> None:
    """Insert one complete Revision without owning a transaction."""

    connection.execute(
        """
        INSERT INTO corrected_transcript_revisions(
            identity, transcript_id, domain_result_id, processing_run_id,
            unit_execution_id, parent_raw_transcript_id, parent_revision_id,
            decision_reference, validation_id, applicability
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.transcript_id.value,
            record.domain_result_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
            record.parent_raw_transcript_id.value if record.parent_raw_transcript_id else None,
            record.parent_revision_id.value if record.parent_revision_id else None,
            record.decision_reference.value if record.decision_reference else None,
            record.validation_id.value if record.validation_id else None,
            record.applicability.value,
        ),
    )
    _insert_revision_children(
        connection,
        "corrected_transcript_revision_segments",
        "transcript_segment_id",
        record,
        tuple(value.value for value in record.segment_ids),
    )
    _insert_revision_children(
        connection,
        "corrected_transcript_revision_candidates",
        "correction_candidate_id",
        record,
        tuple(value.value for value in record.correction_candidate_ids),
    )


def _insert_revision_children(
    connection: sqlite3.Connection,
    table: str,
    value_column: str,
    record: CorrectedTranscriptRevision,
    values: tuple[str, ...],
) -> None:
    connection.executemany(
        f"""
        INSERT INTO {table}(transcript_revision_id, ordinal, {value_column})
        VALUES (?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, value)
            for ordinal, value in enumerate(values)
        ),
    )
