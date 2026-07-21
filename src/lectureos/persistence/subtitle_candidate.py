"""Insert-only SQLite persistence for canonical Subtitle Candidate records.

Serializes one immutable subtitle candidate, its ordered candidate cues (each with its ordered
source-segment provenance) and the candidate's DomainResultReference in a single atomic
transaction. The durable cue model stores one-to-many and many-to-one segment-to-cue relationships
losslessly: each cue owns an ordered tuple of >=1 source segments, and distinct cues may reference
the same segment. Persisting a candidate records only the candidate and starts no downstream
capability.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.identities import (
    SubtitleCandidateCueId,
    SubtitleCandidateId,
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
)
from lectureos.application.subtitle_candidate_generation import (
    SUBTITLE_CANDIDATE_RESULT_KIND,
    SubtitleCandidate,
    SubtitleCandidateCue,
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
    TranscriptSegmentId,
    TranscriptValidationId,
)

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 12


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Subtitle Candidate persistence requires SQLite schema version 12"
        )
    return version


class SQLiteSubtitleCandidateRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: SubtitleCandidateId) -> SubtitleCandidate | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_intake_id, source_readiness_id,
                       source_selection_id, source_applicability_id, source_decision_id,
                       review_item_id, candidate_reference_id, source_transcript_id,
                       source_revision_id, source_media_id, source_timeline_id, validation_id,
                       processing_run_id, unit_execution_id, sequence, reason,
                       previous_candidate_id
                FROM subtitle_candidates
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            cue_ids = tuple(
                SubtitleCandidateCueId(value[0])
                for value in self._connection.execute(
                    """
                    SELECT identity FROM subtitle_candidate_cues
                    WHERE subtitle_candidate_id = ?
                    ORDER BY ordinal
                    """,
                    (identity.value,),
                ).fetchall()
            )
            return _restore_candidate(row, cue_ids)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Candidate: {error}"
            ) from error

    def get_cue(self, identity: SubtitleCandidateCueId) -> SubtitleCandidateCue | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, subtitle_candidate_id, source_transcript_id,
                       source_revision_id, source_timeline_id, text, display_order,
                       start, end
                FROM subtitle_candidate_cues
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            segment_ids = tuple(
                TranscriptSegmentId(value[0])
                for value in self._connection.execute(
                    """
                    SELECT transcript_segment_id FROM subtitle_candidate_cue_segments
                    WHERE subtitle_candidate_cue_id = ?
                    ORDER BY ordinal
                    """,
                    (identity.value,),
                ).fetchall()
            )
            return _restore_cue(row, segment_ids)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Subtitle Candidate Cue: {error}"
            ) from error


class SQLiteSubtitleCandidateCommandPersistence:
    """Owns one atomic v12 transaction persisting a candidate, its cues and Result reference."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_subtitle_candidate(
        self,
        *,
        candidate: SubtitleCandidate,
        cues: tuple[SubtitleCandidateCue, ...],
        candidate_result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Subtitle Candidate persistence requires SQLite schema version 12"
            )
        _validate_candidate_linkage(candidate, cues, candidate_result)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists("subtitle_candidates", candidate.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Subtitle Candidate identity already exists"
                )
            if self._exists("domain_result_references", candidate_result.identity.value):
                raise PersistenceIdentityCollisionError(
                    "subtitle candidate Domain Result identity already exists"
                )
            for cue in cues:
                if self._exists("subtitle_candidate_cues", cue.identity.value):
                    raise PersistenceIdentityCollisionError(
                        "Subtitle Candidate Cue identity already exists"
                    )
            _insert_candidate(self._connection, candidate)
            for ordinal, cue in enumerate(cues):
                _insert_cue(self._connection, cue, ordinal)
            _insert_domain_result_reference_record(self._connection, candidate_result)
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Subtitle Candidate: {error}"
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


