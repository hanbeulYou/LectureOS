"""Atomic SQLite persistence for Corrected Revision Generation (040 §19, PATCH-0026).

Serializes one explicit corrected-revision generation in a single transaction: the new replacement
`TranscriptSegment` (carrying ``replaces_segment_id``), the canonical `CorrectedTranscriptRevision` (reusing the
v5 revision tables — segment membership + candidate references), its `DomainResultReference`, and the additive
`corrected_revision_generations` binding row (candidate, authorizing Accepted Decision, parent raw transcript,
replaced/replacement segments, content fingerprint, replay anchor). It reuses the existing transaction-free
insert helpers so a generated revision is structurally identical to one produced by the internal transcript
composition. Any collision or error rolls back with no partial state; an admitted revision is never updated,
deleted, or overwritten, and no candidate, decision, raw transcript, segment, or selection row is ever touched.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    CorrectedRevisionGenerationId,
    CorrectionCandidateDecisionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import CorrectedTranscriptRevision, TranscriptSegment

from .corrected_transcript_revisions import (
    SQLiteCorrectedTranscriptRevisionRepository,
    _insert_corrected_transcript_revision,
)
from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection
from .transcript_segments import _insert_transcript_segment

if TYPE_CHECKING:
    from lectureos.application.corrected_revision_generation import (
        CorrectedRevisionGeneration,
    )

_REQUIRED_VERSION = 36


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Corrected Revision Generation persistence requires SQLite schema version 36"
        )
    return version


class SQLiteCorrectedRevisionGenerationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: CorrectedRevisionGenerationId
    ) -> "CorrectedRevisionGeneration | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Corrected Revision Generation: {error}"
            ) from error

    def revision(
        self, revision_id: TranscriptRevisionId
    ) -> CorrectedTranscriptRevision | None:
        return SQLiteCorrectedTranscriptRevisionRepository(self._connection).get(revision_id)

    def generations_for_candidate(
        self, candidate_id: CorrectionCandidateId
    ) -> "tuple[CorrectedRevisionGeneration, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE correction_candidate_id = ? ORDER BY identity",
                (candidate_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Corrected Revision Generations: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteCorrectedRevisionGenerationCommandPersistence:
    """Owns one atomic v36 transaction persisting a complete corrected-revision generation."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_corrected_revision_generation(
        self,
        *,
        generation: "CorrectedRevisionGeneration",
        revision: CorrectedTranscriptRevision,
        replacement_segment: TranscriptSegment,
        result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Corrected Revision Generation persistence requires SQLite schema version 36"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            _validate_linkage(generation, revision, replacement_segment, result)
            if (
                self._exists("identity", generation.identity.value)
                or self._exists("corrected_revision_id", generation.corrected_revision_id.value)
                or self._revision_exists(revision.identity)
                or self._segment_exists(replacement_segment.identity)
            ):
                raise PersistenceIdentityCollisionError(
                    "Corrected Revision Generation records already exist"
                )
            _insert_transcript_segment(self._connection, replacement_segment)
            _insert_corrected_transcript_revision(self._connection, revision)
            _insert_domain_result_reference_record(self._connection, result)
            self._connection.execute(
                """
                INSERT INTO corrected_revision_generations(
                    identity, corrected_revision_id, correction_candidate_id,
                    authorizing_decision_id, parent_raw_transcript_id,
                    replaced_segment_id, replacement_segment_id, content_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation.identity.value,
                    generation.corrected_revision_id.value,
                    generation.correction_candidate_id.value,
                    generation.authorizing_decision_id.value,
                    generation.parent_raw_transcript_id.value,
                    generation.replaced_segment_id.value,
                    generation.replacement_segment_id.value,
                    generation.content_fingerprint,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Corrected Revision Generation already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Corrected Revision Generation: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, column: str, value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM corrected_revision_generations WHERE {column} = ?",
                (value,),
            ).fetchone()
            is not None
        )

    def _revision_exists(self, identity: TranscriptRevisionId) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM corrected_transcript_revisions WHERE identity = ?",
                (identity.value,),
            ).fetchone()
            is not None
        )

    def _segment_exists(self, identity: TranscriptSegmentId) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM transcript_segments WHERE identity = ?", (identity.value,)
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _validate_linkage(
    generation: "CorrectedRevisionGeneration",
    revision: CorrectedTranscriptRevision,
    replacement_segment: TranscriptSegment,
    result: DomainResultReference,
) -> None:
    if generation.corrected_revision_id != revision.identity:
        raise PersistenceError("generation revision identity must match the revision")
    if revision.parent_raw_transcript_id != generation.parent_raw_transcript_id:
        raise PersistenceError("revision parent must match the generation parent")
    if revision.correction_candidate_ids != (generation.correction_candidate_id,):
        raise PersistenceError("revision must reference exactly the applied candidate")
    if replacement_segment.identity != generation.replacement_segment_id:
        raise PersistenceError("replacement segment identity must match the generation")
    if replacement_segment.replaces_segment_id != generation.replaced_segment_id:
        raise PersistenceError("replacement segment must replace the generation's replaced segment")
    if replacement_segment.identity not in revision.segment_ids:
        raise PersistenceError("revision must reference the replacement segment")
    if generation.replaced_segment_id in revision.segment_ids:
        raise PersistenceError("revision must not still reference the replaced segment")
    if result.identity != revision.domain_result_id:
        raise PersistenceError("domain result identity must match the revision")
    if result.kind != "corrected_transcript_revision":
        raise PersistenceError("domain result kind must be corrected_transcript_revision")
    if len(result.upstream_results) != 1:
        raise PersistenceError("revision domain result requires exactly one upstream result")


_SELECT_COLUMNS = (
    "SELECT identity, corrected_revision_id, correction_candidate_id, "
    "authorizing_decision_id, parent_raw_transcript_id, replaced_segment_id, "
    "replacement_segment_id, content_fingerprint FROM corrected_revision_generations"
)


def _restore(row: tuple[object, ...]) -> "CorrectedRevisionGeneration":
    from lectureos.application.corrected_revision_generation import (
        CorrectedRevisionGeneration,
    )

    return CorrectedRevisionGeneration(
        identity=CorrectedRevisionGenerationId(row[0]),
        corrected_revision_id=TranscriptRevisionId(row[1]),
        correction_candidate_id=CorrectionCandidateId(row[2]),
        authorizing_decision_id=CorrectionCandidateDecisionId(row[3]),
        parent_raw_transcript_id=TranscriptId(row[4]),
        replaced_segment_id=TranscriptSegmentId(row[5]),
        replacement_segment_id=TranscriptSegmentId(row[6]),
        content_fingerprint=row[7],
    )


__all__ = [
    "SQLiteCorrectedRevisionGenerationCommandPersistence",
    "SQLiteCorrectedRevisionGenerationRepository",
]