def _validate_candidate_linkage(
    candidate: SubtitleCandidate,
    cues: tuple[SubtitleCandidateCue, ...],
    candidate_result: DomainResultReference,
) -> None:
    if candidate.domain_result_id != candidate_result.identity:
        raise PersistenceError("subtitle candidate Domain Result identity mismatch")
    if candidate_result.kind != SUBTITLE_CANDIDATE_RESULT_KIND:
        raise PersistenceError("subtitle candidate Domain Result kind is invalid")
    if len(candidate_result.upstream_results) != 1:
        raise PersistenceError("subtitle candidate Domain Result upstream is invalid")
    if not cues:
        raise PersistenceError("subtitle candidate requires at least one cue")
    if candidate.cue_ids != tuple(cue.identity for cue in cues):
        raise PersistenceError("subtitle candidate cue ordering mismatch")
    for cue in cues:
        if cue.candidate_id != candidate.identity:
            raise PersistenceError("subtitle candidate cue linkage mismatch")


def _restore_candidate(
    row: tuple[object, ...], cue_ids: tuple[SubtitleCandidateCueId, ...]
) -> SubtitleCandidate:
    return SubtitleCandidate(
        identity=SubtitleCandidateId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_intake_id=SubtitleTranscriptIntakeId(row[2]),
        source_readiness_id=TranscriptReadinessEvaluationId(row[3]),
        source_selection_id=TranscriptCurrentSelectionId(row[4]),
        source_applicability_id=TranscriptApplicabilityEvaluationId(row[5]),
        source_decision_id=TranscriptReviewDecisionId(row[6]),
        review_item_id=ReviewItemId(row[7]),
        candidate_reference_id=CandidateReferenceId(row[8]),
        source_transcript_id=TranscriptId(row[9]),
        source_revision_id=TranscriptRevisionId(row[10]),
        source_media_id=SourceMediaId(row[11]),
        source_timeline_id=SourceTimelineId(row[12]),
        validation_id=TranscriptValidationId(row[13]),
        cue_ids=cue_ids,
        run_id=ProcessingRunId(row[14]),
        unit_execution_id=UnitExecutionId(row[15]),
        sequence=row[16],
        reason=row[17],
        previous_candidate_id=(
            SubtitleCandidateId(row[18]) if row[18] is not None else None
        ),
    )


def _restore_cue(
    row: tuple[object, ...], segment_ids: tuple[TranscriptSegmentId, ...]
) -> SubtitleCandidateCue:
    return SubtitleCandidateCue(
        identity=SubtitleCandidateCueId(row[0]),
        candidate_id=SubtitleCandidateId(row[1]),
        source_transcript_id=TranscriptId(row[2]),
        source_revision_id=TranscriptRevisionId(row[3]),
        source_segment_ids=segment_ids,
        text=row[5],
        display_order=row[6],
        source_timeline_id=(
            SourceTimelineId(row[4]) if row[4] is not None else None
        ),
        start=row[7],
        end=row[8],
    )


def _insert_candidate(
    connection: sqlite3.Connection, record: SubtitleCandidate
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_candidates(
            identity, domain_result_id, source_intake_id, source_readiness_id,
            source_selection_id, source_applicability_id, source_decision_id,
            review_item_id, candidate_reference_id, source_transcript_id,
            source_revision_id, source_media_id, source_timeline_id, validation_id,
            processing_run_id, unit_execution_id, sequence, reason, previous_candidate_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
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
            record.previous_candidate_id.value
            if record.previous_candidate_id
            else None,
        ),
    )


def _insert_cue(
    connection: sqlite3.Connection, cue: SubtitleCandidateCue, ordinal: int
) -> None:
    connection.execute(
        """
        INSERT INTO subtitle_candidate_cues(
            identity, subtitle_candidate_id, ordinal, source_transcript_id,
            source_revision_id, source_timeline_id, text, display_order, start, end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cue.identity.value,
            cue.candidate_id.value,
            ordinal,
            cue.source_transcript_id.value,
            cue.source_revision_id.value,
            cue.source_timeline_id.value if cue.source_timeline_id else None,
            cue.text,
            cue.display_order,
            cue.start,
            cue.end,
        ),
    )
    for segment_ordinal, segment_id in enumerate(cue.source_segment_ids):
        connection.execute(
            """
            INSERT INTO subtitle_candidate_cue_segments(
                subtitle_candidate_cue_id, ordinal, transcript_segment_id
            ) VALUES (?, ?, ?)
            """,
            (cue.identity.value, segment_ordinal, segment_id.value),
        )


__all__ = [
    "SQLiteSubtitleCandidateCommandPersistence",
    "SQLiteSubtitleCandidateRepository",
]
